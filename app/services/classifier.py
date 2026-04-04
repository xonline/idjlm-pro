"""Gemini AI classification."""
import json
import os
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))


def classify_tracks(tracks, batch_size=10):
    """Classify tracks using Gemini, batched."""
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
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            text = response.text

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
        except Exception:
            pass
