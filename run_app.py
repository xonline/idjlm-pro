"""Flask sidecar entry point for the Tauri desktop application."""

import math
import os
import platform
import errno
import socket
import sys
import tempfile
import json
import threading
import time
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

    ready_file = os.environ.get("IDJLM_SIDECAR_READY_FILE")
    ready_token = os.environ.get("IDJLM_SIDECAR_READY_TOKEN")
    if bool(ready_file) != bool(ready_token):
        raise RuntimeError("desktop sidecar readiness configuration is incomplete")
    try:
        _acquire_desktop_instance_lock()
    except RuntimeError as error:
        if ready_file and ready_token:
            _publish_sidecar_failure(Path(ready_file), ready_token, str(error))
        raise

    from app import create_app
    from werkzeug.serving import make_server

    host = "127.0.0.1"
    port = int(os.getenv("FLASK_PORT", "5050"))
    app = create_app()

    # The desktop wrapper passes both values per launch.  Publishing only
    # after Werkzeug has bound its socket prevents another local listener
    # from being mistaken for our sidecar.
    try:
        server = _make_desktop_server(app, port, make_server)
    except RuntimeError as error:
        if ready_file and ready_token:
            _publish_sidecar_failure(Path(ready_file), ready_token, str(error))
        raise
    launch_mode = "primary" if server.server_port == 5050 else "fallback"
    os.environ["IDJLM_DESKTOP_LAUNCH_MODE"] = launch_mode
    if ready_file and ready_token:
        _publish_sidecar_ready(Path(ready_file), ready_token, server.server_port, launch_mode)
    _watch_desktop_parent()
    server.serve_forever()


_desktop_instance_lock = None


class _DesktopInstanceLock:
    def __init__(self, handle):
        self.handle = handle

    def release(self) -> None:
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()


def _desktop_data_dir() -> Path:
    override = os.environ.get("IDJLM_USER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if platform.system() == "Darwin":
        return Path("~/Library/Application Support/IDJLM Pro").expanduser()
    return Path("~/.idjlm-pro").expanduser()


def _acquire_desktop_instance_lock() -> None:
    """Prevent two packaged sidecars recovering or writing one library."""
    global _desktop_instance_lock
    if os.environ.get("IDJLM_DESKTOP_SAME_ORIGIN") != "1" or _desktop_instance_lock:
        return
    directory = _desktop_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    handle = (directory / ".desktop-instance.lock").open("a+")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            handle.write("0")
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        handle.close()
        raise RuntimeError(
            "Another IDJLM Pro desktop window is already using this library. "
            "Close it before relaunching."
        ) from error
    _desktop_instance_lock = _DesktopInstanceLock(handle)


def _open_loopback_listener(port: int) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", port))
        listener.listen()
        return listener
    except BaseException:
        listener.close()
        raise


def _is_idjlm_listener(port: int) -> bool:
    """Read-only identity check for a listener that won the bind race."""
    import urllib.error
    import urllib.request

    def get(path: str):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=0.35) as response:
                return json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            return None

    version = get("/api/version")
    if not isinstance(version, dict):
        return False
    if version.get("product") == "idjlm-pro":
        return True
    number = version.get("version")
    if not isinstance(number, str) or not all(part.isdigit() and part for part in number.split(".")):
        return False
    health = get("/api/health")
    return isinstance(health, dict) and health.get("status") == "ok" and {"taxonomy_loaded", "tracks_loaded"}.issubset(health)


def _make_desktop_server(app, requested_port: int, make_server):
    """Bind first so the 5050 preflight-to-bind race has a safe fallback."""
    try:
        listener = _open_loopback_listener(requested_port)
    except OSError as error:
        if error.errno != errno.EADDRINUSE or requested_port != 5050:
            raise
        if _is_idjlm_listener(requested_port):
            raise RuntimeError("Another IDJLM Pro desktop window is already using this library. Close it before relaunching.") from error
        listener = _open_loopback_listener(0)
    try:
        return make_server("127.0.0.1", listener.getsockname()[1], app, threaded=True, fd=listener.fileno())
    finally:
        listener.close()


def _publish_sidecar_ready(path: Path, token: str, port: int, mode: str) -> None:
    """Atomically publish the exact socket bound by this sidecar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps({"version": 1, "token": token, "port": port, "mode": mode}),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _publish_sidecar_failure(path: Path, token: str, error: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps({"version": 1, "token": token, "error": error}),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _parent_is_alive(parent_pid: int) -> bool:
    if parent_pid <= 0:
        return False
    try:
        os.kill(parent_pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _watch_desktop_parent() -> None:
    """Let a PyInstaller child exit if its owning desktop wrapper disappears."""
    raw_parent_pid = os.environ.get("IDJLM_PARENT_PID")
    if not raw_parent_pid or os.name == "nt":
        return
    try:
        parent_pid = int(raw_parent_pid)
    except ValueError:
        return

    def watch() -> None:
        while _parent_is_alive(parent_pid):
            time.sleep(0.5)
        # PyInstaller onefile can have a bootloader parent and a Python child.
        # Exiting this child lets the bootloader unwind instead of orphaning a
        # listener after its Tauri owner has gone away.
        os._exit(0)

    threading.Thread(target=watch, name="idjlm-parent-watch", daemon=True).start()


if __name__ == "__main__":
    _run_server()
