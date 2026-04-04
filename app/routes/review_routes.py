from flask import Blueprint, request, jsonify

bp = Blueprint("review", __name__, url_prefix="/api")


@bp.route("/review/approve", methods=["POST"])
def approve_tracks():
    """
    Approve specific tracks.
    POST /api/review/approve
    body: { "track_paths": ["/path1", "/path2"] }
    """
    try:
        from app import get_track_store

        data = request.get_json() or {}
        track_paths = data.get("track_paths", [])
        track_store = get_track_store()

        approved = 0
        for file_path in track_paths:
            if file_path in track_store:
                track_store[file_path].review_status = "approved"
                approved += 1

        return jsonify({"approved": approved}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/review/skip", methods=["POST"])
def skip_tracks():
    """
    Skip specific tracks.
    POST /api/review/skip
    body: { "track_paths": ["/path1", "/path2"] }
    """
    try:
        from app import get_track_store

        data = request.get_json() or {}
        track_paths = data.get("track_paths", [])
        track_store = get_track_store()

        skipped = 0
        for file_path in track_paths:
            if file_path in track_store:
                track_store[file_path].review_status = "skipped"
                skipped += 1

        return jsonify({"skipped": skipped}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/review/bulk-approve", methods=["POST"])
def bulk_approve():
    """
    Approve all tracks meeting confidence threshold.
    POST /api/review/bulk-approve
    body: { "min_confidence": 80 }
    """
    try:
        from app import get_track_store

        data = request.get_json() or {}
        min_confidence = data.get("min_confidence", 0)
        track_store = get_track_store()

        approved = 0
        for track in track_store.values():
            if (
                track.review_status == "pending" and
                track.confidence is not None and
                track.confidence >= min_confidence
            ):
                track.review_status = "approved"
                approved += 1

        return jsonify({"approved": approved}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/review/write", methods=["POST"])
def write_tags():
    """
    Write approved tracks' tags to ID3.
    POST /api/review/write
    body: { "track_paths": [...] }  # or empty = all approved tracks
    """
    try:
        from app.services.tag_writer import write_tags as write_service
        from app import get_track_store

        data = request.get_json() or {}
        track_paths = data.get("track_paths", [])
        track_store = get_track_store()

        # If empty, write all approved tracks
        if not track_paths:
            track_paths = [
                fp for fp, t in track_store.items()
                if t.review_status == "approved"
            ]

        written = 0
        errors = []

        for file_path in track_paths:
            if file_path not in track_store:
                errors.append({
                    "path": file_path,
                    "error": "Track not found in store"
                })
                continue

            try:
                track = track_store[file_path]
                write_service(track)
                track.tags_written = True
                written += 1
            except Exception as e:
                track.error = str(e)
                errors.append({
                    "path": file_path,
                    "error": str(e)
                })

        return jsonify({
            "written": written,
            "errors": errors
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
