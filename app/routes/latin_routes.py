import re
import json
import uuid
import threading
import queue as _queue
from urllib.parse import quote
from flask import Blueprint, request, jsonify, send_file
import io

bp = Blueprint("latin", __name__, url_prefix="/api")


# ============================================================================
# Feature 1: Clave + Montuno Analyzer
# ============================================================================

@bp.route("/analyze/latin", methods=["POST"])
def analyze_latin_tracks():
    """
    Analyze tracks for clave pattern and montuno detection (async).
    POST /api/analyze/latin
    body: { "paths": ["/path1", "/path2"] }  or { "all": true }
    Returns: { "op_id": "...", "total": N }  (202 Accepted)
    Stream progress via EventSource('/api/progress/<op_id>')
    """
    try:
        from app.services.latin_analyzer import analyze_latin
        from app import get_track_store, get_progress_queues

        data = request.get_json(silent=True) or {}
        paths = data.get("paths", [])
        analyze_all = data.get("all", False)

        track_store = get_track_store()

        # Determine which tracks to analyze
        if analyze_all:
            track_paths = list(track_store.keys())
        else:
            track_paths = paths

        if not track_paths:
            return jsonify({"error": "No tracks specified"}), 400

        op_id = str(uuid.uuid4())[:8]
        q = _queue.Queue()
        get_progress_queues()[op_id] = q

        def run():
            total = len(track_paths)
            analyzed = 0
            errors = []

            for i, file_path in enumerate(track_paths):
                if file_path not in track_store:
                    continue

                try:
                    track = track_store[file_path]
                    # Only analyze if basic audio analysis is done
                    if not track.analysis_done or not track.analyzed_bpm:
                        q.put({
                            'current': i + 1,
                            'total': total,
                            'error': 'Track not analyzed (no BPM)'
                        })
                        continue

                    analyze_latin(track)
                    analyzed += 1
                    q.put({
                        'current': i + 1,
                        'total': total,
                        'track': track.display_title,
                        'clave': track.clave_pattern,
                        'analyzed': analyzed
                    })
                except Exception as e:
                    errors.append({'path': file_path, 'error': str(e)})
                    q.put({
                        'current': i + 1,
                        'total': total,
                        'error': str(e)
                    })

            q.put({'done': True, 'analyzed': analyzed, 'errors': errors})

        threading.Thread(target=run, daemon=True).start()
        return jsonify({'op_id': op_id, 'total': len(track_paths)}), 202

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Feature 2: Cue Points Endpoint
# ============================================================================

@bp.route("/tracks/<path:encoded_path>/cues", methods=["GET"])
def get_track_cues(encoded_path):
    """
    Get suggested cue points for a track.
    GET /api/tracks/{encoded_path}/cues
    Returns: { "cues": [...], "clave_pattern": "2-3"|"3-2"|null }
    """
    try:
        from app import get_track_store

        # Decode path
        file_path = quote(encoded_path, safe="")

        track_store = get_track_store()

        # Find track by encoded path
        found_track = None
        for stored_path, track in track_store.items():
            if quote(stored_path, safe="") == file_path:
                found_track = track
                break

        if not found_track:
            return jsonify({"error": "Track not found"}), 404

        if not found_track.latin_analysis_done:
            return jsonify({
                "error": "Track not analyzed for Latin features",
                "cues": [],
                "clave_pattern": None
            }), 400

        return jsonify({
            "cues": found_track.suggested_cues or [],
            "clave_pattern": found_track.clave_pattern,
            "clave_confidence": found_track.clave_confidence
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Feature 3: Mix Compatibility Scorer
# ============================================================================

@bp.route("/mix/score", methods=["GET"])
def get_mix_score():
    """
    Score mixing compatibility between two tracks.
    GET /api/mix/score?a={path_a}&b={path_b}
    Returns: { score, bpm_score, key_score, energy_score, genre_score, details }
    """
    try:
        from app.services.mix_scorer import score_compatibility
        from app import get_track_store

        path_a = request.args.get("a", "").strip()
        path_b = request.args.get("b", "").strip()

        if not path_a or not path_b:
            return jsonify({"error": "Both 'a' and 'b' parameters required"}), 400

        track_store = get_track_store()

        if path_a not in track_store or path_b not in track_store:
            return jsonify({"error": "One or both tracks not found"}), 404

        track_a = track_store[path_a]
        track_b = track_store[path_b]

        score_dict = score_compatibility(track_a, track_b)
        return jsonify(score_dict), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/mix/suggestions", methods=["GET"])
def get_mix_suggestions():
    """
    Get mix compatibility suggestions for a given track.
    GET /api/mix/suggestions?path={path}&limit=10
    Returns: { "track": {...}, "matches": [{"track": {...}, "score": 0-100, ...}] }
    """
    try:
        from app.services.mix_scorer import score_compatibility
        from app import get_track_store

        path = request.args.get("path", "").strip()
        limit = request.args.get("limit", "10").strip()

        try:
            limit = int(limit)
        except ValueError:
            limit = 10

        if not path:
            return jsonify({"error": "path parameter required"}), 400

        track_store = get_track_store()

        if path not in track_store:
            return jsonify({"error": "Track not found"}), 404

        base_track = track_store[path]

        # Score against all other tracks
        matches = []
        for other_path, other_track in track_store.items():
            if other_path == path:
                continue

            score_dict = score_compatibility(base_track, other_track)
            matches.append({
                "path": other_path,
                "title": other_track.display_title,
                "artist": other_track.display_artist,
                "bpm": other_track.analyzed_bpm,
                "key": other_track.final_key,
                "energy": other_track.analyzed_energy,
                "genre": other_track.final_genre,
                **score_dict
            })

        # Sort by score descending, limit
        matches.sort(key=lambda x: x["score"], reverse=True)
        matches = matches[:limit]

        return jsonify({
            "track": {
                "path": path,
                "title": base_track.display_title,
                "artist": base_track.display_artist,
                "bpm": base_track.analyzed_bpm,
                "key": base_track.final_key,
                "energy": base_track.analyzed_energy,
                "genre": base_track.final_genre
            },
            "matches": matches
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/mixes/compatible/<path:file_path>", methods=["GET"])
def get_compatible_tracks(file_path):
    """
    Return compatible tracks for harmonic mixing.
    GET /api/mixes/compatible/{file_path}
    Finds tracks compatible by:
    - Camelot key: same key or adjacent keys (±1 semitone)
    - BPM: within ±8% of the source track
    Returns: { "compatible_tracks": [{"file_path": ..., "title": ..., "artist": ..., "key": ..., "bpm": ..., "score": ...}] }
    """
    try:
        from app.services.mix_scorer import score_compatibility, camelot_distance
        from app import get_track_store

        track_store = get_track_store()

        # Look up the source track
        if file_path not in track_store:
            return jsonify({"error": "Track not found"}), 404

        source_track = track_store[file_path]

        # Need BPM and key to find compatible tracks
        if not source_track.analyzed_bpm or not source_track.final_key:
            return jsonify({
                "error": "Source track missing BPM or key",
                "compatible_tracks": []
            }), 400

        source_bpm = source_track.analyzed_bpm
        source_key = source_track.final_key
        bpm_tolerance = source_bpm * 0.08  # ±8%

        compatible = []

        for other_path, other_track in track_store.items():
            # Skip source track
            if other_path == file_path:
                continue

            # Must have BPM and key
            if not other_track.analyzed_bpm or not other_track.final_key:
                continue

            # Check Camelot key compatibility (0 = same, 1 = adjacent)
            key_distance = camelot_distance(source_key, other_track.final_key)
            if key_distance > 1:
                continue

            # Check BPM compatibility (within ±8%)
            bpm_diff = abs(source_bpm - other_track.analyzed_bpm)
            if bpm_diff > bpm_tolerance:
                continue

            # Calculate full compatibility score
            score_dict = score_compatibility(source_track, other_track)

            compatible.append({
                "file_path": other_path,
                "title": other_track.display_title,
                "artist": other_track.display_artist,
                "key": other_track.final_key,
                "bpm": other_track.analyzed_bpm,
                "score": score_dict["score"]
            })

        # Sort by score descending, limit to top 10
        compatible.sort(key=lambda x: x["score"], reverse=True)
        compatible = compatible[:10]

        return jsonify({"compatible_tracks": compatible}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Feature 4: Cue Sheet Export
# ============================================================================

@bp.route("/export/cue-sheet", methods=["GET"])
def export_cue_sheet():
    """
    Export a cue sheet as JSON with track metadata and cue points.
    GET /api/export/cue-sheet?genre={optional}
    Returns: JSON file with tracks and their cue points
    """
    try:
        from app import get_track_store

        genre = request.args.get("genre", "").strip() or None

        track_store = get_track_store()
        tracks = list(track_store.values())

        # Filter by genre if provided
        if genre:
            tracks = [t for t in tracks if t.final_genre == genre]

        # Build cue sheet data
        cue_sheet = {
            "export_date": __import__("datetime").datetime.now().isoformat(),
            "genre_filter": genre,
            "total_tracks": len(tracks),
            "tracks": []
        }

        for track in tracks:
            cue_sheet["tracks"].append({
                "title": track.display_title,
                "artist": track.display_artist,
                "file_path": track.file_path,
                "bpm": track.analyzed_bpm,
                "key": track.final_key,
                "energy": track.analyzed_energy,
                "genre": track.final_genre,
                "clave_pattern": track.clave_pattern,
                "cue_points": track.suggested_cues or []
            })

        json_content = json.dumps(cue_sheet, indent=2)
        filename = f"cue-sheet{f'-{genre}' if genre else ''}.json"

        return send_file(
            io.BytesIO(json_content.encode('utf-8')),
            mimetype="application/json",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Feature 5: Tag Validator
# ============================================================================

@bp.route("/validate/tags", methods=["GET"])
def validate_tags():
    """
    Validate all tracks in store for common metadata issues.
    GET /api/validate/tags
    Returns: { "total_issues": N, "tracks": [{"path": ..., "issues": [...]}] }
    """
    try:
        from app import get_track_store, get_taxonomy

        track_store = get_track_store()
        taxonomy = get_taxonomy()
        valid_genres = set(taxonomy.get("genres", []))

        issues_by_track = {}
        total_issues = 0

        for file_path, track in track_store.items():
            track_issues = []

            # Missing genre
            if not track.final_genre:
                track_issues.append("Missing genre")

            # Missing BPM
            elif not track.analyzed_bpm:
                track_issues.append("Missing BPM")

            # BPM out of range
            if track.analyzed_bpm:
                if track.analyzed_bpm > 160:
                    track_issues.append(f"BPM suspiciously high: {track.analyzed_bpm}")
                elif track.analyzed_bpm < 60:
                    track_issues.append(f"BPM suspiciously low: {track.analyzed_bpm}")

            # Key not in Camelot format
            if track.final_key:
                if not re.match(r'^\d{1,2}[AB]$', track.final_key):
                    track_issues.append(f"Invalid key format: {track.final_key} (expected Camelot like '8B')")

            # Missing title
            if not track.display_title or track.display_title == track.filename:
                track_issues.append("Missing or incomplete title")

            # Missing artist
            if not track.display_artist or track.display_artist == "Unknown":
                track_issues.append("Missing artist")

            # Genre not in taxonomy
            if track.final_genre and track.final_genre not in valid_genres:
                track_issues.append(f"Genre '{track.final_genre}' not in taxonomy")

            if track_issues:
                issues_by_track[file_path] = track_issues
                total_issues += len(track_issues)

        # Format response
        result_tracks = [
            {
                "path": path,
                "title": track_store[path].display_title,
                "issues": issues
            }
            for path, issues in issues_by_track.items()
        ]

        return jsonify({
            "total_issues": total_issues,
            "tracks": result_tracks
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
