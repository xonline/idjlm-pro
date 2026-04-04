import os
from flask import Blueprint, send_file, jsonify

bp = Blueprint("audio", __name__, url_prefix="/api")


@bp.route("/audio/<path:file_path>", methods=["GET"])
def serve_audio(file_path):
    """
    Serve MP3 file with range request support for HTML5 audio seeking.
    GET /api/audio/<path:file_path>
    """
    try:
        # Ensure absolute path and normalize
        file_path = os.path.abspath(file_path)

        if not os.path.exists(file_path):
            return jsonify({"error": "Audio file not found"}), 404

        if not os.path.isfile(file_path):
            return jsonify({"error": "Path is not a file"}), 400

        if not file_path.lower().endswith('.mp3'):
            return jsonify({"error": "Only MP3 files are supported"}), 400

        if not os.access(file_path, os.R_OK):
            return jsonify({"error": "Audio file is not readable"}), 403

        # Send file with conditional=True for range request support
        return send_file(
            file_path,
            mimetype="audio/mpeg",
            conditional=True,
            as_attachment=False
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
