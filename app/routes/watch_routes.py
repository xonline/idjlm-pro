import logging
from flask import Blueprint, request, jsonify
from app.services.watcher import start_watching, stop_watching, get_new_files, WatcherState

bp = Blueprint("watch", __name__, url_prefix="/api")

logger = logging.getLogger(__name__)


@bp.route("/watch/start", methods=["POST"])
def watch_start():
    """
    Start watching folder for new MP3 files.
    POST /api/watch/start
    body: { "folder_path": "/path/to/folder" }
    """
    try:
        data = request.get_json(silent=True) or {}
        folder_path = data.get("folder_path", "").strip()

        if not folder_path:
            return jsonify({"error": "folder_path is required"}), 400

        # Start watcher
        start_watching(folder_path)

        # Also scan existing files in folder and add to track store
        from app.services.scanner import scan_folder_incremental
        from app import get_track_store

        track_store = get_track_store()

        # Incremental: files already in the store with an unchanged mtime+size
        # are reused as-is, so watching a 10k folder does not re-read every
        # tag / re-hash / re-fingerprint on start.
        #
        # stale_paths is deliberately DISCARDED. The track store is global, but
        # a watched folder may be a subfolder of — or unrelated to — the
        # imported library, so every track outside folder_path would be listed
        # stale. Only /api/import (the canonical full-library scan) may act on
        # it. watch/start stays add-only.
        tracks, _stale_paths, unchanged_paths = scan_folder_incremental(
            folder_path, track_store
        )

        added = 0
        for track in tracks:
            if track.file_path in unchanged_paths:
                continue
            if track.file_path not in track_store:
                track_store[track.file_path] = track
                added += 1

        return jsonify({
            "watching": True,
            "folder": folder_path,
            "existing_tracks_added": added,
            "skipped": len(unchanged_paths),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/watch/stop", methods=["POST"])
def watch_stop():
    """
    Stop watching folder.
    POST /api/watch/stop
    """
    try:
        stop_watching()
        return jsonify({
            "watching": False
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/watch/status", methods=["GET"])
def watch_status():
    """
    Get current watcher status.
    GET /api/watch/status
    """
    try:
        return jsonify({
            "watching": WatcherState.is_watching,
            "folder": WatcherState.folder,
            "new_count": len(WatcherState.new_files)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/watch/poll", methods=["GET"])
def watch_poll():
    """
    Poll for newly detected MP3 files, scan them, and add to track store.
    GET /api/watch/poll
    """
    try:
        from app import get_track_store

        # Get newly detected files and clear buffer
        new_file_paths = get_new_files()

        if not new_file_paths:
            return jsonify({
                "tracks": []
            }), 200

        # Scan each file individually
        tracks_data = []
        track_store = get_track_store()

        import os
        from pathlib import Path
        from app.services.scanner import _scan_single_file

        for file_path in new_file_paths:
            try:
                # Skip if already in store
                if file_path in track_store:
                    continue

                # Route through the shared single-file scan path rather than
                # hand-rolling a Track here. It reads non-MP3 formats correctly
                # and — critically — stamps file_mtime/file_size/content_hash.
                # Without those, a track that entered via the inbox looks
                # "changed" to scan_folder_incremental forever, so every later
                # import would re-scan it and the inbox would quietly defeat
                # incremental import.
                filename = os.path.basename(file_path)
                suffix = Path(filename).suffix.lower()
                track = _scan_single_file(file_path, filename, suffix)

                # Add to store
                track_store[file_path] = track
                tracks_data.append(track.to_dict())

            except Exception as e:
                # Log error but continue processing other files
                logger.warning("Failed to process new file %s: %s", file_path, e)
                continue

        return jsonify({
            "tracks": tracks_data
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
