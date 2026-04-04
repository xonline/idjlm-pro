from flask import Blueprint, jsonify, request
import json

bp = Blueprint("bulk", __name__, url_prefix="/api/bulk")


@bp.route("/taxonomy", methods=["GET"])
def get_taxonomy():
    """Get full taxonomy."""
    from app import get_taxonomy
    return jsonify(get_taxonomy())


@bp.route("/taxonomy/<genre>", methods=["PUT"])
def update_genre(genre):
    """Update genre definition."""
    from app import get_taxonomy

    taxonomy = get_taxonomy()
    data = request.json or {}
    found = False
    for g in taxonomy.get("genres", []):
        if g["name"] == genre:
            g.update(data)
            found = True
            break
    return jsonify({"success": found})


@bp.route("/taxonomy", methods=["POST"])
def add_genre():
    """Add new genre."""
    from app import get_taxonomy

    taxonomy = get_taxonomy()
    data = request.json or {}
    if "name" in data:
        if not any(g["name"] == data["name"] for g in taxonomy.get("genres", [])):
            taxonomy.setdefault("genres", []).append(data)
            return jsonify({"success": True}), 201
    return jsonify({"success": False}), 400


@bp.route("/taxonomy/<genre>", methods=["DELETE"])
def delete_genre(genre):
    """Delete genre."""
    from app import get_taxonomy

    taxonomy = get_taxonomy()
    original_len = len(taxonomy.get("genres", []))
    taxonomy["genres"] = [g for g in taxonomy.get("genres", []) if g["name"] != genre]
    return jsonify({"success": len(taxonomy["genres"]) < original_len})


@bp.route("/stats", methods=["GET"])
def get_stats():
    """Get track statistics."""
    from app import get_track_store

    track_store = get_track_store()
    tracks = list(track_store.values())
    return jsonify({
        "total": len(tracks),
        "analyzed": len([t for t in tracks if t.bpm]),
        "classified": len([t for t in tracks if t.classified_genre]),
        "approved": len([t for t in tracks if t.approved]),
    })
