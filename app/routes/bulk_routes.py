import os
import json
import logging
import platform
from collections import defaultdict
from flask import Blueprint, request, jsonify, send_file, Response
from io import BytesIO

logger = logging.getLogger(__name__)

bp = Blueprint("bulk", __name__, url_prefix="/api")


def _get_taxonomy_write_path() -> str:
    """Return user-writable path for taxonomy.json (never the read-only bundle)."""
    if platform.system() == "Darwin":
        d = os.path.expanduser("~/Library/Application Support/IDJLM Pro")
    else:
        d = os.path.expanduser("~/.idjlm-pro")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "taxonomy.json")


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
        logger.exception(f"Error in bulk routes endpoint")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/taxonomy", methods=["PUT"])
def update_taxonomy():
    """
    Replace entire taxonomy and write to file.
    PUT /api/taxonomy
    body: { "genres": { ... } }
    """
    try:
        from app import get_taxonomy

        data = request.get_json(silent=True) or {}
        new_taxonomy = data  # Accept full taxonomy object

        if not new_taxonomy:
            return jsonify({"error": "Taxonomy data is required"}), 400

        # Update in-memory taxonomy
        taxonomy = get_taxonomy()
        taxonomy.clear()
        taxonomy.update(new_taxonomy)

        # Write back to taxonomy.json (user-writable location)
        with open(_get_taxonomy_write_path(), "w") as f:
            json.dump(taxonomy, f, indent=2)

        return jsonify({"ok": True}), 200

    except Exception as e:
        logger.exception(f"Error in bulk routes endpoint")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/taxonomy/genre", methods=["POST"])
def add_genre():
    """
    Add a new genre to taxonomy.
    POST /api/taxonomy/genre
    body: { "name": "Cumbia", "description": "...", "subgenres": { "Name": "desc" } }
    """
    try:
        from app import get_taxonomy

        data = request.get_json(silent=True) or {}
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

        # Write back to file (user-writable location)
        with open(_get_taxonomy_write_path(), "w") as f:
            json.dump(taxonomy, f, indent=2)

        return jsonify(taxonomy), 200

    except Exception as e:
        logger.exception(f"Error in bulk routes endpoint")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


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

        # Write back to file (user-writable location)
        with open(_get_taxonomy_write_path(), "w") as f:
            json.dump(taxonomy, f, indent=2)

        return jsonify({"ok": True}), 200

    except Exception as e:
        logger.exception(f"Error in bulk routes endpoint")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


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
        logger.exception(f"Error in bulk routes endpoint")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/stats/age", methods=["GET"])
def get_stats_age():
    """
    Get collection age analysis.
    GET /api/stats/age
    """
    try:
        from app import get_track_store, get_taxonomy

        track_store = get_track_store()
        tracks = list(track_store.values())

        # Helper: determine decade label from a year string
        def decade_label(year_str):
            if not year_str:
                return "Unknown"
            try:
                year = int(year_str)
                decade = (year // 10) * 10
                return f"{decade}s"
            except (ValueError, TypeError):
                return "Unknown"

        # Build by_decade
        by_decade = defaultdict(int)
        by_genre_decade = defaultdict(lambda: defaultdict(int))
        years_list = []

        for track in tracks:
            year = track.final_year or track.existing_year or track.spotify_year
            decade = decade_label(year)
            by_decade[decade] += 1

            genre = track.final_genre or "Unknown"
            if decade != "Unknown":
                by_genre_decade[genre][decade] += 1

            if year:
                try:
                    years_list.append(int(year))
                except (ValueError, TypeError):
                    pass

        # Sort decades chronologically
        decade_order = ["Unknown"]
        for d in sorted(by_decade.keys()):
            if d != "Unknown":
                decade_order.append(d)
        by_decade_sorted = {d: by_decade[d] for d in decade_order}

        # Convert by_genre_decade to serializable dict
        by_genre_decade_serializable = {}
        for genre, decade_counts in by_genre_decade.items():
            by_genre_decade_serializable[genre] = dict(decade_counts)

        # Era labels for Salsa and Bachata
        era_labels = {}
        for genre, decade_counts in by_genre_decade.items():
            if genre == "Salsa":
                clasica = sum(decade_counts.get(d, 0) for d in ["1970s", "1980s"])
                romantica = sum(decade_counts.get(d, 0) for d in ["1980s", "1990s", "2000s"])
                moderna = sum(decade_counts.get(d, 0) for d in ["2000s", "2010s", "2020s"])
                if clasica > 0:
                    era_labels["Salsa Clasica (1970s-1980s)"] = clasica
                if romantica > 0:
                    era_labels["Salsa Romantica (1980s-2000s)"] = romantica
                if moderna > 0:
                    era_labels["Salsa Moderna (2000s+)"] = moderna
            elif genre == "Bachata":
                tradicional = sum(decade_counts.get(d, 0) for d in ["1970s", "1980s", "1990s"])
                moderna = sum(decade_counts.get(d, 0) for d in ["2000s", "2010s", "2020s"])
                if tradicional > 0:
                    era_labels["Bachata Tradicional (pre-2000)"] = tradicional
                if moderna > 0:
                    era_labels["Bachata Moderna (2000+)"] = moderna

        # Newest and oldest tracks
        track_year_info = []
        for track in tracks:
            year = track.final_year or track.existing_year or track.spotify_year
            if year:
                try:
                    track_year_info.append({
                        "title": track.display_title,
                        "artist": track.display_artist,
                        "year": int(year),
                        "genre": track.final_genre or "Unknown"
                    })
                except (ValueError, TypeError):
                    pass

        track_year_info.sort(key=lambda x: x["year"])
        newest_tracks = track_year_info[-10:] if track_year_info else []
        oldest_tracks = track_year_info[:10] if track_year_info else []

        # Median year
        median_year = None
        if years_list:
            years_list.sort()
            n = len(years_list)
            if n % 2 == 1:
                median_year = years_list[n // 2]
            else:
                median_year = (years_list[n // 2 - 1] + years_list[n // 2]) // 2

        return jsonify({
            "by_decade": by_decade_sorted,
            "by_genre_decade": by_genre_decade_serializable,
            "era_labels": era_labels,
            "newest_tracks": newest_tracks,
            "oldest_tracks": oldest_tracks,
            "median_year": median_year
        }), 200

    except Exception as e:
        logger.exception(f"Error in stats/age endpoint")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


# ============================================================================
# Taxonomy Templates — Export, Import, Built-in Templates
# ============================================================================

TEMPLATES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "taxonomy_templates.json")


def _load_templates():
    """Load built-in taxonomy templates from JSON file."""
    if os.path.exists(TEMPLATES_PATH):
        with open(TEMPLATES_PATH, "r") as f:
            return json.load(f)
    return {}


@bp.route("/taxonomy/export", methods=["GET"])
def export_taxonomy():
    """
    Export current taxonomy as a downloadable JSON file.
    GET /api/taxonomy/export
    """
    try:
        from app import get_taxonomy

        taxonomy = get_taxonomy()
        output = BytesIO()
        output.write(json.dumps(taxonomy, indent=2).encode("utf-8"))
        output.seek(0)

        return send_file(
            output,
            mimetype="application/json",
            as_attachment=True,
            download_name="idjlm_taxonomy.json"
        )

    except Exception as e:
        logger.exception(f"Error in taxonomy export endpoint")
        return jsonify({"error": "Export failed. Check server logs."}), 500


@bp.route("/taxonomy/import", methods=["POST"])
def import_taxonomy():
    """
    Import a taxonomy JSON file.
    POST /api/taxonomy/import
    body: { "taxonomy": {...}, "merge": true }
    """
    try:
        from app import get_taxonomy

        data = request.get_json(silent=True) or {}
        new_taxonomy = data.get("taxonomy")
        merge = data.get("merge", True)

        if not new_taxonomy:
            return jsonify({"error": "Taxonomy data is required"}), 400

        # Validate structure
        if not isinstance(new_taxonomy, dict):
            return jsonify({"error": "Invalid taxonomy structure: must be an object"}), 400

        for genre_name, genre_data in new_taxonomy.items():
            if not isinstance(genre_data, dict):
                return jsonify({"error": f"Invalid genre '{genre_name}': must be an object"}), 400
            if "description" in genre_data and not isinstance(genre_data["description"], str):
                return jsonify({"error": f"Invalid description for '{genre_name}'"}), 400
            if "subgenres" in genre_data and not isinstance(genre_data["subgenres"], (dict, list)):
                return jsonify({"error": f"Invalid subgenres for '{genre_name}': must be object or array"}), 400

        taxonomy = get_taxonomy()

        if merge:
            # Merge: add new genres/subgenres, don't remove existing
            added_genres = []
            added_subgenres = 0
            for genre_name, genre_data in new_taxonomy.items():
                if genre_name not in taxonomy:
                    taxonomy[genre_name] = genre_data
                    added_genres.append(genre_name)
                    if isinstance(genre_data.get("subgenres"), dict):
                        added_subgenres += len(genre_data["subgenres"])
                    elif isinstance(genre_data.get("subgenres"), list):
                        added_subgenres += len(genre_data["subgenres"])
                else:
                    # Merge subgenres
                    existing_subs = taxonomy[genre_name].get("subgenres", {})
                    new_subs = genre_data.get("subgenres", {})
                    if isinstance(existing_subs, dict) and isinstance(new_subs, dict):
                        for sub_name, sub_desc in new_subs.items():
                            if sub_name not in existing_subs:
                                existing_subs[sub_name] = sub_desc
                                added_subgenres += 1
                    elif isinstance(existing_subs, list) and isinstance(new_subs, (dict, list)):
                        new_items = list(new_subs.keys()) if isinstance(new_subs, dict) else new_subs
                        for item in new_items:
                            if item not in existing_subs:
                                existing_subs.append(item)
                                added_subgenres += 1

            # Write back to file
            from app.routes.bulk_routes import _get_taxonomy_write_path
            with open(_get_taxonomy_write_path(), "w") as f:
                json.dump(taxonomy, f, indent=2)

            return jsonify({
                "ok": True,
                "added_genres": added_genres,
                "added_subgenres": added_subgenres,
                "taxonomy": taxonomy
            }), 200
        else:
            # Replace entire taxonomy
            taxonomy.clear()
            taxonomy.update(new_taxonomy)

            # Write back to file
            from app.routes.bulk_routes import _get_taxonomy_write_path
            with open(_get_taxonomy_write_path(), "w") as f:
                json.dump(taxonomy, f, indent=2)

            return jsonify({
                "ok": True,
                "replaced": True,
                "genre_count": len(taxonomy),
                "taxonomy": taxonomy
            }), 200

    except Exception as e:
        logger.exception(f"Error in taxonomy import endpoint")
        return jsonify({"error": "Import failed. Check server logs."}), 500


@bp.route("/taxonomy/templates", methods=["GET"])
def list_templates():
    """
    List built-in taxonomy templates.
    GET /api/taxonomy/templates
    """
    try:
        templates = _load_templates()
        result = {}
        for name, data in templates.items():
            genre_count = len(data)
            subgenre_count = sum(
                len(v.get("subgenres", [])) if isinstance(v.get("subgenres"), list)
                else len(v.get("subgenres", {})) if isinstance(v.get("subgenres"), dict)
                else 0
                for v in data.values()
            )
            result[name] = {
                "genre_count": genre_count,
                "subgenre_count": subgenre_count,
                "genres": list(data.keys())
            }
        return jsonify(result), 200

    except Exception as e:
        logger.exception(f"Error in taxonomy templates list endpoint")
        return jsonify({"error": "Failed to list templates. Check server logs."}), 500


@bp.route("/taxonomy/templates/<name>/apply", methods=["POST"])
def apply_template(name):
    """
    Apply a built-in taxonomy template.
    POST /api/taxonomy/templates/<name>/apply
    body: { "merge": true } (optional, defaults to true)
    """
    try:
        from app import get_taxonomy

        templates = _load_templates()
        if name not in templates:
            available = list(templates.keys())
            return jsonify({
                "error": f"Template '{name}' not found",
                "available_templates": available
            }), 404

        template_data = templates[name]
        req_data = request.get_json(silent=True) or {}
        merge = req_data.get("merge", True)

        taxonomy = get_taxonomy()

        # Calculate what will be added
        added_genres = []
        added_subgenres = 0
        for genre_name, genre_data in template_data.items():
            if merge and genre_name in taxonomy:
                existing_subs = taxonomy[genre_name].get("subgenres", {})
                new_subs = genre_data.get("subgenres", {})
                if isinstance(existing_subs, dict) and isinstance(new_subs, dict):
                    for sub_name in new_subs:
                        if sub_name not in existing_subs:
                            added_subgenres += 1
                elif isinstance(existing_subs, list) and isinstance(new_subs, (dict, list)):
                    new_items = list(new_subs.keys()) if isinstance(new_subs, dict) else new_subs
                    for item in new_items:
                        if item not in existing_subs:
                            added_subgenres += 1
            else:
                added_genres.append(genre_name)
                if isinstance(genre_data.get("subgenres"), dict):
                    added_subgenres += len(genre_data["subgenres"])
                elif isinstance(genre_data.get("subgenres"), list):
                    added_subgenres += len(genre_data["subgenres"])

        if not merge:
            taxonomy.clear()

        # Apply template
        for genre_name, genre_data in template_data.items():
            if merge and genre_name in taxonomy:
                existing_subs = taxonomy[genre_name].get("subgenres", {})
                new_subs = genre_data.get("subgenres", {})
                if isinstance(existing_subs, dict) and isinstance(new_subs, dict):
                    for sub_name, sub_desc in new_subs.items():
                        if sub_name not in existing_subs:
                            existing_subs[sub_name] = sub_desc
                elif isinstance(existing_subs, list) and isinstance(new_subs, (dict, list)):
                    new_items = list(new_subs.keys()) if isinstance(new_subs, dict) else new_subs
                    for item in new_items:
                        if item not in existing_subs:
                            existing_subs.append(item)
            else:
                taxonomy[genre_name] = genre_data

        # Write back to file
        with open(_get_taxonomy_write_path(), "w") as f:
            json.dump(taxonomy, f, indent=2)

        return jsonify({
            "ok": True,
            "template": name,
            "added_genres": added_genres,
            "added_subgenres": added_subgenres,
            "taxonomy": taxonomy
        }), 200

    except Exception as e:
        logger.exception(f"Error in apply template endpoint")
        return jsonify({"error": "Failed to apply template. Check server logs."}), 500


@bp.route("/taxonomy/import-onetagger", methods=["POST"])
def import_onetagger():
    """
    Import genre mappings from OneTagger settings.json.
    OneTagger stores genre mappings as a dict of source_genre -> target_genre.
    We convert these into IDJLM taxonomy sub-genres.

    POST /api/taxonomy/import-onetagger
    body: { "settings": { ... }, "merge": true }
      - settings: The full OneTagger settings.json content
      - merge: if true, add to existing taxonomy; if false, replace

    OneTagger genre mapping format in settings.json:
    {
      "genre": { "Salsa": { "target": "Latin", "target_subgenre": "Salsa" }, ... },
      "subgenre": { "Salsa Romantica": { "target": "Latin", "target_subgenre": "Salsa" }, ... }
    }
    """
    try:
        from app import get_taxonomy

        data = request.get_json(silent=True) or {}
        settings = data.get("settings", {})
        do_merge = data.get("merge", True)

        if not settings:
            return jsonify({"error": "OneTagger settings JSON is required"}), 400

        taxonomy = get_taxonomy()

        # Build new genres from OneTagger mappings
        new_genres = {}
        mappings_found = 0

        # Process genre mappings
        genre_mappings = settings.get("genre", {})
        for source_genre, mapping in genre_mappings.items():
            if not isinstance(mapping, dict):
                continue
            target = mapping.get("target", source_genre)
            target_sub = mapping.get("target_subgenre", "")
            mappings_found += 1

            if target not in new_genres:
                new_genres[target] = {"description": f"Imported from OneTagger", "subgenres": {}}
            if target_sub and target_sub not in new_genres[target]["subgenres"]:
                new_genres[target]["subgenres"][target_sub] = f"Mapped from '{source_genre}'"

        # Process subgenre mappings
        subgenre_mappings = settings.get("subgenre", {})
        for source_sub, mapping in subgenre_mappings.items():
            if not isinstance(mapping, dict):
                continue
            target = mapping.get("target", "Unknown")
            target_sub = mapping.get("target_subgenre", source_sub)
            mappings_found += 1

            if target not in new_genres:
                new_genres[target] = {"description": f"Imported from OneTagger", "subgenres": {}}
            if target_sub and target_sub not in new_genres[target]["subgenres"]:
                new_genres[target]["subgenres"][target_sub] = f"Mapped from '{source_sub}'"

        if not new_genres:
            return jsonify({"error": "No genre mappings found in OneTagger settings", "mappings_found": mappings_found}), 400

        if do_merge:
            # Merge into existing taxonomy
            for genre_name, genre_data in new_genres.items():
                if genre_name in taxonomy.get("genres", {}):
                    # Merge subgenres
                    existing_subs = taxonomy["genres"][genre_name].get("subgenres", {})
                    new_subs = genre_data.get("subgenres", {})
                    if isinstance(existing_subs, dict) and isinstance(new_subs, dict):
                        for sub_name, sub_desc in new_subs.items():
                            if sub_name not in existing_subs:
                                existing_subs[sub_name] = sub_desc
                else:
                    taxonomy["genres"][genre_name] = genre_data
        else:
            # Replace taxonomy with imported data
            taxonomy["genres"] = new_genres

        # Write back to file
        with open(_get_taxonomy_write_path(), "w") as f:
            json.dump(taxonomy, f, indent=2)

        genre_count = len(new_genres)
        subgenre_count = sum(len(g.get("subgenres", {})) for g in new_genres.values())

        return jsonify({
            "ok": True,
            "mappings_found": mappings_found,
            "genres_added": genre_count,
            "subgenres_added": subgenre_count,
            "taxonomy": taxonomy
        }), 200

    except Exception as e:
        logger.exception(f"Error in OneTagger import endpoint")
        return jsonify({"error": f"Failed to import OneTagger settings: {str(e)}"}), 500
