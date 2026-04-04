"""Write tags to ID3."""
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TDRC, COMM
import json
import os
from datetime import datetime


def backup_original_tags(tracks: list):
    """Save original tags before any writes."""
    backup_dir = os.path.expanduser("~/.xdj_library_manager/backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = os.path.join(backup_dir, f"backup-{timestamp}.json")
    data = {}
    for track in tracks:
        data[track.file_path] = {
            "genre": track.existing_genre,
            "title": track.existing_title,
            "artist": track.existing_artist,
            "bpm": track.existing_bpm,
            "key": track.existing_key,
            "year": track.existing_year,
            "comment": track.existing_comment,
        }
    with open(backup_path, "w") as f:
        json.dump(data, f, indent=2)
    return backup_path


def write_tags_to_file(track):
    """Persist track metadata to ID3 tags."""
    try:
        tags = ID3(track.file_path)
    except Exception:
        tags = ID3()

    # Write only fields that differ from existing
    if track.final_genre and track.final_genre != track.existing_genre:
        tags.add(TCON(text=[track.final_genre]))

    if track.existing_title and track.final_genre:
        tags.add(TCON(text=[track.final_genre]))

    # Subgenre in COMM frame
    if track.final_subgenre:
        tags.add(COMM(lang="eng", desc="subgenre", text=[track.final_subgenre]))

    if track.final_year:
        tags.add(TDRC(text=[str(track.final_year)]))

    tags.save(track.file_path)
