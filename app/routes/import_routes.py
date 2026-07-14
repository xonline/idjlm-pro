import os
import threading
import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("import", __name__, url_prefix="/api")

# Rate limiting locks — prevent concurrent expensive operations
_analyze_lock = threading.Lock()
_classify_lock = threading.Lock()


@bp.route("/pick-folder", methods=["GET"])
def pick_folder():
    """Open a native folder picker dialog and return the chosen path.

    Cross-platform — uses tkinter on all platforms (macOS, Windows, Linux).
    Returns a structured payload so the frontend can distinguish a real
    cancellation from a headless-environment failure:
      * ``{path: "..."}``           — user selected a folder
      * ``{cancelled: true}``       — user dismissed the dialog
      * ``{unavailable: true, ...}`` — no GUI toolkit (headless server /
        tkinter not installed); the frontend falls back to manual text entry.

    Never returns a 500 on "no display" — that is an expected state, not an
    error. This route must not shell out to ``osascript`` (the old macOS-only
    implementation broke the import flow on Windows/Linux); the tkinter path
    below works everywhere Python runs.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as e:
        logger.info("/api/pick-folder: tkinter unavailable (%s) — headless", e)
        return jsonify({
            "unavailable": True,
            "message": "No GUI toolkit available on this host",
        }), 200

    root = None
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the root window
        root.lift()      # Bring dialog to front on macOS
        root.attributes('-topmost', True)
        path = filedialog.askdirectory(title="Select your music folder:")
    except Exception as e:  # tk.Tk() raises on a display-less host
        logger.info("/api/pick-folder: no display (%s) — headless", e)
        return jsonify({
            "unavailable": True,
            "message": "No display available for a native dialog",
        }), 200
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass

    if path:
        return jsonify({"path": path}), 200
    return jsonify({"cancelled": True}), 200


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
        from app.services.scanner import scan_folder_incremental
        from app import get_track_store, set_current_folder_path, get_track_store_lock

        track_store = get_track_store()
        set_current_folder_path(folder_path)

        # Incremental scan: reuse unchanged tracks, only process new/changed files
        tracks, stale_paths, unchanged_paths = scan_folder_incremental(
            folder_path, track_store
        )

        # Remove stale tracks (files deleted from disk since last import)
        # and upsert newly scanned tracks under _track_store_lock
        _ts_lock = get_track_store_lock()
        from app.services.analysis_cache import restore
        with _ts_lock:
            for stale_path in stale_paths:
                try:
                    del track_store[stale_path]
                except KeyError:
                    pass

            newly_scanned_count = 0
            restored_count = 0
            for track in tracks:
                # Reuse is reported by path, not by object identity: TrackStore
                # returns a fresh _PersistingTrack wrapper on every read, so an
                # `is` check never matches and writing the wrapper back raises
                # ("TrackStore values must be Track instances, got
                # _PersistingTrack") — which made every re-import 500.
                if track.file_path in unchanged_paths:
                    continue
                track_store[track.file_path] = track
                newly_scanned_count += 1
                if restore(track):
                    restored_count += 1
        if restored_count:
            logger.info("Restored analysis from cache for %d tracks", restored_count)

        # Tracks reused verbatim from the store — the whole point of the
        # incremental path. Surfaced in the response (and logged) so a re-import
        # is observably a no-op instead of just being fast.
        skipped_count = len(unchanged_paths)
        logger.info(
            "Import %s: skipped %d unchanged, scanned %d, removed %d stale",
            folder_path, skipped_count, newly_scanned_count, len(stale_paths),
        )

        # Normalize genres from existing tags (e.g. "Salsa Romántica" → "Salsa")
        from app import get_taxonomy
        from app.services.genre_normalizer import normalize_track_genres
        normalize_track_genres(tracks, get_taxonomy())

        return jsonify({
            "count": len(tracks),
            "skipped": skipped_count,
            "scanned": newly_scanned_count,
            "stale_removed": len(stale_paths),
            "tracks": [t.to_dict() for t in tracks]
        }), 200

    except Exception as e:
        logger.exception("Error in /api/import")
        return jsonify({"error": str(e)}), 500


@bp.route("/analyze", methods=["POST"])
def analyze_tracks():
    """
    Analyze tracks for BPM, key, energy (async).
    POST /api/analyze
    body: { "track_paths": ["/path1", "/path2"] }  # or empty list = all tracks
    Returns: { "op_id": "...", "total": N }  (202 Accepted)
    Stream progress via EventSource('/api/progress/<op_id>')
    Rate-limited: only one analysis at a time (429 if busy).
    """
    if not _analyze_lock.acquire(blocking=False):
        return jsonify({"error": "Analysis already in progress"}), 429

    _thread_started = False
    try:
        import uuid
        import threading
        import queue as _queue
        from app.services.analyzer import analyze_track, analyze_tracks_batch
        from app import get_track_store, get_progress_queues, get_cancel_events

        data = request.get_json(silent=True) or {}
        track_paths = data.get("track_paths", [])
        track_store = get_track_store()

        if not track_paths:
            track_paths = list(track_store.keys())

        logger.info(f"Analyze request: {len(track_paths)} tracks, store has {len(track_store)} tracks")

        op_id = str(uuid.uuid4())[:8]
        q = _queue.Queue()
        get_progress_queues()[op_id] = q
        cancel_event = threading.Event()
        get_cancel_events()[op_id] = cancel_event

        total = len(track_paths)

        if total > 1:
            def run():
                logger.info(f"Starting parallel analysis for {total} tracks")
                try:
                    analyze_tracks_batch(track_paths, track_store, progress_queue=q,
                                         cancel_event=cancel_event)
                finally:
                    _analyze_lock.release()
        else:
            def run():
                analyzed = 0
                errors = []
                logger.info(f"Starting sequential analysis for {total} tracks")
                cancelled = False
                try:
                    for i, file_path in enumerate(track_paths):
                        if cancel_event.is_set():
                            logger.info("Analysis cancelled after %d/%d tracks", i, total)
                            cancelled = True
                            break
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
                    terminal = {'done': True, 'analyzed': analyzed, 'errors': errors, 'refetch': True}
                    if cancelled:
                        terminal['cancelled'] = True
                    q.put(terminal)
                finally:
                    _analyze_lock.release()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        _thread_started = True
        return jsonify({'op_id': op_id, 'total': total}), 202

    except Exception as e:
        logger.exception("Error in /api/analyze")
        return jsonify({"error": str(e)}), 500

    finally:
        if not _thread_started:
            _analyze_lock.release()


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
    if not _classify_lock.acquire(blocking=False):
        return jsonify({"error": "Classification already in progress"}), 429

    _thread_started = False
    try:
        import uuid
        import threading
        import queue as _queue
        from app.services.classifier import classify_tracks as classify_service
        from app.services.multi_enricher import enrich_tracks as enrich_service
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

            try:
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

                # Enrich all tracks using the full multi-provider chain
                try:
                    from app.routes.settings_routes import load_env
                    _env = load_env()
                    enrich_config = {
                        "spotify_enabled": bool(_env.get("SPOTIFY_CLIENT_ID") and _env.get("SPOTIFY_CLIENT_SECRET"))
                            and _env.get("SPOTIFY_ENRICH_ENABLED", "true").lower() == "true",
                        "deezer_enabled": _env.get("DEEZER_ENRICH_ENABLED", "true").lower() == "true",
                        "beatport_enabled": _env.get("BEATPORT_ENRICH_ENABLED", "false").lower() == "true",
                        "lastfm_api_key": _env.get("LASTFM_API_KEY", ""),
                    }
                    enrich_service(tracks_to_classify, config=enrich_config)
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
                    logger.exception("Session save failed after classification")
            finally:
                # Always release so a crash/exception cannot leave the lock held
                # and block all future /api/classify calls (issue #199).
                _classify_lock.release()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        _thread_started = True
        return jsonify({'op_id': op_id, 'total': len(track_paths)}), 202

    except Exception as e:
        logger.exception("Error in /api/classify")
        return jsonify({"error": str(e)}), 500

    finally:
        # If the thread never started (exception in setup above), release the
        # lock here — the thread's finally will not run in that case.
        if not _thread_started:
            _classify_lock.release()
