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


def classify_tracks(tracks: list[Track], taxonomy: dict) -> list[Track]:
    """
    Classify tracks using Gemini API.
    Sends up to 10 tracks per API call to reduce costs.
    Populates: proposed_genre, proposed_subgenre, confidence, reasoning, classification_done=True
    Sets track.error on failure.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        for track in tracks:
            track.error = "GEMINI_API_KEY not set"
        return tracks

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    # Process tracks in batches of up to 10
    batch_size = 10
    for batch_start in range(0, len(tracks), batch_size):
        batch_end = min(batch_start + batch_size, len(tracks))
        batch = tracks[batch_start:batch_end]

        try:
            prompt = _build_classification_prompt(batch, taxonomy)

            response = model.generate_content(prompt)
            response_text = response.text

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

        except Exception as e:
            # Mark all tracks in batch with error
            for track in batch:
                track.error = f"Classification API error: {str(e)}"

    return tracks
