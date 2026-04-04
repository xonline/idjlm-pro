from flask import Blueprint, request, jsonify

bp = Blueprint("track", __name__, url_prefix="/api/tracks")


@bp.route("/", methods=["GET"])
def list_tracks():
    """Get all tracks with optional sorting/filtering."""
    from app import get_track_store

    sort_by = request.args.get("sort_by", "id")
    genre_filter = request.args.get("genre")
    search = request.args.get("search", "").lower()

    track_store = get_track_store()
    tracks = list(track_store.values())

    # Filter by genre
    if genre_filter:
        tracks = [t for t in tracks if t.final_genre == genre_filter]

    # Search
    if search:
        tracks = [t for t in tracks if search in (t.existing_title or "").lower()
                  or search in (t.existing_artist or "").lower()]

    # Sort
    if sort_by == "bpm":
        tracks.sort(key=lambda t: t.final_bpm or 0)
    elif sort_by == "key":
        tracks.sort(key=lambda t: t.final_key or "")
    elif sort_by == "genre":
        tracks.sort(key=lambda t: t.final_genre or "")

    return jsonify({"tracks": [t.to_dict() for t in tracks]})


@bp.route("/<track_id>", methods=["PUT"])
def update_track(track_id):
    """Update track overrides."""
    from app import get_track_store

    track_store = get_track_store()
    track = track_store.get(track_id)

    if not track:
        return jsonify({"success": False}), 404

    data = request.json or {}
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

    return jsonify({"success": True, "track": track.to_dict()})
