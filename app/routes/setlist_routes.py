"""
Setlist: ordered list of tracks for DJ set planning.
Persisted to setlist.json in project root.
"""
import json
import os
from flask import Blueprint, request, jsonify, send_file
import io

bp = Blueprint("setlist", __name__, url_prefix="/api")
SETLIST_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'setlist.json')


def _load_setlist():
    if os.path.exists(SETLIST_PATH):
        with open(SETLIST_PATH) as f:
            return json.load(f)
    return {"tracks": [], "name": "My Set"}


def _save_setlist(data):
    from app.utils.paths import atomic_write
    atomic_write(SETLIST_PATH, data, indent=2)


@bp.route("/setlist", methods=["GET"])
def get_setlist():
    return jsonify(_load_setlist()), 200


@bp.route("/setlist", methods=["POST"])
def update_setlist():
    """Replace full setlist. body: {"tracks": [file_path, ...], "name": "..."}"""
    data = request.get_json(silent=True) or {}
    _save_setlist(data)
    return jsonify({"saved": True}), 200


@bp.route("/setlist/add", methods=["POST"])
def add_to_setlist():
    """Add track to setlist. body: {"file_path": "...", "position": null (append)}"""

    data = request.get_json(silent=True) or {}
    file_path = data.get("file_path")
    position = data.get("position")  # None = append

    setlist = _load_setlist()
    if file_path not in setlist["tracks"]:
        if position is not None:
            setlist["tracks"].insert(int(position), file_path)
        else:
            setlist["tracks"].append(file_path)
    _save_setlist(setlist)
    return jsonify({"count": len(setlist["tracks"])}), 200


@bp.route("/setlist/remove", methods=["POST"])
def remove_from_setlist():
    """Remove track. body: {"file_path": "..."}"""
    data = request.get_json(silent=True) or {}
    file_path = data.get("file_path")
    setlist = _load_setlist()
    setlist["tracks"] = [t for t in setlist["tracks"] if t != file_path]
    _save_setlist(setlist)
    return jsonify({"count": len(setlist["tracks"])}), 200


def _get_compatible_keys(key: str) -> set:
    """Return harmonically compatible Camelot keys (same, +1/-1, same number other mode)."""
    compatible = {key}
    try:
        num = int(key[:-1])
        mode = key[-1]  # 'A' or 'B'
        # Same number, other mode
        other_mode = 'B' if mode == 'A' else 'A'
        compatible.add(f"{num}{other_mode}")
        # +1 and -1 (circular 1-12)
        compatible.add(f"{(num % 12) + 1}{mode}")
        compatible.add(f"{((num - 2) % 12) + 1}{mode}")
    except (ValueError, IndexError):
        pass
    return compatible


@bp.route("/setlist/suggest", methods=["POST"])
def suggest_next():
    """
    Given a track's Camelot key, suggest harmonically compatible tracks.
    body: {"file_path": "...", "limit": 5, "bpm_weight": 1.0, "energy_weight": 1.0, "genre_weight": 1.0, "key_weight": 1.0}
    Returns tracks with same key, +1/-1 Camelot, or same number different mode.
    """
    from app import get_track_store

    data = request.get_json(silent=True) or {}
    file_path = data.get("file_path")
    limit = int(data.get("limit", 5))
    key_weight = float(data.get("key_weight", 1.0))
    bpm_weight = float(data.get("bpm_weight", 1.0))
    energy_weight = float(data.get("energy_weight", 1.0))
    genre_weight = float(data.get("genre_weight", 1.0))
    track_store = get_track_store()

    if file_path not in track_store:
        return jsonify({"error": "Track not found"}), 404

    source = track_store[file_path]
    source_key = source.final_key  # e.g. "8B"

    if not source_key:
        return jsonify({"suggestions": []}), 200

    # Parse Camelot key
    compatible_keys = _get_compatible_keys(source_key)
    setlist = _load_setlist()

    suggestions = []
    for fp, track in track_store.items():
        if fp == file_path or fp in setlist["tracks"]:
            continue
        if track.final_key in compatible_keys:
            suggestions.append({
                "file_path": fp,
                "title": track.display_title,
                "artist": track.display_artist,
                "key": track.final_key,
                "bpm": track.final_bpm,
                "energy": track.analyzed_energy,
                "genre": track.final_genre,
                "compatibility": "same" if track.final_key == source_key else "adjacent",
            })

    # Apply weighted scoring similar to advisor service
    source_bpm = float(source.final_bpm or 0)
    source_energy = track.analyzed_energy if (track := source).analyzed_energy is not None else 5
    source_genre = (source.override_genre or source.proposed_genre or source.existing_genre or "").lower()

    # Score each suggestion using weighted parameters
    for s in suggestions:
        score = 0.0
        max_score = 0.0

        # Key compatibility
        max_score += 40 * key_weight
        track_key = s["key"]
        if track_key == source_key:
            score += 40 * key_weight
        elif track_key and track_key.replace('A', 'B').replace('B', 'A') in [source_key]:
            score += 35 * key_weight
        else:
            score += 25 * key_weight

        # BPM compatibility
        max_score += 30 * bpm_weight
        track_bpm = float(s["bpm"] or 0)
        if source_bpm > 0 and track_bpm > 0:
            bpm_diff = abs(track_bpm - source_bpm)
            bpm_pct = (bpm_diff / source_bpm) * 100
            if bpm_pct <= 3:
                score += 30 * bpm_weight
            elif bpm_pct <= 5:
                score += 25 * bpm_weight
            elif bpm_pct <= 8:
                score += 15 * bpm_weight
            elif bpm_pct <= 15:
                score += 5 * bpm_weight

        # Energy match
        max_score += 20 * energy_weight
        track_energy = s["energy"] or 5
        energy_diff = abs(track_energy - source_energy)
        if energy_diff == 0:
            score += 20 * energy_weight
        elif energy_diff == 1:
            score += 15 * energy_weight
        elif energy_diff == 2:
            score += 8 * energy_weight

        # Genre continuity
        max_score += 10 * genre_weight
        track_genre = (s.get("genre") or "").lower()
        if source_genre and track_genre == source_genre:
            score += 10 * genre_weight
        elif source_genre and track_genre:
            score += 3 * genre_weight

        s["score"] = round((score / max_score) * 100) if max_score > 0 else 0

    # Sort by score descending
    suggestions.sort(key=lambda t: t["score"], reverse=True)

    return jsonify({"suggestions": suggestions[:limit]}), 200


@bp.route("/setlist/export", methods=["GET"])
def export_setlist():
    """Export current setlist as M3U."""
    from app import get_track_store

    track_store = get_track_store()
    setlist = _load_setlist()

    lines = ["#EXTM3U"]
    for fp in setlist["tracks"]:
        track = track_store.get(fp)
        if track:
            lines.append(f"#EXTINF:0,{track.display_artist} - {track.display_title}")
        lines.append(fp)

    name = setlist.get("name", "My Set").replace(" ", "-")
    return send_file(
        io.BytesIO("\n".join(lines).encode()),
        mimetype="audio/x-mpegurl",
        as_attachment=True,
        download_name=f"{name}.m3u"
    )
