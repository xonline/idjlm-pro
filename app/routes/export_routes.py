import io
import csv
import json
import zipfile
import xml.etree.ElementTree as ET
from urllib.parse import quote
from flask import Blueprint, request, send_file, jsonify

bp = Blueprint("export", __name__, url_prefix="/api")


def _generate_m3u_content(tracks: list, relative: bool = False, base_path: str = "") -> str:
    """Helper function to generate M3U content from a list of tracks.

    Args:
        tracks: List of Track objects.
        relative: If True, make paths relative to base_path.
        base_path: Common prefix to strip for relative paths.
    """
    import os
    m3u_lines = ["#EXTM3U"]
    for track in tracks:
        artist = track.display_artist
        title = track.display_title
        extinf_line = f"#EXTINF:0,{artist} - {title}"
        m3u_lines.append(extinf_line)
        if relative and base_path:
            path = track.file_path
            if path.startswith(base_path):
                m3u_lines.append(os.path.relpath(path, base_path))
            else:
                m3u_lines.append(path)
        else:
            m3u_lines.append(track.file_path)
    return "\n".join(m3u_lines)


@bp.route("/export/m3u", methods=["GET"])
def export_m3u():
    """
    Export filtered tracks as M3U playlist.
    GET /api/export/m3u?genre=...&subgenre=...&status=approved&bpm_min=90&bpm_max=130&energy_min=5&energy_max=9&key=8B&filename=my-playlist.m3u&split=true
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
    - split: "true" to create ZIP with multiple M3U files (optional)
    - chunk_size: tracks per file when split=true, default 500 (options: 100, 500, 1000)
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
        split = request.args.get("split", "false").strip().lower() == "true"
        relative = request.args.get("relative", "false").strip().lower() == "true"
        base_path = request.args.get("base_path", "").strip()
        try:
            chunk_size = int(request.args.get("chunk_size", "500"))
            chunk_size = max(100, min(1000, chunk_size))
        except ValueError:
            chunk_size = 500

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

        # Handle split: if split=true, return ZIP with multiple M3U files
        if split and len(tracks) > chunk_size:
            chunks = [tracks[i:i + chunk_size] for i in range(0, len(tracks), chunk_size)]

            # Create ZIP file in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for idx, chunk in enumerate(chunks, start=1):
                    m3u_content = _generate_m3u_content(chunk, relative=relative, base_path=base_path)
                    # Use genre in filename if available, else generic name
                    base_name = genre if genre else "playlist"
                    m3u_filename = f"{base_name}-{idx}.m3u"
                    zf.writestr(m3u_filename, m3u_content)

            zip_buffer.seek(0)
            zip_filename = filename.replace('.m3u', '.zip')

            return send_file(
                zip_buffer,
                mimetype="application/zip",
                as_attachment=True,
                download_name=zip_filename
            )

        # Default: single M3U file
        m3u_content = _generate_m3u_content(tracks, relative=relative, base_path=base_path)

        return send_file(
            io.BytesIO(m3u_content.encode('utf-8')),
            mimetype="audio/x-mpegurl",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _apply_filters(tracks: list, query_params: dict) -> list:
    """
    Apply common filters to tracks list.
    Filters: genre, subgenre, status, bpm_min/max, energy_min/max, key
    """
    genre = query_params.get("genre", "").strip() or None
    subgenre = query_params.get("subgenre", "").strip() or None
    status = query_params.get("status", "approved").strip() or None
    bpm_min = query_params.get("bpm_min", "")
    bpm_max = query_params.get("bpm_max", "")
    energy_min = query_params.get("energy_min", "")
    energy_max = query_params.get("energy_max", "")
    key = query_params.get("key", "").strip() or None

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

    return tracks


@bp.route("/export/csv", methods=["GET"])
def export_csv():
    """
    Export filtered tracks as CSV.
    GET /api/export/csv?genre=...&subgenre=...&status=approved&bpm_min=90&bpm_max=130&energy_min=5&energy_max=9&key=8B&filename=my-library.csv
    CSV columns: title, artist, album, year, genre, subgenre, bpm, key, energy, confidence, file_path
    """
    try:
        from app import get_track_store

        track_store = get_track_store()
        tracks = list(track_store.values())

        # Apply filters
        tracks = _apply_filters(tracks, request.args)

        # Build CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'title', 'artist', 'album', 'year', 'genre', 'subgenre',
            'bpm', 'key', 'energy', 'confidence', 'file_path'
        ])

        for track in tracks:
            writer.writerow([
                track.display_title,
                track.display_artist,
                track.existing_album or '',
                track.existing_year or '',
                track.final_genre or '',
                track.final_subgenre or '',
                track.analyzed_bpm or '',
                track.final_key or '',
                track.analyzed_energy or '',
                track.confidence or '',
                track.file_path,
            ])

        csv_content = output.getvalue()
        filename = request.args.get("filename", "idlm-library.csv").strip()

        return send_file(
            io.BytesIO(csv_content.encode('utf-8')),
            mimetype="text/csv",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/export/json", methods=["GET"])
def export_json():
    """
    Export filtered tracks as JSON.
    GET /api/export/json?genre=...&subgenre=...&status=approved&bpm_min=90&bpm_max=130&energy_min=5&energy_max=9&key=8B&filename=my-library.json
    Returns array of track objects.
    """
    try:
        from app import get_track_store

        track_store = get_track_store()
        tracks = list(track_store.values())

        # Apply filters
        tracks = _apply_filters(tracks, request.args)

        # Convert tracks to dict
        tracks_data = [
            {
                'title': track.display_title,
                'artist': track.display_artist,
                'album': track.existing_album,
                'year': track.existing_year,
                'genre': track.final_genre,
                'subgenre': track.final_subgenre,
                'bpm': track.analyzed_bpm,
                'key': track.final_key,
                'energy': track.analyzed_energy,
                'confidence': track.confidence,
                'file_path': track.file_path,
            }
            for track in tracks
        ]

        json_content = json.dumps(tracks_data, indent=2)
        filename = request.args.get("filename", "idlm-library.json").strip()

        return send_file(
            io.BytesIO(json_content.encode('utf-8')),
            mimetype="application/json",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/export/rekordbox", methods=["GET"])
def export_rekordbox():
    """
    Export filtered tracks as Rekordbox XML.
    GET /api/export/rekordbox?genre=...&subgenre=...&status=approved&bpm_min=90&bpm_max=130&energy_min=5&energy_max=9&key=8B&filename=rekordbox-export.xml
    Generates valid Rekordbox 6.0 XML format.
    """
    try:
        from app import get_track_store

        track_store = get_track_store()
        tracks = list(track_store.values())

        # Apply filters
        tracks = _apply_filters(tracks, request.args)

        # Build Rekordbox XML
        root = ET.Element('DJ_PLAYLISTS')
        root.set('Version', '1.0.0')

        product = ET.SubElement(root, 'PRODUCT')
        product.set('Name', 'rekordbox')
        product.set('Version', '6.0.0')
        product.set('Company', 'AlphaTheta')

        collection = ET.SubElement(root, 'COLLECTION')
        collection.set('Entries', str(len(tracks)))

        for i, track in enumerate(tracks):
            track_elem = ET.SubElement(collection, 'TRACK')
            track_elem.set('TrackID', str(i + 1))
            track_elem.set('Name', track.display_title or 'Unknown')
            track_elem.set('Artist', track.display_artist or 'Unknown')
            track_elem.set('Album', track.existing_album or '')
            track_elem.set('Genre', track.final_genre or '')
            track_elem.set('Kind', 'MP3 File')
            track_elem.set('TotalTime', '0')
            track_elem.set('AverageBpm', str(track.analyzed_bpm or 0))
            track_elem.set('Year', track.existing_year or '')
            track_elem.set('Comments', track.final_subgenre or '')
            track_elem.set('Tonality', track.final_key or '')
            # URL-encode file path for Location attribute
            location = f"file://localhost{quote(track.file_path, safe='/:')}"
            track_elem.set('Location', location)

        # Build playlists section
        playlists = ET.SubElement(root, 'PLAYLISTS')
        root_node = ET.SubElement(playlists, 'NODE')
        root_node.set('Type', '0')
        root_node.set('Name', 'ROOT')
        root_node.set('Count', '1')

        playlist_node = ET.SubElement(root_node, 'NODE')
        playlist_node.set('Name', 'IDJLM Pro Export')
        playlist_node.set('Type', '1')
        playlist_node.set('KeyType', '0')
        playlist_node.set('Entries', str(len(tracks)))

        for i in range(len(tracks)):
            track_ref = ET.SubElement(playlist_node, 'TRACK')
            track_ref.set('Key', str(i + 1))

        # Convert to string
        xml_content = ET.tostring(root, encoding='utf-8').decode('utf-8')
        xml_with_declaration = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_content}'

        filename = request.args.get("filename", "rekordbox-export.xml").strip()

        return send_file(
            io.BytesIO(xml_with_declaration.encode('utf-8')),
            mimetype="application/xml",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/export/rekordbox-cues", methods=["GET"])
def export_rekordbox_cues():
    """
    Export filtered tracks as Rekordbox XML with embedded cue points.
    GET /api/export/rekordbox-cues?genre=...&status=approved&filename=rekordbox-cues.xml
    Extends the base Rekordbox XML format with POSITION_MARK elements for each
    track's suggested cues.
    """
    try:
        from app import get_track_store

        track_store = get_track_store()
        tracks = list(track_store.values())
        tracks = _apply_filters(tracks, request.args)

        root = ET.Element('DJ_PLAYLISTS')
        root.set('Version', '1.0.0')

        product = ET.SubElement(root, 'PRODUCT')
        product.set('Name', 'rekordbox')
        product.set('Version', '6.0.0')
        product.set('Company', 'AlphaTheta')

        collection = ET.SubElement(root, 'COLLECTION')
        collection.set('Entries', str(len(tracks)))

        for i, track in enumerate(tracks):
            track_elem = ET.SubElement(collection, 'TRACK')
            track_elem.set('TrackID', str(i + 1))
            track_elem.set('Name', track.display_title or 'Unknown')
            track_elem.set('Artist', track.display_artist or 'Unknown')
            track_elem.set('Album', track.existing_album or '')
            track_elem.set('Genre', track.final_genre or '')
            track_elem.set('Kind', 'MP3 File')
            track_elem.set('TotalTime', str(int(track.duration or 0)))
            track_elem.set('AverageBpm', str(track.analyzed_bpm or 0))
            track_elem.set('Year', track.existing_year or '')
            track_elem.set('Comments', track.final_subgenre or '')
            track_elem.set('Tonality', track.final_key or '')
            location = f"file://localhost{quote(track.file_path, safe='/:')}"
            track_elem.set('Location', location)

            cues = getattr(track, "suggested_cues", None) or []
            for c_idx, cue in enumerate(cues):
                pm = ET.SubElement(track_elem, 'POSITION_MARK')
                pm.set('Name', cue.get("label", f"Cue {c_idx + 1}"))
                pm.set('Type', '0')
                pm.set('Start', str(int(cue.get("position_sec", 0) * 1000)))
                pm.set('Num', str(c_idx + 1))

        playlists = ET.SubElement(root, 'PLAYLISTS')
        root_node = ET.SubElement(playlists, 'NODE')
        root_node.set('Type', '0')
        root_node.set('Name', 'ROOT')
        root_node.set('Count', '1')

        playlist_node = ET.SubElement(root_node, 'NODE')
        playlist_node.set('Name', 'IDJLM Pro Export (with Cues)')
        playlist_node.set('Type', '1')
        playlist_node.set('KeyType', '0')
        playlist_node.set('Entries', str(len(tracks)))

        for i in range(len(tracks)):
            track_ref = ET.SubElement(playlist_node, 'TRACK')
            track_ref.set('Key', str(i + 1))

        xml_content = ET.tostring(root, encoding='utf-8').decode('utf-8')
        xml_with_declaration = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_content}'

        filename = request.args.get("filename", "rekordbox-cues-export.xml").strip()

        return send_file(
            io.BytesIO(xml_with_declaration.encode('utf-8')),
            mimetype="application/xml",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/export/serato-crate", methods=["GET"])
def export_serato_crate():
    """
    Export filtered tracks as Serato .crate binary file.
    GET /api/export/serato-crate?genre=...&status=approved&beta=true&filename=my-crate.crate

    Beta feature: requires explicit ?beta=true query parameter to activate.
    Produces tag-based binary crate files compatible with Serato DJ / Scratch Live.
    """
    try:
        beta = request.args.get("beta", "false").strip().lower() == "true"
        if not beta:
            return jsonify({
                "error": "Serato crate export is a beta feature. Pass ?beta=true to enable.",
                "detail": "This export format is still under validation against Serato 4. "
                          "Use with caution on production libraries.",
            }), 400

        from app import get_track_store
        from app.services.serato_writer import write_crate

        track_store = get_track_store()
        tracks = list(track_store.values())
        tracks = _apply_filters(tracks, request.args)

        base_path = request.args.get("base_path", "").strip()
        crate_bytes = write_crate(tracks, base_path=base_path)

        filename = request.args.get("filename", "idlm-export.crate").strip()

        return send_file(
            io.BytesIO(crate_bytes),
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/export/traktor-nml", methods=["GET"])
def export_traktor_nml():
    """
    Export filtered tracks as Traktor NML playlist.
    GET /api/export/traktor-nml?genre=...&status=approved&filename=traktor-export.nml

    Generates Native Instruments Traktor NML format with cue points, BPM, and key.
    """
    try:
        from app import get_track_store
        from app.services.traktor_writer import write_nml

        track_store = get_track_store()
        tracks = list(track_store.values())
        tracks = _apply_filters(tracks, request.args)

        nml_content = write_nml(tracks)
        filename = request.args.get("filename", "idlm-export.nml").strip()

        return send_file(
            io.BytesIO(nml_content.encode('utf-8')),
            mimetype="application/xml",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
