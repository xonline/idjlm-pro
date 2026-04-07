import os
import json
import logging
import queue as _queue
from flask import Flask, render_template
from flask_cors import CORS


def _setup_file_logging():
    """Write app logs to ~/Library/Logs/IDJLM Pro/idjlm.log (macOS) or ~/.idjlm-pro/idjlm.log."""
    import platform
    if platform.system() == "Darwin":
        log_dir = os.path.expanduser("~/Library/Logs/IDJLM Pro")
    else:
        log_dir = os.path.expanduser("~/.idjlm-pro/logs")
    os.makedirs(log_dir, exist_ok=True)
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


# In-memory session store: { file_path: Track }
_track_store: dict = {}
# Taxonomy loaded from taxonomy.json (mutable at runtime)
_taxonomy: dict = {}
# Progress queues: { op_id: queue.Queue }
_progress_queues: dict = {}
# Last imported folder path (used for auto-save)
_current_folder_path: str = ""


def get_track_store() -> dict:
    return _track_store


def get_taxonomy() -> dict:
    return _taxonomy


def get_progress_queues() -> dict:
    return _progress_queues


def get_current_folder_path() -> str:
    return _current_folder_path


def set_current_folder_path(path: str) -> None:
    global _current_folder_path
    _current_folder_path = path


def create_app() -> Flask:
    import logging.handlers
    log_path = _setup_file_logging()

    app = Flask(__name__, template_folder="../templates", static_folder="static")
    CORS(app)
    logging.getLogger(__name__).info("IDJLM Pro starting — log: %s", log_path)

    # Load taxonomy — prefer user-writable copy (may have edits), fall back to bundle
    import platform
    if platform.system() == "Darwin":
        _user_taxonomy = os.path.expanduser("~/Library/Application Support/IDJLM Pro/taxonomy.json")
    else:
        _user_taxonomy = os.path.expanduser("~/.idjlm-pro/taxonomy.json")
    _bundle_taxonomy = os.path.join(os.path.dirname(__file__), "..", "taxonomy.json")
    taxonomy_path = _user_taxonomy if os.path.exists(_user_taxonomy) else _bundle_taxonomy
    with open(taxonomy_path) as f:
        _taxonomy.update(json.load(f))

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
    from app.routes.latin_routes import bp as latin_bp
    from app.routes.organise_routes import bp as organise_bp
    from app.routes.key_routes import bp as key_bp
    from app.routes.applescript_routes import bp as applescript_bp

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
    app.register_blueprint(latin_bp)
    app.register_blueprint(organise_bp)
    app.register_blueprint(key_bp)
    app.register_blueprint(applescript_bp)

    @app.route("/")
    def index():
        import sys as _sys
        base = getattr(_sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
        try:
            version = open(os.path.join(base, "VERSION")).read().strip()
        except Exception:
            version = ""
        return render_template("index.html", version=version)

    return app
