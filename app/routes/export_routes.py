import io
from flask import Blueprint, request, send_file, jsonify

bp = Blueprint("export", __name__, url_prefix="/api")


@bp.route("/export/m3u", methods=["GET"])
def export_m3u():
    """
    Export filtered tracks as M3U playlist.
    GET /api/export/m3u?genre=...&subgenre=...&status=approved&bpm_min=90&bpm_max=130&energy_min=5&energy_max=9&key=8B&filename=my-playlist.m3u
    Optional query params:
    - genre: filter by genre
    - subgenre: filter by subgenre
    - status: review status (default: "approved")
    - bpm_min: minimum BPM (int)
    - bpm_max: maximum BPM (int)
    - energy_min: minimum energy 1-10 (int)
    - energy_max: maximum energy 1-10 (int)
    - key: Camelot key filter e.g. "8B" (str)
    - filename: custom download filename (default: "idlm-playlist.m3u")
    """
    try:
        from app import get_track_store

        # Get filter parameters
        genre = request.args.get("genre", "").strip() or None
        subgenre = request.args.get("subgenre", "").strip() or None
        status = request.args.get("status", "approved").strip() or None
        bpm_min = request.args.get("bpm_min", "").strip()
        bpm_max = request.args.get("bpm_max", "").strip()
        energy_min = request.args.get("energy_min", "").strip()
        energy_max = request.args.get("energy_max", "").strip()
        key = request.args.get("key", "").strip() or None
        filename = request.args.get("filename", "idlm-playlist.m3u").strip()

        # Parse numeric filters
        try:
            bpm_min = int(bpm_min) if bpm_min else None
        except ValueError:
            bpm_min = None

        try:
            bpm_max = int(bpm_max) if bpm_max else None
        except ValueError:
            bpm_max = None

        try:
            energy_min = int(energy_min) if energy_min else None
        except ValueError:
            energy_min = None

        try:
            energy_max = int(energy_max) if energy_max else None
        except ValueError:
            energy_max = None

        track_store = get_track_store()
        tracks = list(track_store.values())

        # Apply filters
        if genre:
            tracks = [t for t in tracks if t.final_genre == genre]

        if subgenre:
            tracks = [t for t in tracks if t.final_subgenre == subgenre]

        if status:
            tracks = [t for t in tracks if t.review_status == status]

        if bpm_min is not None:
            tracks = [t for t in tracks if t.analyzed_bpm and t.analyzed_bpm >= bpm_min]

        if bpm_max is not None:
            tracks = [t for t in tracks if t.analyzed_bpm and t.analyzed_bpm <= bpm_max]

        if energy_min is not None:
            tracks = [t for t in tracks if t.analyzed_energy and t.analyzed_energy >= energy_min]

        if energy_max is not None:
            tracks = [t for t in tracks if t.analyzed_energy and t.analyzed_energy <= energy_max]

        if key:
            tracks = [t for t in tracks if t.final_key == key]

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
            download_name=filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
