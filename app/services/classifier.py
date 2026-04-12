import json
import logging
import os
import time

try:
    import google.genai as genai  # New API (2026+)
    USES_NEW_API = True
except ImportError:
    import google.generativeai as genai  # Legacy API (deprecated but still works)
    USES_NEW_API = False

from app.models.track import Track

logger = logging.getLogger(__name__)


def _build_classification_prompt(tracks: list[Track], taxonomy: dict) -> str:
    """Build the classification prompt for Claude."""
    track_descriptions = []
    for idx, track in enumerate(tracks):
        desc = f"""Track {idx}:
  - Title: {track.display_title}
  - Artist: {track.display_artist}
  - Existing Genre: {track.existing_genre or "N/A"}
  - Comment: {track.existing_comment or "N/A"}
  - BPM: {track.analyzed_bpm or track.existing_bpm or "N/A"}
  - Key: {track.analyzed_key or track.existing_key or "N/A"}
  - Energy: {track.analyzed_energy or "N/A"}
"""
        # Add clave pattern if detected
        if track.clave_pattern:
            desc += f"  - Detected clave: {track.clave_pattern}.\n"

        # Add existing comment tag if present
        if track.existing_comment:
            desc += f"  - Existing comment tag: {track.existing_comment}.\n"

        track_descriptions.append(desc)

    tracks_str = "\n".join(track_descriptions)
    taxonomy_str = json.dumps(taxonomy, indent=2)

    # Inject DJ correction hints if available
    correction_hints = ""
    try:
        from app.services.learning import get_correction_hints
        correction_hints = get_correction_hints()
    except ImportError:
        pass

    hints_section = f"\n{correction_hints}\n" if correction_hints else ""

    prompt = f"""You are a Latin dance music expert. Classify each track into genre and sub-genre based on the provided taxonomy.{hints_section}
TAXONOMY (genres and subgenres):
{taxonomy_str}

TRACKS TO CLASSIFY:
{tracks_str}

Return a JSON array with one object per track, in the same order. Each object must have:
- "index": track index (0-based)
- "genre": genre from taxonomy (or "Unknown" if unclassifiable)
- "subgenre": subgenre from taxonomy (or "Unknown" if unclassifiable)
- "confidence": integer 0-100 (90+ = very certain, 70-89 = likely, 50-69 = unsure, <50 = guessing)
- "reasoning": brief explanation of classification

RULES:
1. Only use genres and subgenres that exist in the taxonomy provided above
2. Consider existing_genre, bpm, key, energy, clave pattern, and existing comment tags when making decisions
3. If truly unclassifiable, use genre "Unknown" and subgenre "Unknown" with low confidence
4. Return valid JSON array only, no other text

STYLE HINTS FOR DISAMBIGUATION:
- For Bachata: If BPM 120-135 + romantic/slow feel = Romántica; if BPM 130-145 + heavy guitar = Sensual; if BPM 140-160 + aggressive = Urbana.
- For Salsa: If BPM 165-185 + aggressive brass = Dura; if BPM 155-175 + romantic vocals = Romántica.
- Use clave pattern (2-3 vs 3-2) to disambiguate Latin dance styles when BPM alone is ambiguous.

Example output format:
[
  {{"index": 0, "genre": "Salsa", "subgenre": "Romántica", "confidence": 85, "reasoning": "Upbeat vocals with 95 BPM typical of romantic salsa"}},
  {{"index": 1, "genre": "Reggaeton", "subgenre": "Unknown", "confidence": 45, "reasoning": "Drum pattern could be reggaeton but metadata insufficient"}}
]"""

    return prompt


def _call_with_backoff(call_fn, max_retries=3):
    """
    Call fn with exponential backoff on rate limit errors.
    Returns the result if successful.
    Raises Exception if all retries exhausted or non-rate-limit error occurs.
    """
    for attempt in range(max_retries):
        try:
            return call_fn()
        except Exception as e:
            err = str(e).lower()
            if '429' in err or 'rate limit' in err or 'quota' in err:
                if attempt < max_retries - 1:
                    wait = 30 * (2 ** attempt)  # 30s, 60s, 120s
                    time.sleep(wait)
                    continue
            raise  # Re-raise non-rate-limit errors immediately
    raise Exception("Rate limit exceeded after retries")


def _parse_classification_response(response_text: str, num_tracks: int) -> list[dict]:
    """
    Parse Claude's JSON response. Returns list of dicts with keys:
    index, genre, subgenre, confidence, reasoning
    Handles malformed responses gracefully.
    """
    try:
        # Extract JSON array from response
        json_str = response_text.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]

        classifications = json.loads(json_str)

        if not isinstance(classifications, list):
            return []

        return classifications

    except (json.JSONDecodeError, ValueError):
        return []


def _classify_with_claude(prompt: str, batch: list[Track]) -> tuple[bool, str]:
    """
    Classify tracks using Claude Sonnet API with exponential backoff retry.
    Returns (success: bool, response_text: str)
    """
    try:
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return False, "ANTHROPIC_API_KEY not set"

        def call_claude():
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-opus-4-6-20260522",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text

        response_text = _call_with_backoff(call_claude, max_retries=3)
        return True, response_text
    except Exception as e:
        return False, str(e)


def _classify_with_gemini(prompt: str, batch: list[Track]) -> tuple[bool, str]:
    """
    Classify tracks using Gemini API with exponential backoff retry (fallback).
    Returns (success: bool, response_text: str)
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return False, "GEMINI_API_KEY not set"

        def call_gemini():
            if USES_NEW_API:
                # New google.genai API (2026+)
                client = genai.Client(api_key=api_key)
                # Try gemini-2.5-flash first, fallback to 2.0-flash
                try:
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt
                    )
                except Exception as e:
                    logger.debug("gemini-2.5-flash failed: %s, trying gemini-2.0-flash", e)
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt
                    )
                return response.text
            else:
                # Legacy google.generativeai API (deprecated but still works)
                genai.configure(api_key=api_key)
                try:
                    model = genai.GenerativeModel("gemini-2.5-flash")
                    response = model.generate_content(prompt)
                except Exception as e:
                    logger.debug("gemini-2.5-flash failed: %s, trying gemini-2.0-flash", e)
                    model = genai.GenerativeModel("gemini-2.0-flash")
                    response = model.generate_content(prompt)
                return response.text

        response_text = _call_with_backoff(call_gemini, max_retries=3)
        return True, response_text
    except Exception as e:
        return False, str(e)


def _classify_with_ollama(prompt: str, batch: list[Track]) -> tuple[bool, str]:
    """
    Classify tracks using Ollama (fallback).
    Returns (success: bool, response_text: str)
    """
    try:
        import requests as req
        model_name = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
        response = req.post(
            "http://localhost:11434/api/generate",
            json={"model": model_name, "prompt": prompt, "stream": False},
            timeout=120
        )
        if response.status_code != 200:
            return False, f"Ollama API error: {response.status_code}"
        return True, response.json()["response"]
    except Exception as e:
        return False, str(e)


def _classify_with_openai(prompt: str, batch: list[Track]) -> tuple[bool, str]:
    """
    Classify tracks using OpenAI (GPT) API with exponential backoff retry.
    Returns (success: bool, response_text: str)
    """
    try:
        import requests as req
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return False, "OPENAI_API_KEY not set"
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")

        def call_openai():
            response = req.post(
                "https://api.openai.com/v1/chat/completions",
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2048,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120,
            )
            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} — {response.text[:200]}")
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                raise Exception("OpenAI returned empty response")
            return content

        response_text = _call_with_backoff(call_openai, max_retries=3)
        return True, response_text
    except Exception as e:
        return False, str(e)


def _classify_with_qwen(prompt: str, batch: list[Track]) -> tuple[bool, str]:
    """
    Classify tracks using Qwen (DashScope) API with exponential backoff retry.
    Uses OpenAI-compatible endpoint for portability.
    Returns (success: bool, response_text: str)
    """
    try:
        import requests as req
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            return False, "DASHSCOPE_API_KEY not set"
        model_name = os.getenv("QWEN_MODEL", "qwen3.5-plus")

        def call_qwen():
            response = req.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2048,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120,
            )
            if response.status_code != 200:
                raise Exception(f"Qwen API error: {response.status_code} — {response.text[:200]}")
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                raise Exception("Qwen returned empty response")
            return content

        response_text = _call_with_backoff(call_qwen, max_retries=3)
        return True, response_text
    except Exception as e:
        return False, str(e)


def _classify_with_openrouter(prompt: str, batch: list[Track]) -> tuple[bool, str]:
    """
    Classify tracks using OpenRouter API (supports many models via OpenAI-compatible endpoint).
    Returns (success: bool, response_text: str)
    """
    try:
        import requests as req
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return False, "OPENROUTER_API_KEY not set"
        model_name = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")
        response = req.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2048,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "http://localhost",
                "X-Title": "IDJLM Pro",
            },
            timeout=120,
        )
        if response.status_code != 200:
            return False, f"OpenRouter API error: {response.status_code} — {response.text[:200]}"
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return False, "OpenRouter returned empty response"
        return True, content
    except Exception as e:
        return False, str(e)


def classify_tracks(tracks: list[Track], taxonomy: dict, force: bool = False, model_override: str | None = None) -> list[Track]:
    """
    Classify tracks using Claude Sonnet (primary) with Gemini and Ollama fallbacks.
    Sends up to batch_size tracks per API call.
    Populates: proposed_genre, proposed_subgenre, confidence, reasoning, classification_done=True
    Sets track.error on failure.

    If force=False, skips tracks that already have proposed_genre set (already classified).
    If force=True, reclassifies all tracks regardless of prior classification status.

    If model_override is set, use ONLY that model (no fallback chain).
    """
    ai_model = os.getenv("AI_MODEL", "claude").lower()
    batch_size = int(os.getenv("CLASSIFY_BATCH_SIZE", "10"))

    logger.debug("Starting classification: ai_model=%s, batch_size=%d, tracks=%d",
                 ai_model, batch_size, len(tracks))
    if model_override:
        logger.debug("Model override: %s (no fallback)", model_override)

    # Skip already-classified tracks unless forced
    if not force:
        tracks = [
            t for t in tracks
            if t.review_status == 'pending' and t.proposed_genre is None
        ]

    logger.debug("After filtering (excluding already classified): %d tracks", len(tracks))

    # Define model chain in order
    if model_override:
        # Use ONLY the specified model, no fallback
        model_chain = [model_override.lower()]
    elif ai_model == "claude" or ai_model == "":
        model_chain = ["claude", "gemini", "openai", "qwen", "openrouter", "ollama"]
    elif ai_model == "gemini":
        model_chain = ["gemini", "claude", "openai", "qwen", "openrouter", "ollama"]
    elif ai_model == "openai":
        model_chain = ["openai", "claude", "gemini", "qwen", "openrouter", "ollama"]
    elif ai_model == "qwen":
        model_chain = ["qwen", "openai", "gemini", "claude", "openrouter", "ollama"]
    elif ai_model == "ollama":
        model_chain = ["ollama", "qwen", "openrouter", "claude", "gemini", "openai"]
    elif ai_model == "openrouter":
        model_chain = ["openrouter", "claude", "gemini", "openai", "qwen", "ollama"]
    else:
        model_chain = ["claude", "gemini", "openai", "qwen", "openrouter", "ollama"]

    # Process tracks in batches
    for batch_start in range(0, len(tracks), batch_size):
        batch_end = min(batch_start + batch_size, len(tracks))
        batch = tracks[batch_start:batch_end]

        prompt = _build_classification_prompt(batch, taxonomy)

        # Try models in chain order
        success = False
        response_text = None
        used_model = None

        for model_name in model_chain:
            if model_name == "claude":
                success, response_text = _classify_with_claude(prompt, batch)
                if success:
                    used_model = "claude"
                    break
            elif model_name == "gemini":
                success, response_text = _classify_with_gemini(prompt, batch)
                if success:
                    used_model = "gemini"
                    break
            elif model_name == "openai":
                success, response_text = _classify_with_openai(prompt, batch)
                if success:
                    used_model = "openai"
                    break
            elif model_name == "qwen":
                success, response_text = _classify_with_qwen(prompt, batch)
                if success:
                    used_model = "qwen"
                    break
            elif model_name == "ollama":
                success, response_text = _classify_with_ollama(prompt, batch)
                if success:
                    used_model = "ollama"
                    break
            elif model_name == "openrouter":
                success, response_text = _classify_with_openrouter(prompt, batch)
                if success:
                    used_model = "openrouter"
                    break

        if not success or not response_text:
            # All models failed
            for track in batch:
                track.error = f"Classification failed: {response_text}"
            continue

        logger.debug("Using %s", used_model)

        # Parse response
        classifications = _parse_classification_response(response_text, len(batch))

        # Apply results to batch
        for classification in classifications:
            idx = classification.get("index")
            if idx is None or not (0 <= idx < len(batch)):
                continue

            track = batch[idx]
            track.proposed_genre = classification.get("genre")
            track.proposed_subgenre = classification.get("subgenre")
            track.confidence = classification.get("confidence")
            track.reasoning = classification.get("reasoning")
            track.classification_done = True

        # Mark any unprocessed tracks in batch as failed
        processed_indices = {c.get("index") for c in classifications if c.get("index") is not None}
        for idx, track in enumerate(batch):
            if idx not in processed_indices and not track.classification_done:
                track.error = "Classification response malformed"

    return tracks
