import os
import ssl
import json
import logging
import subprocess
import platform
import urllib.request
import urllib.error
import threading
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("version", __name__, url_prefix="/api/version")

GITHUB_RELEASES_URL = "https://api.github.com/repos/xonline/idjlm-pro/releases/latest"
GITHUB_REPO_URL = "https://github.com/xonline/idjlm-pro"


def _ssl_context():
    """Auto-fix SSL certs using certifi (macOS Python bundles don't include root CAs)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _get_base_dir():
    """Get the base directory, handling PyInstaller bundles."""
    import sys
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def _read_version():
    """Read the current version from the VERSION file."""
    base = _get_base_dir()
    try:
        with open(os.path.join(base, "VERSION")) as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


def _get_git_commit():
    """Get the short git commit hash if available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=_get_base_dir()
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _parse_semver(version_str):
    """Parse a semver string like 'v2.7.0' or '2.7.0' into a tuple of ints."""
    v = version_str.strip().lstrip("v")
    parts = v.split(".")
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except (ValueError, TypeError):
            result.append(0)
    while len(result) < 3:
        result.append(0)
    return tuple(result[:3])


def _is_newer(latest, current):
    """Return True if latest semver > current semver."""
    return _parse_semver(latest) > _parse_semver(current)


# In-memory download state: { "url": ..., "path": ..., "size": ..., "downloaded": ..., "error": ..., "done": ... }
_download_state = {}
_download_lock = threading.Lock()


def _download_file(url, dest_dir):
    """Download a file in a background thread, updating shared state."""
    global _download_state
    try:
        filename = url.rsplit("/", 1)[-1]
        if not filename:
            filename = "IDJLM-Pro-update.dmg"
        dest_path = os.path.join(dest_dir, filename)

        req = urllib.request.Request(url)
        req.add_header("User-Agent", "IDJLM-Pro-UpdateChecker/1.0")

        with urllib.request.urlopen(req, timeout=300, context=_ssl_context()) as resp:
            total_size = resp.headers.get("Content-Length")
            total_size = int(total_size) if total_size else None

            with open(dest_path, "wb") as f:
                downloaded = 0
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    with _download_lock:
                        _download_state["downloaded"] = downloaded
                        _download_state["size"] = total_size

        with _download_lock:
            _download_state["done"] = True
            _download_state["path"] = dest_path
            _download_state["size"] = os.path.getsize(dest_path)

    except Exception as e:
        logger.exception("Download failed")
        with _download_lock:
            _download_state["error"] = str(e)
            _download_state["done"] = True


@bp.route("", methods=["GET"])
def get_version():
    """GET /api/version — returns current version and optional commit hash."""
    version = _read_version()
    commit = _get_git_commit()
    result = {"version": version}
    if commit:
        result["commit"] = commit
    return jsonify(result), 200


@bp.route("/check", methods=["GET"])
def check_for_updates():
    """GET /api/version/check — check GitHub for latest release."""
    current = _read_version()

    # On non-macOS, only offer git-pull (no .dmg updates)
    is_macos = platform.system() == "Darwin"

    try:
        req = urllib.request.Request(GITHUB_RELEASES_URL)
        req.add_header("User-Agent", "IDJLM-Pro-UpdateChecker/1.0")
        req.add_header("Accept", "application/vnd.github.v3+json")

        with urllib.request.urlopen(req, timeout=10, context=_ssl_context()) as resp:
            data = json.loads(resp.read().decode())

        latest_tag = data.get("tag_name", "")
        # Strip leading 'v' for comparison
        latest_version = latest_tag.lstrip("v") if latest_tag else current
        published_at = data.get("published_at", "")
        release_notes = data.get("body", "") or "No release notes available."

        # Find macOS .dmg asset if on macOS
        download_url = None
        assets = data.get("assets", [])
        for asset in assets:
            name = asset.get("name", "")
            if is_macos and (name.endswith(".dmg") or "macOS" in name):
                download_url = asset.get("browser_download_url")
                break

        # Fallback: use the HTML URL for the release
        if not download_url:
            download_url = data.get("html_url", GITHUB_REPO_URL)

        has_update = _is_newer(latest_version, current)

        return jsonify({
            "current": current,
            "latest": latest_version,
            "has_update": has_update,
            "release_notes": release_notes,
            "download_url": download_url,
            "published_at": published_at,
            "is_macos": is_macos,
        }), 200

    except urllib.error.HTTPError as e:
        status_code = e.code
        error_body = ""
        try:
            error_body = e.read().decode()
        except Exception:
            pass
        error_msg = f"GitHub API error ({status_code})"
        if status_code == 403:
            error_msg = "GitHub API rate limit exceeded. Try again in a few minutes."
        elif status_code == 404:
            error_msg = "No releases found on GitHub."
        logger.warning("Check updates HTTP error %d: %s", status_code, error_body)
        return jsonify({
            "current": current,
            "latest": None,
            "has_update": False,
            "error": error_msg,
            "is_macos": is_macos,
        }), 200

    except urllib.error.URLError as e:
        msg = str(e.reason) if hasattr(e, "reason") else str(e)
        logger.warning("Check updates URL error: %s", msg)
        return jsonify({
            "current": current,
            "latest": None,
            "has_update": False,
            "error": f"Network error: {msg}",
            "is_macos": is_macos,
        }), 200

    except Exception as e:
        logger.exception("Check updates error")
        return jsonify({
            "current": current,
            "latest": None,
            "has_update": False,
            "error": str(e),
            "is_macos": is_macos,
        }), 200


@bp.route("/download", methods=["POST"])
def download_update():
    """POST /api/version/download — start downloading a .dmg update."""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "url is required"}), 400

    # Check if we're already downloading
    with _download_lock:
        if _download_state and not _download_state.get("done"):
            return jsonify({
                "downloading": True,
                "path": _download_state.get("path"),
                "downloaded": _download_state.get("downloaded", 0),
                "size": _download_state.get("size"),
                "done": False,
            }), 200

    # Start download in background thread
    downloads_dir = os.path.expanduser("~/Downloads")
    os.makedirs(downloads_dir, exist_ok=True)

    with _download_lock:
        _download_state.clear()
        _download_state["url"] = url
        _download_state["done"] = False
        _download_state["downloaded"] = 0
        _download_state["size"] = None
        _download_state["error"] = None
        _download_state["path"] = None

    t = threading.Thread(target=_download_file, args=(url, downloads_dir), daemon=True)
    t.start()

    return jsonify({
        "downloading": True,
        "done": False,
    }), 200


@bp.route("/download/status", methods=["GET"])
def download_status():
    """GET /api/version/download/status — poll for download progress."""
    with _download_lock:
        if not _download_state:
            return jsonify({"idle": True}), 200

        state = dict(_download_state)

    response = {
        "done": state.get("done", False),
        "downloaded": state.get("downloaded", 0),
        "size": state.get("size"),
        "path": state.get("path"),
    }
    if state.get("error"):
        response["error"] = state["error"]
    if not state.get("done"):
        response["downloading"] = True

    return jsonify(response), 200


@bp.route("/open-dmg", methods=["POST"])
def open_dmg():
    """POST /api/version/open-dmg — open a downloaded .dmg file."""
    data = request.get_json(silent=True) or {}
    path = data.get("path", "")
    if not path:
        return jsonify({"error": "path is required"}), 400

    if not os.path.exists(path):
        return jsonify({"error": f"File not found: {path}"}), 404

    try:
        subprocess.run(["open", path], timeout=10, check=True)
        return jsonify({"opened": True, "path": path}), 200
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Opening DMG timed out"}), 500
    except Exception as e:
        logger.exception("Failed to open DMG")
        return jsonify({"error": f"Failed to open DMG: {str(e)}"}), 500


@bp.route("/git-pull", methods=["GET"])
def git_pull():
    """GET /api/version/git-pull — run git pull for source installs."""
    try:
        result = subprocess.run(
            ["git", "pull"],
            capture_output=True, text=True, timeout=60,
            cwd=_get_base_dir()
        )
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "output": result.stdout.strip() or "Already up to date.",
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": result.stderr.strip() or "git pull failed",
                "output": result.stdout.strip(),
            }), 200

    except subprocess.TimeoutExpired:
        return jsonify({"error": "git pull timed out"}), 500
    except FileNotFoundError:
        return jsonify({"error": "git is not installed"}), 500
    except Exception as e:
        logger.exception("git pull error")
        return jsonify({"error": f"git pull failed: {str(e)}"}), 500
