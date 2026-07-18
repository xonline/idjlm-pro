import logging
import os
import threading
import uuid
import queue as _queue

from flask import Blueprint, jsonify, request, send_file

from app import get_track_store, get_progress_queues
from app.services.stem_separator import (
    STEM_NAMES,
    get_stems_dir,
    get_stems_for_track,
    separate_stems,
    delete_stems,
)
from app.utils import paths

logger = logging.getLogger(__name__)
bp = Blueprint("stem", __name__, url_prefix="/api")

_stem_lock = threading.Lock()


def _resolve_track(track_id):
    track_store = get_track_store()
    track = track_store.get(track_id)
    if track:
        return track
    if not track_id.startswith("/"):
        track = track_store.get("/" + track_id)
    return track


def _safe_stem_dir(content_hash):
    base = os.path.realpath(os.path.join(paths.app_user_dir(), "stems"))
    safe = str(content_hash).replace("\\", "/").strip("/")
    if ".." in safe.split("/") or os.path.isabs(safe):
        raise ValueError("invalid track id")
    candidate = os.path.realpath(os.path.join(base, safe))
    if not (candidate == base or candidate.startswith(base + os.sep)):
        raise ValueError("path escapes stems dir")
    return candidate


@bp.route("/stem/separate", methods=["POST"])
def separate_track():
    data = request.get_json(silent=True) or {}
    file_path = data.get("file_path", "")

    if not file_path:
        return jsonify({"error": "file_path is required"}), 400

    track_store = get_track_store()
    if file_path not in track_store:
        return jsonify({"error": "Track not found"}), 404

    track = track_store[file_path]
    if not os.path.isfile(track.file_path):
        return jsonify({"error": "Audio file not found on disk"}), 404

    if not _stem_lock.acquire(blocking=False):
        return jsonify({"error": "Stem separation already in progress"}), 429

    thread_started = False
    try:
        op_id = str(uuid.uuid4())[:8]
        q = _queue.Queue()
        get_progress_queues()[op_id] = q

        import copy
        track_snapshot = copy.deepcopy(track)
        content_hash = track_snapshot.content_hash or track_snapshot.file_path
        output_dir = get_stems_dir(content_hash)

        def run():
            try:
                def on_progress(message, current, total):
                    q.put({
                        "current": current,
                        "total": total,
                        "message": message,
                        "track": track_snapshot.display_title,
                    })

                q.put({
                    "current": 0,
                    "total": len(STEM_NAMES),
                    "message": "Starting stem separation...",
                    "track": track_snapshot.display_title,
                })

                saved = separate_stems(track_snapshot, output_dir, progress_callback=on_progress)
                stem_list = [{"name": name, "path": path} for name, path in sorted(saved.items())]
                q.put({
                    "done": True,
                    "stems": stem_list,
                    "output_dir": output_dir,
                })
            except Exception as e:
                logger.exception("Stem separation failed for %s", track_snapshot.display_title)
                q.put({"done": True, "error": str(e)})
            finally:
                _stem_lock.release()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        thread_started = True
        return jsonify({"op_id": op_id, "total": len(STEM_NAMES)}), 202

    except Exception as e:
        logger.exception("Error in /api/stem/separate")
        return jsonify({"error": str(e)}), 500

    finally:
        if not thread_started:
            _stem_lock.release()


@bp.route("/stem/<path:track_id>/stems", methods=["GET"], strict_slashes=False)
def list_stems(track_id):
    track = _resolve_track(track_id)
    if not track:
        content_hash = track_id
    else:
        content_hash = track.content_hash or track.file_path

    stems = get_stems_for_track(track) if track else {}
    if not stems:
        try:
            stem_root = _safe_stem_dir(content_hash)
        except ValueError:
            return jsonify({"error": "Invalid track id"}), 400
        stems_path = os.path.join(stem_root, "stems")
        if os.path.isdir(stems_path):
            for name in STEM_NAMES:
                path = os.path.join(stems_path, f"{name}.wav")
                if os.path.isfile(path) and os.path.getsize(path) > 0:
                    stems[name] = path

    return jsonify({
        "stems": [{"name": name, "path": path} for name, path in sorted(stems.items())],
        "has_stems": len(stems) > 0,
    })


@bp.route("/stem/<path:track_id>/stem/<stem_name>", methods=["GET"])
def serve_stem(track_id, stem_name):
    if stem_name not in STEM_NAMES:
        return jsonify({"error": f"Unknown stem: {stem_name}. Valid: {', '.join(STEM_NAMES)}"}), 400

    track = _resolve_track(track_id)
    if track:
        content_hash = track.content_hash or track.file_path
    else:
        content_hash = track_id

    try:
        stem_root = _safe_stem_dir(content_hash)
    except ValueError:
        return jsonify({"error": "Invalid track id"}), 400

    stem_path = os.path.join(stem_root, "stems", f"{stem_name}.wav")

    if not os.path.isfile(stem_path):
        return jsonify({"error": f"Stem '{stem_name}' not found"}), 404

    return send_file(
        stem_path,
        mimetype="audio/wav",
        conditional=True,
        as_attachment=False,
    )


@bp.route("/stem/<path:track_id>", methods=["DELETE"])
def delete_stems_route(track_id):
    # CSRF mitigation: plain HTML forms cannot set this content type, and a
    # cross-origin fetch() sending it would be blocked by the CORS preflight
    # (see CORS(app, origins=[...]) in app/__init__.py) before reaching here.
    if not (request.content_type or "").startswith("application/json"):
        return jsonify({"error": "Unsupported Content-Type"}), 403

    track = _resolve_track(track_id)
    if not track:
        # track_id must resolve to a known track from the store — it is
        # never used to derive a filesystem path directly (path traversal).
        return jsonify({"error": "Track not found"}), 404

    deleted = delete_stems(track)
    return jsonify({"deleted": deleted}), 200
