"""Gemini AI classification with model fallback on rate limits."""
import json
import os
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))

MODELS_BY_PRIORITY = [
    "gemini-2.5-pro-preview-05-06",
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]
DEFAULT_MODEL = "gemini-2.5-flash-preview-04-17"


def _get_model(preferred: str = None) -> str:
    """Get model name: preferred > env var > default."""
    return preferred or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)


def classify_with_fallback(prompt: str, preferred_model: str = None) -> tuple:
    """
    Classify using Gemini with auto-rotation on rate limits.
    Returns (response_text, model_used).
    """
    start_idx = 0
    model_to_use = _get_model(preferred_model)
    
    if model_to_use in MODELS_BY_PRIORITY:
        start_idx = MODELS_BY_PRIORITY.index(model_to_use)
    else:
        start_idx = 0
    
    for model_name in MODELS_BY_PRIORITY[start_idx:]:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            print(f"[classifier] ✓ {model_name} responded successfully")
            return response.text, model_name
        except (ResourceExhausted, Exception) as e:
            err = str(e).lower()
            if "429" in err or "quota" in err or "resource_exhausted" in err or "rate" in err:
                print(f"[classifier] {model_name} rate limited, trying next model...")
                continue
            raise
    
    raise RuntimeError("All Gemini models exhausted (rate limited)")


def classify_tracks(tracks, batch_size=10):
    """Classify tracks using Gemini, batched, with auto-fallback."""
    from app import get_taxonomy

    if not os.getenv("GEMINI_API_KEY"):
        return

    taxonomy = get_taxonomy()
    genre_names = [g["name"] for g in taxonomy.get("genres", [])]

    # Batch process
    for i in range(0, len(tracks), batch_size):
        batch = tracks[i : i + batch_size]

        # Build prompt
        prompt = f"""Classify these songs into genres and subgenres.
        Valid genres: {', '.join(genre_names)}
        
        For each track, respond with JSON:
        {{
            "title": "<title>",
            "genre": "<genre>",
            "subgenre": "<subgenre>",
            "confidence": <0-1>
        }}
        
        Tracks:
        """
        for track in batch:
            prompt += f"\n- {track.existing_title or 'Unknown'} by {track.existing_artist or 'Unknown'}"

        try:
            text, model_used = classify_with_fallback(prompt)
            print(f"[classifier] Batch {i // batch_size + 1} classified with {model_used}")

            # Parse JSON array from response
            try:
                import re
                match = re.search(r"\[.*\]", text, re.DOTALL)
                if match:
                    results = json.loads(match.group())
                else:
                    results = []
            except:
                results = []

            # Apply results
            for j, result in enumerate(results):
                if j < len(batch):
                    track = batch[j]
                    track.classified_genre = result.get("genre")
                    track.classified_subgenre = result.get("subgenre")
                    track.classification_confidence = result.get("confidence", 0)
        except Exception as e:
            print(f"[classifier] Error: {e}")
            pass
