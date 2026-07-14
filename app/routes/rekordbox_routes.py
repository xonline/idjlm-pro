import io
import logging
import os
import shutil
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file
from app import get_track_store

logger = logging.getLogger(__name__)

bp = Blueprint("rekordbox", __name__, url_prefix="/api")


@bp.route("/rekordbox/matches", methods=["GET"])
def rekordbox_matches():
    """GET /api/rekordbox/matches — return rekordbox data matched to IDJLM tracks."""
    try:
        from app.services.rekordbox_reader import match_rekordbox_tracks
        store = get_track_store()
        matches = match_rekordbox_tracks(store)
        return jsonify({
            "total_rekordbox_tracks": len(matches),
            "matches": matches
        }), 200
    except Exception as e:
        logger.exception("Error in /api/rekordbox/matches")
        return jsonify({"error": str(e)}), 500


@bp.route("/rekordbox/status", methods=["GET"])
def rekordbox_status():
    """GET /api/rekordbox/status — check if rekordbox DB is accessible."""
    try:
        from app.services.rekordbox_reader import _find_rekordbox_db
        db_path = _find_rekordbox_db()
        return jsonify({
            "found": bool(db_path),
            "path": db_path,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/rekordbox/write-check", methods=["POST"])
def rekordbox_write_check():
    """
    POST /api/rekordbox/write-check
    Check whether Rekordbox database is safe to write to.

    Body: {"db_path": "/path/to/master.db"} (optional — uses auto-detect if omitted)
    """
    try:
        from app.services.rekordbox_writer import check_write_safety
        from app.services.rekordbox_reader import _find_rekordbox_db

        body = request.get_json(silent=True) or {}
        db_path = body.get("db_path") or _find_rekordbox_db()

        if not db_path:
            return jsonify({
                "safe": False,
                "reason": "Rekordbox database not found. Ensure Rekordbox is installed.",
                "path": None,
            }), 200

        safety = check_write_safety(db_path)
        safety["path"] = db_path
        return jsonify(safety), 200

    except Exception as e:
        logger.exception("Error in /api/rekordbox/write-check")
        return jsonify({"error": str(e)}), 500


@bp.route("/rekordbox/write-back", methods=["POST"])
def rekordbox_write_back():
    """
    POST /api/rekordbox/write-back
    Write IDJLM analysis results back to Rekordbox's master.db.

    Body:
    {
        "db_path": "/path/to/master.db",          # optional
        "backup": true,                            # optional — create backup first
        "track_ids": ["path1", "path2", ...],      # optional — limit to specific tracks
        "field_mappings": {                        # optional — override default mappings
            "final_genre": "strGenre",
            "final_key": "strKey",
            "final_subgenre": "strComment",
            "final_bpm": "dBPM",
            "final_year": "nYear"
        }
    }

    SAFETY: Returns error if Rekordbox is running. Direct DB writes can corrupt
    the library — always use the XML export path unless Rekordbox is closed.
    """
    try:
        from app.services.rekordbox_writer import check_write_safety, write_back_tracks
        from app.services.rekordbox_reader import _find_rekordbox_db

        body = request.get_json(silent=True) or {}
        db_path = body.get("db_path") or _find_rekordbox_db()

        if not db_path:
            return jsonify({
                "written": 0, "skipped": 0, "errors": ["Rekordbox database not found"]
            }), 400

        safety = check_write_safety(db_path)
        if not safety["safe"]:
            return jsonify({
                "written": 0, "skipped": 0, "errors": [safety["reason"]]
            }), 400

        if body.get("backup", False):
            backup_dir = os.path.join(os.path.dirname(db_path), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"master.db.backup-{stamp}")
            try:
                shutil.copy2(db_path, backup_path)
                logger.info("Created Rekordbox DB backup: %s", backup_path)
            except OSError as e:
                return jsonify({
                    "written": 0, "skipped": 0, "errors": [f"Backup failed: {e}"]
                }), 500

        store = get_track_store()
        track_ids = body.get("track_ids")
        field_mappings = body.get("field_mappings")

        matched_tracks = []
        if track_ids:
            for tid in track_ids:
                t = store.get(tid)
                if t:
                    matched_tracks.append({
                        "idjlm_path": t.file_path,
                        "final_genre": t.final_genre,
                        "final_subgenre": t.final_subgenre,
                        "final_key": t.final_key,
                        "final_bpm": t.final_bpm,
                        "final_year": t.final_year,
                        "final_energy": t.analyzed_energy,
                    })
        else:
            for fp in store.keys():
                t = store.get(fp)
                if t:
                    matched_tracks.append({
                        "idjlm_path": t.file_path,
                        "final_genre": t.final_genre,
                        "final_subgenre": t.final_subgenre,
                        "final_key": t.final_key,
                        "final_bpm": t.final_bpm,
                        "final_year": t.final_year,
                        "final_energy": t.analyzed_energy,
                    })

        result = write_back_tracks(db_path, matched_tracks, field_mappings)
        return jsonify(result), 200

    except Exception as e:
        logger.exception("Error in /api/rekordbox/write-back")
        return jsonify({"error": str(e)}), 500


@bp.route("/rekordbox/write-xml", methods=["GET"])
def rekordbox_write_xml():
    """
    GET /api/rekordbox/write-xml
    Export tracks as Rekordbox-compatible XML with cue points for import into Rekordbox.

    This is the safe write-back path: Rekordbox can import this XML file directly
    without risk to the master.db integrity. Includes POSITION_MARK elements for
    each track's suggested cue points when available.
    """
    try:
        import xml.etree.ElementTree as ET
        from urllib.parse import quote

        store = get_track_store()
        tracks = list(store.values())

        status = request.args.get("status", "approved").strip() or None
        if status:
            tracks = [t for t in tracks if t.review_status == status]

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
            track_elem.set('Comments', track.final_comment or track.final_subgenre or '')
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
        playlist_node.set('Name', 'IDJLM Pro Write-Back')
        playlist_node.set('Type', '1')
        playlist_node.set('KeyType', '0')
        playlist_node.set('Entries', str(len(tracks)))
        for i in range(len(tracks)):
            track_ref = ET.SubElement(playlist_node, 'TRACK')
            track_ref.set('Key', str(i + 1))

        xml_content = ET.tostring(root, encoding='utf-8').decode('utf-8')
        xml_with_declaration = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_content}'
        filename = request.args.get("filename", "rekordbox-writeback.xml").strip()

        return send_file(
            io.BytesIO(xml_with_declaration.encode('utf-8')),
            mimetype="application/xml",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.exception("Error in /api/rekordbox/write-xml")
        return jsonify({"error": str(e)}), 500
