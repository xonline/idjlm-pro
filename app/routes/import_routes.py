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

        # Normalize genres from existing tags (e.g. "Salsa Romántica" → "Salsa")
        from app import get_taxonomy
        from app.services.genre_normalizer import normalize_track_genres
        normalize_track_genres(tracks, get_taxonomy())

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
        
        logger.info(f"Analyze request: {len(track_paths)} tracks, store has {len(track_store)} tracks")

        op_id = str(uuid.uuid4())[:8]
        q = _queue.Queue()
        get_progress_queues()[op_id] = q

        def run():
            total = len(track_paths)
            analyzed = 0
            errors = []
            logger.info(f"Starting analysis thread for {total} tracks")
            for i, file_path in enumerate(track_paths):
                if file_path not in track_store:
                    logger.warning(f"Track {file_path} not found in store, skipping")
                    continue
                try:
                    track = track_store[file_path]
                    logger.info(f"Analyzing track {i+1}/{total}: {track.display_title}")
                    analyze_track(track)
                    analyzed += 1
                    q.put({
                        'current': i + 1,
                        'total': total,
                        'track': track.display_title,
                        'analyzed': analyzed
                    })
                    logger.info(f"Successfully analyzed {track.display_title}, analysis_done={track.analysis_done}")
                    if track.error:
                        logger.warning(f"Track {track.display_title} has error after analysis: {track.error}")
                    if not track.analysis_done:
                        logger.warning(f"Track {track.display_title} analysis_done is still False!")
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error analyzing {file_path}: {error_msg}")
                    errors.append({'path': file_path, 'error': error_msg})
                    q.put({
                        'current': i + 1,
                        'total': total,
                        'error': error_msg
                    })
            logger.info(f"Analysis complete: {analyzed}/{total} succeeded, {len(errors)} errors")
            q.put({'done': True, 'analyzed': analyzed, 'errors': errors, 'refetch': True})

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
    body: {
        "track_paths": ["/path1", "/path2"],
        "force": false,
        "model_override": "claude" | "gemini" | "openrouter" | "ollama" | null,
        "reclassify": false
    }
    - model_override: use ONLY this model (no fallback chain)
    - reclassify: force reclassification even on already-classified tracks
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
        force = data.get("force", False) or data.get("reclassify", False)
        model_override = data.get("model_override")
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
            errors = []

            # Filter to tracks that actually exist in the store
            tracks_to_classify = []
            valid_paths = []
            for file_path in track_paths:
                if file_path in track_store:
                    track = track_store[file_path]
                    tracks_to_classify.append(track)
                    valid_paths.append(file_path)

            # When reclassifying, reset approved tracks to pending so they get fresh classification
            if force:
                for track in tracks_to_classify:
                    if track.review_status == 'approved':
                        track.review_status = 'pending'
                    # Clear previous classification so it gets re-done
                    track.proposed_genre = None
                    track.proposed_subgenre = None
                    track.confidence = None
                    track.reasoning = None
                    track.classification_done = False

            # Classify all tracks at once (service handles batching internally)
            try:
                classify_service(tracks_to_classify, get_taxonomy(), force=force, model_override=model_override)
            except Exception as e:
                errors.append({'error': str(e)})

            # Enrich all tracks
            try:
                enrich_service(tracks_to_classify)
            except Exception as e:
                errors.append({'error': str(e)})

            classified = sum(1 for t in tracks_to_classify if t.classification_done)

            # Report progress for each track
            for i, file_path in enumerate(track_paths):
                if file_path in track_store:
                    track = track_store[file_path]
                    q.put({
                        'current': i + 1,
                        'total': total,
                        'track': track.display_title,
                        'classified': classified
                    })

            q.put({'done': True, 'classified': classified, 'errors': errors, 'refetch': True})
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
