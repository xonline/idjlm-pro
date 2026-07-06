import hashlib
import json
import logging
import os
import threading
from typing import Optional

from app.models.track import Track
from app.utils.paths import user_data_path, atomic_write

logger = logging.getLogger(__name__)

ANALYSIS_CACHE_FILE = "analysis_cache.json"

ANALYSIS_CACHE_FIELDS = [
    "analyzed_bpm", "analyzed_key", "analyzed_energy", "raw_rms",
    "duration", "bpm_corrected", "bpm_confidence", "key_confidence",
    "vocal_flag", "vocal_confidence", "tempo_category",
    "analyzed_lufs", "analyzed_lufs_range", "analyzed_true_peak",
    "waveform_data", "waveform_peaks", "bpm_from_tags",
    "analysis_done",
]

_cache: dict = {}
_cache_lock = threading.Lock()
_cache_loaded = False


def _ensure_loaded() -> None:
    global _cache, _cache_loaded
    if _cache_loaded:
        return
    path = user_data_path(ANALYSIS_CACHE_FILE)
    if os.path.exists(path):
        try:
            with open(path) as f:
                _cache = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load analysis cache: %s", e)
            _cache = {}
    else:
        _cache = {}
    _cache_loaded = True


def _save() -> None:
    path = user_data_path(ANALYSIS_CACHE_FILE)
    try:
        atomic_write(path, _cache, indent=2)
    except OSError as e:
        logger.error("Failed to save analysis cache: %s", e)


def get(content_hash: str) -> Optional[dict]:
    if not content_hash:
        return None
    with _cache_lock:
        _ensure_loaded()
        return _cache.get(content_hash)


def put(track: Track) -> None:
    if not track.content_hash:
        return
    entry = {}
    for field in ANALYSIS_CACHE_FIELDS:
        val = getattr(track, field, None)
        if val is not None:
            entry[field] = val
    if not entry:
        return
    with _cache_lock:
        _ensure_loaded()
        _cache[track.content_hash] = entry
        _save()


def restore(track: Track) -> bool:
    if not track.content_hash:
        return False
    cached = get(track.content_hash)
    if cached is None:
        return False
    for field, value in cached.items():
        setattr(track, field, value)
    logger.debug("Restored analysis from cache for %s", track.file_path)
    return True


def compute_hash(file_path: str, max_bytes: int = 1048576) -> str:
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(max_bytes)
            h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def clear() -> None:
    with _cache_lock:
        _cache.clear()
        _save()
