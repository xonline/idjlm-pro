import io
from flask import Blueprint, request, send_file, jsonify

bp = Blueprint("export", __name__, url_prefix="/api")


@bp.route("/export/m3u", methods=["GET"])
def export_m3u():
    """
    Export filtered tracks as M3U playlist.
    GET /api/export/m3u?genre=...&subgenre=...&status=approved
    Optional query params: genre, subgenre, status (default: "approved")
    """
    try:
        from app import get_track_store

        # Get filter parameters
        genre = request.args.get("genre", "").strip() or None
        subgenre = request.args.get("subgenre", "").strip() or None
        status = request.args.get("status", "approved").strip() or None

        track_store = get_track_store()
        tracks = list(track_store.values())

        # Apply filters
        if genre:
            tracks = [t for t in tracks if t.final_genre == genre]

        if subgenre:
            tracks = [t for t in tracks if t.final_subgenre == subgenre]

        if status:
            tracks = [t for t in tracks if t.review_status == status]

        # Generate M3U content
        m3u_lines = ["#EXTM3U"]

        for track in tracks:
            # Format: #EXTINF:duration,artist - title
            artist = track.display_artist
            title = track.display_title
            extinf_line = f"#EXTINF:0,{artist} - {title}"
            m3u_lines.append(extinf_line)
            m3u_lines.append(track.file_path)

        m3u_content = "\n".join(m3u_lines)

        # Return as file download
        return send_file(
            io.BytesIO(m3u_content.encode('utf-8')),
            mimetype="audio/x-mpegurl",
            as_attachment=True,
            download_name="dj-playlist.m3u"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
