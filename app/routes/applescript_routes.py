import subprocess
import sys
import os
from flask import Blueprint, jsonify
import io

bp = Blueprint("applescript", __name__, url_prefix="/api")

APPLESCRIPT = '''
tell application "Music"
    refresh
end tell
'''


@bp.route("/sync/apple-music", methods=["POST"])
def sync_apple_music():
    """Trigger Apple Music library refresh. Mac only."""
    if sys.platform != "darwin":
        return jsonify({
            "success": False,
            "message": "Apple Music sync only available on macOS",
            "script": APPLESCRIPT.strip()
        }), 200  # Not an error — just unavailable

    try:
        result = subprocess.run(
            ["osascript", "-e", APPLESCRIPT],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return jsonify({"success": True, "message": "Apple Music library refreshed"}), 200
        else:
            return jsonify({"success": False, "message": result.stderr.strip()}), 200
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "message": "Apple Music sync timed out"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@bp.route("/sync/apple-music/script", methods=["GET"])
def download_applescript():
    """Download the AppleScript for manual execution on Mac."""
    from flask import send_file

    return send_file(
        io.BytesIO(APPLESCRIPT.strip().encode()),
        mimetype="text/plain",
        as_attachment=True,
        download_name="refresh-apple-music.applescript"
    )
