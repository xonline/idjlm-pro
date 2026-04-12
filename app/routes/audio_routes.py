import os
from flask import Blueprint, send_file, jsonify, request
from app import get_current_folder_path

bp = Blueprint("audio", __name__, url_prefix="/api")


@bp.route("/audio", methods=["GET"])
def serve_audio():
    """
    Serve MP3 file with range request support for HTML5 audio seeking.
    GET /api/audio?path=/absolute/path/to/file.mp3
    Security: file must be within the current music folder.
    """
    try:
        file_path = request.args.get("path", "")
        if not file_path:
            return jsonify({"error": "Missing path parameter"}), 400
        # Ensure absolute path and normalize
        file_path = os.path.abspath(file_path)

        # Security: restrict to the current music folder
        music_folder = get_current_folder_path()
        if music_folder:
            real_folder = os.path.realpath(music_folder)
            real_file = os.path.realpath(file_path)
            if not real_file.startswith(real_folder + os.sep) and real_file != real_folder:
                return jsonify({"error": "Access denied: file outside music folder"}), 403

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
