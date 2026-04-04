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
    with open(SETLIST_PATH, 'w') as f:
        json.dump(data, f, indent=2)


@bp.route("/setlist", methods=["GET"])
def get_setlist():
    return jsonify(_load_setlist()), 200


@bp.route("/setlist", methods=["POST"])
def update_setlist():
    """Replace full setlist. body: {"tracks": [file_path, ...], "name": "..."}"""
    data = request.get_json() or {}
    _save_setlist(data)
    return jsonify({"saved": True}), 200


@bp.route("/setlist/add", methods=["POST"])
def add_to_setlist():
    """Add track to setlist. body: {"file_path": "...", "position": null (append)}"""
    from app import get_track_store

    data = request.get_json() or {}
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
    data = request.get_json() or {}
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
    body: {"file_path": "...", "limit": 5}
    Returns tracks with same key, +1/-1 Camelot, or same number different mode.
    """
    from app import get_track_store

    data = request.get_json() or {}
    file_path = data.get("file_path")
    limit = int(data.get("limit", 5))
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

    # Sort by BPM proximity to source
    source_bpm = float(source.final_bpm or 0)
    suggestions.sort(key=lambda t: abs(float(t["bpm"] or 0) - source_bpm))

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
