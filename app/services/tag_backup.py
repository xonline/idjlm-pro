"""
Tag backup & restore service.
Before writing tags, current ID3 values are backed up.
Restore from any backup point via API.
Auto-cleanup removes backups older than 7 days (max 20 kept).
"""
import os
import json
import glob
import logging
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _get_backup_dir() -> str:
    """Get user-writable backup directory."""
    import platform
    if platform.system() == "Darwin":
        base = os.path.expanduser("~/Library/Application Support/IDJLM Pro")
    else:
        base = os.path.expanduser("~/.idjlm-pro")
    backup_dir = os.path.join(base, "tag-backups")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def create_backup(track_backups: list[dict]) -> str:
    """
    Save current tag state as a backup.
    track_backups: list of {file_path, existing_title, existing_artist, existing_genre, ...}
    Returns backup ID (timestamp string).
    """
    backup_dir = _get_backup_dir()
    backup_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"{backup_id}.json")

    with open(backup_path, "w") as f:
        json.dump({
            "id": backup_id,
            "created_at": datetime.now().isoformat(),
            "tracks": track_backups,
        }, f, indent=2)

    logger.info("Created tag backup: %s (%d tracks)", backup_id, len(track_backups))

    # Auto-cleanup: remove backups older than 7 days, keep max 20
    _cleanup_backups()

    return backup_id


def list_backups() -> list[dict]:
    """List all available backups, newest first."""
    backup_dir = _get_backup_dir()
    backups = []
    for path in sorted(glob.glob(os.path.join(backup_dir, "*.json")), reverse=True):
        try:
            with open(path) as f:
                data = json.load(f)
            backups.append({
                "id": data.get("id", os.path.basename(path).replace(".json", "")),
                "created_at": data.get("created_at", ""),
                "track_count": len(data.get("tracks", [])),
            })
        except Exception as e:
            logger.warning("Failed to read backup %s: %s", path, e)
    return backups


def get_latest_backup() -> Optional[dict]:
    """Get the most recent backup."""
    backups = list_backups()
    if backups:
        return backups[0]
    return None


def load_backup(backup_id: str) -> Optional[dict]:
    """Load a specific backup by ID."""
    backup_dir = _get_backup_dir()
    backup_path = os.path.join(backup_dir, f"{backup_id}.json")
    if not os.path.exists(backup_path):
        return None
    try:
        with open(backup_path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load backup %s: %s", backup_id, e)
        return None


def _cleanup_backups():
    """Remove backups older than 7 days and keep max 20."""
    backup_dir = _get_backup_dir()
    paths = sorted(glob.glob(os.path.join(backup_dir, "*.json")))

    # Remove backups older than 7 days
    cutoff = time.time() - (7 * 24 * 3600)
    to_remove = []
    for path in paths:
        if os.path.getmtime(path) < cutoff:
            to_remove.append(path)

    # If we still have more than 20, remove oldest first
    remaining = [p for p in paths if p not in to_remove]
    if len(remaining) > 20:
        to_remove.extend(remaining[:len(remaining) - 20])

    for path in to_remove:
        try:
            os.remove(path)
            logger.debug("Removed old backup: %s", os.path.basename(path))
        except Exception:
            pass
