from flask import Blueprint, request, Response
from urllib.parse import quote

bp = Blueprint("export", __name__, url_prefix="/api/export")


@bp.route("/m3u", methods=["GET"])
def export_m3u():
    """Export M3U playlist with optional filters."""
    from app import get_track_store

    genre = request.args.get("genre")
    subgenre = request.args.get("subgenre")
    status = request.args.get("status")  # 'approved', 'pending'

    track_store = get_track_store()
    tracks = list(track_store.values())

    # Filter
    if genre:
        tracks = [t for t in tracks if t.final_genre == genre]
    if subgenre:
        tracks = [t for t in tracks if t.final_subgenre == subgenre]
    if status == "approved":
        tracks = [t for t in tracks if t.approved]
    elif status == "pending":
        tracks = [t for t in tracks if not t.approved]

    # Build M3U
    lines = ["#EXTM3U"]
    for track in tracks:
        artist = track.existing_artist or "Unknown"
        title = track.existing_title or "Unknown"
        lines.append(f"#EXTINF:-1, {artist} - {title}")
        lines.append(f"file://{quote(track.file_path)}")

    content = "\n".join(lines)
    return Response(content, mimetype="audio/x-mpegurl", headers={
        "Content-Disposition": 'attachment; filename="playlist.m3u"'
    })
