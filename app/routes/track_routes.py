from flask import Blueprint, request, jsonify

bp = Blueprint("track", __name__, url_prefix="/api")


@bp.route("/tracks", methods=["GET"])
def list_tracks():
    """
    List all tracks with optional filtering and sorting.
    GET /api/tracks?sort_by=field&sort_dir=asc&status=pending
    """
    try:
        from app import get_track_store

        track_store = get_track_store()
        tracks = list(track_store.values())

        # Filter by status
        status = request.args.get("status", "all").lower()
        if status != "all":
            tracks = [t for t in tracks if t.review_status == status]

        # Sort
        sort_by = request.args.get("sort_by", "filename").lower()
        sort_dir = request.args.get("sort_dir", "asc").lower()
        reverse = sort_dir == "desc"

        # Map sort_by to track attribute
        sort_key_map = {
            "filename": "filename",
            "file_path": "file_path",
            "title": "display_title",
            "artist": "display_artist",
            "genre": "final_genre",
            "subgenre": "final_subgenre",
            "bpm": "final_bpm",
            "key": "final_key",
            "confidence": "confidence",
            "status": "review_status",
            "year": "final_year"
        }

        sort_attr = sort_key_map.get(sort_by, "filename")

        try:
            tracks.sort(
                key=lambda t: getattr(t, sort_attr) or "",
                reverse=reverse
            )
        except Exception:
            # Fallback to filename if sort fails
            tracks.sort(key=lambda t: t.filename, reverse=reverse)

        return jsonify({
            "tracks": [t.to_dict() for t in tracks],
            "total": len(tracks)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/tracks/<path:file_path>", methods=["GET"])
def get_track(file_path):
    """
    Get a single track by file_path.
    GET /api/tracks/<file_path>
    """
    try:
        from app import get_track_store

        track_store = get_track_store()

        if file_path not in track_store:
            return jsonify({"error": "Track not found"}), 404

        track = track_store[file_path]
        return jsonify(track.to_dict()), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/tracks/<path:file_path>", methods=["PUT"])
def update_track(file_path):
    """
    Update track overrides (genre, subgenre, bpm, key, year).
    PUT /api/tracks/<file_path>
    body: { "override_genre": "...", "override_subgenre": "...", ... }
    """
    try:
        from app import get_track_store

        track_store = get_track_store()

        if file_path not in track_store:
            return jsonify({"error": "Track not found"}), 404

        track = track_store[file_path]
        data = request.get_json() or {}

        # Update overrides if provided
        if "override_genre" in data:
            track.override_genre = data["override_genre"]
        if "override_subgenre" in data:
            track.override_subgenre = data["override_subgenre"]
        if "override_bpm" in data:
            track.override_bpm = data["override_bpm"]
        if "override_key" in data:
            track.override_key = data["override_key"]
        if "override_year" in data:
            track.override_year = data["override_year"]

        # Mark as edited if any override is set
        if any([
            track.override_genre,
            track.override_subgenre,
            track.override_bpm,
            track.override_key,
            track.override_year
        ]):
            track.review_status = "edited"

        return jsonify(track.to_dict()), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
