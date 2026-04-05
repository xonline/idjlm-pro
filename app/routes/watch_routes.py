from flask import Blueprint, request, jsonify
from app.services.watcher import start_watching, stop_watching, get_new_files, WatcherState

bp = Blueprint("watch", __name__, url_prefix="/api")


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
        from app.services.scanner import scan_folder
        from app import get_track_store

        tracks = scan_folder(folder_path)
        track_store = get_track_store()

        added = 0
        for track in tracks:
            if track.file_path not in track_store:
                track_store[track.file_path] = track
                added += 1

        return jsonify({
            "watching": True,
            "folder": folder_path,
            "existing_tracks_added": added
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
        from app.services.scanner import scan_folder
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

        from app.services.scanner import _read_id3_tags
        from app.models.track import Track

        for file_path in new_file_paths:
            try:
                # Skip if already in store
                if file_path in track_store:
                    continue

                # Read tags
                id3_tags = _read_id3_tags(file_path)
                import os
                filename = os.path.basename(file_path)

                # Create Track object
                track = Track(
                    file_path=file_path,
                    filename=filename,
                    existing_title=id3_tags['title'],
                    existing_artist=id3_tags['artist'],
                    existing_album=id3_tags['album'],
                    existing_year=id3_tags['year'],
                    existing_genre=id3_tags['genre'],
                    existing_comment=id3_tags['comment'],
                    existing_bpm=id3_tags['bpm'],
                    existing_key=id3_tags['key'],
                )

                # Add to store
                track_store[file_path] = track
                tracks_data.append(track.to_dict())

            except Exception as e:
                # Log error but continue processing other files
                print(f"Warning: Failed to process new file {file_path}: {str(e)}")
                continue

        return jsonify({
            "tracks": tracks_data
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
