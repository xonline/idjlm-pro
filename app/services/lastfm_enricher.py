import os
import logging
from typing import Optional

from app.models.track import Track

logger = logging.getLogger(__name__)


def _search_lastfm(query: str, api_key: str) -> Optional[dict]:
    """
    Search Last.fm for a track. Returns track info dict or None.
    Requires a free API key from last.fm/api.
    """
    import urllib.request
    import urllib.parse
    import json
    import ssl

    try:
        url = (
            f"https://ws.audioscrobbler.com/2.0/?method=track.search"
            f"&track={urllib.parse.quote(query)}"
            f"&api_key={api_key}"
            f"&format=json"
            f"&limit=1"
        )
        req = urllib.request.Request(url)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            result = json.loads(resp.read().decode())
        
        matches = result.get("results", {}).get("trackmatches", {}).get("track", [])
        if not matches:
            return None
        
        track = matches[0] if isinstance(matches, list) else matches
        return {
            "title": track.get("name"),
            "artist": track.get("artist"),
            "url": track.get("url"),
            "listeners": track.get("listeners"),
            "playcount": track.get("playcount"),
            "image": track.get("image", [])[-1].get("#text") if track.get("image") else None,
        }
    except Exception as e:
        logger.debug("Last.fm search failed for '%s': %s", query, e)
        return None


def _get_track_info(track_name: str, artist_name: str, api_key: str) -> Optional[dict]:
    """Get detailed track info including tags from Last.fm."""
    import urllib.request
    import urllib.parse
    import json
    import ssl

    try:
        url = (
            f"https://ws.audioscrobbler.com/2.0/?method=track.getInfo"
            f"&track={urllib.parse.quote(track_name)}"
            f"&artist={urllib.parse.quote(artist_name)}"
            f"&api_key={api_key}"
            f"&format=json"
        )
        req = urllib.request.Request(url)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            result = json.loads(resp.read().decode())
        
        track_data = result.get("track", {})
        if not track_data:
            return None
        
        tags = []
        for tag in track_data.get("toptags", {}).get("tag", []):
            tag_name = tag.get("name", "").strip()
            if tag_name:
                tags.append(tag_name)
        
        return {
            "title": track_data.get("name"),
            "artist": track_data.get("artist", {}).get("name"),
            "album": track_data.get("album"),
            "duration": track_data.get("duration"),
            "playcount": track_data.get("playcount"),
            "listeners": track_data.get("listeners"),
            "tags": tags,
            "url": track_data.get("url"),
            "wiki": track_data.get("wiki", {}).get("summary"),
        }
    except Exception as e:
        logger.debug("Last.fm track.getInfo failed: %s", e)
        return None


def enrich_with_lastfm(track: Track, api_key: str) -> Track:
    """
    Enrich a single track with Last.fm data (genre tags, cover art).
    Only fills in fields that are currently empty.
    """
    if track.enrichment_done:
        return track

    if track.existing_artist and track.existing_title:
        result = _get_track_info(track.existing_title, track.existing_artist, api_key)
    else:
        query = track.existing_title or track.existing_artist or os.path.splitext(track.filename)[0]
        result = _search_lastfm(query, api_key)

    if result is None:
        return track

    # Genre tags from Last.fm
    if result.get("tags") and not track.lastfm_genres:
        # Filter to meaningful genre-like tags
        genre_tags = []
        skip_tags = {"seen live", "favorite", "to own", "my music", "music", "male vocalists", 
                     "female vocalists", "i love", "00s", "10s", "90s", "80s", "70s", "60s"}
        for tag in result["tags"]:
            tag_lower = tag.lower()
            if tag_lower not in skip_tags and len(tag) > 1:
                genre_tags.append(tag)
        track.lastfm_genres = genre_tags[:10]  # Top 10 tags

    # Cover art fallback
    if not track.album_art_url and result.get("image"):
        track.lastfm_cover = result["image"]

    track.lastfm_enriched = True
    return track


def enrich_tracks_with_lastfm(tracks: list[Track], api_key: str) -> list[Track]:
    """Enrich all tracks with Last.fm metadata."""
    if not api_key:
        return tracks
    for track in tracks:
        enrich_with_lastfm(track, api_key)
    return tracks
