import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("tag", __name__, url_prefix="/api")


def _get_tags_from_track(track) -> dict:
    """Get custom_tags dict from a track, ensuring it's a dict."""
    tags = getattr(track, 'custom_tags', None)
    return dict(tags) if tags else {}


@bp.route("/tags", methods=["GET"])
def list_tag_keys():
    """
    List all custom tag keys used across the library, with per-key counts.
    GET /api/tags
    """
    try:
        from app import get_track_store
        track_store = get_track_store()

        key_counts = {}
        for track in track_store.values():
            for key in _get_tags_from_track(track):
                key_counts[key] = key_counts.get(key, 0) + 1

        return jsonify({
            "keys": sorted(key_counts.keys()),
            "counts": key_counts,
            "total_tracks_with_tags": sum(1 for t in track_store.values() if _get_tags_from_track(t)),
        }), 200

    except Exception as e:
        logger.exception("Error in /api/tags GET")
        return jsonify({"error": str(e)}), 500


@bp.route("/tags/<key>", methods=["GET"])
def get_tracks_by_tag(key):
    """
    Get all tracks that have a specific custom tag key, optionally filtered by value.
    GET /api/tags/<key>?value=something
    """
    try:
        from app import get_track_store
        track_store = get_track_store()

        filter_value = request.args.get("value", "").strip() or None

        matched = []
        for file_path, track in track_store.items():
            tags = _get_tags_from_track(track)
            if key in tags:
                if filter_value is None or tags[key] == filter_value:
                    matched.append(track)

        return jsonify({
            "tracks": [t.to_dict() for t in matched],
            "count": len(matched),
            "key": key,
            "value": filter_value,
        }), 200

    except Exception as e:
        logger.exception("Error in /api/tags/%s GET", key)
        return jsonify({"error": str(e)}), 500


@bp.route("/tracks/<path:file_path>/tags", methods=["GET"])
def get_track_tags(file_path):
    """Get custom tags for a single track."""
    try:
        from app import get_track_store
        track_store = get_track_store()

        if file_path not in track_store:
            return jsonify({"error": "Track not found"}), 404

        track = track_store[file_path]
        return jsonify({"custom_tags": _get_tags_from_track(track)}), 200

    except Exception as e:
        logger.exception("Error in /api/tracks/%s/tags GET", file_path)
        return jsonify({"error": str(e)}), 500


@bp.route("/tracks/<path:file_path>/tags", methods=["PUT"])
def set_track_tag(file_path):
    """
    Set one or more custom tags on a track (upsert).
    PUT /api/tracks/<file_path>/tags
    body: { "key": "MyTag", "value": "MyValue" }
      or: { "tags": { "Key1": "Val1", "Key2": "Val2" } }
    """
    try:
        from app import get_track_store
        track_store = get_track_store()

        if file_path not in track_store:
            return jsonify({"error": "Track not found"}), 404

        data = request.get_json(silent=True) or {}
        track = track_store[file_path]

        if "tags" in data:
            # Bulk upsert
            for k, v in data["tags"].items():
                if not isinstance(k, str) or not k.strip():
                    return jsonify({"error": "Tag key must be a non-empty string"}), 400
                if v is not None and not isinstance(v, str):
                    return jsonify({"error": "Tag value must be a string or null"}), 400
            for k, v in data["tags"].items():
                k = k.strip()
                if v is None:
                    track.custom_tags.pop(k, None)
                else:
                    track.custom_tags[k] = v.strip() if v.strip() else None
        elif "key" in data:
            key = data["key"]
            if not isinstance(key, str) or not key.strip():
                return jsonify({"error": "Tag key must be a non-empty string"}), 400
            value = data.get("value")
            key = key.strip()
            if value is None or (isinstance(value, str) and not value.strip()):
                track.custom_tags.pop(key, None)
            else:
                track.custom_tags[key] = str(value).strip()
        else:
            return jsonify({"error": "Provide 'key' + 'value' or 'tags' object"}), 400

        return jsonify({"custom_tags": dict(track.custom_tags)}), 200

    except Exception as e:
        logger.exception("Error in /api/tracks/%s/tags PUT", file_path)
        return jsonify({"error": str(e)}), 500


@bp.route("/tracks/<path:file_path>/tags/<key>", methods=["DELETE"])
def delete_track_tag(file_path, key):
    """Remove a specific custom tag from a track."""
    try:
        from app import get_track_store
        track_store = get_track_store()

        if file_path not in track_store:
            return jsonify({"error": "Track not found"}), 404

        track = track_store[file_path]
        removed = track.custom_tags.pop(key, None)

        if removed is None:
            return jsonify({"error": "Tag not found"}), 404

        return jsonify({"custom_tags": dict(track.custom_tags), "removed": key}), 200

    except Exception as e:
        logger.exception("Error in /api/tracks/%s/tags/%s DELETE", file_path, key)
        return jsonify({"error": str(e)}), 500
