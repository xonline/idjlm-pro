"""
Beatport enrichment service — web scraping (no public API).
Returns: BPM, musical key (Camelot), genre, sub-genre, cover art.
Best source for electronic music metadata.
"""
import re
import json
import logging
import urllib.request
import urllib.parse
import ssl
from typing import Optional

from app.models.track import Track

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _search_beatport(query: str) -> Optional[dict]:
    """
    Search Beatport for a track by scraping their search results page.
    Returns track info dict or None.
    """
    try:
        url = f"https://www.beatport.com/search/tracks?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", _USER_AGENT)
        req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")

        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Try Next.js __NEXT_DATA__ first (most reliable source for Beatport data)
        next_data_match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html,
        )
        if next_data_match:
            try:
                data = json.loads(next_data_match.group(1))
                props = data.get("props", {}).get("pageProps", {})
                results = props.get("results", [])
                if results:
                    item = results[0]
                    return {
                        "title": item.get("title") or item.get("name"),
                        "artist": (
                            item.get("artists", [{}])[0].get("name")
                            if item.get("artists")
                            else None
                        ),
                        "bpm": item.get("bpm"),
                        "key": item.get("musicalKey") or item.get("key"),
                        "genre": (
                            item.get("genre", {}).get("name")
                            if isinstance(item.get("genre"), dict)
                            else item.get("genre")
                        ),
                        "cover_art": item.get("images", {}).get("large") or item.get("image"),
                    }
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        # Fallback: JSON-LD structured data
        json_ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
        matches = re.findall(json_ld_pattern, html, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict) and data.get("@type") == "MusicRecording":
                    return {
                        "title": data.get("name"),
                        "artist": (
                            data.get("byArtist", {}).get("name")
                            if isinstance(data.get("byArtist"), dict)
                            else None
                        ),
                        "bpm": None,
                        "key": None,
                        "genre": None,
                        "cover_art": (
                            data.get("image", [None])[0]
                            if isinstance(data.get("image"), list)
                            else data.get("image")
                        ),
                    }
            except (json.JSONDecodeError, KeyError):
                continue

        return None

    except Exception as e:
        logger.debug("Beatport search failed for '%s': %s", query, e)
        return None


def enrich_with_beatport(track: Track) -> Track:
    """
    Enrich a single track with Beatport data (BPM, key, genre).
    Only fills in fields that are currently empty.
    """
    if track.beatport_enriched:
        return track

    if track.existing_artist and track.existing_title:
        query = f"{track.existing_artist} {track.existing_title}"
    elif track.existing_title:
        query = track.existing_title
    else:
        track.beatport_enriched = True
        return track

    try:
        result = _search_beatport(query)
        if result is None:
            track.beatport_enriched = True
            return track

        # BPM from Beatport (valuable for DJ use)
        if track.analyzed_bpm is None and result.get("bpm") is not None:
            track.beatport_bpm = result["bpm"]

        # Key from Beatport (Camelot notation)
        if not track.analyzed_key and result.get("key") is not None:
            track.beatport_key = result["key"]

        # Genre from Beatport
        if result.get("genre") is not None:
            track.beatport_genre = result["genre"]

        # Cover art fallback
        if not track.album_art_url and not track.beatport_cover_art and result.get("cover_art"):
            track.beatport_cover_art = result["cover_art"]

        track.beatport_enriched = True

    except Exception as e:
        logger.debug("Beatport enrichment failed for %s: %s", track.filename, e)

    return track


def enrich_tracks_with_beatport(tracks: list[Track]) -> list[Track]:
    """Enrich all tracks with Beatport metadata."""
    for track in tracks:
        enrich_with_beatport(track)
    return tracks
