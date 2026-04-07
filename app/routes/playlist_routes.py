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

        # BPM filter
        try:
            bpm_min = float(filters["bpm_min"]) if filters.get("bpm_min") else None
            bpm_max = float(filters["bpm_max"]) if filters.get("bpm_max") else None
        except (ValueError, TypeError):
            bpm_min = None
            bpm_max = None

        if bpm_min is not None or bpm_max is not None:
            try:
                bpm = float(track.final_bpm or 0)
            except (ValueError, TypeError):
                bpm = 0
            if bpm_min is not None and bpm < bpm_min:
                continue
            if bpm_max is not None and bpm > bpm_max:
                continue

        # Energy filter
        try:
            energy_min = int(filters["energy_min"]) if filters.get("energy_min") else None
            energy_max = int(filters["energy_max"]) if filters.get("energy_max") else None
        except (ValueError, TypeError):
            energy_min = None
            energy_max = None

        if energy_min is not None or energy_max is not None:
            energy = track.analyzed_energy
            if energy is None:
                continue  # Can't filter by energy if track has no energy data
            if energy_min is not None and energy < energy_min:
                continue
            if energy_max is not None and energy > energy_max:
                continue

        # Year filter
        try:
            year_min = int(filters["year_min"]) if filters.get("year_min") else None
            year_max = int(filters["year_max"]) if filters.get("year_max") else None
        except (ValueError, TypeError):
            year_min = None
            year_max = None

        if year_min is not None or year_max is not None:
            try:
                year = int(track.final_year or 0)
            except (ValueError, TypeError):
                year = 0
            if year_min is not None and year < year_min:
                continue
            if year_max is not None and year > year_max:
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
