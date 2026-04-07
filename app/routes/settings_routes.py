import os
import ssl
import logging
import json
import urllib.request
import urllib.error
import certifi
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("settings", __name__, url_prefix="/api")


def _ssl_context():
    """Create SSL context using certifi CA bundle (fixes macOS Python cert errors)."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    return ctx


def get_env_path():
    """
    Get path to .env settings file in a user-writable location.

    Uses ~/Library/Application Support/IDJLM Pro/.env on macOS,
    falling back to ~/.idjlm-pro/.env on other platforms.
    This ensures settings persist whether the app is run from a DMG,
    the Applications folder, or any other location.

    On first call, migrates any existing .env from the legacy bundle-relative
    path so users don't lose previously saved keys.
    """
    import platform
    if platform.system() == "Darwin":
        settings_dir = os.path.expanduser("~/Library/Application Support/IDJLM Pro")
    else:
        settings_dir = os.path.expanduser("~/.idjlm-pro")

    os.makedirs(settings_dir, exist_ok=True)
    new_path = os.path.join(settings_dir, ".env")

    # One-time migration from legacy bundle-relative .env
    if not os.path.exists(new_path):
        legacy_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        legacy_path = os.path.normpath(legacy_path)
        if os.path.exists(legacy_path):
            try:
                import shutil
                shutil.copy2(legacy_path, new_path)
            except Exception:
                pass

    return new_path


def mask_key(key_value):
    """Mask a key to show first 4 and last 4 characters."""
    if not key_value:
        return None
    key_str = str(key_value).strip()
    if len(key_str) <= 8:
        return "****"
    return key_str[:4] + "..." + key_str[-4:]


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


# ---------------------------------------------------------------------------
# Model listing — cascading provider → model selection
# ---------------------------------------------------------------------------

VALID_PROVIDERS = {"claude", "openrouter", "gemini", "ollama"}


@bp.route("/list_models", methods=["POST"])
def list_models():
    """
    POST /api/list_models
    Body: { "provider": "claude"|"openrouter"|"gemini"|"ollama", "api_key": "..." (optional) }
    Returns: { "models": [{ "id": "...", "name": "...", "free": false, "context": 200000 }, ...] }
    """
    data = request.get_json(silent=True) or {}
    provider = data.get("provider", "").strip().lower()

    if not provider:
        return jsonify({"error": "provider is required"}), 400

    if provider not in VALID_PROVIDERS:
        return jsonify({"error": f"Unknown provider: {provider}. Must be one of: {', '.join(sorted(VALID_PROVIDERS))}"}), 400

    api_key = data.get("api_key", "").strip()

    # If the user didn't provide a key in the request, try to use the saved one
    if not api_key:
        env = load_env()
        if provider == "claude":
            api_key = env.get("ANTHROPIC_API_KEY", "")
        elif provider == "openrouter":
            api_key = env.get("OPENROUTER_API_KEY", "")
        elif provider == "gemini":
            api_key = env.get("GEMINI_API_KEY", "")

    try:
        if provider == "claude":
            if not api_key:
                return jsonify({"error": "API key required for claude -- paste your key in settings first"}), 400
            models = _list_claude_models(api_key)
        elif provider == "openrouter":
            models = _list_openrouter_models(api_key)
        elif provider == "gemini":
            if not api_key:
                return jsonify({"error": "API key required for gemini -- paste your key in settings first"}), 400
            models = _list_gemini_models(api_key)
        elif provider == "ollama":
            models = _list_ollama_models()
        else:
            return jsonify({"error": f"Unknown provider: {provider}"}), 400

        return jsonify({"models": models}), 200

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()
        except Exception:
            pass
        logger.exception("HTTP error listing models for %s: %s %s", provider, e.code, body)
        return jsonify({"error": f"Failed to fetch models from {provider} (HTTP {e.code})"}), 502
    except urllib.error.URLError as e:
        logger.exception("URL error listing models for %s: %s", provider, e.reason)
        msg = str(e.reason) if hasattr(e, "reason") else str(e)
        return jsonify({"error": f"Network error: {msg}"}), 502
    except Exception as e:
        logger.exception("Error listing models for %s", provider)
        return jsonify({"error": f"Failed to fetch models: {str(e)}"}), 500


def _list_claude_models(api_key):
    """Fetch available Claude models from Anthropic API."""
    url = "https://api.anthropic.com/v1/models"
    req = urllib.request.Request(url)
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("X-Api-Key", api_key)
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
        result = json.loads(resp.read().decode())

    models = []
    for item in result.get("data", []):
        model_id = item.get("id", "")
        if not model_id.startswith("claude-"):
            continue
        display_name = item.get("display_name", model_id)
        models.append({
            "id": model_id,
            "name": display_name,
            "free": False,
            "context": item.get("context_length", 0),
        })

    return models


def _list_openrouter_models(api_key):
    """Fetch available models from OpenRouter API."""
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
        result = json.loads(resp.read().decode())

    models = []
    for item in result.get("data", []):
        model_id = item.get("id", "")
        name = item.get("name", model_id)
        pricing = item.get("pricing", {})

        # Model is free if all pricing values are zero or absent
        is_free = True
        if pricing:
            for price in pricing.values():
                try:
                    if float(price) > 0:
                        is_free = False
                        break
                except (ValueError, TypeError):
                    pass

        models.append({
            "id": model_id,
            "name": name,
            "free": is_free,
            "context": item.get("context_length", 0),
        })

    # Sort by name for easier browsing
    models.sort(key=lambda m: m["name"].lower())
    return models


def _list_gemini_models(api_key):
    """Fetch available models from Google Gemini API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    req = urllib.request.Request(url)

    with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
        result = json.loads(resp.read().decode())

    models = []
    for item in result.get("models", []):
        raw_name = item.get("name", "")
        # Strip "models/" prefix
        model_id = raw_name.replace("models/", "") if raw_name.startswith("models/") else raw_name
        display_name = item.get("displayName", model_id)
        input_tokens = item.get("inputTokenLimit", 0)
        output_tokens = item.get("outputTokenLimit", 0)
        context = input_tokens + output_tokens if input_tokens or output_tokens else 0

        models.append({
            "id": model_id,
            "name": display_name,
            "free": False,  # Gemini free tier is per-account, not per-model
            "context": context,
        })

    return models


def _list_ollama_models():
    """Fetch locally installed Ollama models."""
    url = "http://localhost:11434/api/tags"
    req = urllib.request.Request(url)

    with urllib.request.urlopen(req, timeout=5, context=_ssl_context()) as resp:
        result = json.loads(resp.read().decode())

    models = []
    for item in result.get("models", result.get("models", [])):
        # Ollama returns {"models": [{"name": "qwen3:1.7b", ...}]} or same structure
        model_id = item.get("name", "")
        models.append({
            "id": model_id,
            "name": model_id,
            "free": True,
            "context": 0,
        })

    if not models:
        return [{"id": "", "name": "No models installed — run 'ollama pull <model>' first", "free": True, "context": 0}]

    return models


# ---------------------------------------------------------------------------
# Settings GET / POST
# ---------------------------------------------------------------------------


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
        "ai_model": "claude" | "gemini" | "ollama" | "openrouter",
        "ollama_model": "qwen3:1.7b",
        "openrouter_model": "google/gemini-2.5-flash:free",
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
            "openrouter_api_key": mask_key(env_dict.get("OPENROUTER_API_KEY")) if env_dict.get("OPENROUTER_API_KEY") else None,
            "has_openrouter_key": bool(env_dict.get("OPENROUTER_API_KEY")),
            "openrouter_model": env_dict.get("OPENROUTER_MODEL", "google/gemini-2.5-flash:free"),
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
        "openrouter_api_key": "sk-...",          (optional, full unmasked value)
        "spotify_client_id": "...",              (optional)
        "spotify_client_secret": "...",          (optional)
        "ai_model": "claude" | "gemini" | "ollama" | "openrouter",  (optional)
        "model_id": "claude-sonnet-4-6-20260219", (optional — the actual model ID)
        "ollama_model": "qwen3:1.7b",            (optional)
        "openrouter_model": "google/gemini-2.5-flash:free", (optional)
        "classify_batch_size": 10,               (optional, 1-20)
        "auto_approve_threshold": 0,             (optional, 0-100)
        "spotify_enrich_enabled": true           (optional, boolean)
    }
    Only sends non-empty values; existing values not provided are preserved.
    """
    try:
        data = request.get_json(silent=True) or {}

        # Load current .env
        env_dict = load_env()

        # Update only provided fields
        if "gemini_api_key" in data and data["gemini_api_key"]:
            env_dict["GEMINI_API_KEY"] = data["gemini_api_key"]

        if "anthropic_api_key" in data and data["anthropic_api_key"]:
            env_dict["ANTHROPIC_API_KEY"] = data["anthropic_api_key"]

        if "openrouter_api_key" in data and data["openrouter_api_key"]:
            env_dict["OPENROUTER_API_KEY"] = data["openrouter_api_key"]

        if "openrouter_model" in data and data["openrouter_model"]:
            env_dict["OPENROUTER_MODEL"] = data["openrouter_model"]

        if "spotify_client_id" in data and data["spotify_client_id"]:
            env_dict["SPOTIFY_CLIENT_ID"] = data["spotify_client_id"]

        if "spotify_client_secret" in data and data["spotify_client_secret"]:
            env_dict["SPOTIFY_CLIENT_SECRET"] = data["spotify_client_secret"]

        if "ai_model" in data and data["ai_model"]:
            if data["ai_model"] in ["claude", "gemini", "ollama", "openrouter"]:
                env_dict["AI_MODEL"] = data["ai_model"]

        # Save model_id to the correct env var based on provider
        if "model_id" in data and data["model_id"]:
            provider = data.get("ai_model", env_dict.get("AI_MODEL", "claude"))
            if provider == "openrouter":
                env_dict["OPENROUTER_MODEL"] = data["model_id"]
            elif provider == "ollama":
                env_dict["OLLAMA_MODEL"] = data["model_id"]
            elif provider == "claude":
                env_dict["ANTHROPIC_MODEL"] = data["model_id"]
            elif provider == "gemini":
                env_dict["GEMINI_MODEL"] = data["model_id"]

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

        # Reload environment variables into the running process
        # This ensures os.getenv() returns the new values immediately
        from dotenv import load_dotenv
        load_dotenv(get_env_path(), override=True)

        return jsonify({"saved": True}), 200

    except Exception as e:
        logger.exception("Error in /api/settings POST")
        return jsonify({"error": "Operation failed. Check server logs."}), 500
