from flask import Blueprint, request, Response
from urllib.parse import quote
import csv
import io

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


@bp.route("/csv", methods=["GET"])
def export_csv():
    """Export library as CSV with all track metadata."""
    from app import get_track_store

    track_store = get_track_store()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Title", "Artist", "Album", "Year", "BPM", "Key", "Energy",
        "Current Genre", "Proposed Genre", "Proposed Sub-genre",
        "Confidence", "Status", "File Path"
    ])

    for fp, t in track_store.items():
        writer.writerow([
            t.existing_title or "",
            t.existing_artist or "",
            t.existing_album or "",
            t.existing_year or "",
            t.analyzed_bpm or "",
            t.analyzed_key or "",
            t.analyzed_energy or "",
            t.final_genre or t.existing_genre or "",
            t.final_genre or t.proposed_genre or "",
            t.final_subgenre or t.proposed_subgenre or "",
            t.classification_confidence or "",
            "approved" if t.approved else ("skipped" if t.skipped else "pending"),
            fp
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=xdj-library.csv"}
    )
