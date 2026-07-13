import os
from pathlib import Path
from typing import Optional

from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from mutagen import File as MutagenFile

from app.models.track import Track

# Supported audio file extensions
SUPPORTED_EXTENSIONS = {'.mp3', '.flac', '.wav', '.m4a', '.aac', '.ogg', '.aiff', '.aif'}


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
    Returns dict with keys: title, artist, album, year, genre, comment, bpm, key, custom_tags
    All values are Optional[str] or None if tag missing/unreadable.
    custom_tags is a dict of user-defined TXXX frame descriptions -> values.
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
        'custom_tags': {},
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

    # Read TXXX custom tags (skip INITIALKEY which is managed internally)
    for txxx in audio.tags.getall('TXXX'):
        if hasattr(txxx, 'desc') and hasattr(txxx, 'text') and txxx.text:
            desc = txxx.desc
            if desc and desc != 'INITIALKEY':
                tags['custom_tags'][desc] = str(txxx.text[0])

    return tags


def _read_tags_universal(file_path: str) -> dict:
    """
    Read tags from audio files using mutagen's format-agnostic API.
    Used for FLAC, WAV, M4A, AAC, OGG, and other formats.
    Returns dict with keys: title, artist, album, year, genre, comment, bpm, key, custom_tags
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
        'custom_tags': {},
    }

    try:
        audio = MutagenFile(file_path, easy=True)
        if audio is None or audio.tags is None:
            return tags

        def get(key):
            """Extract first value from tag, or None if missing."""
            v = audio.tags.get(key)
            return str(v[0]) if v else None

        tags['title'] = get('title')
        tags['artist'] = get('artist')
        tags['album'] = get('album')
        tags['year'] = get('date')
        tags['genre'] = get('genre')
        tags['comment'] = get('comment')
        tags['bpm'] = get('bpm')
        tags['key'] = get('initialkey')

        # Read custom tags: open with full (non-easy) API to access TXXX-like frames
        try:
            audio_full = MutagenFile(file_path)
            if audio_full and audio_full.tags:
                # For MP3/ID3 files caught here (edge case) read TXXX frames
                for txxx in audio_full.tags.getall('TXXX'):
                    if hasattr(txxx, 'desc') and hasattr(txxx, 'text') and txxx.text:
                        desc = txxx.desc
                        if desc and desc != 'INITIALKEY':
                            tags['custom_tags'][desc] = str(txxx.text[0])
                # For Vorbis/FLAC: all keys not in the standard set are custom
                if hasattr(audio_full.tags, 'get'):
                    standard_keys = {'title', 'artist', 'album', 'date', 'genre',
                                     'comment', 'bpm', 'initialkey', 'tracknumber',
                                     'discnumber', 'composer', 'performer', 'copyright',
                                     'encodedby', 'encoding', 'vendor', 'description',
                                     'mimetype'}
                    if hasattr(audio_full.tags, 'keys'):
                        for key in audio_full.tags.keys():
                            if key.lower() not in standard_keys:
                                vals = audio_full.tags.get(key)
                                if vals:
                                    tags['custom_tags'][key] = str(vals[0])
        except Exception:
            pass
    except Exception:
        pass

    return tags


def _get_file_stat(file_path: str) -> tuple:
    """Return (mtime, file_size) for a file, or (None, None) on error."""
    try:
        st = os.stat(file_path)
        return st.st_mtime, st.st_size
    except OSError:
        return None, None


def _read_duration_seconds(file_path: str, suffix: str) -> Optional[float]:
    """
    Read track duration in seconds from mutagen. Returns None on failure.
    """
    try:
        if suffix == '.mp3':
            audio = MP3(file_path)
        else:
            audio = MutagenFile(file_path)
        if audio is None:
            return None
        length = getattr(audio.info, 'length', None)
        if length is None or length <= 0:
            return None
        return round(float(length), 2)
    except Exception:
        return None


def scan_folder(folder_path: str) -> list[Track]:
    """
    Recursively scan folder for supported audio files (MP3, FLAC, WAV, M4A, AAC, OGG)
    and extract tags.
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
            suffix = Path(filename).suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                continue

            file_path = os.path.join(root, filename)

            try:
                # Use MP3-specific reader for MP3 files, universal reader for others
                if suffix == '.mp3':
                    audio_tags = _read_id3_tags(file_path)
                else:
                    audio_tags = _read_tags_universal(file_path)

                from app.services.analysis_cache import compute_hash
                from app.services.fingerprint import compute_fingerprint
                content_hash = compute_hash(file_path)
                audio_fingerprint = compute_fingerprint(file_path)
                file_mtime, file_size = _get_file_stat(file_path)
                track = Track(
                    file_path=file_path,
                    filename=filename,
                    existing_title=audio_tags['title'],
                    existing_artist=audio_tags['artist'],
                    existing_album=audio_tags['album'],
                    existing_year=audio_tags['year'],
                    existing_genre=audio_tags['genre'],
                    existing_comment=audio_tags['comment'],
                    existing_bpm=audio_tags['bpm'],
                    existing_key=audio_tags['key'],
                    custom_tags=audio_tags.get('custom_tags', {}),
                    duration=_read_duration_seconds(file_path, suffix),
                    content_hash=content_hash,
                    audio_fingerprint=audio_fingerprint,
                    file_mtime=file_mtime,
                    file_size=file_size,
                )
                tracks.append(track)

            except Exception as e:
                # File couldn't be read at all
                file_mtime, file_size = _get_file_stat(file_path)
                track = Track(
                    file_path=file_path,
                    filename=filename,
                    error=f"Failed to read tags: {str(e)}",
                    file_mtime=file_mtime,
                    file_size=file_size,
                )
                tracks.append(track)

    return tracks


def scan_folder_incremental(folder_path: str, track_store: dict) -> tuple[list[Track], list[str]]:
    """
    Recursively scan folder for audio files, skipping unchanged files.

    For each file on disk:
      - If the file is already in the track_store with the same mtime AND
        file_size, reuse the existing Track from the store (no I/O for
        reading tags or computing hashes).
      - If the file is new or has changed (different mtime or size), process
        it fully via _scan_single_file.

    Returns (tracks, stale_paths) where:
      - tracks: list of Track objects for ALL current files (unchanged +
        newly scanned)
      - stale_paths: list of file paths that are in the store but no longer
        exist on disk (should be removed from the store by the caller)
    """
    import logging
    logger = logging.getLogger(__name__)

    tracks = []
    folder = Path(folder_path).expanduser().resolve()
    if not folder.is_dir():
        return [], []

    store_keys = set(track_store.keys())
    disk_paths: set[str] = set()
    unchanged_count = 0
    scanned_count = 0

    for root, dirs, files in os.walk(folder):
        for filename in files:
            suffix = Path(filename).suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                continue

            file_path = os.path.join(root, filename)
            disk_paths.add(file_path)

            disk_mtime, disk_size = _get_file_stat(file_path)
            if disk_mtime is None:
                continue

            existing = track_store.get(file_path)
            if existing is not None:
                if (existing.file_mtime == disk_mtime and
                        existing.file_size == disk_size):
                    tracks.append(existing)
                    unchanged_count += 1
                    continue

            track = _scan_single_file(file_path, filename, suffix)
            tracks.append(track)
            scanned_count += 1

    stale_paths = sorted(store_keys - disk_paths)

    if unchanged_count or scanned_count:
        logger.info(
            "Incremental scan: %d unchanged, %d scanned, %d stale",
            unchanged_count, scanned_count, len(stale_paths),
        )

    return tracks, stale_paths


def _scan_single_file(file_path: str, filename: str, suffix: str) -> Track:
    """Fully scan a single audio file and return a Track object."""
    try:
        if suffix == '.mp3':
            audio_tags = _read_id3_tags(file_path)
        else:
            audio_tags = _read_tags_universal(file_path)

        from app.services.analysis_cache import compute_hash
        from app.services.fingerprint import compute_fingerprint
        content_hash = compute_hash(file_path)
        audio_fingerprint = compute_fingerprint(file_path)
        file_mtime, file_size = _get_file_stat(file_path)
        return Track(
            file_path=file_path,
            filename=filename,
            existing_title=audio_tags['title'],
            existing_artist=audio_tags['artist'],
            existing_album=audio_tags['album'],
            existing_year=audio_tags['year'],
            existing_genre=audio_tags['genre'],
            existing_comment=audio_tags['comment'],
            existing_bpm=audio_tags['bpm'],
            existing_key=audio_tags['key'],
            custom_tags=audio_tags.get('custom_tags', {}),
            duration=_read_duration_seconds(file_path, suffix),
            content_hash=content_hash,
            audio_fingerprint=audio_fingerprint,
            file_mtime=file_mtime,
            file_size=file_size,
        )
    except Exception as e:
        file_mtime, file_size = _get_file_stat(file_path)
        return Track(
            file_path=file_path,
            filename=filename,
            error=f"Failed to read tags: {str(e)}",
            file_mtime=file_mtime,
            file_size=file_size,
        )
