from flask import Blueprint, request, jsonify

bp = Blueprint("review", __name__, url_prefix="/api/review")


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


@bp.route("/write-tags", methods=["POST"])
def write_tags():
    """Write approved changes to ID3 tags."""
    from app.services.tag_writer import write_tags_to_file
    from app import get_track_store

    data = request.json or {}
    track_ids = data.get("track_ids", [])
    track_store = get_track_store()

    written = []
    for track_id in track_ids:
        track = track_store.get(track_id)
        if track and track.approved:
            try:
                write_tags_to_file(track)
                track.tags_written = True
                written.append(track_id)
            except Exception:
                pass

    return jsonify({"written": written})
