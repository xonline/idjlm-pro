from flask import Blueprint, request, jsonify, Response, stream_with_context
import os
import json
import time

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
    """SSE stream for analysis progress with ETA and auto-save every 30 tracks."""
    from app.services.analyzer import analyze_track

    data = request.json or {}
    track_ids = data.get("track_ids", [])

    tracks = _current_import_state["tracks"]
    selected = [t for t in tracks if t.id in track_ids] if track_ids else tracks
    total = len(selected)

    def generate():
        start_time = time.time()
        for i, track in enumerate(selected):
            try:
                analyze_track(track)
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                remaining = (total - (i + 1)) / rate if rate > 0 else 0
                eta_str = f"{int(remaining // 60)}m {int(remaining % 60)}s" if remaining > 60 else f"{int(remaining)}s"
                yield f"data: {json.dumps({\"done\": i+1, \"total\": total, \"track\": track.existing_title or track.id, \"status\": \"success\", \"eta\": eta_str, \"rate\": round(rate, 1)})}
"""
            except Exception as e:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                remaining = (total - (i + 1)) / rate if rate > 0 else 0
                eta_str = f"{int(remaining // 60)}m {int(remaining % 60)}s" if remaining > 60 else f"{int(remaining)}s"
                yield f"data: {json.dumps({\"done\": i+1, \"total\": total, \"track\": track.existing_title or track.id, \"status\": \"error\", \"error\": str(e), \"eta\": eta_str, \"rate\": round(rate, 1)})}
"""
            
            # Auto-save every 30 tracks
            if (i + 1) % 30 == 0:
                try:
                    from app.services.session_service import save_session
                    from app import get_track_store
                    save_session(get_track_store())
                except Exception:
                    pass  # Never block progress for auto-save
        
        yield f"data: {json.dumps({\"complete\": True, \"total\": total})}
"""

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
    """SSE stream for classification progress with ETA and auto-save every 30 tracks."""
    from app.services.classifier import classify_tracks
    from app.services.enricher import enrich_tracks

    data = request.json or {}
    track_ids = data.get("track_ids", [])

    tracks = _current_import_state["tracks"]
    selected = [t for t in tracks if t.id in track_ids] if track_ids else [t for t in tracks if t.bpm]
    total = len(selected)

    def generate():
        start_time = time.time()
        for i, track in enumerate(selected):
            try:
                classify_tracks([track])
                enrich_tracks([track])
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                remaining = (total - (i + 1)) / rate if rate > 0 else 0
                eta_str = f"{int(remaining // 60)}m {int(remaining % 60)}s" if remaining > 60 else f"{int(remaining)}s"
                yield f"data: {json.dumps({\"done\": i+1, \"total\": total, \"track\": track.existing_title or track.id, \"status\": \"success\", \"genre\": track.classified_genre or \"—\", \"confidence\": round(track.classification_confidence or 0, 2), \"eta\": eta_str, \"rate\": round(rate, 1)})}
"""
            except Exception as e:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                remaining = (total - (i + 1)) / rate if rate > 0 else 0
                eta_str = f"{int(remaining // 60)}m {int(remaining % 60)}s" if remaining > 60 else f"{int(remaining)}s"
                yield f"data: {json.dumps({\"done\": i+1, \"total\": total, \"track\": track.existing_title or track.id, \"status\": \"error\", \"error\": str(e), \"eta\": eta_str, \"rate\": round(rate, 1)})}
"""
            
            # Auto-save every 30 tracks
            if (i + 1) % 30 == 0:
                try:
                    from app.services.session_service import save_session
                    from app import get_track_store
                    save_session(get_track_store())
                except Exception:
                    pass  # Never block progress for auto-save
        
        yield f"data: {json.dumps({\"complete\": True, \"total\": total})}
"""

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@bp.route("/classify/low-confidence", methods=["POST"])
def classify_low_confidence():
    """Re-run classification only on tracks below confidence threshold."""
    from app import get_track_store, get_taxonomy
    
    data = request.get_json() or {}
    threshold = int(data.get("threshold", 70))
    track_store = get_track_store()
    
    low_conf = [
        fp for fp, t in track_store.items()
        if t.analysis_done and (t.proposed_confidence is None or t.proposed_confidence < threshold)
    ]
    
    return jsonify({"track_paths": low_conf, "count": len(low_conf)})


@bp.route("/finalize", methods=["POST"])
def finalize():
    """Move imported tracks into main store."""
    from app import get_track_store

    track_store = get_track_store()
    for track in _current_import_state["tracks"]:
        track_store[track.id] = track
    return jsonify({"success": True})
