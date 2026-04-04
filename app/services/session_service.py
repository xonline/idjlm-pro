"""Session persistence."""
import json
import os
from datetime import datetime
from app.models.track import Track

# Global tracking for last save time
_last_save_time = None


def save_session(track_store: dict, folder: str = None):
    """Persist track store to session.json."""
    global _last_save_time
    
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
    
    _last_save_time = datetime.now().isoformat()


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


def get_last_save_time() -> str:
    """Get the last save timestamp (ISO format)."""
    global _last_save_time
    return _last_save_time or "never"
