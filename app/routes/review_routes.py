from flask import Blueprint, request, jsonify
import logging
import threading

logger = logging.getLogger(__name__)
_log_lock = threading.Lock()

bp = Blueprint("review", __name__, url_prefix="/api")


@bp.route("/review/approve", methods=["POST"])
def approve_tracks():
    """
    Approve specific tracks.
    POST /api/review/approve
    body: { "track_paths": ["/path1", "/path2"] }
    """
    try:
        from app import get_track_store

        data = request.get_json(silent=True) or {}
        track_paths = data.get("track_paths", [])
        track_store = get_track_store()

        approved = 0
        for file_path in track_paths:
            if file_path in track_store:
                track = track_store[file_path]
                track.review_status = "approved"
                approved += 1
                # Learn from this correction for future classifications
                try:
                    from app.services.learning import save_correction
                    save_correction(track)
                except ImportError:
                    pass

        return jsonify({"approved": approved}), 200

    except Exception:
        logger.exception("Error in /api/review/approve")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/review/skip", methods=["POST"])
def skip_tracks():
    """
    Skip specific tracks.
    POST /api/review/skip
    body: { "track_paths": ["/path1", "/path2"] }
    """
    try:
        from app import get_track_store

        data = request.get_json(silent=True) or {}
        track_paths = data.get("track_paths", [])
        track_store = get_track_store()

        skipped = 0
        for file_path in track_paths:
            if file_path in track_store:
                track_store[file_path].review_status = "skipped"
                skipped += 1

        return jsonify({"skipped": skipped}), 200

    except Exception:
        logger.exception("Error in /api/review/skip")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/review/bulk-approve", methods=["POST"])
def bulk_approve():
    """
    Approve all tracks meeting confidence threshold.
    POST /api/review/bulk-approve
    body: { "min_confidence": 80 }
    """
    try:
        from app import get_track_store

        data = request.get_json(silent=True) or {}
        # Support both min_confidence and threshold for backwards compatibility
        min_confidence = data.get("min_confidence") or data.get("threshold") or 0
        track_store = get_track_store()

        approved = 0
        for track in track_store.values():
            if (
                track.review_status == "pending" and
                track.confidence is not None and
                track.confidence >= min_confidence
            ):
                track.review_status = "approved"
                approved += 1

        return jsonify({"approved": approved}), 200

    except Exception:
        logger.exception("Error in /api/review/bulk-approve")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/review/write", methods=["POST"])
def write_tags():
    """
    Write approved tracks' tags to ID3 (async).
    POST /api/review/write
    body: { "track_paths": [...] }  # or empty = all approved tracks
    Returns: { "op_id": "...", "total": N }  (202 Accepted)
    Stream progress via EventSource('/api/progress/<op_id>')
    """
    try:
        import uuid
        import threading
        import queue as _queue
        import json
        import datetime
        import os
        from app.services.tag_writer import write_tags as write_service
        from app import get_track_store, get_progress_queues

        data = request.get_json(silent=True) or {}
        track_paths = data.get("track_paths", [])
        track_store = get_track_store()

        # If empty, write all approved tracks
        if not track_paths:
            track_paths = [
                fp for fp, t in track_store.items()
                if t.review_status == "approved"
            ]

        op_id = str(uuid.uuid4())[:8]
        q = _queue.Queue()
        get_progress_queues()[op_id] = q

        def run():
            total = len(track_paths)
            written = 0
            errors = []
            change_summary = []
            log_path = os.path.join(os.path.dirname(__file__), '..', '..', 'approval_log.jsonl')

            for i, file_path in enumerate(track_paths):
                if file_path not in track_store:
                    continue

                try:
                    track = track_store[file_path]

                    # Capture existing values before write
                    existing = {
                        'genre': track.existing_genre,
                        'comment': track.existing_comment,
                        'bpm': track.existing_bpm,
                        'key': track.existing_key,
                        'year': track.existing_year,
                    }

                    write_service(track)
                    track.tags_written = True
                    written += 1

                    # Build change summary by comparing existing vs final
                    changes = []
                    genre_before = existing['genre'] or ''
                    genre_after = track.final_genre or ''
                    if genre_before != genre_after:
                        changes.append(f"genre: {genre_before} -> {genre_after}")

                    comment_before = existing['comment'] or ''
                    comment_after = track.final_subgenre or ''
                    if comment_before != comment_after:
                        changes.append(f"comment: {comment_before} -> {comment_after}")

                    bpm_before = existing['bpm'] or ''
                    bpm_after = track.final_bpm or ''
                    if bpm_before != bpm_after:
                        changes.append(f"bpm: {bpm_before} -> {bpm_after}")

                    key_before = existing['key'] or ''
                    key_after = track.final_key or ''
                    if key_before != key_after:
                        changes.append(f"key: {key_before} -> {key_after}")

                    year_before = existing['year'] or ''
                    year_after = track.final_year or ''
                    if year_before != year_after:
                        changes.append(f"year: {year_before} -> {year_after}")

                    if changes:
                        change_summary.append({
                            'filename': track.filename,
                            'changes': changes,
                        })

                    # Log approval if there are overrides (thread-safe)
                    if track.override_genre or track.override_subgenre or track.override_bpm or track.override_key or track.override_year:
                        entry = {
                            'ts': datetime.datetime.utcnow().isoformat(),
                            'title': track.display_title,
                            'artist': track.display_artist,
                            'ai_genre': track.proposed_genre,
                            'ai_subgenre': track.proposed_subgenre,
                            'final_genre': track.final_genre,
                            'final_subgenre': track.final_subgenre,
                            'bpm': track.final_bpm,
                            'key': track.final_key,
                        }
                        with _log_lock:
                            with open(log_path, 'a') as f:
                                f.write(json.dumps(entry) + '\n')
                        track.approval_logged = True

                    q.put({
                        'current': i + 1,
                        'total': total,
                        'track': track.display_title,
                        'written': written
                    })
                except Exception as e:
                    track.error = str(e)
                    errors.append({
                        'path': file_path,
                        'error': str(e)
                    })
                    q.put({
                        'current': i + 1,
                        'total': total,
                        'error': str(e)
                    })

            q.put({'done': True, 'written': written, 'errors': errors, 'change_summary': change_summary, 'refetch': True})
            try:
                from app.services.session_service import save_session
                from app import get_track_store, get_current_folder_path
                save_session(get_track_store(), get_current_folder_path())
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()
        return jsonify({'op_id': op_id, 'total': len(track_paths)}), 202

    except Exception:
        logger.exception("Error in /api/review/write")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/review/bulk-edit", methods=["POST"])
def bulk_edit():
    """
    Set genre/subgenre/bpm/key/year for multiple tracks at once.
    POST /api/review/bulk-edit
    body: {
        "track_paths": ["/path1", "/path2"],
        "genre": "Salsa",          # optional
        "subgenre": "Romántica",   # optional
        "bpm": "95",               # optional
        "key": "8B",               # optional
        "year": "2023"             # optional
    }
    Only sets fields that are present in the request body.
    """
    try:
        from app import get_track_store

        data = request.get_json(silent=True) or {}
        track_paths = data.get("track_paths", [])
        track_store = get_track_store()

        # Validate BPM: numeric, 40-300 range (allow wider for Latin music)
        if "bpm" in data:
            bpm = data["bpm"]
            if bpm != "" and bpm is not None:
                try:
                    bpm_num = float(bpm)
                    if not (40 <= bpm_num <= 300):
                        return jsonify({"error": "BPM must be between 40 and 300"}), 400
                except (ValueError, TypeError):
                    return jsonify({"error": "BPM must be numeric"}), 400

        # Validate Key: string ≤10 chars
        if "key" in data:
            key = data["key"]
            if key != "" and key is not None:
                if not isinstance(key, str) or len(key) > 10:
                    return jsonify({"error": "Key must be a string up to 10 characters"}), 400

        # Validate Year: 4-digit number between 1900-2030
        if "year" in data:
            year = data["year"]
            if year != "" and year is not None:
                try:
                    year_num = int(year)
                    if not (1900 <= year_num <= 2030):
                        return jsonify({"error": "Year must be between 1900 and 2030"}), 400
                except (ValueError, TypeError):
                    return jsonify({"error": "Year must be a 4-digit number"}), 400

        updated = 0
        for file_path in track_paths:
            if file_path not in track_store:
                continue
            track = track_store[file_path]
            if 'genre' in data:
                track.override_genre = data['genre']
            if 'subgenre' in data:
                track.override_subgenre = data['subgenre']
            if 'bpm' in data:
                track.override_bpm = data['bpm']
            if 'key' in data:
                track.override_key = data['key']
            if 'year' in data:
                track.override_year = data['year']

            # Recompute review_status based on whether any overrides are set
            has_overrides = any([
                track.override_genre,
                track.override_subgenre,
                track.override_bpm,
                track.override_key,
                track.override_year
            ])
            if has_overrides:
                track.review_status = "edited"
            elif track.review_status == "edited":
                # Revert to pending if no overrides are set and status was edited
                track.review_status = "pending"

            # Learn from this correction
            try:
                from app.services.learning import save_correction
                save_correction(track)
            except ImportError:
                pass

            updated += 1

        return jsonify({"updated": updated}), 200

    except Exception:
        logger.exception("Error in /api/review/bulk-edit")
        return jsonify({"error": "Operation failed. Check server logs."}), 500
