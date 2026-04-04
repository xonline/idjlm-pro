"""Spotify metadata enrichment."""
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


def enrich_tracks(tracks):
    """Optionally enrich with Spotify metadata."""
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    if not (client_id and client_secret):
        return

    try:
        auth = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        sp = spotipy.Spotify(auth_manager=auth)

        for track in tracks:
            try:
                # Search by artist
                if track.existing_artist:
                    results = sp.search(
                        q=f"artist:{track.existing_artist}",
                        type="artist",
                        limit=1
                    )
                    if results["artists"]["items"]:
                        artist = results["artists"]["items"][0]
                        track.spotify_artist_genres = artist.get("genres", [])
                        # Try to get year from first album
                        albums = sp.artist_albums(
                            artist["id"],
                            album_type="album",
                            limit=1
                        )
                        if albums["items"]:
                            year_str = albums["items"][0]["release_date"][:4]
                            try:
                                track.spotify_year = int(year_str)
                            except:
                                pass
            except Exception:
                pass
    except Exception:
        pass
