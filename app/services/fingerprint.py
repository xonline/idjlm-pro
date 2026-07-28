import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

SUPPORTED_FINGERPRINT_SUFFIXES = frozenset({'.mp3', '.flac', '.wav', '.m4a', '.aac', '.ogg', '.aiff', '.aif', '.wma'})

# AcoustID match scores below this are noise, not identifications.
MIN_ACOUSTID_SCORE = 0.5


def compute_fingerprint(file_path: str) -> Optional[str]:
    result = compute_fingerprint_with_duration(file_path)
    return result[0] if result else None


def compute_fingerprint_with_duration(file_path: str) -> Optional[Tuple[str, int]]:
    """Chromaprint fingerprint plus duration — AcoustID lookup requires both."""
    suffix = os.path.splitext(file_path)[1].lower()
    if suffix not in SUPPORTED_FINGERPRINT_SUFFIXES:
        return None

    try:
        import acoustid
        duration, fingerprint = acoustid.fingerprint_file(file_path)
        if fingerprint:
            if isinstance(fingerprint, bytes):
                fingerprint = fingerprint.decode('utf-8', errors='replace')
            return str(fingerprint), int(duration)
    except ImportError:
        logger.warning("acoustid not available — fingerprint disabled")
    except Exception as exc:
        logger.debug("Fingerprint failed for %s: %s", file_path, exc)

    return None


def is_acoustid_enabled() -> bool:
    return bool(os.getenv("ACOUSTID_API_KEY"))


def identify_track(file_path: str) -> Optional[dict]:
    """Identify a track with no usable metadata via AcoustID + MusicBrainz.

    Returns the best-scoring match, or None when the key is absent, the lookup
    fails, or nothing clears MIN_ACOUSTID_SCORE. Never raises — identification
    is best-effort enrichment, not a hard dependency of the import path.
    """
    api_key = os.getenv("ACOUSTID_API_KEY")
    if not api_key:
        logger.info("ACOUSTID_API_KEY not set — track identification disabled")
        return None

    computed = compute_fingerprint_with_duration(file_path)
    if not computed:
        return None
    fingerprint, duration = computed

    try:
        import acoustid
        # meta is a list of keywords per pyacoustid's contract (DEFAULT_META).
        raw = acoustid.lookup(api_key, fingerprint, duration, meta=["recordings"])
    except Exception as exc:
        logger.warning("AcoustID lookup failed for %s: %s", file_path, exc)
        return None

    return _parse_lookup_response(raw)


def _parse_lookup_response(raw: dict) -> Optional[dict]:
    """Pick the best-scoring recording out of an AcoustID lookup payload."""
    if not isinstance(raw, dict) or raw.get("status") != "ok":
        return None

    best = None
    for result in raw.get("results") or []:
        score = float(result.get("score") or 0.0)
        if score < MIN_ACOUSTID_SCORE:
            continue
        for recording in result.get("recordings") or []:
            title = recording.get("title")
            if not title:
                continue
            artists = recording.get("artists") or []
            artist = ", ".join(a.get("name", "") for a in artists if a.get("name"))
            candidate = {
                "acoustid": result.get("id"),
                "musicbrainz_id": recording.get("id"),
                "title": title,
                "artist": artist or None,
                "score": round(score, 4),
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate

    return best
