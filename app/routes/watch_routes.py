from flask import Blueprint, jsonify, request
import threading

bp = Blueprint("watch", __name__, url_prefix="/api/watch")

_watcher = None
_watch_thread = None


@bp.route("/start", methods=["POST"])
def start_watch():
    """Start folder monitoring."""
    global _watcher, _watch_thread
    from app.services.watcher import Watcher

    data = request.json or {}
    folder = data.get("folder")

    if not folder:
        return jsonify({"error": "folder required"}), 400

    try:
        _watcher = Watcher(folder)
        _watch_thread = threading.Thread(target=_watcher.start, daemon=True)
        _watch_thread.start()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/stop", methods=["POST"])
def stop_watch():
    """Stop folder monitoring."""
    global _watcher
    if _watcher:
        _watcher.stop()
        _watcher = None
    return jsonify({"success": True})


@bp.route("/poll", methods=["GET"])
def poll_watch():
    """Check for newly detected files."""
    global _watcher
    if _watcher:
        return jsonify({"new_files": _watcher.get_new_files()})
    return jsonify({"new_files": []})
