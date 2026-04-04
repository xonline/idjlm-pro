import os
import json
from flask import Blueprint, request, jsonify

bp = Blueprint("bulk", __name__, url_prefix="/api")


@bp.route("/taxonomy", methods=["GET"])
def get_taxonomy():
    """
    Get full taxonomy.
    GET /api/taxonomy
    """
    try:
        from app import get_taxonomy

        return jsonify(get_taxonomy()), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/taxonomy", methods=["PUT"])
def update_taxonomy():
    """
    Replace entire taxonomy and write to file.
    PUT /api/taxonomy
    body: { "genres": { ... } }
    """
    try:
        from app import get_taxonomy

        data = request.get_json() or {}
        new_taxonomy = data  # Accept full taxonomy object

        if not new_taxonomy:
            return jsonify({"error": "Taxonomy data is required"}), 400

        # Update in-memory taxonomy
        taxonomy = get_taxonomy()
        taxonomy.clear()
        taxonomy.update(new_taxonomy)

        # Write back to taxonomy.json
        taxonomy_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "taxonomy.json"
        )
        with open(taxonomy_path, "w") as f:
            json.dump(taxonomy, f, indent=2)

        return jsonify({"ok": True}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/taxonomy/genre", methods=["POST"])
def add_genre():
    """
    Add a new genre to taxonomy.
    POST /api/taxonomy/genre
    body: { "name": "Cumbia", "description": "...", "subgenres": { "Name": "desc" } }
    """
    try:
        from app import get_taxonomy

        data = request.get_json() or {}
        genre_name = data.get("name", "").strip()
        description = data.get("description", "")
        subgenres = data.get("subgenres", {})

        if not genre_name:
            return jsonify({"error": "Genre name is required"}), 400

        taxonomy = get_taxonomy()

        # Add genre
        if "genres" not in taxonomy:
            taxonomy["genres"] = {}

        taxonomy["genres"][genre_name] = {
            "description": description,
            "subgenres": subgenres
        }

        # Write back to file
        taxonomy_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "taxonomy.json"
        )
        with open(taxonomy_path, "w") as f:
            json.dump(taxonomy, f, indent=2)

        return jsonify(taxonomy), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/taxonomy/genre/<name>", methods=["DELETE"])
def delete_genre(name):
    """
    Remove a genre from taxonomy.
    DELETE /api/taxonomy/genre/<name>
    """
    try:
        from app import get_taxonomy

        taxonomy = get_taxonomy()

        if "genres" not in taxonomy:
            return jsonify({"error": "No genres in taxonomy"}), 404

        if name not in taxonomy["genres"]:
            return jsonify({"error": f"Genre '{name}' not found"}), 404

        del taxonomy["genres"][name]

        # Write back to file
        taxonomy_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "taxonomy.json"
        )
        with open(taxonomy_path, "w") as f:
            json.dump(taxonomy, f, indent=2)

        return jsonify({"ok": True}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/stats", methods=["GET"])
def get_stats():
    """
    Get library statistics.
    GET /api/stats
    """
    try:
        from app import get_track_store

        track_store = get_track_store()
        tracks = list(track_store.values())

        total = len(tracks)
        analyzed = sum(1 for t in tracks if t.analysis_done)
        classified = sum(1 for t in tracks if t.classification_done)
        approved = sum(1 for t in tracks if t.review_status == "approved")
        skipped = sum(1 for t in tracks if t.review_status == "skipped")
        written = sum(1 for t in tracks if t.tags_written)
        errors = sum(1 for t in tracks if t.error)

        return jsonify({
            "total": total,
            "analyzed": analyzed,
            "classified": classified,
            "approved": approved,
            "skipped": skipped,
            "written": written,
            "errors": errors
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
