from flask import Blueprint, jsonify, request
import os
from datetime import datetime

bp = Blueprint("session", __name__, url_prefix="/api/session")


@bp.route("/save", methods=["POST"])
def save_session():
    """Save entire track store to session.json."""
    from app import get_track_store
    from app.services.session_service import save_session

    data = request.json or {}
    folder = data.get("folder")
    try:
        save_session(get_track_store(), folder)
        return jsonify({"success": True, "timestamp": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@bp.route("/load", methods=["POST"])
def load_session():
    """Load track store from session.json."""
    from app import get_track_store
    from app.services.session_service import load_session

    data = request.json or {}
    folder = data.get("folder", os.path.expanduser("~/Music"))
    try:
        tracks = load_session(folder)
        track_store = get_track_store()
        track_store.clear()
        for t in tracks:
            track_store[t.id] = t
        return jsonify({"success": True, "count": len(tracks)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@bp.route("/stats", methods=["GET"])
def get_stats():
    """Get session statistics."""
    from app import get_track_store

    track_store = get_track_store()
    tracks = list(track_store.values())
    return jsonify({
        "total": len(tracks),
        "analyzed": len([t for t in tracks if t.bpm]),
        "classified": len([t for t in tracks if t.classified_genre]),
        "approved": len([t for t in tracks if t.approved]),
    })


@bp.route("/status", methods=["GET"])
def get_status():
    """Get session status including track counts and last save time."""
    from app import get_track_store
    from app.services.session_service import get_last_save_time

    track_store = get_track_store()
    tracks = list(track_store.values())
    
    return jsonify({
        "track_count": len(tracks),
        "analyzed": len([t for t in tracks if t.bpm]),
        "classified": len([t for t in tracks if t.classified_genre]),
        "approved": len([t for t in tracks if t.approved]),
        "last_saved": get_last_save_time(),
    })
