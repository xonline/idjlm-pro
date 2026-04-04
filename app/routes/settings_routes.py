from flask import Blueprint, jsonify, request
import os
import json
import pathlib
from dotenv import load_dotenv, find_dotenv

bp = Blueprint("settings", __name__, url_prefix="/api/settings")


def _get_settings_dir():
    """Get user-level settings directory (~/.xdj_library_manager)."""
    settings_dir = os.path.expanduser("~/.xdj_library_manager")
    os.makedirs(settings_dir, exist_ok=True)
    return settings_dir


def _get_settings_file():
    """Get path to user-level settings.json file."""
    return os.path.join(_get_settings_dir(), "settings.json")


def _load_settings():
    """Load settings from ~/.xdj_library_manager/settings.json."""
    settings_file = _get_settings_file()
    if os.path.exists(settings_file):
        try:
            with open(settings_file) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_settings(settings):
    """Save settings to ~/.xdj_library_manager/settings.json."""
    settings_file = _get_settings_file()
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)


@bp.route("/", methods=["GET"])
def get_settings():
    """Get current API key status (masked), model config, and confidence threshold."""
    load_dotenv(find_dotenv())
    from app.services.classifier import MODELS_BY_PRIORITY, DEFAULT_MODEL
    
    current_model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    settings = _load_settings()
    confidence_threshold = settings.get("confidence_threshold", 70)
    
    return jsonify({
        "gemini_key": "set" if os.getenv("GEMINI_API_KEY") else "unset",
        "spotify_id": "set" if os.getenv("SPOTIFY_CLIENT_ID") else "unset",
        "spotify_secret": "set" if os.getenv("SPOTIFY_CLIENT_SECRET") else "unset",
        "model": current_model,
        "confidence_threshold": confidence_threshold,
    })


@bp.route("/", methods=["POST"])
def update_settings():
    """Update settings in ~/.xdj_library_manager/settings.json and .env."""
    data = request.json or {}
    settings_file = _get_settings_file()
    env_file = find_dotenv() or ".env"

    try:
        # Load existing settings from user home directory
        settings = _load_settings()

        # Update with new values
        if "gemini_key" in data:
            settings["GEMINI_API_KEY"] = data["gemini_key"]
            os.environ["GEMINI_API_KEY"] = data["gemini_key"]
        if "spotify_id" in data:
            settings["SPOTIFY_CLIENT_ID"] = data["spotify_id"]
            os.environ["SPOTIFY_CLIENT_ID"] = data["spotify_id"]
        if "spotify_secret" in data:
            settings["SPOTIFY_CLIENT_SECRET"] = data["spotify_secret"]
            os.environ["SPOTIFY_CLIENT_SECRET"] = data["spotify_secret"]
        if "confidence_threshold" in data:
            try:
                threshold = int(data["confidence_threshold"])
                if 0 <= threshold <= 100:
                    settings["confidence_threshold"] = threshold
                else:
                    return jsonify({"success": False, "error": "confidence_threshold must be between 0 and 100"}), 400
            except (ValueError, TypeError):
                return jsonify({"success": False, "error": "confidence_threshold must be an integer"}), 400

        # Write to user home directory (persistent across app launches)
        _save_settings(settings)

        # Also attempt to write to .env if it's writable (bundled .env may be read-only)
        try:
            env_vars = {}
            if os.path.exists(env_file):
                for line in open(env_file):
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip()

            if "gemini_key" in data:
                env_vars["GEMINI_API_KEY"] = data["gemini_key"]
            if "spotify_id" in data:
                env_vars["SPOTIFY_CLIENT_ID"] = data["spotify_id"]
            if "spotify_secret" in data:
                env_vars["SPOTIFY_CLIENT_SECRET"] = data["spotify_secret"]

            with open(env_file, "w") as f:
                for k, v in env_vars.items():
                    f.write(f"{k}={v}\n")
        except (OSError, IOError):
            # .env file is read-only (bundled .app), but settings.json was saved above
            pass

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@bp.route("/models", methods=["GET"])
def list_models():
    """List available Gemini models and current selection."""
    from app.services.classifier import MODELS_BY_PRIORITY, DEFAULT_MODEL
    current = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    return jsonify({
        "models": MODELS_BY_PRIORITY,
        "current": current,
        "default": DEFAULT_MODEL,
    })


@bp.route("/model", methods=["POST"])
def set_model():
    """Set the preferred Gemini model (session + env)."""
    data = request.get_json() or {}
    model = data.get("model", "").strip()
    from app.services.classifier import MODELS_BY_PRIORITY, DEFAULT_MODEL
    
    if model and model not in MODELS_BY_PRIORITY:
        return jsonify({"error": "Unknown model"}), 400
    
    # Set in environment for this session
    os.environ["GEMINI_MODEL"] = model or DEFAULT_MODEL
    
    return jsonify({"model": os.environ["GEMINI_MODEL"]})


@bp.route("/version", methods=["GET"])
def get_version():
    """Get app version from VERSION file and build SHA."""
    version_file = pathlib.Path(__file__).parent.parent.parent / "VERSION"
    try:
        version = version_file.read_text().strip()
    except Exception:
        version = "unknown"
    return jsonify({"version": version, "build": os.getenv("BUILD_SHA", "dev")})
