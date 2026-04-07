import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

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
            # For numeric fields (confidence, bpm, year), sort None as 0 (lowest value)
            # For string fields, sort None as empty string
            numeric_fields = {"confidence", "final_bpm", "final_year"}
            is_numeric = sort_attr in numeric_fields

            tracks.sort(
                key=lambda t: (getattr(t, sort_attr) or (0 if is_numeric else "")),
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
        logger.exception("Error in /api/tracks GET")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/tracks/search", methods=["GET"])
def search_tracks():
    """
    Search tracks across all text fields.
    GET /api/tracks/search?q=query
    Returns tracks matching the query (case-insensitive substring match),
    plus count and query string.
    """
    try:
        from app import get_track_store

        track_store = get_track_store()
        tracks = list(track_store.values())

        q = request.args.get("q", "").strip()

        if q:
            search_fields = [
                "display_title", "display_artist", "existing_genre",
                "proposed_genre", "final_genre", "existing_comment",
                "proposed_subgenre", "final_subgenre", "existing_album",
                "spotify_artist", "spotify_title", "analyzed_key",
                "final_key", "clave_pattern", "filename", "file_path",
                "reasoning"
            ]

            matched = []
            for track in tracks:
                for field in search_fields:
                    value = getattr(track, field, None)
                    if value and q.lower() in str(value).lower():
                        matched.append(track)
                        break
            tracks = matched

        return jsonify({
            "tracks": [t.to_dict() for t in tracks],
            "count": len(tracks),
            "query": q
        }), 200

    except Exception as e:
        logger.exception("Error in /api/tracks/search GET")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


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
        logger.exception(f"Error in /api/tracks/{file_path} PUT")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/tracks/by-path", methods=["PUT"])
def update_track_by_query():
    """
    Update track via query parameter.
    PUT /api/tracks/by-path?path=/absolute/path/to/file.mp3
    Avoids URL encoding issues with path parameters containing slashes.
    """
    file_path = request.args.get("path", "")
    if not file_path:
        return jsonify({"error": "Missing path parameter"}), 400
    return update_track(file_path)


@bp.route("/tracks/<path:file_path>", methods=["PUT"])
def update_track(file_path):
    """
    Update track overrides (genre, subgenre, bpm, key, year) or review_status.
    PUT /api/tracks/<file_path>
    body: { "override_genre": "...", "override_subgenre": "...", ... } or { "review_status": "approved|pending|skipped" }
    """
    try:
        from app import get_track_store

        track_store = get_track_store()

        if file_path not in track_store:
            return jsonify({"error": "Track not found"}), 404

        track = track_store[file_path]
        data = request.get_json(silent=True) or {}

        # Update review_status if provided
        if "review_status" in data:
            track.review_status = data["review_status"]
            return jsonify(track.to_dict()), 200

        # Update overrides if provided with validation
        if "override_genre" in data:
            track.override_genre = data["override_genre"]
        if "override_subgenre" in data:
            track.override_subgenre = data["override_subgenre"]

        # Validate BPM: numeric, 40-300 range (allow wider for Latin music)
        if "override_bpm" in data:
            bpm = data["override_bpm"]
            if bpm == "" or bpm is None:
                track.override_bpm = ""
            else:
                try:
                    bpm_num = float(bpm)
                    if not (40 <= bpm_num <= 300):
                        return jsonify({"error": "BPM must be between 40 and 300"}), 400
                    track.override_bpm = data["override_bpm"]
                except (ValueError, TypeError):
                    return jsonify({"error": "BPM must be numeric"}), 400

        # Validate Key: Camelot format or standard notation, up to 10 chars
        if "override_key" in data:
            key = data["override_key"]
            if key == "" or key is None:
                track.override_key = ""
            else:
                if not isinstance(key, str) or len(key) > 10:
                    return jsonify({"error": "Key must be a string up to 10 characters"}), 400
                track.override_key = key

        # Validate Year: 4-digit number between 1900-2030
        if "override_year" in data:
            year = data["override_year"]
            if year == "" or year is None:
                track.override_year = ""
            else:
                try:
                    year_num = int(year)
                    if not (1900 <= year_num <= 2030):
                        return jsonify({"error": "Year must be between 1900 and 2030"}), 400
                    track.override_year = data["override_year"]
                except (ValueError, TypeError):
                    return jsonify({"error": "Year must be a 4-digit number"}), 400

        # Recompute review_status based on whether any overrides are set
        has_overrides = any([
            track.override_genre,
            track.override_subgenre,
            track.override_bpm,
            track.override_key,
            track.override_year
        ])
        if has_overrides:
            track.review_status = "edited"
        elif track.review_status == "edited":
            # Revert to pending if no overrides are set and status was edited
            track.review_status = "pending"

        return jsonify(track.to_dict()), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
