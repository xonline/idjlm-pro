import os
import json
import logging
import threading
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from app.services.track_store import TrackStore


def _setup_file_logging():
    """Write app logs to ~/Library/Logs/IDJLM Pro/idjlm.log (macOS) or ~/.idjlm-pro/logs/idjlm.log."""
    from .utils import paths
    log_dir = paths.ensure_app_user_log_dir()
    log_path = os.path.join(log_dir, "idjlm.log")

    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=2 * 1024 * 1024, backupCount=3
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s — %(message)s"
    ))
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(handler)
    else:
        root.addHandler(handler)
    root.setLevel(logging.INFO)
    return log_path


# In-memory session store: dict-like facade persisting to SQLite.
# Issue #187 (B.1) migrated the previous in-memory dict + session.json to a
# SQLite-backed TrackStore with content-hash IDs. The SQLite database lives
# next to the user data dir (<user_dir>/tracks.db). Migration from any
# pre-existing session.json runs automatically inside create_app() once.
_track_store: "TrackStore | dict" = None
# Reentrant lock protecting _track_store from concurrent mutations
# (import clear vs background analyse/classify iteration race — issue #199)
_track_store_lock = threading.RLock()
# Taxonomy loaded from taxonomy.json (mutable at runtime)
_taxonomy: dict = {}
# Progress queues: { op_id: queue.Queue }
class _LimitedProgressQueues(dict):
    """Size-capped dict that evicts oldest entries when limit is reached."""
    _MAX = 50

    def __setitem__(self, key, value):
        while len(self) >= self._MAX:
            try:
                oldest = next(iter(self))
                del self[oldest]
            except StopIteration:
                break
        super().__setitem__(key, value)

_progress_queues = _LimitedProgressQueues()
# Cancel signals: { op_id: threading.Event } — set by /api/progress/<op>/cancel
# and polled by long-running workers so a cancelled run stops the pool instead
# of draining it. Capped alongside the progress queues.
_cancel_events = _LimitedProgressQueues()
# Last imported folder path (used for auto-save)
_current_folder_path: str = ""


def get_track_store():
    """Return the active TrackStore (dict-like façade).

    Kept untyped so legacy route code (`track_store[fp]`, etc.) compiles
    unchanged. Returns the underlying SQLite-backed TrackStore once
    create_app() has wired it up; returns a fresh empty dict during
    test imports before create_app() runs (legacy behaviour preserved).
    """
    return _track_store if _track_store is not None else {}


def get_track_store_lock() -> threading.RLock:
    """Return the process-wide RLock that guards multi-step _track_store operations.

    Callers that do clear-then-repopulate (import) or snapshot-then-iterate
    (analyze/classify) should acquire this lock for the duration of the
    multi-step sequence so a concurrent import cannot clear the store mid-flight.
    """
    return _track_store_lock


def set_track_store(store) -> None:
    """Install a TrackStore instance as the active store (test seam)."""
    global _track_store
    _track_store = store


def get_taxonomy() -> dict:
    return _taxonomy


def get_progress_queues() -> dict:
    return _progress_queues


def get_cancel_events() -> dict:
    return _cancel_events


def is_cancelled(op_id: str) -> bool:
    ev = _cancel_events.get(op_id)
    return ev is not None and ev.is_set()


def cleanup_progress_queue(op_id: str) -> None:
    _progress_queues.pop(op_id, None)
    _cancel_events.pop(op_id, None)


def get_current_folder_path() -> str:
    return _current_folder_path


def set_current_folder_path(path: str) -> None:
    global _current_folder_path
    _current_folder_path = path


def create_app() -> Flask:
    import logging.handlers
    log_path = _setup_file_logging()

    app = Flask(__name__, template_folder="../templates", static_folder="static")
    CORS(app, origins=["http://localhost:5050", "http://127.0.0.1:5050"])
    logging.getLogger(__name__).info("IDJLM Pro starting — log: %s", log_path)

    # Clear any stale progress queues from previous sessions
    _progress_queues.clear()
    _cancel_events.clear()

    # Wire up the SQLite track store (issue #187 — B.1). The previous
    # in-memory dict + session.json pair is replaced by a small
    # dict-facade over SQLite. Migration from a pre-existing
    # session.json runs once on first launch and is recorded in the
    # store's `store_meta` table so subsequent launches skip it.
    from .utils import paths as _paths
    store = TrackStore()
    try:
        migrated = store.migrate_from_session_json(
            _paths.user_data_path("session.json")
        )
        if migrated is True:
            logging.getLogger(__name__).info(
                "IDJLM Pro: migrated previous session.json into SQLite track store"
            )
    except Exception as exc:
        # Migration failure must not crash app startup. The store is
        # still usable; the JSON file is left untouched for the next
        # attempt.
        logging.getLogger(__name__).warning(
            "IDJLM Pro: track-store migration skipped due to error: %s",
            exc,
        )
    global _track_store
    _track_store = store

    # Load taxonomy — prefer user-writable copy (may have edits), fall back to bundle
    from .utils import paths  # noqa: F811  (re-import scoped to function)
    _user_taxonomy = paths.user_data_path("taxonomy.json")
    _bundle_taxonomy = os.path.join(os.path.dirname(__file__), "..", "taxonomy.json")
    taxonomy_path = _user_taxonomy if os.path.exists(_user_taxonomy) else _bundle_taxonomy
    try:
        with open(taxonomy_path) as f:
            _taxonomy.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        logging.getLogger(__name__).warning(
            "Failed to load taxonomy from %s: %s. Using built-in default taxonomy.", taxonomy_path, e
        )
        _taxonomy.update({"genres": {"Unknown": {"description": "Default genre", "subgenres": {}}}})

    # Register blueprints
    from app.routes.import_routes import bp as import_bp
    from app.routes.track_routes import bp as track_bp
    from app.routes.review_routes import bp as review_bp
    from app.routes.bulk_routes import bp as bulk_bp
    from app.routes.settings_routes import bp as settings_bp
    from app.routes.audio_routes import bp as audio_bp
    from app.routes.session_routes import bp as session_bp
    from app.routes.watch_routes import bp as watch_bp
    from app.routes.export_routes import bp as export_bp
    from app.routes.duplicate_routes import bp as duplicate_bp
    from app.routes.progress_routes import bp as progress_bp
    from app.routes.setlist_routes import bp as setlist_bp
    from app.routes.setplan_routes import bp as setplan_bp
    from app.routes.playlist_routes import bp as playlist_bp
    from app.routes.latin_routes import bp as latin_bp
    from app.routes.organise_routes import bp as organise_bp
    from app.routes.key_routes import bp as key_bp
    from app.routes.applescript_routes import bp as applescript_bp
    from app.routes.version_routes import bp as version_bp
    from app.routes.health_routes import bp as health_bp
    from app.routes.advisor_routes import bp as advisor_bp
    from app.routes.rekordbox_routes import bp as rekordbox_bp
    from app.routes.backup_routes import bp as backup_bp
    from app.routes.tag_routes import bp as tag_bp

    app.register_blueprint(import_bp)
    app.register_blueprint(track_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(bulk_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(audio_bp)
    app.register_blueprint(session_bp)
    app.register_blueprint(watch_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(duplicate_bp)
    app.register_blueprint(progress_bp)
    app.register_blueprint(setlist_bp)
    app.register_blueprint(setplan_bp)
    app.register_blueprint(playlist_bp)
    app.register_blueprint(latin_bp)
    app.register_blueprint(organise_bp)
    app.register_blueprint(key_bp)
    app.register_blueprint(applescript_bp)
    app.register_blueprint(version_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(advisor_bp)
    app.register_blueprint(rekordbox_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(tag_bp)

    @app.route("/")
    def index():
        import sys as _sys
        base = getattr(_sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
        try:
            version = open(os.path.join(base, "VERSION")).read().strip()
        except Exception:
            version = ""
        # IDJLM 0.4: opt-in flag pointing the page at the Vite dev server
        # (`npm run dev`, http://localhost:5173) instead of the built
        # app/static/dist/main.js bundle. Defaults off (prod-safe).
        dev_mode = os.getenv("IDJLM_VITE_DEV") == "1"
        return render_template("index.html", version=version, dev_mode=dev_mode)

    # Centralised error handlers — A.2 structured-error taxonomy.
    # Any uncaught exception in a route handler is converted to the
    # {"error", "detail", "op"} shape; real exception stays in server log only.
    from .utils.errors import AppError, Err, log_app_error, log_unexpected_error, make_error_payload

    @app.errorhandler(AppError)
    def _handle_app_error(err: AppError):
        log_app_error(err, route=request.path if request else None)
        return (
            jsonify({"error": err.code, "detail": err.message, **({"op": err.op} if err.op else {})}),
            err.status_code,
        )

    @app.errorhandler(404)
    def _handle_404(_e):
        return jsonify(make_error_payload(Err.NOT_FOUND, "No such endpoint")), 404

    @app.errorhandler(405)
    def _handle_405(_e):
        return jsonify(make_error_payload(Err.INVALID_STATE, "Method not allowed")), 405

    @app.errorhandler(Exception)
    def _handle_unexpected(e: Exception):
        # Skip HTTPException — those are handled by their own status handlers.
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        # Never include str(e) in the payload — it can leak path/class info.
        log_unexpected_error(e, route=request.path if request else None)
        return jsonify(make_error_payload(Err.UNKNOWN, "Server error")), 500

    return app
