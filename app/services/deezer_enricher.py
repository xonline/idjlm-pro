"""
Deezer enrichment service — free, no API key needed.
Returns: BPM, gain (loudness), cover art, release date.
"""
import os
import logging
import urllib.request
import urllib.parse
import json
import ssl
from typing import Optional

from app.models.track import Track

logger = logging.getLogger(__name__)


def _search_deezer(query: str) -> Optional[dict]:
    """
    Search Deezer for a track. Returns track info dict or None.
    Deezer public API requires no API key for read access.
    """
    try:
        url = f"https://api.deezer.com/search?q={urllib.parse.quote(query)}&limit=1"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "IDJLM-Pro/1.0")

        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            result = json.loads(resp.read().decode())

        tracks = result.get("data", [])
        if not tracks:
            return None

        track = tracks[0]

        # Get additional track details for BPM
        track_id = track.get("id")
        bpm = None
        gain = None
        try:
            detail_url = f"https://api.deezer.com/track/{track_id}"
            detail_req = urllib.request.Request(detail_url)
            detail_req.add_header("User-Agent", "IDJLM-Pro/1.0")
            with urllib.request.urlopen(detail_req, timeout=10, context=ctx) as detail_resp:
                detail = json.loads(detail_resp.read().decode())
                bpm = detail.get("BPM")
                gain = detail.get("gain")
        except Exception:
            pass

        return {
            "title": track.get("title"),
            "artist": track.get("artist", {}).get("name"),
            "album": track.get("album", {}).get("title"),
            "bpm": bpm,
            "gain": gain,
            "duration": track.get("duration"),
            "release_date": track.get("release_date") or track.get("album", {}).get("release_date"),
            "preview_url": track.get("preview"),
            "cover_art": track.get("album", {}).get("cover_xl") or track.get("album", {}).get("cover_big"),
            "id": track_id,
        }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        logger.debug("Deezer HTTP error: %s", e.code)
        return None
    except Exception as e:
        logger.debug("Deezer search failed for '%s': %s", query, e)
        return None


def enrich_with_deezer(track: Track) -> Track:
    """
    Enrich a single track with Deezer data.
    Only fills in fields that are currently empty/None.
    Never overwrites existing data from other providers.
    """
    if track.deezer_enriched:
        return track

    # Build search query
    if track.existing_artist and track.existing_title:
        query = f"{track.existing_artist} {track.existing_title}"
    elif track.existing_title:
        query = track.existing_title
    elif track.existing_artist:
        query = track.existing_artist
    else:
        query = os.path.splitext(track.filename)[0]

    try:
        result = _search_deezer(query)
        if result is None:
            track.deezer_enriched = True
            return track

        # Only fill in missing fields — never overwrite
        if not track.deezer_title:
            track.deezer_title = result.get("title")
        if not track.deezer_artist:
            track.deezer_artist = result.get("artist")
        if not track.deezer_year and result.get("release_date"):
            rd = result["release_date"]
            if rd and len(rd) >= 4:
                track.deezer_year = rd[:4]

        # BPM from Deezer (valuable — Spotify doesn't provide this)
        if track.analyzed_bpm is None and result.get("bpm") is not None:
            track.deezer_bpm = result["bpm"]

        # Loudness/gain from Deezer
        if result.get("gain") is not None:
            track.deezer_gain = result["gain"]

        # Cover art URL fallback
        if not track.album_art_url and not track.deezer_cover_art and result.get("cover_art"):
            track.deezer_cover_art = result["cover_art"]

        track.deezer_enriched = True

    except Exception as e:
        logger.debug("Deezer enrichment failed for %s: %s", track.filename, e)

    return track


def enrich_tracks_with_deezer(tracks: list[Track]) -> list[Track]:
    """Enrich all tracks with Deezer metadata."""
    for track in tracks:
        enrich_with_deezer(track)
    return tracks
