import os
from flask import Blueprint, request, jsonify
from app.services.session_service import save_session, load_session, SESSION_FILE

bp = Blueprint("session", __name__, url_prefix="/api")


@bp.route("/session/save", methods=["POST"])
def save_session_endpoint():
    """
    Save current track store to session.json.
    POST /api/session/save
    body: { "folder_path": "..." }  # optional
    """
    try:
        from app import get_track_store

        data = request.get_json() or {}
        folder_path = data.get("folder_path")

        track_store = get_track_store()
        session_data = save_session(track_store, folder_path)

        return jsonify({
            "saved": True,
            "path": os.path.abspath(SESSION_FILE),
            "track_count": session_data.get("track_count", 0),
            "saved_at": session_data.get("saved_at")
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/session/load", methods=["POST"])
def load_session_endpoint():
    """
    Load session from session.json and repopulate track store.
    POST /api/session/load
    """
    try:
        from app import get_track_store

        track_store_loaded, metadata = load_session()

        if track_store_loaded is None:
            return jsonify({
                "error": "No saved session found"
            }), 404

        # Clear current track store and populate with loaded data
        track_store = get_track_store()
        track_store.clear()
        track_store.update(track_store_loaded)

        # Convert tracks to dicts for response
        tracks_response = [t.to_dict() for t in track_store_loaded.values()]

        return jsonify({
            "loaded": True,
            "count": len(track_store_loaded),
            "tracks": tracks_response,
            "metadata": metadata
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/session/exists", methods=["GET"])
def session_exists():
    """
    Check if session.json exists and return metadata.
    GET /api/session/exists
    """
    try:
        if not os.path.exists(SESSION_FILE):
            return jsonify({
                "exists": False,
                "track_count": 0
            }), 200

        track_store_loaded, metadata = load_session()

        if track_store_loaded is None:
            return jsonify({
                "exists": False,
                "track_count": 0
            }), 200

        return jsonify({
            "exists": True,
            "track_count": len(track_store_loaded),
            "saved_at": metadata.get("saved_at"),
            "folder_path": metadata.get("folder_path")
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
