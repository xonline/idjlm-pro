import os

from flask import Blueprint, request, jsonify

bp = Blueprint("duplicates", __name__, url_prefix="/api")


def _read_audio_info(file_path: str) -> dict:
    try:
        stat = os.stat(file_path)
        file_size = stat.st_size
        mtime = stat.st_mtime
    except OSError:
        file_size = 0
        mtime = 0

    bitrate = None
    sample_rate = None
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(file_path)
        if audio and audio.info:
            bitrate = getattr(audio.info, 'bitrate', None)
            sample_rate = getattr(audio.info, 'sample_rate', None)
    except Exception:
        pass

    return {
        'bitrate': int(bitrate) if bitrate else None,
        'sample_rate': int(sample_rate) if sample_rate else None,
        'file_size': file_size,
        'mtime': mtime
    }


def _compute_tag_completeness(track_dict: dict) -> dict:
    tag_fields = [
        'existing_title', 'existing_artist', 'existing_album',
        'existing_year', 'existing_genre', 'existing_bpm',
        'existing_key', 'existing_comment'
    ]
    metadata_fields = [
        'final_genre', 'final_subgenre', 'final_bpm', 'final_key',
        'final_year', 'analyzed_energy', 'duration', 'analyzed_lufs'
    ]

    tag_populated = sum(1 for f in tag_fields if track_dict.get(f))
    metadata_populated = sum(1 for f in metadata_fields if track_dict.get(f))

    return {
        'tag_count': tag_populated,
        'tag_total': len(tag_fields),
        'tag_pct': round(tag_populated / len(tag_fields) * 100),
        'metadata_count': metadata_populated,
        'metadata_total': len(metadata_fields),
        'metadata_pct': round(metadata_populated / len(metadata_fields) * 100),
        'overall_pct': round(
            (tag_populated + metadata_populated) / (len(tag_fields) + len(metadata_fields)) * 100
        )
    }


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
            track_objects = []
            for fp in tracks:
                if fp not in track_store:
                    continue
                td = track_store[fp].to_dict()
                td['audio_info'] = _read_audio_info(fp)
                td['tag_completeness'] = _compute_tag_completeness(td)
                track_objects.append(td)
            if len(track_objects) >= 2:
                duplicates.append({
                    "group_id": group.get("reason", "unknown"),
                    "tracks": track_objects,
                    "reason": group.get("reason", "unknown"),
                    "group_label": group.get(
                        "artist", group.get("filename_pattern", "")
                    )
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


@bp.route("/duplicates/batch-resolve", methods=["POST"])
def batch_resolve_duplicates():
    """
    Batch-resolve multiple duplicate groups at once.
    POST /api/duplicates/batch-resolve
    Body: {
        "resolutions": [
            {"keep_path": "...", "merge_paths": ["..."], "field_strategy": "best"},
            ...
        ]
    }
    Returns: { "resolved_groups": N, "total_merged": N, "errors": [], "results": [...] }
    """
    try:
        from app import get_track_store
        from app.services.session_service import save_session

        body = request.get_json(silent=True)
        if not body or "resolutions" not in body:
            return jsonify({"error": "Missing resolutions in request body"}), 400

        resolutions = body["resolutions"]
        if not isinstance(resolutions, list) or len(resolutions) == 0:
            return jsonify({"error": "resolutions must be a non-empty list"}), 400

        track_store = get_track_store()
        results = []
        errors = []
        total_merged = 0

        for i, res in enumerate(resolutions):
            keep_path = res.get("keep_path")
            merge_paths = res.get("merge_paths", [])
            field_strategy = res.get("field_strategy", "best")

            if not keep_path or not merge_paths:
                errors.append({"index": i, "error": "Missing keep_path or merge_paths"})
                continue

            missing = [p for p in merge_paths if p not in track_store]
            if missing:
                errors.append({
                    "index": i,
                    "keep_path": keep_path,
                    "error": f"Merge tracks not found: {missing}"
                })
                continue

            try:
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

                total_merged += len(merge_paths)
                results.append({
                    "keep_path": keep_path,
                    "merged": len(merge_paths),
                    "updated_fields": updated_fields,
                    "result": keep_track.to_dict()
                })
            except Exception as e:
                errors.append({
                    "index": i,
                    "keep_path": keep_path,
                    "error": str(e)
                })

        if total_merged > 0:
            save_session(track_store)

        return jsonify({
            "resolved_groups": len(results),
            "total_merged": total_merged,
            "errors": errors,
            "results": results
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
