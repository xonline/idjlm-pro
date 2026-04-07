"""AI Learning from Corrections — remembers DJ edits and uses them in future prompts."""
import json
import os
from datetime import datetime


def _get_data_dir():
    """User-writable data directory (same location as settings)."""
    import platform
    if platform.system() == "Darwin":
        return os.path.expanduser("~/Library/Application Support/IDJLM Pro")
    return os.path.expanduser("~/.idjlm-pro")


def _get_corrections_path():
    return os.path.join(_get_data_dir(), "corrections.json")


def save_correction(track):
    """
    Save a correction pattern from an approved/edited track.
    Deduplicates: if the same pattern+genre combo exists, increment count.
    """
    os.makedirs(_get_data_dir(), exist_ok=True)
    data = {"corrections": []}
    if os.path.exists(_get_corrections_path()):
        with open(_get_corrections_path()) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {"corrections": []}

    genre = track.final_genre or track.override_genre or track.proposed_genre
    subgenre = track.final_subgenre or track.override_subgenre or track.proposed_subgenre
    if not genre:
        return

    # Build pattern from available metadata
    pattern = {}
    if track.display_artist:
        pattern["artist_contains"] = track.display_artist
    bpm = track.final_bpm
    if bpm:
        try:
            bpm_num = float(bpm)
            pattern["bpm_range"] = [round(bpm_num - 5, 1), round(bpm_num + 5, 1)]
        except (ValueError, TypeError):
            pass
    energy = track.analyzed_energy
    if energy:
        try:
            pattern["energy_range"] = [max(1, int(energy) - 1), min(10, int(energy) + 1)]
        except (ValueError, TypeError):
            pass

    # Find matching existing correction or add new
    found = False
    for c in data["corrections"]:
        same_genre = c.get("corrected_genre") == genre
        same_sub = c.get("corrected_subgenre") == subgenre
        same_artist = c.get("pattern", {}).get("artist_contains") == pattern.get("artist_contains")
        if same_genre and same_sub and same_artist:
            c["count"] = c.get("count", 1) + 1
            c["last_seen"] = datetime.utcnow().isoformat()
            found = True
            break

    if not found and pattern:
        data["corrections"].append({
            "pattern": pattern,
            "corrected_genre": genre,
            "corrected_subgenre": subgenre or "Unknown",
            "count": 1,
            "last_seen": datetime.utcnow().isoformat()
        })

    # Keep max 100 entries — keep highest count
    if len(data["corrections"]) > 100:
        data["corrections"].sort(key=lambda x: x.get("count", 1), reverse=True)
        data["corrections"] = data["corrections"][:100]

    with open(_get_corrections_path(), "w") as f:
        json.dump(data, f, indent=2)


def get_correction_hints():
    """Return formatted correction hints for injection into the classification prompt."""
    data = {"corrections": []}
    if os.path.exists(_get_corrections_path()):
        with open(_get_corrections_path()) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                return ""

    corrections = data.get("corrections", [])
    corrections.sort(key=lambda x: x.get("count", 1), reverse=True)

    if not corrections:
        return ""

    hints = ["DJ CORRECTION HISTORY (apply these patterns when you see similar tracks):"]
    for c in corrections[:20]:
        p = c.get("pattern", {})
        parts = []
        if p.get("artist_contains"):
            parts.append(f"artist contains '{p['artist_contains']}'")
        if p.get("bpm_range"):
            parts.append(f"BPM {p['bpm_range'][0]}-{p['bpm_range'][1]}")
        if p.get("energy_range"):
            parts.append(f"energy {p['energy_range'][0]}-{p['energy_range'][1]}")
        hint = ", ".join(parts) if parts else "general pattern"
        hints.append(
            f"- When {hint}: prefer {c['corrected_genre']} / "
            f"{c.get('corrected_subgenre', '')} ({c['count']}x corrected)"
        )

    return "\n".join(hints)


def get_learning_stats():
    """Return learning statistics."""
    data = {"corrections": []}
    if os.path.exists(_get_corrections_path()):
        with open(_get_corrections_path()) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {"corrections": []}

    corrections = data.get("corrections", [])
    total = sum(c.get("count", 1) for c in corrections)

    return {
        "total_corrections": total,
        "unique_patterns": len(corrections),
        "top_corrections": sorted(
            corrections, key=lambda x: x.get("count", 1), reverse=True
        )[:10]
    }


def reset_corrections():
    """Delete all corrections."""
    if os.path.exists(_get_corrections_path()):
        os.remove(_get_corrections_path())
