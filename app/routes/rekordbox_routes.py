import logging
from flask import Blueprint, jsonify
from app import get_track_store

logger = logging.getLogger(__name__)

bp = Blueprint("rekordbox", __name__, url_prefix="/api")


@bp.route("/rekordbox/matches", methods=["GET"])
def rekordbox_matches():
    """GET /api/rekordbox/matches — return rekordbox data matched to IDJLM tracks."""
    try:
        from app.services.rekordbox_reader import match_rekordbox_tracks
        store = get_track_store()
        matches = match_rekordbox_tracks(store)
        return jsonify({
            "total_rekordbox_tracks": len(matches),
            "matches": matches
        }), 200
    except Exception as e:
        logger.exception("Error in /api/rekordbox/matches")
        return jsonify({"error": str(e)}), 500


@bp.route("/rekordbox/status", methods=["GET"])
def rekordbox_status():
    """GET /api/rekordbox/status — check if rekordbox DB is accessible."""
    try:
        from app.services.rekordbox_reader import _find_rekordbox_db
        db_path = _find_rekordbox_db()
        return jsonify({
            "found": bool(db_path),
            "path": db_path,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
