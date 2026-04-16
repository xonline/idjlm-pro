"""
Multi-source metadata enrichment orchestrator.
Chains providers: Spotify → Deezer → Last.fm → Beatport.
Each provider only fills in fields that are still empty.
"""
import os
import logging
from typing import Optional

from app.models.track import Track
from app.services.enricher import enrich_tracks as enrich_with_spotify

logger = logging.getLogger(__name__)


def _enrich_single_track(track: Track, config: dict) -> Track:
    """Run a track through the configured enrichment chain."""
    # 1. Spotify (if enabled and has credentials)
    if config.get("spotify_enabled"):
        track = enrich_with_spotify([track])[0]

    # 2. Deezer (free, no auth needed — always runs)
    if config.get("deezer_enabled"):
        from app.services.deezer_enricher import enrich_with_deezer
        track = enrich_with_deezer(track)

    # 3. Last.fm (needs API key)
    lastfm_key = config.get("lastfm_api_key") or os.getenv("LASTFM_API_KEY")
    if lastfm_key:
        from app.services.lastfm_enricher import enrich_with_lastfm
        track = enrich_with_lastfm(track, lastfm_key)

    # 4. Beatport (scraping — optional, can be slow)
    if config.get("beatport_enabled"):
        from app.services.beatport_enricher import enrich_with_beatport
        track = enrich_with_beatport(track)

    track.enrichment_done = True
    return track


def enrich_tracks(tracks: list[Track], config: Optional[dict] = None) -> list[Track]:
    """
    Enrich tracks through the configured provider chain.

    config dict keys:
        spotify_enabled: bool
        deezer_enabled: bool
        lastfm_api_key: str (optional, falls back to LASTFM_API_KEY env)
        beatport_enabled: bool
    """
    if config is None:
        config = {
            "spotify_enabled": bool(os.getenv("SPOTIFY_CLIENT_ID") and os.getenv("SPOTIFY_CLIENT_SECRET"))
                and os.getenv("SPOTIFY_ENRICH_ENABLED", "true").lower() == "true",
            "deezer_enabled": os.getenv("DEEZER_ENRICH_ENABLED", "true").lower() == "true",
            "beatport_enabled": os.getenv("BEATPORT_ENRICH_ENABLED", "false").lower() == "true",
            "lastfm_api_key": os.getenv("LASTFM_API_KEY", ""),
        }

    for track in tracks:
        try:
            _enrich_single_track(track, config)
        except Exception as e:
            logger.debug("Enrichment failed for %s: %s", track.filename, e)
            track.enrichment_done = True

    return tracks
