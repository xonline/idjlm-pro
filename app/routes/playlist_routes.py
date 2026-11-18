"""
Playlist Management: named playlists with filter-based track selection and M3U export.
Persisted in the user-data SQLite document store, never a project-root file.
"""

import io
import os
from datetime import datetime, timezone
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file

from app.services.json_store import JsonStore
from app.utils.paths import user_data_path

bp = Blueprint("playlists", __name__, url_prefix="/api")


def playlists_storage_path() -> str:
    """Return the isolated user-data SQLite path used for playlists."""
    return user_data_path("tracks.db")


def _playlists_store() -> JsonStore:
    store = JsonStore("playlists")
    # Keep a one-time upgrade path for normal source-tree installs without
    # letting explicitly isolated data directories probe project-root files.
    if not os.environ.get("IDJLM_USER_DATA_DIR"):
        store.migrate_from_json(
            str(Path(__file__).resolve().parents[2] / "playlists.json")
        )
    return store


def _load_playlists():
    data = _playlists_store().get()
    if not isinstance(data, dict):
        return {"playlists": []}
    return {
        "playlists": data.get("playlists")
        if isinstance(data.get("playlists"), list)
        else []
    }


def _save_playlists(data):
    _playlists_store().set(data)


# Field mapping for rule-to-track attribute lookups
_RULE_FIELD_MAP = {
    "genre": "final_genre",
    "subgenre": "final_subgenre",
    "status": "review_status",
    "key": "final_key",
    "bpm": "final_bpm",
    "energy": "analyzed_energy",
    "year": "final_year",
    "artist": "display_artist",
    "title": "display_title",
}


def _get_track_field(track, field):
    mapped = _RULE_FIELD_MAP.get(field, field)
    return getattr(track, mapped, None)


def _rule_matches(track, rule):
    field = rule.get("field", "")
    operator = rule.get("operator", "equals")
    value = rule.get("value")
    track_val = _get_track_field(track, field)

    if operator == "equals":
        return str(track_val or "") == str(value or "")
    if operator == "contains":
        return value and str(track_val or "").lower().find(str(value).lower()) != -1
    if operator == "not_equals":
        return str(track_val or "") != str(value or "")
    if operator == "starts_with":
        return str(track_val or "").lower().startswith(str(value or "").lower())

    try:
        tv = float(track_val or 0)
        fv = float(value or 0)
    except (ValueError, TypeError):
        return False

    if operator == "gte":
        return tv >= fv
    if operator == "lte":
        return tv <= fv
    if operator == "gt":
        return tv > fv
    if operator == "lt":
        return tv < fv

    return False


def _group_matches(track, group):
    combinator = group.get("combinator", "AND")
    rules = group.get("rules", [])

    if not rules:
        return True

    results = []
    for r in rules:
        if "combinator" in r:
            results.append(_group_matches(track, r))
        else:
            results.append(_rule_matches(track, r))

    if combinator == "OR":
        return any(results)
    return all(results)


def _apply_filters(track_store, filters):
    """Filter tracks based on filter criteria via nested AND/OR rule groups.
    Supports both legacy flat dicts and new {combinator, rules} format.
    """
    results = []

    # Legacy flat format: convert to rules
    if not filters.get("rules") and not filters.get("combinator"):
        filters = _legacy_filters_to_rules(filters)

    if not filters.get("rules"):
        # Empty rules = match all
        return [track.to_dict() for track in track_store.values()]

    for fp, track in track_store.items():
        if _group_matches(track, filters):
            results.append(track.to_dict())
    return results


def _legacy_filters_to_rules(filters):
    """Convert old flat filter dict to new {combinator, rules} format."""
    rules = []
    if filters.get("genre"):
        rules.append(
            {"field": "genre", "operator": "equals", "value": filters["genre"]}
        )
    if filters.get("subgenre"):
        rules.append(
            {"field": "subgenre", "operator": "equals", "value": filters["subgenre"]}
        )
    if filters.get("status"):
        rules.append(
            {"field": "status", "operator": "equals", "value": filters["status"]}
        )
    if filters.get("key"):
        rules.append({"field": "key", "operator": "equals", "value": filters["key"]})
    if filters.get("bpm_min"):
        rules.append({"field": "bpm", "operator": "gte", "value": filters["bpm_min"]})
    if filters.get("bpm_max"):
        rules.append({"field": "bpm", "operator": "lte", "value": filters["bpm_max"]})
    if filters.get("energy_min"):
        rules.append(
            {"field": "energy", "operator": "gte", "value": filters["energy_min"]}
        )
    if filters.get("energy_max"):
        rules.append(
            {"field": "energy", "operator": "lte", "value": filters["energy_max"]}
        )
    if filters.get("year_min"):
        rules.append({"field": "year", "operator": "gte", "value": filters["year_min"]})
    if filters.get("year_max"):
        rules.append({"field": "year", "operator": "lte", "value": filters["year_max"]})
    return {"combinator": "AND", "rules": rules}


@bp.route("/playlists", methods=["GET"])
def list_playlists():
    data = _load_playlists()
    playlists = []
    for p in data.get("playlists", []):
        playlists.append(
            {
                "id": p["id"],
                "name": p["name"],
                "track_count": len(p.get("tracks", [])),
                "created": p.get("created"),
                "filters": p.get("filters", {}),
            }
        )
    return jsonify({"playlists": playlists}), 200


@bp.route("/playlists", methods=["POST"])
def create_playlist():
    body = request.get_json(silent=True) or {}
    data = _load_playlists()
    pid = body.get("id") or f"pl_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    playlist = {
        "id": pid,
        "name": body.get("name", "Untitled"),
        "filters": body.get("filters", {}),
        "tracks": body.get("tracks", []),
        "created": datetime.now(timezone.utc).isoformat(),
    }
    data["playlists"].append(playlist)
    _save_playlists(data)
    return jsonify({"id": pid, "saved": True}), 200


@bp.route("/playlists/<playlist_id>", methods=["GET"])
def get_playlist(playlist_id):
    data = _load_playlists()
    for p in data.get("playlists", []):
        if p["id"] == playlist_id:
            return jsonify(p), 200
    return jsonify({"error": "Not found"}), 404


@bp.route("/playlists/<playlist_id>", methods=["PUT"])
def update_playlist(playlist_id):
    body = request.get_json(silent=True) or {}
    data = _load_playlists()
    for p in data.get("playlists", []):
        if p["id"] == playlist_id:
            if "name" in body:
                p["name"] = body["name"]
            if "filters" in body:
                p["filters"] = body["filters"]
            if "tracks" in body:
                p["tracks"] = body["tracks"]
            _save_playlists(data)
            return jsonify({"saved": True}), 200
    return jsonify({"error": "Not found"}), 404


@bp.route("/playlists/<playlist_id>", methods=["DELETE"])
def delete_playlist(playlist_id):
    data = _load_playlists()
    data["playlists"] = [p for p in data.get("playlists", []) if p["id"] != playlist_id]
    _save_playlists(data)
    return jsonify({"deleted": True}), 200


@bp.route("/playlists/<playlist_id>/run", methods=["POST"])
def run_playlist(playlist_id):
    from app import get_track_store

    data = _load_playlists()
    for p in data.get("playlists", []):
        if p["id"] == playlist_id:
            filters = p.get("filters", {})
            tracks = _apply_filters(get_track_store(), filters)
            return jsonify({"tracks": tracks, "count": len(tracks)}), 200
    return jsonify({"error": "Not found"}), 404


@bp.route("/playlists/match-preview", methods=["POST"])
def match_preview():
    """Return match count and track list for a rule set (no persistence)."""
    from app import get_track_store

    body = request.get_json(silent=True) or {}
    rules = body.get("rules") or body.get("filters", {})
    tracks = _apply_filters(get_track_store(), rules)
    return jsonify({"tracks": tracks, "count": len(tracks)}), 200


@bp.route("/playlists/<playlist_id>/export-m3u", methods=["GET"])
def export_playlist_m3u(playlist_id):
    from app import get_track_store

    data = _load_playlists()
    track_store = get_track_store()
    for p in data.get("playlists", []):
        if p["id"] == playlist_id:
            lines = ["#EXTM3U"]
            for fp in p.get("tracks", []):
                track = track_store.get(fp)
                if track:
                    lines.append(
                        f"#EXTINF:0,{track.display_artist} - {track.display_title}"
                    )
                    lines.append(fp)
            name = p["name"].replace(" ", "-")
            return send_file(
                io.BytesIO("\n".join(lines).encode()),
                mimetype="audio/x-mpegurl",
                as_attachment=True,
                download_name=f"{name}.m3u",
            )
    return jsonify({"error": "Not found"}), 404


@bp.route("/playlists/run", methods=["POST"])
def run_filters_adhoc():
    from app import get_track_store

    body = request.get_json(silent=True) or {}
    filters = body.get("filters", {})
    tracks = _apply_filters(get_track_store(), filters)
    return jsonify({"tracks": tracks, "count": len(tracks)}), 200
