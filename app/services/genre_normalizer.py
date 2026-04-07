"""
Genre normalization — maps common genre variants to canonical taxonomy genres.
"""

# Mapping of common variants to canonical names
GENRE_ALIASES = {
    # Salsa variants
    "salsa": "Salsa",
    "salsa dura": "Salsa",
    "salsa-dura": "Salsa",
    "salsa romantica": "Salsa",
    "salsa romántica": "Salsa",
    "salsa-romantica": "Salsa",
    "salsa jazz": "Salsa",
    "latin jazz": "Salsa",
    "timba": "Salsa",
    "mambo": "Salsa",
    "son cubano": "Salsa",
    "son": "Salsa",
    # Bachata variants
    "bachata": "Bachata",
    "bachata moderna": "Bachata",
    "bachata sensual": "Bachata",
    "bachata dominicana": "Bachata",
    "bachata tradicional": "Bachata",
    # Kizomba variants
    "kizomba": "Kizomba",
    "kizomba classica": "Kizomba",
    "ghetto zouk": "Kizomba",
    "urban kiz": "Kizomba",
    "semba": "Kizomba",
    # Reggaeton
    "reggaeton": "Reggaeton",
    "reggaetón": "Reggaeton",
    "reggaeton lento": "Reggaeton",
    # Merengue
    "merengue": "Merengue",
    "merengue tipico": "Merengue",
    # Cha Cha
    "cha cha cha": "Cha Cha",
    "chachacha": "Cha Cha",
    "cha-cha": "Cha Cha",
    # Zouk
    "zouk": "Zouk",
    "zouk love": "Zouk",
    # Tropical / Latin catch-alls
    "tropical": "Salsa",
    "latin": "Salsa",
    "cumbia": "Cumbia",
}


def normalize_genre(genre: str) -> str:
    """
    Normalize a genre string to a canonical taxonomy genre.
    Returns the canonical genre, or the original if no mapping exists.
    """
    if not genre:
        return genre
    cleaned = genre.strip().lower()
    return GENRE_ALIASES.get(cleaned, genre)


def normalize_track_genres(tracks: list, taxonomy: dict) -> list:
    """
    Normalize genres for a list of tracks.
    Only normalizes if the result exists in the taxonomy.
    Returns list of (track, old_genre, new_genre) tuples for tracks that were changed.
    """
    changes = []
    canonical_genres = set(taxonomy.get("genres", {}).keys())
    for track in tracks:
        existing = track.existing_genre or track.proposed_genre
        if not existing:
            continue
        normalized = normalize_genre(existing)
        if normalized != existing and normalized in canonical_genres:
            if not track.proposed_genre or track.proposed_genre == existing:
                track.proposed_genre = normalized
                changes.append((track, existing, normalized))
    return changes
