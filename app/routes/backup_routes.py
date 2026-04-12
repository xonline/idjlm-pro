import logging
from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("backup", __name__, url_prefix="/api")

@bp.route("/organise/backups/latest", methods=["GET"])
def backups_latest():
    """GET /api/organise/backups/latest — return latest backup info."""
    from app.services.tag_backup import get_latest_backup
    latest = get_latest_backup()
    if latest:
        return jsonify({"backups": [latest]}), 200
    return jsonify({"backups": []}), 200

@bp.route("/organise/backups", methods=["GET"])
def backups_list():
    """GET /api/organise/backups — list all backups."""
    from app.services.tag_backup import list_backups
    return jsonify({"backups": list_backups()}), 200

@bp.route("/organise/backups/<backup_id>/restore", methods=["POST"])
def backups_restore(backup_id):
    """POST /api/organise/backups/{id}/restore — restore tags from backup."""
    try:
        from app import get_track_store
        from app.services.tag_backup import load_backup

        backup = load_backup(backup_id)
        if not backup:
            return jsonify({"error": f"Backup {backup_id} not found"}), 404

        store = get_track_store()
        restored = 0

        for track_data in backup.get("tracks", []):
            file_path = track_data.get("file_path", "")
            if not file_path:
                continue

            # Restore ID3 tags from backup
            try:
                audio = MutagenFile(file_path, easy=True)
                if audio is None:
                    continue

                if "title" in track_data:
                    audio["title"] = track_data["title"]
                if "artist" in track_data:
                    audio["artist"] = track_data["artist"]
                if "album" in track_data:
                    audio["album"] = track_data["album"]
                if "genre" in track_data:
                    audio["genre"] = track_data["genre"]
                if "date" in track_data:
                    audio["date"] = track_data["date"]

                audio.save()
                restored += 1

                # Update in-memory store
                if file_path in store:
                    track = store[file_path]
                    track.existing_title = track_data.get("title")
                    track.existing_artist = track_data.get("artist")
                    track.existing_genre = track_data.get("genre")
            except Exception as e:
                logger.warning("Failed to restore %s: %s", file_path, e)
                continue

        return jsonify({"restored": restored, "backup_id": backup_id}), 200

    except Exception as e:
        logger.exception("Error restoring backup %s", backup_id)
        return jsonify({"error": str(e)}), 500
