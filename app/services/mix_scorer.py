import re
from app.models.track import Track


def parse_camelot(key_str: str) -> tuple[int, str]:
    """
    Parse Camelot key string like "8B" into (number, letter).
    Returns: (number: 1-12, letter: "A"|"B") or (0, "") if invalid
    """
    if not key_str:
        return 0, ""

    match = re.match(r'^(\d{1,2})([AB])$', key_str.strip())
    if match:
        return int(match.group(1)), match.group(2)
    return 0, ""


def camelot_distance(key1: str, key2: str) -> int:
    """
    Calculate distance between two Camelot keys.
    Returns: 0 (same), 1 (adjacent), or >1 (further away)
    """
    num1, letter1 = parse_camelot(key1)
    num2, letter2 = parse_camelot(key2)

    if num1 == 0 or num2 == 0:
        return 999  # Invalid key

    # Same key = 0
    if num1 == num2 and letter1 == letter2:
        return 0

    # Adjacent on wheel: ±1 number with same letter, OR same number with different letter
    if num1 == num2 and letter1 != letter2:
        return 1  # Same number, different letter (e.g. 8A → 8B)

    num_diff = abs(num1 - num2)
    # Circular distance (1-12 wheel)
    num_diff = min(num_diff, 12 - num_diff)

    if num_diff == 1 and letter1 == letter2:
        return 1  # Adjacent number, same letter

    if num_diff == 1 and letter1 != letter2:
        return 2  # Adjacent number, different letter

    if num_diff <= 2:
        return 2

    return 3  # Far away


def score_bpm_compatibility(bpm1: float, bpm2: float) -> int:
    """
    Score BPM compatibility (0-25).
    Checks exact, ±2, ±5, ±8, or half/double BPM.
    """
    if not bpm1 or not bpm2:
        return 0

    diff = abs(bpm1 - bpm2)

    # Check double/half BPM (harmonic mix)
    if abs(bpm1 * 2 - bpm2) < 1 or abs(bpm1 / 2 - bpm2) < 1:
        return 25

    # Exact match
    if diff == 0:
        return 25

    # ±2 BPM
    if diff <= 2:
        return 20

    # ±5 BPM
    if diff <= 5:
        return 15

    # ±8 BPM
    if diff <= 8:
        return 8

    # >8 BPM difference
    return 0


def score_key_compatibility(key1: str, key2: str) -> int:
    """
    Score key/Camelot compatibility (0-35).
    Same key → 35
    Adjacent on wheel → 25
    2 steps away → 10
    Further → 0
    """
    if not key1 or not key2:
        return 0

    distance = camelot_distance(key1, key2)

    if distance == 0:
        return 35
    elif distance == 1:
        return 25
    elif distance == 2:
        return 10
    else:
        return 0


def score_energy_compatibility(energy1: int, energy2: int) -> int:
    """
    Score energy compatibility (0-20).
    Exact match → 20
    1 level diff → 15
    2 level diff → 10
    3 level diff → 5
    >3 level diff → 0
    """
    if not energy1 or not energy2:
        return 0

    diff = abs(energy1 - energy2)

    if diff == 0:
        return 20
    elif diff == 1:
        return 15
    elif diff == 2:
        return 10
    elif diff == 3:
        return 5
    else:
        return 0


def normalize_genre(genre: str) -> str:
    """Normalize genre name for comparison."""
    if not genre:
        return ""
    return genre.lower().strip()


def get_genre_family(genre: str) -> str:
    """Map genre to family group for loose matching."""
    genre = normalize_genre(genre)

    # Latin family
    if any(x in genre for x in ["salsa", "son", "mambo", "cha", "rumba", "tango", "latin"]):
        return "latin"

    # House family
    if any(x in genre for x in ["house", "deep house", "tech house", "progressive house"]):
        return "house"

    # Electronic family
    if any(x in genre for x in ["techno", "trance", "drum", "dnb", "breaks", "electro"]):
        return "electronic"

    # Hip-hop family
    if any(x in genre for x in ["hip-hop", "hip hop", "rap", "trap"]):
        return "hiphop"

    # Soul/Funk family
    if any(x in genre for x in ["soul", "funk", "disco", "groov"]):
        return "soulfunk"

    return genre


def score_genre_compatibility(genre1: str, genre2: str) -> int:
    """
    Score genre compatibility (0-20).
    Exact match → 20
    Same family → 10
    Different → 0
    """
    if not genre1 or not genre2:
        return 0

    norm1 = normalize_genre(genre1)
    norm2 = normalize_genre(genre2)

    # Exact match
    if norm1 == norm2:
        return 20

    # Family match
    family1 = get_genre_family(genre1)
    family2 = get_genre_family(genre2)

    if family1 and family2 and family1 == family2:
        return 10

    return 0


def score_compatibility(track_a: Track, track_b: Track) -> dict:
    """
    Score mixing compatibility between two tracks.

    Returns:
    {
      "score": 0-100,
      "bpm_score": 0-25,
      "key_score": 0-35,
      "energy_score": 0-20,
      "genre_score": 0-20,
      "details": "explanation string"
    }
    """
    if not track_a or not track_b:
        return {
            "score": 0,
            "bpm_score": 0,
            "key_score": 0,
            "energy_score": 0,
            "genre_score": 0,
            "details": "One or both tracks missing"
        }

    # Get final values
    bpm_a = track_a.analyzed_bpm
    bpm_b = track_b.analyzed_bpm
    key_a = track_a.final_key
    key_b = track_b.final_key
    energy_a = track_a.analyzed_energy
    energy_b = track_b.analyzed_energy
    genre_a = track_a.final_genre
    genre_b = track_b.final_genre

    # Calculate component scores
    bpm_score = score_bpm_compatibility(bpm_a, bpm_b)
    key_score = score_key_compatibility(key_a, key_b)
    energy_score = score_energy_compatibility(energy_a, energy_b)
    genre_score = score_genre_compatibility(genre_a, genre_b)

    # Total score
    total_score = bpm_score + key_score + energy_score + genre_score

    # Build details string
    details_parts = []

    if bpm_a and bpm_b:
        bpm_diff = abs(bpm_a - bpm_b)
        if bpm_diff == 0:
            details_parts.append("BPM exact match")
        elif bpm_diff <= 2:
            details_parts.append(f"BPM diff {bpm_diff:.1f} (+{bpm_score}pts)")
        elif bpm_diff <= 5:
            details_parts.append(f"BPM diff {bpm_diff:.1f} (+{bpm_score}pts)")
        elif bpm_diff <= 8:
            details_parts.append(f"BPM diff {bpm_diff:.1f} (+{bpm_score}pts)")
        else:
            details_parts.append(f"BPM diff {bpm_diff:.1f} (incompatible)")

    if key_a and key_b:
        dist = camelot_distance(key_a, key_b)
        if dist == 0:
            details_parts.append(f"same Camelot key (+{key_score}pts)")
        elif dist == 1:
            details_parts.append(f"adjacent Camelot (+{key_score}pts)")
        else:
            details_parts.append(f"Camelot distance {dist} (+{key_score}pts)")

    if energy_a and energy_b:
        energy_diff = abs(energy_a - energy_b)
        if energy_diff == 0:
            details_parts.append("same energy level")
        else:
            details_parts.append(f"energy diff {energy_diff} (+{energy_score}pts)")

    if genre_a and genre_b:
        if normalize_genre(genre_a) == normalize_genre(genre_b):
            details_parts.append("same genre (+20pts)")
        elif get_genre_family(genre_a) == get_genre_family(genre_b):
            details_parts.append("same genre family (+10pts)")

    return {
        "score": total_score,
        "bpm_score": bpm_score,
        "key_score": key_score,
        "energy_score": energy_score,
        "genre_score": genre_score,
        "details": ", ".join(details_parts) if details_parts else "Incomplete metadata"
    }
