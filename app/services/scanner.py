"""Scan folders for MP3 files."""
import os
import hashlib
from pathlib import Path
from mutagen.id3 import ID3, ID3NoHeaderError
from app.models.track import Track


def scan_folder(folder_path: str) -> list:
    """Recursively scan for MP3s, read existing tags."""
    tracks = []
    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            if filename.lower().endswith(".mp3"):
                file_path = os.path.join(root, filename)
                track_id = hashlib.md5(file_path.encode()).hexdigest()

                # Read existing tags
                try:
                    tags = ID3(file_path)
                    title = str(tags.get("TIT2", ""))
                    artist = str(tags.get("TPE1", ""))
                    album = str(tags.get("TALB", ""))
                    genre = str(tags.get("TCON", ""))
                    year_str = str(tags.get("TDRC", ""))
                    year = int(year_str) if year_str.isdigit() else None
                except (ID3NoHeaderError, Exception):
                    title = artist = album = genre = None
                    year = None

                track = Track(
                    id=track_id,
                    file_path=file_path,
                    existing_title=title or None,
                    existing_artist=artist or None,
                    existing_album=album or None,
                    existing_genre=genre or None,
                    existing_year=year,
                )
                tracks.append(track)
    return tracks
