import os
from flask import Blueprint, send_file, jsonify, request

bp = Blueprint("audio", __name__, url_prefix="/api")


@bp.route("/audio", methods=["GET"])
def serve_audio():
    """
    Serve MP3 file with range request support for HTML5 audio seeking.
    GET /api/audio?path=/absolute/path/to/file.mp3
    """
    try:
        file_path = request.args.get("path", "")
        if not file_path:
            return jsonify({"error": "Missing path parameter"}), 400
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
