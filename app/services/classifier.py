import json
import os

import google.generativeai as genai

from app.models.track import Track


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
        track_descriptions.append(desc)

    tracks_str = "\n".join(track_descriptions)
    taxonomy_str = json.dumps(taxonomy, indent=2)

    prompt = f"""You are a Latin dance music expert. Classify each track into genre and sub-genre based on the provided taxonomy.

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
2. Consider existing_genre, bpm, key, and energy when making decisions
3. If truly unclassifiable, use genre "Unknown" and subgenre "Unknown" with low confidence
4. Return valid JSON array only, no other text

Example output format:
[
  {{"index": 0, "genre": "Salsa", "subgenre": "Romántica", "confidence": 85, "reasoning": "Upbeat vocals with 95 BPM typical of romantic salsa"}},
  {{"index": 1, "genre": "Reggaeton", "subgenre": "Unknown", "confidence": 45, "reasoning": "Drum pattern could be reggaeton but metadata insufficient"}}
]"""

    return prompt


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
    Classify tracks using Claude Sonnet API.
    Returns (success: bool, response_text: str)
    """
    try:
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return False, "ANTHROPIC_API_KEY not set"

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        return True, response.content[0].text
    except Exception as e:
        return False, str(e)


def _classify_with_gemini(prompt: str, batch: list[Track]) -> tuple[bool, str]:
    """
    Classify tracks using Gemini API (fallback).
    Returns (success: bool, response_text: str)
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return False, "GEMINI_API_KEY not set"

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return True, response.text
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


def classify_tracks(tracks: list[Track], taxonomy: dict) -> list[Track]:
    """
    Classify tracks using Claude Sonnet (primary) with Gemini and Ollama fallbacks.
    Sends up to batch_size tracks per API call.
    Populates: proposed_genre, proposed_subgenre, confidence, reasoning, classification_done=True
    Sets track.error on failure.
    """
    ai_model = os.getenv("AI_MODEL", "claude").lower()
    batch_size = int(os.getenv("CLASSIFY_BATCH_SIZE", "10"))

    # Define model chain in order
    model_chain = []
    if ai_model == "claude" or ai_model == "":
        model_chain = ["claude", "gemini", "ollama"]
    elif ai_model == "gemini":
        model_chain = ["gemini", "claude", "ollama"]
    elif ai_model == "ollama":
        model_chain = ["ollama", "claude", "gemini"]
    else:
        model_chain = ["claude", "gemini", "ollama"]

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
            elif model_name == "ollama":
                success, response_text = _classify_with_ollama(prompt, batch)
                if success:
                    used_model = "ollama"
                    break

        if not success or not response_text:
            # All models failed
            for track in batch:
                track.error = f"Classification failed: {response_text}"
            continue

        print(f"[classifier] Using {used_model}")

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
