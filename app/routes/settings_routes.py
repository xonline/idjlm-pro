from flask import Blueprint, jsonify, request
import os
from dotenv import load_dotenv, find_dotenv

bp = Blueprint("settings", __name__, url_prefix="/api/settings")


@bp.route("/", methods=["GET"])
def get_settings():
    """Get current API key status (masked)."""
    load_dotenv(find_dotenv())
    return jsonify({
        "gemini_key": "set" if os.getenv("GEMINI_API_KEY") else "unset",
        "spotify_id": "set" if os.getenv("SPOTIFY_CLIENT_ID") else "unset",
        "spotify_secret": "set" if os.getenv("SPOTIFY_CLIENT_SECRET") else "unset",
    })


@bp.route("/", methods=["POST"])
def update_settings():
    """Update .env file with new API keys."""
    data = request.json or {}
    env_file = find_dotenv() or ".env"

    try:
        env_vars = {}
        if os.path.exists(env_file):
            for line in open(env_file):
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()

        # Update with new values
        if "gemini_key" in data:
            env_vars["GEMINI_API_KEY"] = data["gemini_key"]
        if "spotify_id" in data:
            env_vars["SPOTIFY_CLIENT_ID"] = data["spotify_id"]
        if "spotify_secret" in data:
            env_vars["SPOTIFY_CLIENT_SECRET"] = data["spotify_secret"]

        # Write back
        with open(env_file, "w") as f:
            for k, v in env_vars.items():
                f.write(f"{k}={v}\n")

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
