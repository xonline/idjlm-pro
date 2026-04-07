from flask import Blueprint, request, jsonify

bp = Blueprint("duplicates", __name__, url_prefix="/api")


def _has_value(v) -> bool:
    return v is not None and v != "" and v != 0


def _merge_tracks_best(keep_track, merge_tracks):
    """For each field, keep the value from whichever track has the most complete data."""
    fields = [
        ("final_genre", "override_genre"),
        ("final_subgenre", "override_subgenre"),
        ("final_bpm", "override_bpm"),
        ("final_key", "override_key"),
        ("final_year", "override_year"),
        ("analyzed_energy", "analyzed_energy"),
        ("clave_pattern", "clave_pattern"),
        ("vocal_flag", "vocal_flag"),
    ]
    updated = []

    for final_field, attr in fields:
        keep_val = getattr(keep_track, attr, None)
        if _has_value(keep_val):
            continue

        best = None
        for t in merge_tracks:
            mv = getattr(t, attr, None)
            if _has_value(mv):
                best = mv
                break

        if best is not None:
            setattr(keep_track, attr, best)
            updated.append(final_field)

    return updated


def _merge_tracks_keep_primary(keep_track, merge_tracks):
    """Keep all fields from primary, only fill gaps from merge tracks."""
    fields = [
        ("final_genre", "override_genre"),
        ("final_subgenre", "override_subgenre"),
        ("final_bpm", "override_bpm"),
        ("final_key", "override_key"),
        ("final_year", "override_year"),
        ("analyzed_energy", "analyzed_energy"),
        ("clave_pattern", "clave_pattern"),
        ("vocal_flag", "vocal_flag"),
    ]
    updated = []

    for final_field, attr in fields:
        keep_val = getattr(keep_track, attr, None)
        if _has_value(keep_val):
            continue
        for t in merge_tracks:
            mv = getattr(t, attr, None)
            if _has_value(mv):
                setattr(keep_track, attr, mv)
                updated.append(final_field)
                break

    return updated


@bp.route("/duplicates/scan", methods=["POST"])
def scan_duplicates():
    """
    Scan track store for duplicate tracks.
    POST /api/duplicates/scan
    Returns: {
        "groups": [...],
        "total_duplicates": int
    }
    """
    try:
        from app import get_track_store
        from app.services.duplicate_detector import find_duplicates

        track_store = get_track_store()
        result = find_duplicates(track_store)

        # Transform groups to duplicates format expected by frontend
        duplicates = []
        for group in result.get("groups", []):
            tracks = group.get("tracks", [])
            track_objects = [track_store[fp].to_dict() for fp in tracks if fp in track_store]
            if len(track_objects) >= 2:
                duplicates.append({
                    "group_id": group.get("reason", "unknown"),
                    "tracks": track_objects
                })

        return jsonify({"duplicates": duplicates, "total_duplicates": result.get("total_duplicates", 0)}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/duplicates/merge", methods=["POST"])
def merge_duplicates():
    """
    Merge duplicate tracks into a single kept track.
    POST /api/duplicates/merge
    Body: {
        "keep_path": "/path/to/track/to/keep",
        "merge_paths": ["/path/to/track1", "/path/to/track2"],
        "field_strategy": "best" | "keep_primary"
    }
    Returns: { "merged": N, "kept": "/path", "updated_fields": [...], "result": { track dict } }
    """
    try:
        from app import get_track_store
        from app.services.session_service import save_session

        body = request.get_json(silent=True)
        if not body:
            return jsonify({"error": "Missing request body"}), 400

        keep_path = body.get("keep_path")
        merge_paths = body.get("merge_paths", [])
        field_strategy = body.get("field_strategy", "best")

        if not keep_path:
            return jsonify({"error": "Missing keep_path"}), 400
        if not merge_paths:
            return jsonify({"error": "Missing merge_paths"}), 400

        track_store = get_track_store()

        if keep_path not in track_store:
            return jsonify({"error": f"Keep track not found: {keep_path}"}), 404

        missing = [p for p in merge_paths if p not in track_store]
        if missing:
            return jsonify({"error": f"Merge tracks not found: {missing}"}), 404

        keep_track = track_store[keep_path]
        merge_tracks = [track_store[p] for p in merge_paths]

        if field_strategy == "keep_primary":
            updated_fields = _merge_tracks_keep_primary(keep_track, merge_tracks)
        else:
            updated_fields = _merge_tracks_best(keep_track, merge_tracks)

        for mp in merge_paths:
            track_store[mp].is_duplicate = True
            track_store[mp].duplicate_of = keep_path
            del track_store[mp]

        save_session(track_store)

        return jsonify({
            "merged": len(merge_paths),
            "kept": keep_path,
            "updated_fields": updated_fields,
            "result": keep_track.to_dict()
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/duplicates/remove", methods=["POST"])
def remove_duplicate():
    """
    Remove a duplicate track from the track store.
    POST /api/duplicates/remove
    Body: { "file_path": "..." }
    Returns: { "total_duplicates": int, "remaining_tracks": int }
    """
    try:
        from app import get_track_store

        body = request.get_json(silent=True)
        if not body or "file_path" not in body:
            return jsonify({"error": "Missing file_path in request body"}), 400

        file_path = body.get("file_path")
        track_store = get_track_store()

        if file_path not in track_store:
            return jsonify({"error": f"Track not found: {file_path}"}), 404

        del track_store[file_path]

        from app.services.duplicate_detector import find_duplicates
        result = find_duplicates(track_store)

        return jsonify({
            "total_duplicates": result["total_duplicates"],
            "remaining_tracks": len(track_store)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
