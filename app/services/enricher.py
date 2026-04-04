import os
from typing import Optional

from app.models.track import Track

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials

    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False


def _search_spotify(sp: Optional[object], query: str) -> Optional[dict]:
    """
    Search Spotify for a track. Returns track info dict or None.
    Expected keys: name, artists[0].name, release_date, id
    """
    if sp is None:
        return None

    try:
        results = sp.search(q=query, type="track", limit=1)
        items = results.get("tracks", {}).get("items", [])
        if items:
            return items[0]
        return None
    except Exception:
        return None


def _extract_artist_genres(sp: Optional[object], artist_id: str) -> list[str]:
    """Fetch genres for an artist from Spotify."""
    if sp is None:
        return []

    try:
        artist = sp.artist(artist_id)
        return artist.get("genres", [])
    except Exception:
        return []


def _enrich_track(track: Track, sp: Optional[object]) -> Track:
    """Enrich a single track with Spotify data."""
    if track.error or sp is None:
        return track

    # Build search query: prefer existing metadata, fall back to filename
    if track.existing_artist and track.existing_title:
        query = f"{track.existing_artist} {track.existing_title}"
    elif track.existing_title:
        query = track.existing_title
    elif track.existing_artist:
        query = track.existing_artist
    else:
        # Use filename without extension
        query = os.path.splitext(track.filename)[0]

    try:
        result = _search_spotify(sp, query)
        if result is None:
            # No match found, leave enrichment fields None
            track.enrichment_done = True
            return track

        # Extract Spotify metadata
        track.spotify_title = result.get("name")

        # Artist
        artists = result.get("artists", [])
        if artists:
            track.spotify_artist = artists[0].get("name")

        # Release date (YYYY-MM-DD format, extract year)
        release_date = result.get("release_date")
        if release_date:
            track.spotify_year = release_date[:4]

        # Genres from artist(s)
        all_genres = []
        for artist in artists:
            artist_id = artist.get("id")
            if artist_id:
                genres = _extract_artist_genres(sp, artist_id)
                all_genres.extend(genres)

        if all_genres:
            # Deduplicate while preserving order
            seen = set()
            deduped = []
            for g in all_genres:
                if g not in seen:
                    deduped.append(g)
                    seen.add(g)
            track.spotify_genres = deduped

        # Album art URL
        album = result.get("album", {})
        images = album.get("images", [])
        if images:
            track.album_art_url = images[0].get("url")

        track.enrichment_done = True

    except Exception as e:
        track.error = f"Spotify enrichment failed: {str(e)}"

    return track


def enrich_tracks(tracks: list[Track]) -> list[Track]:
    """
    Enrich tracks with Spotify metadata.
    If SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET not set, returns tracks unchanged.
    Never overwrites existing_* fields.
    Sets enrichment_done=True when complete, error on failure.
    """
    if not SPOTIPY_AVAILABLE:
        for track in tracks:
            track.error = "spotipy package not installed"
        return tracks

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        # Skip enrichment gracefully
        for track in tracks:
            track.enrichment_done = True
        return tracks

    try:
        auth_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
    except Exception as e:
        for track in tracks:
            track.error = f"Spotify auth failed: {str(e)}"
        return tracks

    # Enrich each track
    for track in tracks:
        _enrich_track(track, sp)

    return tracks
