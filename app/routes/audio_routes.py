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

        if not os.access(file_path, os.R_OK):
            return jsonify({"error": "Audio file is not readable"}), 403

        ext = file_path.lower().rsplit('.', 1)[-1]
        mime_map = {
            'mp3': 'audio/mpeg',
            'flac': 'audio/flac',
            'wav': 'audio/wav',
            'm4a': 'audio/mp4',
            'aac': 'audio/aac',
            'ogg': 'audio/ogg',
        }
        mimetype = mime_map.get(ext)
        if not mimetype:
            return jsonify({"error": f"Unsupported audio format: .{ext}"}), 400

        # Send file with conditional=True for range request support (enables seeking)
        return send_file(
            file_path,
            mimetype=mimetype,
            conditional=True,
            as_attachment=False
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
