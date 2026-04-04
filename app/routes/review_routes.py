from flask import Blueprint, request, jsonify
import os
import json
from datetime import datetime

bp = Blueprint("review", __name__, url_prefix="/api/review")


def _get_backups_dir():
    """Get backups directory."""
    backups_dir = os.path.expanduser("~/.xdj_library_manager/backups")
    os.makedirs(backups_dir, exist_ok=True)
    return backups_dir


@bp.route("/approve", methods=["POST"])
def approve_track():
    """Mark single track as approved."""
    from app import get_track_store

    data = request.json or {}
    track_id = data.get("track_id")
    track_store = get_track_store()

    track = track_store.get(track_id)
    if track:
        track.approved = True
        track.skipped = False
        return jsonify({"success": True})
    return jsonify({"success": False}), 404


@bp.route("/skip", methods=["POST"])
def skip_track():
    """Mark single track as skipped."""
    from app import get_track_store

    data = request.json or {}
    track_id = data.get("track_id")
    track_store = get_track_store()

    track = track_store.get(track_id)
    if track:
        track.skipped = True
        track.approved = False
        return jsonify({"success": True})
    return jsonify({"success": False}), 404


@bp.route("/bulk-approve", methods=["POST"])
def bulk_approve():
    """Approve tracks above confidence threshold."""
    from app import get_track_store

    data = request.json or {}
    threshold = data.get("threshold", 0.8)
    track_store = get_track_store()

    count = 0
    for track in track_store.values():
        if (track.classification_confidence or 0) >= threshold and not track.approved:
            track.approved = True
            count += 1

    return jsonify({"approved": count})


@bp.route("/backups", methods=["GET"])
def list_backups():
    """List available tag backups with metadata."""
    backups_dir = _get_backups_dir()
    backups = []
    
    try:
        for filename in sorted(os.listdir(backups_dir), reverse=True):
            if filename.startswith("backup-") and filename.endswith(".json"):
                filepath = os.path.join(backups_dir, filename)
                try:
                    with open(filepath) as f:
                        data = json.load(f)
                    # Extract timestamp from filename (format: backup-YYYY-MM-DD_HH-MM-SS.json)
                    timestamp_str = filename.replace("backup-", "").replace(".json", "")
                    backups.append({
                        "filename": filename,
                        "timestamp": timestamp_str,
                        "track_count": len(data),
                    })
                except Exception:
                    pass
    except Exception:
        pass
    
    return jsonify({"backups": backups})


@bp.route("/write-tags", methods=["POST"])
def write_tags():
    """Write approved changes to ID3 tags with backup."""
    from app.services.tag_writer import write_tags_to_file, backup_original_tags
    from app import get_track_store

    data = request.json or {}
    track_ids = data.get("track_ids", [])
    track_store = get_track_store()

    # Collect tracks to write
    tracks_to_write = []
    for track_id in track_ids:
        track = track_store.get(track_id)
        if track and track.approved:
            tracks_to_write.append(track)
    
    if not tracks_to_write:
        return jsonify({"written": []})
    
    # Backup original tags before any writes
    try:
        backup_original_tags(tracks_to_write)
    except Exception as e:
        return jsonify({"error": f"Failed to backup tags: {str(e)}"}), 400
    
    # Write tags
    written = []
    for track in tracks_to_write:
        try:
            write_tags_to_file(track)
            track.tags_written = True
            written.append(track.id)
        except Exception:
            pass

    return jsonify({"written": written})
