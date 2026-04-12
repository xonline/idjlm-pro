import os
from difflib import SequenceMatcher


def _normalize_string(s: str) -> str:
    """Normalize string for comparison: lowercase, stripped, single spaces."""
    if not s:
        return ""
    return " ".join(s.lower().strip().split())


def _normalize_filename(filename: str) -> str:
    """Normalize filename: remove extension, normalize spaces."""
    if not filename:
        return ""
    # Remove extension
    name_without_ext = os.path.splitext(filename)[0]
    # Normalize
    return _normalize_string(name_without_ext)


def _fuzzy_match(s1: str, s2: str, threshold: float = 0.85) -> bool:
    """Check if two strings are fuzzy matches above threshold."""
    if not s1 or not s2:
        return False
    ratio = SequenceMatcher(None, s1, s2).ratio()
    return ratio >= threshold


def find_duplicates(track_store: dict) -> dict:
    """
    Detect duplicate tracks based on:
    1. Exact duplicate: same artist + title (case-insensitive, stripped)
    2. Fuzzy duplicate: similar filename (normalized)

    Args:
        track_store: dict mapping file_path -> Track

    Returns:
        {
            "groups": [
                {
                    "tracks": [file_path1, file_path2, ...],
                    "reason": "same_metadata" | "fuzzy_filename",
                    "artist": str,
                    "title": str
                }
            ],
            "total_duplicates": int
        }
    """
    groups = []
    visited = set()
    total_duplicates = 0

    # Convert to list of (file_path, track) tuples
    tracks_list = list(track_store.items())

    # Check exact duplicates by artist + title
    for i, (fp1, track1) in enumerate(tracks_list):
        if fp1 in visited:
            continue

        # Get artist and title to compare
        artist1 = _normalize_string(
            track1.existing_artist or track1.spotify_artist or ""
        )
        title1 = _normalize_string(
            track1.existing_title or track1.spotify_title or ""
        )

        if not artist1 or not title1:
            continue

        # Find all tracks with same artist+title
        group = [fp1]
        for j, (fp2, track2) in enumerate(tracks_list):
            if i >= j or fp2 in visited:
                continue

            artist2 = _normalize_string(
                track2.existing_artist or track2.spotify_artist or ""
            )
            title2 = _normalize_string(
                track2.existing_title or track2.spotify_title or ""
            )

            if artist1 == artist2 and title1 == title2:
                group.append(fp2)
                visited.add(fp2)

        if len(group) > 1:
            visited.add(fp1)
            groups.append({
                "tracks": group,
                "reason": "same_metadata",
                "artist": artist1,
                "title": title1
            })
            total_duplicates += len(group) - 1  # All except the first are duplicates

    # Check fuzzy filename duplicates (only if not already in exact match group)
    for i, (fp1, track1) in enumerate(tracks_list):
        if fp1 in visited:
            continue

        filename1 = _normalize_filename(track1.filename)
        if not filename1:
            continue

        group = [fp1]
        for j, (fp2, track2) in enumerate(tracks_list):
            if i >= j or fp2 in visited:
                continue

            filename2 = _normalize_filename(track2.filename)
            if _fuzzy_match(filename1, filename2):
                group.append(fp2)
                visited.add(fp2)

        if len(group) > 1:
            visited.add(fp1)
            groups.append({
                "tracks": group,
                "reason": "fuzzy_filename",
                "filename_pattern": filename1
            })
            total_duplicates += len(group) - 1

    return {
        "groups": groups,
        "total_duplicates": total_duplicates
    }


def mark_duplicates(track_store: dict) -> None:
    """
    Mark duplicate tracks in track_store with is_duplicate=True and duplicate_of.
    For each group, marks all but the first track as duplicates.
    """
    duplicates_result = find_duplicates(track_store)

    for group in duplicates_result["groups"]:
        tracks = group["tracks"]
        if len(tracks) > 1:
            # First track is the original
            original_path = tracks[0]

            # Mark remaining as duplicates
            for dup_path in tracks[1:]:
                if dup_path in track_store:
                    track_store[dup_path].is_duplicate = True
                    track_store[dup_path].duplicate_of = original_path
