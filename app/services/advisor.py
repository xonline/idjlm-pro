"""
Next Track Advisor — recommends next tracks combining harmonic, BPM, energy, and genre compatibility.
"""
import logging
from app.models.track import Track

logger = logging.getLogger(__name__)

# Camelot wheel adjacency
CAMELOT_COMPATIBLE = {
    '1A': ['1A', '1B', '2A', '12A'],
    '1B': ['1B', '1A', '2B', '12B'],
    '2A': ['2A', '2B', '1A', '3A'],
    '2B': ['2B', '2A', '1B', '3B'],
    '3A': ['3A', '3B', '2A', '4A'],
    '3B': ['3B', '3A', '2B', '4B'],
    '4A': ['4A', '4B', '3A', '5A'],
    '4B': ['4B', '4A', '3B', '5B'],
    '5A': ['5A', '5B', '4A', '6A'],
    '5B': ['5B', '5A', '4B', '6B'],
    '6A': ['6A', '6B', '5A', '7A'],
    '6B': ['6B', '6A', '5B', '7B'],
    '7A': ['7A', '7B', '6A', '8A'],
    '7B': ['7B', '7A', '6B', '8B'],
    '8A': ['8A', '8B', '7A', '9A'],
    '8B': ['8B', '8A', '7B', '9B'],
    '9A': ['9A', '9B', '8A', '10A'],
    '9B': ['9B', '9A', '8B', '10B'],
    '10A': ['10A', '10B', '9A', '11A'],
    '10B': ['10B', '10A', '9B', '11B'],
    '11A': ['11A', '11B', '10A', '12A'],
    '11B': ['11B', '11A', '10B', '12B'],
    '12A': ['12A', '12B', '11A', '1A'],
    '12B': ['12B', '12A', '11B', '1B'],
}


def _get_key(track: Track) -> str:
    return track.analyzed_key or track.existing_key or ''

def _get_bpm(track: Track) -> float:
    return track.analyzed_bpm or float(track.existing_bpm or 0)

def _get_energy(track: Track) -> int:
    return track.analyzed_energy or 5

def _get_genre(track: Track) -> str:
    return (track.override_genre or track.proposed_genre or track.existing_genre or '').lower()


def suggest_next_tracks(track_store: dict, source_path: str, limit: int = 5) -> list[dict]:
    """
    Given a source track, return ranked suggestions from the store.
    Each result: {file_path, score, score_key, score_bpm, score_energy, score_genre, display_title, display_artist}
    """
    source = track_store.get(source_path)
    if not source:
        return []

    source_key = _get_key(source)
    source_bpm = _get_bpm(source)
    source_energy = _get_energy(source)
    source_genre = _get_genre(source)

    compatible_keys = set(CAMELOT_COMPATIBLE.get(source_key, []))

    results = []
    for path, track in track_store.items():
        if path == source_path:
            continue

        score = 0
        max_score = 0

        # Key compatibility (40 points)
        max_score += 40
        track_key = _get_key(track)
        if track_key in compatible_keys:
            if track_key == source_key:
                score += 40  # Same key = perfect
            elif track_key.replace('A', 'B').replace('B', 'A') in [source_key]:  # Relative major/minor
                score += 35
            else:
                score += 25  # Adjacent
        elif track_key:
            # +/- 2 keys
            try:
                src_num = int(source_key[:-1])
                tgt_num = int(track_key[:-1])
                if abs(src_num - tgt_num) <= 2:
                    score += 15
            except (ValueError, IndexError):
                pass

        # BPM compatibility (30 points)
        max_score += 30
        track_bpm = _get_bpm(track)
        if source_bpm > 0 and track_bpm > 0:
            bpm_diff = abs(track_bpm - source_bpm)
            bpm_pct = (bpm_diff / source_bpm) * 100
            if bpm_pct <= 3:
                score += 30
            elif bpm_pct <= 5:
                score += 25
            elif bpm_pct <= 8:
                score += 15
            elif bpm_pct <= 15:
                score += 5

        # Energy match (20 points)
        max_score += 20
        track_energy = _get_energy(track)
        energy_diff = abs(track_energy - source_energy)
        if energy_diff == 0:
            score += 20
        elif energy_diff == 1:
            score += 15
        elif energy_diff == 2:
            score += 8

        # Genre continuity (10 points)
        max_score += 10
        track_genre = _get_genre(track)
        if source_genre and track_genre == source_genre:
            score += 10
        elif source_genre and track_genre:
            score += 3  # At least has a genre

        if max_score > 0:
            normalized = round((score / max_score) * 100)
            results.append({
                'file_path': path,
                'score': normalized,
                'score_key': 1 if track_key in compatible_keys else 0,
                'score_bpm': round(100 - min(abs(track_bpm - source_bpm) / source_bpm * 100, 100)) if source_bpm > 0 else 0,
                'score_energy': max(100 - energy_diff * 25, 0),
                'score_genre': 100 if (source_genre and track_genre == source_genre) else (30 if track_genre else 0),
                'display_title': track.display_title,
                'display_artist': track.display_artist,
                'final_genre': track.final_genre,
                'final_subgenre': track.final_subgenre,
                'final_bpm': track.final_bpm,
                'final_key': track.final_key,
                'analyzed_energy': track.analyzed_energy,
            })

    # Sort by score descending
    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]
