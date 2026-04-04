from flask import Blueprint, request, jsonify
import os

bp = Blueprint("import", __name__, url_prefix="/api/import")

_current_import_state = {"folder": None, "tracks": []}


@bp.route("/pick-folder", methods=["POST"])
def pick_folder():
    """macOS native folder picker (dummy for now)."""
    data = request.json or {}
    folder = data.get("folder") or os.path.expanduser("~/Music")
    return jsonify({"folder": folder})


@bp.route("/import", methods=["POST"])
def import_folder():
    """Scan folder for MP3s."""
    from app.services.scanner import scan_folder

    data = request.json or {}
    folder = data.get("folder", os.path.expanduser("~/Music"))

    try:
        tracks = scan_folder(folder)
        _current_import_state["folder"] = folder
        _current_import_state["tracks"] = tracks
        return jsonify({"count": len(tracks), "tracks": [t.to_dict() for t in tracks]})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/analyze", methods=["POST"])
def analyze():
    """Analyze BPM, key, energy."""
    from app.services.analyzer import analyze_track

    data = request.json or {}
    track_ids = data.get("track_ids", [])

    tracks = _current_import_state["tracks"]
    for t in tracks:
        if t.id in track_ids:
            try:
                analyze_track(t)
            except Exception:
                pass

    return jsonify({"tracks": [t.to_dict() for t in tracks]})


@bp.route("/classify", methods=["POST"])
def classify():
    """AI genre classification + Spotify enrichment."""
    from app.services.classifier import classify_tracks
    from app.services.enricher import enrich_tracks

    data = request.json or {}
    track_ids = data.get("track_ids", [])

    tracks = _current_import_state["tracks"]
    selected = [t for t in tracks if t.id in track_ids]

    try:
        classify_tracks(selected)
        enrich_tracks(selected)
    except Exception as e:
        pass

    return jsonify({"tracks": [t.to_dict() for t in tracks]})


@bp.route("/finalize", methods=["POST"])
def finalize():
    """Move imported tracks into main store."""
    from app import get_track_store

    track_store = get_track_store()
    for track in _current_import_state["tracks"]:
        track_store[track.id] = track
    return jsonify({"success": True})
