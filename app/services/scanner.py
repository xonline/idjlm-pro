import os
from pathlib import Path
from typing import Optional

from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TYER, TCON, COMM, TBPM, TKEY
from mutagen.mp3 import MP3

from app.models.track import Track


def _extract_id3_text(frame) -> Optional[str]:
    """Safely extract text from ID3 frame, handling various frame types."""
    if frame is None:
        return None
    if hasattr(frame, 'text') and frame.text:
        return str(frame.text[0])
    return None


def _read_id3_tags(file_path: str) -> dict:
    """
    Read ID3 tags from MP3 file.
    Returns dict with keys: title, artist, album, year, genre, comment, bpm, key
    All values are Optional[str] or None if tag missing/unreadable.
    """
    tags = {
        'title': None,
        'artist': None,
        'album': None,
        'year': None,
        'genre': None,
        'comment': None,
        'bpm': None,
        'key': None,
    }

    try:
        audio = MP3(file_path, ID3=ID3)
    except Exception:
        # File has no ID3 tag at all
        return tags

    if audio.tags is None:
        return tags

    # Extract each tag frame
    tags['title'] = _extract_id3_text(audio.tags.get('TIT2'))
    tags['artist'] = _extract_id3_text(audio.tags.get('TPE1'))
    tags['album'] = _extract_id3_text(audio.tags.get('TALB'))

    # Year: try TDRC first (TDRC=date), fallback to TYER (deprecated)
    year_frame = audio.tags.get('TDRC') or audio.tags.get('TYER')
    tags['year'] = _extract_id3_text(year_frame)

    tags['genre'] = _extract_id3_text(audio.tags.get('TCON'))
    tags['bpm'] = _extract_id3_text(audio.tags.get('TBPM'))
    tags['key'] = _extract_id3_text(audio.tags.get('TKEY'))

    # COMM (comment) frame: desc, lang, text
    comm_frame = audio.tags.get('COMM')
    if comm_frame and hasattr(comm_frame, 'text') and comm_frame.text:
        tags['comment'] = str(comm_frame.text[0])

    return tags


def scan_folder(folder_path: str) -> list[Track]:
    """
    Recursively scan folder for MP3 files and extract ID3 tags.
    Returns list of Track objects with existing_* fields populated.
    Handles files with no tags gracefully (sets all existing_* to None).
    Files that can't be read set the error field.
    """
    tracks = []
    folder_path = Path(folder_path).expanduser().resolve()

    if not folder_path.is_dir():
        return []

    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            if not filename.lower().endswith('.mp3'):
                continue

            file_path = os.path.join(root, filename)

            try:
                id3_tags = _read_id3_tags(file_path)

                track = Track(
                    file_path=file_path,
                    filename=filename,
                    existing_title=id3_tags['title'],
                    existing_artist=id3_tags['artist'],
                    existing_album=id3_tags['album'],
                    existing_year=id3_tags['year'],
                    existing_genre=id3_tags['genre'],
                    existing_comment=id3_tags['comment'],
                    existing_bpm=id3_tags['bpm'],
                    existing_key=id3_tags['key'],
                )
                tracks.append(track)

            except Exception as e:
                # File couldn't be read at all
                track = Track(
                    file_path=file_path,
                    filename=filename,
                    error=f"Failed to read ID3 tags: {str(e)}",
                )
                tracks.append(track)

    return tracks
