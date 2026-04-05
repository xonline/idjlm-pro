import os
import shutil
import re
import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("organise", __name__, url_prefix="/api")


def _sanitize_path_component(component: str) -> str:
    """Remove invalid path characters from a string."""
    if component is None:
        return "Unknown"
    # Remove invalid characters: / \ : * ? " < > |
    sanitized = re.sub(r'[/\\:*?"<>|]', '', str(component))
    return sanitized.strip() or "Unknown"


@bp.route("/library/health", methods=["GET"])
def library_health():
    """
    Get library health statistics.
    Returns: total tracks, analyzed, classified, approved, tags_written, missing_artwork,
    duplicates, breakdown by genre, breakdown by review_status, and coverage metrics.
    """
    try:
        from app import get_track_store

        track_store = get_track_store()
        tracks = list(track_store.values())

        total = len(tracks)

        if total == 0:
            return jsonify({
                "total": 0,
                "analyzed": 0,
                "classified": 0,
                "approved": 0,
                "tags_written": 0,
                "missing_artwork": 0,
                "duplicates": 0,
                "by_genre": {},
                "by_review_status": {},
                "coverage": {
                    "bpm": 0.0,
                    "key": 0.0,
                    "energy": 0.0,
                    "artwork": 0.0
                }
            })

        # Count various states
        analyzed = sum(1 for t in tracks if t.analysis_done)
        classified = sum(1 for t in tracks if t.classification_done)
        approved = sum(1 for t in tracks if t.review_status == "approved")
        tags_written = sum(1 for t in tracks if t.tags_written)
        missing_artwork = sum(1 for t in tracks if not t.album_art_url)
        duplicates = sum(1 for t in tracks if t.is_duplicate)

        # Breakdown by genre
        by_genre = {}
        for t in tracks:
            genre = t.final_genre or "Unknown"
            by_genre[genre] = by_genre.get(genre, 0) + 1

        # Breakdown by review_status
        by_review_status = {}
        for t in tracks:
            status = t.review_status or "unknown"
            by_review_status[status] = by_review_status.get(status, 0) + 1

        # Coverage metrics
        coverage_bpm = sum(1 for t in tracks if t.analyzed_bpm is not None) / total if total > 0 else 0
        coverage_key = sum(1 for t in tracks if t.analyzed_key is not None) / total if total > 0 else 0
        coverage_energy = sum(1 for t in tracks if t.analyzed_energy is not None) / total if total > 0 else 0
        coverage_artwork = sum(1 for t in tracks if t.album_art_url) / total if total > 0 else 0

        return jsonify({
            "total": total,
            "analyzed": analyzed,
            "classified": classified,
            "approved": approved,
            "tags_written": tags_written,
            "missing_artwork": missing_artwork,
            "duplicates": duplicates,
            "by_genre": by_genre,
            "by_review_status": by_review_status,
            "coverage": {
                "bpm": round(coverage_bpm, 2),
                "key": round(coverage_key, 2),
                "energy": round(coverage_energy, 2),
                "artwork": round(coverage_artwork, 2)
            }
        })

    except Exception as e:
        logger.exception(f"Error in organise routes endpoint")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/organise/parse-filenames", methods=["POST"])
def parse_filenames():
    """
    Parse filenames to extract artist and title.
    Body: {"paths": ["...", ...]} OR {"all": true}
    Returns array of parsed results with conflicts marked.
    """
    try:
        from app import get_track_store

        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is empty"}), 400

        track_store = get_track_store()
        tracks = list(track_store.values())

        # Determine which tracks to process
        if data.get("all"):
            target_tracks = tracks
        else:
            paths = data.get("paths", [])
            if not isinstance(paths, list):
                return jsonify({"error": "paths must be a list"}), 400
            target_tracks = [t for t in tracks if t.file_path in paths]

        results = []

        for track in target_tracks:
            # Extract filename without extension
            filename_with_ext = track.filename
            filename_no_ext = os.path.splitext(filename_with_ext)[0]

            # Try to parse "Artist - Title" pattern
            parts = filename_no_ext.split(" - ", 1)
            parsed_artist = None
            parsed_title = None

            if len(parts) == 2:
                parsed_artist = parts[0].strip() if parts[0].strip() else None
                parsed_title = parts[1].strip() if parts[1].strip() else None

            # Check for conflicts (only if current values are non-empty)
            has_conflict = False
            if parsed_artist is not None or parsed_title is not None:
                if parsed_artist and track.existing_artist and parsed_artist != track.existing_artist:
                    has_conflict = True
                if parsed_title and track.existing_title and parsed_title != track.existing_title:
                    has_conflict = True

            # Only include if parsing was attempted
            if parsed_artist is not None or parsed_title is not None:
                results.append({
                    "file_path": track.file_path,
                    "filename": filename_with_ext,
                    "parsed_artist": parsed_artist,
                    "parsed_title": parsed_title,
                    "current_artist": track.existing_artist,
                    "current_title": track.existing_title,
                    "has_conflict": has_conflict
                })

        return jsonify(results)

    except Exception as e:
        logger.exception(f"Error in organise routes endpoint")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/organise/apply-filename-tags", methods=["POST"])
def apply_filename_tags():
    """
    Apply parsed filename tags to tracks.
    Body: {"updates": [{"file_path": "...", "artist": "...", "title": "..."}]}
    Returns: {"updated": N, "errors": [...]}
    """
    try:
        from app import get_track_store

        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is empty"}), 400

        updates = data.get("updates", [])
        if not isinstance(updates, list):
            return jsonify({"error": "updates must be a list"}), 400

        track_store = get_track_store()
        updated_count = 0
        errors = []

        for update in updates:
            file_path = update.get("file_path")
            artist = update.get("artist")
            title = update.get("title")

            if not file_path:
                errors.append(f"Missing file_path in update")
                continue

            if file_path not in track_store:
                errors.append(f"Track not found: {file_path}")
                continue

            track = track_store[file_path]

            try:
                track.existing_artist = artist
                track.existing_title = title
                track.review_status = "pending"
                updated_count += 1
            except Exception as e:
                errors.append(f"Failed to update {file_path}: {str(e)}")

        return jsonify({
            "updated": updated_count,
            "errors": errors
        })

    except Exception as e:
        logger.exception(f"Error in organise routes endpoint")
        return jsonify({"error": "Operation failed. Check server logs."}), 500


@bp.route("/organise/folders", methods=["POST"])
def organise_folders():
    """
    Organise tracks into folders based on metadata pattern.
    Body: {
        "destination": "/path/to/dest",
        "pattern": "genre" | "genre/subgenre" | "genre/subgenre/year",
        "dry_run": true/false,
        "paths": ["..."]  // optional, omit = all approved
    }
    Returns dry_run preview or actual move results.
    """
    try:
        from app import get_track_store

        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is empty"}), 400

        destination = data.get("destination")
        pattern = data.get("pattern", "genre/subgenre")
        dry_run = data.get("dry_run", True)
        paths = data.get("paths")

        if not destination:
            return jsonify({"error": "destination is required"}), 400

        if pattern not in ["genre", "genre/subgenre", "genre/subgenre/year"]:
            return jsonify({"error": "pattern must be 'genre', 'genre/subgenre', or 'genre/subgenre/year'"}), 400

        track_store = get_track_store()
        all_tracks = list(track_store.values())

        # Filter to approved tracks, or specific paths if provided
        if paths:
            tracks = [t for t in all_tracks if t.file_path in paths and t.review_status == "approved"]
        else:
            tracks = [t for t in all_tracks if t.review_status == "approved"]

        moves = []
        errors = []

        for track in tracks:
            # Build destination path components
            components = []

            if "genre" in pattern:
                components.append(_sanitize_path_component(track.final_genre))

            if "subgenre" in pattern:
                components.append(_sanitize_path_component(track.final_subgenre))

            if "year" in pattern:
                components.append(_sanitize_path_component(track.final_year))

            # Construct full destination path
            rel_path = os.path.join(*components) if components else ""
            dest_dir = os.path.join(destination, rel_path)
            dest_file = os.path.join(dest_dir, track.filename)

            would_overwrite = os.path.exists(dest_file) if not dry_run else False

            moves.append({
                "from": track.file_path,
                "to": dest_file,
                "would_overwrite": would_overwrite
            })

            # Perform actual move if not dry_run
            if not dry_run:
                try:
                    # Create destination directory
                    os.makedirs(dest_dir, exist_ok=True)

                    # Move file
                    shutil.move(track.file_path, dest_file)

                    # Update track's file_path in store
                    track.file_path = dest_file

                except Exception as e:
                    errors.append(f"Failed to move {track.file_path}: {str(e)}")

        if dry_run:
            return jsonify({
                "dry_run": True,
                "moves": moves
            })
        else:
            return jsonify({
                "moved": len(moves) - len(errors),
                "errors": errors
            })

    except Exception as e:
        logger.exception(f"Error in organise routes endpoint")
        return jsonify({"error": "Operation failed. Check server logs."}), 500
