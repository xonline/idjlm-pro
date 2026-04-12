import os
import sys
import json
import logging
import platform
from datetime import datetime
from typing import Optional, Tuple
from app.models.track import Track

logger = logging.getLogger(__name__)


def _get_session_path() -> str:
    """Return user-writable path for session.json (never the read-only bundle)."""
    if platform.system() == "Darwin":
        d = os.path.expanduser("~/Library/Application Support/IDJLM Pro")
    else:
        d = os.path.expanduser("~/.idjlm-pro")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "session.json")


SESSION_FILE = _get_session_path()


def save_session(track_store: dict, folder_path: Optional[str] = None) -> dict:
    """
    Serialise the entire track store to session.json.
    Args:
        track_store: dict of file_path -> Track objects
        folder_path: optional folder path to include in metadata
    Returns:
        dict with serialized session data
    """
    try:
        # Serialize tracks
        tracks_data = {}
        for file_path, track in track_store.items():
            tracks_data[file_path] = track.to_dict()

        # Build session object
        session_data = {
            "saved_at": datetime.utcnow().isoformat() + "Z",
            "folder_path": folder_path,
            "track_count": len(tracks_data),
            "tracks": tracks_data
        }

        # Write to session.json in project root
        with open(SESSION_FILE, 'w') as f:
            json.dump(session_data, f, indent=2)

        return session_data

    except Exception as e:
        raise Exception(f"Failed to save session: {str(e)}")


def load_session() -> Tuple[Optional[dict], Optional[dict]]:
    """
    Load session from session.json and reconstruct Track objects.
    Returns:
        tuple of (track_store_dict, metadata) or (None, None) if file missing
    """
    try:
        if not os.path.exists(SESSION_FILE):
            return None, None

        with open(SESSION_FILE, 'r') as f:
            session_data = json.load(f)

        # Extract metadata
        metadata = {
            "saved_at": session_data.get("saved_at"),
            "folder_path": session_data.get("folder_path"),
            "track_count": session_data.get("track_count", 0)
        }

        # Reconstruct Track objects
        track_store = {}
        tracks_data = session_data.get("tracks", {})

        # Get the actual dataclass field names to filter out computed properties
        _dataclass_fields = set(Track.__dataclass_fields__.keys())

        for file_path, track_dict in tracks_data.items():
            try:
                # Filter out non-dataclass keys (display_title, final_genre, etc.)
                clean_dict = {k: v for k, v in track_dict.items() if k in _dataclass_fields}
                track = Track(**clean_dict)
                track_store[file_path] = track
            except Exception as e:
                # Log issue but continue loading other tracks
                logger.warning("Failed to reconstruct track %s: %s", file_path, e)
                continue

        return track_store, metadata

    except Exception as e:
        raise Exception(f"Failed to load session: {str(e)}")
