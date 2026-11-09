"""Flask sidecar entry point for the Tauri desktop application."""
import os
import sys


def _verify_audio_runtime() -> int:
    """Read-only frozen-sidecar check; never downloads model weights."""
    import soundfile
    import torch
    from transformers import AutoProcessor, ClapModel
    from app.services.audio_classification import ModelRegistry

    spec = ModelRegistry().get()
    assert spec.adapter == "transformers_clap"
    assert spec.required_files
    assert torch.__version__ and soundfile.__version__
    assert AutoProcessor and ClapModel
    print(f"audio runtime ready: {spec.id}@{spec.revision} torch={torch.__version__}")
    return 0


# Keep this before dotenv/app creation: build verification must neither read
# user configuration nor create an app data directory.
if "--verify-audio-runtime" in sys.argv:
    raise SystemExit(_verify_audio_runtime())

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
