"""Flask sidecar entry point for the Tauri desktop application."""
import os

from dotenv import load_dotenv
import platform as _platform

# Installed builds keep provider settings in the user-writable application
# directory. A Tauri sidecar never reads a bundle-relative .env file.
if _platform.system() == "Darwin":
    _user_env = os.path.expanduser("~/Library/Application Support/IDJLM Pro/.env")
else:
    _user_env = os.path.expanduser("~/.idjlm-pro/.env")

if os.path.exists(_user_env):
    load_dotenv(_user_env)

from app import create_app


PORT = int(os.getenv("FLASK_PORT", "5050"))


if __name__ == "__main__":
    create_app().run(port=PORT, debug=False, use_reloader=False, threaded=True)
