"""Flask sidecar entry point for the Tauri desktop application."""

import math
import os
import sys
import tempfile
import wave
from pathlib import Path


if __name__ == "__main__":
    # Must happen before verifier dispatch, dotenv, or application imports.
    # Frozen spawn workers exit here instead of starting a second sidecar.
    import multiprocessing

    multiprocessing.freeze_support()


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


def _verify_analyzer_runtime() -> int:
    """Exercise the legacy spawned analyzer with disposable WAV fixtures."""
    root = Path(tempfile.mkdtemp(prefix="idjlm-analyzer-runtime-"))
    os.environ["IDJLM_USER_DATA_DIR"] = str(root / "state")
    os.environ["NUMBA_CACHE_DIR"] = str(root / "numba-cache")

    sample_rate = 22_050
    paths = []
    for index, frequency in enumerate((120.0, 130.0)):
        path = root / f"synthetic-{index}.wav"
        frames = bytearray()
        for sample in range(sample_rate * 2):
            value = int(
                10_000 * math.sin(2 * math.pi * frequency * sample / sample_rate)
            )
            frames.extend(value.to_bytes(2, "little", signed=True))
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(bytes(frames))
        paths.append(path)

    from app.models.track import Track
    from app.services.analyzer import analyze_tracks_batch

    tracks = {
        str(path): Track(
            file_path=str(path), filename=path.name, existing_genre="Salsa"
        )
        for path in paths
    }
    analyzed, errors = analyze_tracks_batch(list(tracks), tracks)
    if analyzed != len(paths) or errors:
        raise RuntimeError(
            f"analyzer smoke failed: analyzed={analyzed}, errors={errors}"
        )
    for track in tracks.values():
        if not (
            track.analysis_done
            and track.duration is not None
            and track.duration > 0
            and track.raw_rms is not None
            and math.isfinite(track.raw_rms)
            and track.raw_rms > 0
            and track.waveform_data
        ):
            raise RuntimeError(f"analyzer smoke returned incomplete result: {track.filename}")
    print(f"analyzer runtime ready: {analyzed} synthetic tracks")
    return 0


# Keep this before dotenv/app creation: build verification must neither read
# user configuration nor create an app data directory.
if __name__ == "__main__" and "--verify-audio-runtime" in sys.argv:
    raise SystemExit(_verify_audio_runtime())
if __name__ == "__main__" and "--verify-analyzer-runtime" in sys.argv:
    raise SystemExit(_verify_analyzer_runtime())


def _run_server() -> None:
    """Load user settings and start Flask only in the sidecar parent process."""
    import platform

    from dotenv import load_dotenv

    # Installed builds keep provider settings in the user-writable application
    # directory. A Tauri sidecar never reads a bundle-relative .env file. An
    # explicit data-dir override is used by isolated tests and runtime verifiers.
    override_data_dir = os.environ.get("IDJLM_USER_DATA_DIR")
    if override_data_dir:
        user_env = os.path.join(
            os.path.abspath(os.path.expanduser(override_data_dir)), ".env"
        )
    elif platform.system() == "Darwin":
        user_env = os.path.expanduser("~/Library/Application Support/IDJLM Pro/.env")
    else:
        user_env = os.path.expanduser("~/.idjlm-pro/.env")

    if os.path.exists(user_env):
        load_dotenv(user_env)

    from app import create_app

    port = int(os.getenv("FLASK_PORT", "5050"))
    create_app().run(port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    _run_server()
