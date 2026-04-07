"""
Playlist Management: named playlists with filter-based track selection and M3U export.
Persisted to playlists.json in project root.
"""
import json
import os
import io
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file

bp = Blueprint("playlists", __name__, url_prefix="/api")
PLAYLISTS_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'playlists.json')


def _load_playlists():
    if os.path.exists(PLAYLISTS_PATH):
        with open(PLAYLISTS_PATH) as f:
            return json.load(f)
    return {"playlists": []}


def _save_playlists(data):
    with open(PLAYLISTS_PATH, 'w') as f:
        json.dump(data, f, indent=2)


def _apply_filters(track_store, filters):
    """Filter tracks based on filter criteria. All AND-combined."""
    results = []
    for fp, track in track_store.items():
        if filters.get("genre") and track.final_genre != filters["genre"]:
            continue
        if filters.get("subgenre") and track.final_subgenre != filters["subgenre"]:
            continue
        if filters.get("status") and track.review_status != filters["status"]:
            continue
        if filters.get("key") and track.final_key != filters["key"]:
            continue
        bpm = track.final_bpm
        if filters.get("bpm_min"):
            try:
                if float(bpm or 0) < float(filters["bpm_min"]):
                    continue
            except (ValueError, TypeError):
                continue
        if filters.get("bpm_max"):
            try:
                if float(bpm or 0) > float(filters["bpm_max"]):
                    continue
            except (ValueError, TypeError):
                continue
        energy = track.analyzed_energy
        if filters.get("energy_min") and (not energy or energy < int(filters["energy_min"])):
            continue
        if filters.get("energy_max") and (not energy or energy > int(filters["energy_max"])):
            continue
        year = track.final_year
        if filters.get("year_min"):
            try:
                if int(year or 0) < int(filters["year_min"]):
                    continue
            except (ValueError, TypeError):
                continue
        if filters.get("year_max"):
            try:
                if int(year or 0) > int(filters["year_max"]):
                    continue
            except (ValueError, TypeError):
                continue
        results.append(track.to_dict())
    return results


@bp.route("/playlists", methods=["GET"])
def list_playlists():
    data = _load_playlists()
    playlists = []
    for p in data.get("playlists", []):
        playlists.append({
            "id": p["id"],
            "name": p["name"],
            "track_count": len(p.get("tracks", [])),
            "created": p.get("created"),
            "filters": p.get("filters", {})
        })
    return jsonify({"playlists": playlists}), 200


@bp.route("/playlists", methods=["POST"])
def create_playlist():
    body = request.get_json(silent=True) or {}
    data = _load_playlists()
    pid = body.get("id") or f"pl_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    playlist = {
        "id": pid,
        "name": body.get("name", "Untitled"),
        "filters": body.get("filters", {}),
        "tracks": body.get("tracks", []),
        "created": datetime.utcnow().isoformat()
    }
    data["playlists"].append(playlist)
    _save_playlists(data)
    return jsonify({"id": pid, "saved": True}), 200


@bp.route("/playlists/<playlist_id>", methods=["GET"])
def get_playlist(playlist_id):
    data = _load_playlists()
    for p in data.get("playlists", []):
        if p["id"] == playlist_id:
            return jsonify(p), 200
    return jsonify({"error": "Not found"}), 404


@bp.route("/playlists/<playlist_id>", methods=["PUT"])
def update_playlist(playlist_id):
    body = request.get_json(silent=True) or {}
    data = _load_playlists()
    for p in data.get("playlists", []):
        if p["id"] == playlist_id:
            if "name" in body:
                p["name"] = body["name"]
            if "filters" in body:
                p["filters"] = body["filters"]
            if "tracks" in body:
                p["tracks"] = body["tracks"]
            _save_playlists(data)
            return jsonify({"saved": True}), 200
    return jsonify({"error": "Not found"}), 404


@bp.route("/playlists/<playlist_id>", methods=["DELETE"])
def delete_playlist(playlist_id):
    data = _load_playlists()
    data["playlists"] = [p for p in data.get("playlists", []) if p["id"] != playlist_id]
    _save_playlists(data)
    return jsonify({"deleted": True}), 200


@bp.route("/playlists/<playlist_id>/run", methods=["POST"])
def run_playlist(playlist_id):
    from app import get_track_store
    data = _load_playlists()
    for p in data.get("playlists", []):
        if p["id"] == playlist_id:
            tracks = _apply_filters(get_track_store(), p.get("filters", {}))
            return jsonify({"tracks": tracks, "count": len(tracks)}), 200
    return jsonify({"error": "Not found"}), 404


@bp.route("/playlists/<playlist_id>/export-m3u", methods=["GET"])
def export_playlist_m3u(playlist_id):
    from app import get_track_store
    data = _load_playlists()
    track_store = get_track_store()
    for p in data.get("playlists", []):
        if p["id"] == playlist_id:
            lines = ["#EXTM3U"]
            for fp in p.get("tracks", []):
                track = track_store.get(fp)
                if track:
                    lines.append(f"#EXTINF:0,{track.display_artist} - {track.display_title}")
                    lines.append(fp)
            name = p["name"].replace(" ", "-")
            return send_file(
                io.BytesIO("\n".join(lines).encode()),
                mimetype="audio/x-mpegurl",
                as_attachment=True,
                download_name=f"{name}.m3u"
            )
    return jsonify({"error": "Not found"}), 404


@bp.route("/playlists/run", methods=["POST"])
def run_filters_adhoc():
    from app import get_track_store
    body = request.get_json(silent=True) or {}
    filters = body.get("filters", {})
    tracks = _apply_filters(get_track_store(), filters)
    return jsonify({"tracks": tracks, "count": len(tracks)}), 200
