from mutagen.id3 import ID3, TCON, COMM, TBPM, TKEY, TDRC, APIC, TXXX
from mutagen.mp3 import MP3
import requests

from app.models.track import Track


def _ensure_id3_tags(mp3: MP3) -> None:
    """Create ID3 tag container if it doesn't exist."""
    if mp3.tags is None:
        mp3.add_tags()


def _write_frame(tags, frame_class, value: str, frame_id: str) -> None:
    """Write a simple text frame to ID3 tags."""
    if value is None:
        return

    frame = frame_class(encoding=3, text=[value])
    tags[frame_id] = frame


def write_tags(track: Track) -> Track:
    """
    Write approved tag changes to ID3.
    Only writes fields where final_* differs from existing_*.
    Uses: track.final_genre, track.final_subgenre, track.final_bpm, track.final_key, track.final_year
    Also writes album art if track.album_art_url is set.
    Sets track.tags_written=True on success, track.error on failure.
    """
    if track.error:
        return track

    try:
        mp3 = MP3(track.file_path, ID3=ID3)
        _ensure_id3_tags(mp3)
        tags = mp3.tags

        # Genre: final_genre vs existing_genre
        if track.final_genre and track.final_genre != track.existing_genre:
            _write_frame(tags, TCON, track.final_genre, "TCON")

        # Subgenre: write to COMMENT frame with desc='subgenre'
        if track.final_subgenre and track.final_subgenre != track.existing_comment:
            comm = COMM(encoding=3, lang="eng", desc="subgenre", text=[track.final_subgenre])
            tags["COMM:subgenre:eng"] = comm

        # BPM: final_bpm vs existing_bpm
        if track.final_bpm and track.final_bpm != track.existing_bpm:
            _write_frame(tags, TBPM, track.final_bpm, "TBPM")

        # Key: final_key vs existing_key
        if track.final_key and track.final_key != track.existing_key:
            _write_frame(tags, TKEY, track.final_key, "TKEY")

        # INITIALKEY: Write Camelot notation for Rekordbox/Serato compatibility
        if track.final_key:
            initialkey_frame = TXXX(encoding=3, desc='INITIALKEY', text=[track.final_key])
            tags["TXXX:INITIALKEY"] = initialkey_frame

        # Year: final_year vs existing_year
        if track.final_year and track.final_year != track.existing_year:
            _write_frame(tags, TDRC, track.final_year, "TDRC")

        # Album art from Spotify
        if track.album_art_url:
            try:
                response = requests.get(track.album_art_url, timeout=10)
                if response.status_code == 200:
                    image_data = response.content
                    apic = APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,  # Cover (front)
                        desc='Cover',
                        data=image_data
                    )
                    tags['APIC:'] = apic
            except Exception as img_err:
                # Log image fetch failure but don't fail the entire tag write
                print(f"Warning: Failed to fetch/write album art for {track.filename}: {str(img_err)}")

        # Latin metadata to COMM frames
        # Clave pattern (e.g. "2-3", "3-2")
        if track.clave_pattern:
            clave_comm = COMM(encoding=3, lang="eng", desc="clave", text=[track.clave_pattern])
            tags["COMM:clave:eng"] = clave_comm

        # Energy score
        if track.analyzed_energy:
            energy_comm = COMM(encoding=3, lang="eng", desc="energy", text=[str(track.analyzed_energy)])
            tags["COMM:energy:eng"] = energy_comm

        # Vocal/Instrumental flag
        if track.vocal_flag:
            vocal_comm = COMM(encoding=3, lang="eng", desc="vocal_flag", text=[track.vocal_flag])
            tags["COMM:vocal_flag:eng"] = vocal_comm

        # Tempo category (slow/medium/fast)
        if track.tempo_category:
            tempo_comm = COMM(encoding=3, lang="eng", desc="tempo_category", text=[track.tempo_category])
            tags["COMM:tempo_category:eng"] = tempo_comm

        # Save to file
        mp3.save(v2_version=4)
        track.tags_written = True

    except Exception as e:
        track.error = f"Failed to write tags: {str(e)}"

    return track
