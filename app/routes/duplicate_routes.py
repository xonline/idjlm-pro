from flask import Blueprint, request, jsonify

bp = Blueprint("duplicates", __name__, url_prefix="/api")


@bp.route("/duplicates/scan", methods=["POST"])
def scan_duplicates():
    """
    Scan track store for duplicate tracks.
    POST /api/duplicates/scan
    Returns: {
        "groups": [...],
        "total_duplicates": int
    }
    """
    try:
        from app import get_track_store
        from app.services.duplicate_detector import find_duplicates

        track_store = get_track_store()
        result = find_duplicates(track_store)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/duplicates/remove", methods=["POST"])
def remove_duplicate():
    """
    Remove a duplicate track from the track store.
    POST /api/duplicates/remove
    Body: { "file_path": "..." }
    Returns: { "total_duplicates": int, "remaining_tracks": int }
    """
    try:
        from app import get_track_store

        body = request.get_json()
        if not body or "file_path" not in body:
            return jsonify({"error": "Missing file_path in request body"}), 400

        file_path = body.get("file_path")
        track_store = get_track_store()

        if file_path not in track_store:
            return jsonify({"error": f"Track not found: {file_path}"}), 404

        # Remove from store (does NOT delete the actual file)
        del track_store[file_path]

        # Rescan to get updated counts
        from app.services.duplicate_detector import find_duplicates
        result = find_duplicates(track_store)

        return jsonify({
            "total_duplicates": result["total_duplicates"],
            "remaining_tracks": len(track_store)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
