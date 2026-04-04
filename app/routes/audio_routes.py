from flask import Blueprint, send_file, abort
import os

bp = Blueprint("audio", __name__, url_prefix="/api/audio")


@bp.route("/<track_id>", methods=["GET"])
def get_audio(track_id):
    """Serve MP3 file with range request support."""
    from app import get_track_store

    track_store = get_track_store()
    track = next((t for t in track_store.values() if t.id == track_id), None)
    if not track:
        abort(404)

    if not os.path.exists(track.file_path):
        abort(404)

    try:
        return send_file(
            track.file_path,
            mimetype="audio/mpeg",
            as_attachment=False,
        )
    except Exception:
        abort(500)
