import os
import json
from flask import Flask, render_template
from flask_cors import CORS


# In-memory session store: { file_path: Track }
_track_store: dict = {}
# Taxonomy loaded from taxonomy.json (mutable at runtime)
_taxonomy: dict = {}


def get_track_store() -> dict:
    return _track_store


def get_taxonomy() -> dict:
    return _taxonomy


def _load_settings_from_home():
    """Load API keys and settings from ~/.xdj_library_manager/settings.json if available."""
    settings_file = os.path.expanduser("~/.xdj_library_manager/settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file) as f:
                settings = json.load(f)
                # Load into environment variables
                for key, value in settings.items():
                    os.environ[key] = value
        except Exception:
            pass  # Silently ignore if settings file is unreadable


def create_app() -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="static")
    CORS(app)

    # Load user-level settings first (persistent across app launches)
    _load_settings_from_home()
    
    # Load .env file (may override or supplement settings)
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())

    # Load taxonomy
    taxonomy_path = os.path.join(os.path.dirname(__file__), "..", "taxonomy.json")
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

    app.register_blueprint(import_bp)
    app.register_blueprint(track_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(bulk_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(audio_bp)
    app.register_blueprint(session_bp)
    app.register_blueprint(watch_bp)
    app.register_blueprint(export_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    return app
