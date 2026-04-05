import os
import subprocess
import sys
import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("import", __name__, url_prefix="/api")


@bp.route("/pick-folder", methods=["GET"])
def pick_folder():
    """Open a native folder picker dialog and return the chosen path."""
    try:
        if sys.platform == "darwin":
            result = subprocess.run(
                ["osascript", "-e",
                 'POSIX path of (choose folder with prompt "Select your music folder:")'],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                # User cancelled
                return jsonify({"cancelled": True}), 200
            path = result.stdout.strip()
            return jsonify({"path": path}), 200
        else:
            return jsonify({"error": "Folder picker only supported on macOS"}), 400
    except subprocess.TimeoutExpired:
        return jsonify({"cancelled": True}), 200
    except Exception as e:
        logger.exception("Error in /api/pick-folder")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/import", methods=["POST"])
def import_tracks():
    """
    Import MP3 tracks from a folder.
    POST /api/import
    body: { "folder_path": "/path/to/folder" }
    """
    try:
        data = request.get_json(silent=True) or {}
        folder_path = data.get("folder_path", "").strip()

        if not folder_path:
            return jsonify({"error": "folder_path is required"}), 400

        if not os.path.exists(folder_path):
            return jsonify({"error": f"Folder does not exist: {folder_path}"}), 400

        if not os.path.isdir(folder_path):
            return jsonify({"error": f"Path is not a directory: {folder_path}"}), 400

        # Verify folder is readable
        if not os.access(folder_path, os.R_OK):
            return jsonify({"error": f"Folder is not readable: {folder_path}"}), 400

        # Import scanner service
        from app.services.scanner import scan_folder
        from app import get_track_store, set_current_folder_path

        # Clear previous session and scan
        track_store = get_track_store()
        track_store.clear()
        set_current_folder_path(folder_path)
        tracks = scan_folder(folder_path)

        # Store tracks in memory by file_path
        for track in tracks:
            track_store[track.file_path] = track

        return jsonify({
            "count": len(tracks),
            "tracks": [t.to_dict() for t in tracks]
        }), 200

    except Exception as e:
        logger.exception("Error in /api/import")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/analyze", methods=["POST"])
def analyze_tracks():
    """
    Analyze tracks for BPM, key, energy (async).
    POST /api/analyze
    body: { "track_paths": ["/path1", "/path2"] }  # or empty list = all tracks
    Returns: { "op_id": "...", "total": N }  (202 Accepted)
    Stream progress via EventSource('/api/progress/<op_id>')
    """
    try:
        import uuid
        import threading
        import queue as _queue
        from app.services.analyzer import analyze_track
        from app import get_track_store, get_progress_queues

        data = request.get_json(silent=True) or {}
        track_paths = data.get("track_paths", [])
        track_store = get_track_store()

        # If empty, analyze all tracks
        if not track_paths:
            track_paths = list(track_store.keys())

        op_id = str(uuid.uuid4())[:8]
        q = _queue.Queue()
        get_progress_queues()[op_id] = q

        def run():
            total = len(track_paths)
            analyzed = 0
            errors = []
            for i, file_path in enumerate(track_paths):
                if file_path not in track_store:
                    continue
                try:
                    track = track_store[file_path]
                    analyze_track(track)
                    analyzed += 1
                    q.put({
                        'current': i + 1,
                        'total': total,
                        'track': track.display_title,
                        'analyzed': analyzed
                    })
                except Exception as e:
                    errors.append({'path': file_path, 'error': str(e)})
                    q.put({
                        'current': i + 1,
                        'total': total,
                        'error': str(e)
                    })
            q.put({'done': True, 'analyzed': analyzed, 'errors': errors})

        threading.Thread(target=run, daemon=True).start()
        return jsonify({'op_id': op_id, 'total': len(track_paths)}), 202

    except Exception as e:
        logger.exception("Error in /api/analyze")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/classify", methods=["POST"])
def classify_tracks():
    """
    Classify tracks by genre and enrich metadata (async).
    POST /api/classify
    body: { "track_paths": ["/path1", "/path2"], "force": false }  # or empty = all analyzed tracks; force=true reclassifies already-classified
    Returns: { "op_id": "...", "total": N }  (202 Accepted)
    Stream progress via EventSource('/api/progress/<op_id>')
    """
    try:
        import uuid
        import threading
        import queue as _queue
        from app.services.classifier import classify_tracks as classify_service
        from app.services.enricher import enrich_tracks as enrich_service
        from app import get_track_store, get_taxonomy, get_progress_queues

        data = request.get_json(silent=True) or {}
        track_paths = data.get("track_paths", [])
        force = data.get("force", False)
        track_store = get_track_store()

        # If empty, classify all analyzed tracks
        if not track_paths:
            track_paths = [
                fp for fp, t in track_store.items() if t.analysis_done
            ]

        op_id = str(uuid.uuid4())[:8]
        q = _queue.Queue()
        get_progress_queues()[op_id] = q

        def run():
            total = len(track_paths)
            classified = 0
            errors = []
            for i, file_path in enumerate(track_paths):
                if file_path not in track_store:
                    continue
                try:
                    track = track_store[file_path]
                    # Classify (pass force parameter)
                    classify_service([track], get_taxonomy(), force=force)
                    # Enrich
                    enrich_service([track])
                    classified += 1
                    q.put({
                        'current': i + 1,
                        'total': total,
                        'track': track.display_title,
                        'classified': classified
                    })
                except Exception as e:
                    errors.append({'path': file_path, 'error': str(e)})
                    q.put({
                        'current': i + 1,
                        'total': total,
                        'error': str(e)
                    })
            q.put({'done': True, 'classified': classified, 'errors': errors})
            try:
                from app.services.session_service import save_session
                from app import get_current_folder_path
                save_session(track_store, get_current_folder_path())
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()
        return jsonify({'op_id': op_id, 'total': len(track_paths)}), 202

    except Exception as e:
        logger.exception("Error in /api/classify")
        return jsonify({"error": "Operation failed. Check server logs."}), 500
