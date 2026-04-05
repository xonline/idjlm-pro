import re
from flask import Blueprint, request, jsonify

bp = Blueprint("key", __name__, url_prefix="/api")


def camelot_distance(k1: str, k2: str) -> int:
    """
    Returns distance between two Camelot keys (0=same, 1=adjacent, >1=mismatch).
    Camelot wheel has 12 positions (1-12), wrapping around.
    Letters are A or B. Adjacent means: same number ±1 OR same letter ±1 number.
    """
    if k1 == k2:
        return 0

    # Parse number and letter
    m1 = re.match(r'(\d+)([AB])', k1.upper())
    m2 = re.match(r'(\d+)([AB])', k2.upper())
    if not m1 or not m2:
        return 99  # unparseable

    n1, l1 = int(m1.group(1)), m1.group(2)
    n2, l2 = int(m2.group(1)), m2.group(2)

    # Same letter, numeric distance
    if l1 == l2:
        diff = abs(n1 - n2)
        return min(diff, 12 - diff)  # wrap around

    # Different letter, same number = 1 step
    if n1 == n2:
        return 1

    return 99  # different number + different letter = significant mismatch


@bp.route("/validate/keys", methods=["GET"])
def validate_keys():
    """
    Check all tracks where both analyzed_key and final_key are present.
    Compares them using Camelot notation.
    Returns tracks with key mismatches (distance >= 2).

    GET /api/validate/keys
    Returns: {
        "total_checked": N,
        "mismatch_count": M,
        "match_count": N - M,
        "mismatches": [
            {
                "file_path": "...",
                "title": "...",
                "artist": "...",
                "stored_key": "8A",
                "analyzed_key": "7B",
                "distance": 2,
                "recommendation": "Update stored key to 7B"
            }
        ]
    }
    """
    try:
        from app import get_track_store

        track_store = get_track_store()
        mismatches = []
        total_checked = 0
        match_count = 0

        for file_path, track in track_store.items():
            # Only check tracks with both analyzed and final keys
            if not track.analyzed_key or not track.final_key:
                continue

            total_checked += 1
            distance = camelot_distance(track.final_key, track.analyzed_key)

            if distance >= 2:
                mismatches.append({
                    "file_path": file_path,
                    "title": track.display_title,
                    "artist": track.display_artist,
                    "stored_key": track.final_key,
                    "analyzed_key": track.analyzed_key,
                    "distance": distance,
                    "recommendation": f"Update stored key to {track.analyzed_key}"
                })
            else:
                match_count += 1

        return jsonify({
            "total_checked": total_checked,
            "mismatch_count": len(mismatches),
            "match_count": match_count,
            "mismatches": mismatches
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/validate/keys/fix", methods=["POST"])
def fix_keys():
    """
    For each path in the request, if use_analyzed=true, set override_key = analyzed_key.
    This ensures the analyzed key will be written on next save.

    POST /api/validate/keys/fix
    body: { "paths": ["...", ...], "use_analyzed": true }
    Returns: { "fixed": N }
    """
    try:
        from app import get_track_store

        data = request.get_json(silent=True) or {}
        paths = data.get("paths", [])
        use_analyzed = data.get("use_analyzed", False)

        if not paths or not use_analyzed:
            return jsonify({"error": "paths array and use_analyzed=true required"}), 400

        track_store = get_track_store()
        fixed = 0

        for file_path in paths:
            if file_path not in track_store:
                continue

            track = track_store[file_path]
            if track.analyzed_key:
                track.override_key = track.analyzed_key
                fixed += 1

        return jsonify({"fixed": fixed}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
