"""Session persistence."""
import json
import os
from datetime import datetime
from app.models.track import Track


def save_session(track_store: dict, folder: str = None):
    """Persist track store to session.json."""
    if folder is None:
        folder = os.path.expanduser("~/Music")

    session_file = os.path.join(folder, "session.json")
    session_data = {
        "timestamp": datetime.now().isoformat(),
        "folder": folder,
        "tracks": [t.to_dict() for t in track_store.values()],
    }

    with open(session_file, "w") as f:
        json.dump(session_data, f, indent=2)


def load_session(folder: str = None) -> list:
    """Restore track store from session.json."""
    if folder is None:
        folder = os.path.expanduser("~/Music")

    session_file = os.path.join(folder, "session.json")
    if not os.path.exists(session_file):
        return []

    with open(session_file) as f:
        session_data = json.load(f)

    tracks = []
    for track_dict in session_data.get("tracks", []):
        try:
            track = Track(**track_dict)
            tracks.append(track)
        except Exception:
            pass

    return tracks
