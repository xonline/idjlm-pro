import os
import logging
from flask import Blueprint, jsonify
from app import get_track_store, get_taxonomy, get_current_folder_path

logger = logging.getLogger(__name__)

bp = Blueprint("health", __name__, url_prefix="/api")

@bp.route("/health", methods=["GET"])
def health_check():
    """Lightweight health check endpoint."""
    track_store = get_track_store()
    taxonomy = get_taxonomy()
    folder_path = get_current_folder_path()

    checks = {
        "status": "ok",
        "taxonomy_loaded": bool(taxonomy),
        "genre_count": len(taxonomy.get("genres", [])),
        "tracks_loaded": len(track_store),
        "music_folder": folder_path or None,
        "folder_exists": os.path.isdir(folder_path) if folder_path else None,
    }
    return jsonify(checks), 200
