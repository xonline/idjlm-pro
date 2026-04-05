import os
import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("settings", __name__, url_prefix="/api")


def get_env_path():
    """Get path to .env file at project root."""
    return os.path.join(os.path.dirname(__file__), "..", "..", ".env")


def mask_key(key_value):
    """Mask a key to show only last 4 characters."""
    if not key_value:
        return None
    key_str = str(key_value).strip()
    if len(key_str) <= 4:
        return "****"
    return "*" * (len(key_str) - 4) + key_str[-4:]


def load_env():
    """Load .env file as a dict."""
    env_dict = {}
    env_path = get_env_path()

    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, value = line.split("=", 1)
                            env_dict[key.strip()] = value.strip()
        except Exception:
            pass

    return env_dict


def write_env(env_dict):
    """Write env_dict back to .env file, preserving order and comments."""
    env_path = get_env_path()

    # Read existing file to preserve structure
    existing_lines = []
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                existing_lines = f.readlines()
        except Exception:
            pass

    # Build new content
    new_content = []
    written_keys = set()

    # First pass: update existing lines
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            if "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in env_dict:
                    new_content.append(f"{key}={env_dict[key]}\n")
                    written_keys.add(key)
                else:
                    new_content.append(line)
            else:
                new_content.append(line)
        else:
            new_content.append(line)

    # Second pass: add new keys not in existing file
    for key, value in env_dict.items():
        if key not in written_keys:
            new_content.append(f"{key}={value}\n")

    # Write back
    with open(env_path, "w") as f:
        f.writelines(new_content)


@bp.route("/settings", methods=["GET"])
def get_settings():
    """
    Get current settings from .env file.
    GET /api/settings
    Returns: {
        "gemini_api_key": "****...xxxx" or null,
        "has_gemini_key": true/false,
        "anthropic_api_key": "****...xxxx" or null,
        "has_anthropic_key": true/false,
        "spotify_client_id": "****...xxxx" or null,
        "spotify_client_secret": "****...xxxx" or null,
        "has_spotify": true/false,
        "ai_model": "claude" | "gemini" | "ollama",
        "ollama_model": "qwen3:1.7b",
        "classify_batch_size": 10,
        "auto_approve_threshold": 0,
        "spotify_enrich_enabled": true
    }
    """
    try:
        env_dict = load_env()

        gemini_key = env_dict.get("GEMINI_API_KEY")
        anthropic_key = env_dict.get("ANTHROPIC_API_KEY")
        spotify_id = env_dict.get("SPOTIFY_CLIENT_ID")
        spotify_secret = env_dict.get("SPOTIFY_CLIENT_SECRET")

        return jsonify({
            "gemini_api_key": mask_key(gemini_key) if gemini_key else None,
            "has_gemini_key": bool(gemini_key),
            "anthropic_api_key": mask_key(anthropic_key) if anthropic_key else None,
            "has_anthropic_key": bool(anthropic_key),
            "spotify_client_id": mask_key(spotify_id) if spotify_id else None,
            "spotify_client_secret": mask_key(spotify_secret) if spotify_secret else None,
            "has_spotify": bool(spotify_id) and bool(spotify_secret),
            "ai_model": env_dict.get("AI_MODEL", "claude"),
            "ollama_model": env_dict.get("OLLAMA_MODEL", "qwen3:1.7b"),
            "classify_batch_size": int(env_dict.get("CLASSIFY_BATCH_SIZE", "10")),
            "auto_approve_threshold": int(env_dict.get("AUTO_APPROVE_THRESHOLD", "0")),
            "spotify_enrich_enabled": env_dict.get("SPOTIFY_ENRICH_ENABLED", "true").lower() == "true",
        }), 200

    except Exception as e:
        logger.exception("Error in /api/settings GET")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/settings", methods=["POST"])
def save_settings():
    """
    Save settings to .env file.
    POST /api/settings
    body: {
        "gemini_api_key": "sk-...",              (optional, full unmasked value)
        "anthropic_api_key": "sk-...",           (optional, full unmasked value)
        "spotify_client_id": "...",              (optional)
        "spotify_client_secret": "...",          (optional)
        "ai_model": "claude" | "gemini" | "ollama",  (optional)
        "ollama_model": "qwen3:1.7b",            (optional)
        "classify_batch_size": 10,               (optional, 1-20)
        "auto_approve_threshold": 0,             (optional, 0-100)
        "spotify_enrich_enabled": true           (optional, boolean)
    }
    Only sends non-empty values; existing values not provided are preserved.
    """
    try:
        data = request.get_json() or {}

        # Load current .env
        env_dict = load_env()

        # Update only provided fields
        if "gemini_api_key" in data and data["gemini_api_key"]:
            env_dict["GEMINI_API_KEY"] = data["gemini_api_key"]

        if "anthropic_api_key" in data and data["anthropic_api_key"]:
            env_dict["ANTHROPIC_API_KEY"] = data["anthropic_api_key"]

        if "spotify_client_id" in data and data["spotify_client_id"]:
            env_dict["SPOTIFY_CLIENT_ID"] = data["spotify_client_id"]

        if "spotify_client_secret" in data and data["spotify_client_secret"]:
            env_dict["SPOTIFY_CLIENT_SECRET"] = data["spotify_client_secret"]

        if "ai_model" in data and data["ai_model"]:
            if data["ai_model"] in ["claude", "gemini", "ollama"]:
                env_dict["AI_MODEL"] = data["ai_model"]

        if "ollama_model" in data and data["ollama_model"]:
            env_dict["OLLAMA_MODEL"] = data["ollama_model"]

        if "classify_batch_size" in data:
            try:
                batch_size = int(data["classify_batch_size"])
                if 1 <= batch_size <= 20:
                    env_dict["CLASSIFY_BATCH_SIZE"] = str(batch_size)
            except (ValueError, TypeError):
                pass

        if "auto_approve_threshold" in data:
            try:
                threshold = int(data["auto_approve_threshold"])
                if 0 <= threshold <= 100:
                    env_dict["AUTO_APPROVE_THRESHOLD"] = str(threshold)
            except (ValueError, TypeError):
                pass

        if "spotify_enrich_enabled" in data:
            env_dict["SPOTIFY_ENRICH_ENABLED"] = "true" if data["spotify_enrich_enabled"] else "false"

        # Write back
        write_env(env_dict)

        return jsonify({"saved": True}), 200

    except Exception as e:
        logger.exception("Error in /api/settings POST")
        return jsonify({"error": "Operation failed. Check server logs."}), 500
