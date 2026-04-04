from flask import Blueprint, request, jsonify, Response, stream_with_context
import os
import json

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


@bp.route("/analyze/stream", methods=["POST"])
def analyze_stream():
    """SSE stream for analysis progress."""
    from app.services.analyzer import analyze_track

    data = request.json or {}
    track_ids = data.get("track_ids", [])

    tracks = _current_import_state["tracks"]
    selected = [t for t in tracks if t.id in track_ids] if track_ids else tracks
    total = len(selected)

    def generate():
        for i, track in enumerate(selected):
            try:
                analyze_track(track)
                yield f"data: {json.dumps({\"done\": i+1, \"total\": total, \"track\": track.existing_title or track.id, \"status\": \"success\"})}
\n\n"
            except Exception as e:
                yield f"data: {json.dumps({\"done\": i+1, \"total\": total, \"track\": track.existing_title or track.id, \"status\": \"error\", \"error\": str(e)})}
\n\n"
        yield f"data: {json.dumps({\"complete\": True, \"total\": total})}
\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


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


@bp.route("/classify/stream", methods=["POST"])
def classify_stream():
    """SSE stream for classification progress."""
    from app.services.classifier import classify_tracks
    from app.services.enricher import enrich_tracks

    data = request.json or {}
    track_ids = data.get("track_ids", [])

    tracks = _current_import_state["tracks"]
    selected = [t for t in tracks if t.id in track_ids] if track_ids else [t for t in tracks if t.bpm]
    total = len(selected)

    def generate():
        for i, track in enumerate(selected):
            try:
                classify_tracks([track])
                enrich_tracks([track])
                yield f"data: {json.dumps({\"done\": i+1, \"total\": total, \"track\": track.existing_title or track.id, \"status\": \"success\", \"genre\": track.classified_genre or \"—\", \"confidence\": round(track.classification_confidence or 0, 2)})}
\n\n"
            except Exception as e:
                yield f"data: {json.dumps({\"done\": i+1, \"total\": total, \"track\": track.existing_title or track.id, \"status\": \"error\", \"error\": str(e)})}
\n\n"
        yield f"data: {json.dumps({\"complete\": True, \"total\": total})}
\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@bp.route("/finalize", methods=["POST"])
def finalize():
    """Move imported tracks into main store."""
    from app import get_track_store

    track_store = get_track_store()
    for track in _current_import_state["tracks"]:
        track_store[track.id] = track
    return jsonify({"success": True})
