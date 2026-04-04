"""Write tags to ID3."""
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TDRC, COMM


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
