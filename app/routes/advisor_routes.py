import logging
from flask import Blueprint, request, jsonify
from app import get_track_store

logger = logging.getLogger(__name__)

bp = Blueprint("advisor", __name__, url_prefix="/api")

@bp.route("/suggest_next", methods=["POST"])
def suggest_next():
    """POST /api/suggest_next { "file_path": "/path/to/track.mp3", "limit": 5 }"""
    data = request.get_json(silent=True) or {}
    file_path = data.get("file_path", "")
    limit = min(int(data.get("limit", 5)), 20)

    if not file_path:
        return jsonify({"error": "file_path is required"}), 400

    store = get_track_store()
    results = []
    try:
        from app.services.advisor import suggest_next_tracks
        results = suggest_next_tracks(store, file_path, limit)
    except Exception as e:
        logger.exception("Error in /api/suggest_next")
        return jsonify({"error": str(e)}), 500

    return jsonify({"suggestions": results}), 200
