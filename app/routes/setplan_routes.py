"""
Set planner: auto-generate DJ sets with shaped energy arcs.
"""
import io
from flask import Blueprint, request, jsonify, send_file

bp = Blueprint("setplan", __name__, url_prefix="/api")


# Arc definitions: energy targets for different set shapes
ARC_TEMPLATES = {
    "warmup": [3, 4, 5, 5, 6, 7, 7, 8],
    "peak": [6, 7, 8, 8, 9, 9, 8, 8],
    "cooldown": [8, 8, 7, 7, 6, 5, 4, 3],
    "full_night": [3, 4, 5, 6, 7, 8, 9, 9, 8, 7, 8, 9],
}


def _interpolate_arc(arc_template: list, num_tracks: int) -> list:
    """
    Interpolate arc template to desired number of tracks.
    Uses linear interpolation: target[i] = arc_template[int(i * len(arc_template) / num_tracks)]
    """
    if num_tracks == 0:
        return []
    targets = []
    for i in range(num_tracks):
        # Map track position i to arc_template index
        arc_idx = int(i * len(arc_template) / num_tracks)
        arc_idx = min(arc_idx, len(arc_template) - 1)
        targets.append(arc_template[arc_idx])
    return targets


def _is_harmonically_compatible(bpm1: float, bpm2: float, tolerance_percent: float = 8) -> bool:
    """
    Check if two BPMs are harmonically compatible.
    Compatible if:
    - Within tolerance_percent of each other, OR
    - One is double/half the other
    """
    if not bpm1 or not bpm2:
        return True

    ratio = max(bpm1, bpm2) / min(bpm1, bpm2)
    # Within tolerance
    if abs(bpm1 - bpm2) / bpm2 * 100 <= tolerance_percent:
        return True
    # Double/half
    if abs(ratio - 2.0) < 0.1 or abs(ratio - 0.5) < 0.1:
        return True
    return False


@bp.route("/setplan/arcs", methods=["GET"])
def get_arcs():
    """Return available arc types with descriptions."""
    arcs = [
        {
            "id": "warmup",
            "name": "Warm-Up Set",
            "description": "Start gentle, build the floor gradually",
            "energy_curve": ARC_TEMPLATES["warmup"],
        },
        {
            "id": "peak",
            "name": "Peak Hour Set",
            "description": "High energy from the start, keep the dance floor packed",
            "energy_curve": ARC_TEMPLATES["peak"],
        },
        {
            "id": "cooldown",
            "name": "Cool-Down Set",
            "description": "Bring the energy down gracefully at the end of the night",
            "energy_curve": ARC_TEMPLATES["cooldown"],
        },
        {
            "id": "full_night",
            "name": "Full Night",
            "description": "Complete arc from warm-up through peak hour",
            "energy_curve": ARC_TEMPLATES["full_night"],
        },
    ]
    return jsonify(arcs), 200


@bp.route("/setplan/generate", methods=["POST"])
def generate_setplan():
    """
    Auto-generate a set plan based on desired arc shape and parameters.

    Request body:
    {
        "arc": "warmup",
        "duration_minutes": 60,
        "genre": "Salsa",  (optional)
        "bpm_range": [85, 110],  (optional)
        "seed_path": null  (optional: start from this track)
    }
    """
    try:
        from app import get_track_store

        data = request.get_json(silent=True) or {}
        arc = data.get("arc", "warmup")
        duration_minutes = int(data.get("duration_minutes", 60))
        genre = data.get("genre")
        bpm_range = data.get("bpm_range")  # [min, max]
        seed_path = data.get("seed_path")

        # Validate arc
        if arc not in ARC_TEMPLATES:
            return jsonify({"error": f"Unknown arc: {arc}"}), 400

        track_store = get_track_store()

        # Filter: must have analyzed energy (approved or analyzed tracks)
        tracks = [
            t for t in track_store.values()
            if t.analyzed_energy is not None and t.final_bpm is not None
        ]

        # Apply genre filter
        if genre:
            tracks = [t for t in tracks if t.final_genre == genre]

        # Apply BPM range filter
        if bpm_range and len(bpm_range) == 2:
            bpm_min, bpm_max = bpm_range
            tracks = [
                t for t in tracks
                if t.analyzed_bpm and bpm_min <= t.analyzed_bpm <= bpm_max
            ]

        if not tracks:
            error_detail = "No analyzed tracks found. Run Analyse All first."
            if genre:
                error_detail = f"No analyzed tracks found for genre '{genre}'. Run Analyse All or try a different genre."
            return jsonify({"error": error_detail}), 400

        # Calculate number of tracks needed (assume 4 min average)
        num_tracks = max(8, duration_minutes // 4)

        # Get energy targets
        arc_template = ARC_TEMPLATES[arc]
        energy_targets = _interpolate_arc(arc_template, num_tracks)

        # Track selection algorithm
        selected_tracks = []
        available_tracks = tracks.copy()
        last_bpm = None

        for position, target_energy in enumerate(energy_targets):
            best_track = None
            best_score = float("inf")

            # Try to find track within tolerance
            for tolerance in [1, 2, 3]:
                candidates = [
                    t for t in available_tracks
                    if abs(t.analyzed_energy - target_energy) <= tolerance
                ]

                if not candidates:
                    continue

                # Score candidates by BPM compatibility and energy match
                for candidate in candidates:
                    energy_diff = abs(candidate.analyzed_energy - target_energy)

                    # BPM compatibility score
                    if last_bpm:
                        bpm_compatible = _is_harmonically_compatible(
                            float(candidate.final_bpm or 0), last_bpm
                        )
                        bpm_score = 0 if bpm_compatible else 10
                    else:
                        bpm_score = 0

                    # Total score (lower is better)
                    score = energy_diff + bpm_score

                    if score < best_score:
                        best_score = score
                        best_track = candidate

                if best_track:
                    break

            # If still no track, fallback to any available
            if not best_track and available_tracks:
                best_track = available_tracks[0]

            if best_track:
                selected_tracks.append(best_track)
                available_tracks.remove(best_track)
                last_bpm = float(best_track.final_bpm or 0) if best_track.final_bpm else None

        # Build response with stats
        bpms = [float(t.final_bpm or 0) for t in selected_tracks if t.final_bpm]
        energies = [t.analyzed_energy for t in selected_tracks if t.analyzed_energy]
        genres = {}
        for track in selected_tracks:
            genre_name = track.final_genre or "Unknown"
            genres[genre_name] = genres.get(genre_name, 0) + 1

        # BPM transition analysis
        transitions = []
        for i in range(len(selected_tracks) - 1):
            t1 = selected_tracks[i]
            t2 = selected_tracks[i + 1]
            bpm1 = float(t1.final_bpm) if t1.final_bpm else None
            bpm2 = float(t2.final_bpm) if t2.final_bpm else None
            if bpm1 and bpm2:
                delta = round(bpm2 - bpm1, 1)
                pct = abs(delta) / bpm1 * 100
                if pct <= 3:
                    rating = "smooth"
                elif pct <= 5:
                    rating = "moderate"
                elif pct <= 8:
                    rating = "challenging"
                else:
                    rating = "hard"
                transitions.append({
                    "from": t1.display_title,
                    "to": t2.display_title,
                    "bpm_delta": delta,
                    "bpm_pct_change": round(pct, 1),
                    "rating": rating,
                })

        response = {
            "arc": arc,
            "duration_minutes": duration_minutes,
            "tracks": [
                {
                    "file_path": t.file_path,
                    "title": t.display_title,
                    "artist": t.display_artist,
                    "genre": t.final_genre,
                    "bpm": float(t.final_bpm) if t.final_bpm else None,
                    "key": t.final_key,
                    "energy": t.analyzed_energy,
                    "tempo_category": t.tempo_category,
                    "position": idx + 1,
                    "target_energy": energy_targets[idx],
                }
                for idx, t in enumerate(selected_tracks)
            ],
            "transitions": transitions,
            "stats": {
                "total_tracks": len(selected_tracks),
                "estimated_duration_minutes": len(selected_tracks) * 4,
                "bpm_range": [int(min(bpms)), int(max(bpms))] if bpms else [0, 0],
                "energy_range": [min(energies), max(energies)] if energies else [0, 0],
                "genres": genres,
                "smooth_transitions": sum(1 for t in transitions if t["rating"] in ("smooth", "moderate")),
                "challenging_transitions": sum(1 for t in transitions if t["rating"] in ("challenging", "hard")),
            },
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/setplan/export-m3u", methods=["POST"])
def export_setplan_m3u():
    """
    Export a set plan as M3U.
    Body: {"tracks": [{"file_path": "..."}], "filename": "my-set.m3u"}
    """
    try:
        from app import get_track_store
        from app.routes.export_routes import _generate_m3u_content

        data = request.get_json(silent=True) or {}
        track_paths = [t.get("file_path") for t in data.get("tracks", [])]
        filename = data.get("filename", "setplan.m3u").strip()

        track_store = get_track_store()
        tracks = [track_store[fp] for fp in track_paths if fp in track_store]

        if not tracks:
            return jsonify({"error": "No tracks found"}), 400

        m3u_content = _generate_m3u_content(tracks)

        return send_file(
            io.BytesIO(m3u_content.encode("utf-8")),
            mimetype="audio/x-mpegurl",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
