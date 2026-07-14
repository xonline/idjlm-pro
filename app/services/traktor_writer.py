"""Traktor NML format writer.

Produces Native Instruments Traktor NML (Native Instrument's XML playlist format)
compatible with Traktor Pro 3/4. Supports cue points, BPM, key, and basic track
metadata.
"""

import xml.etree.ElementTree as ET
from urllib.parse import quote
from typing import Optional


def _camelot_to_traktor_key(camelot: Optional[str]) -> str:
    if not camelot:
        return ""
    mapping = {
        "1A": "1d", "1B": "8m",
        "2A": "2d", "2B": "9m",
        "3A": "3d", "3B": "10m",
        "4A": "4d", "4B": "11m",
        "5A": "5d", "5B": "12m",
        "6A": "6d", "6B": "1m",
        "7A": "7d", "7B": "2m",
        "8A": "8d", "8B": "3m",
        "9A": "9d", "9B": "4m",
        "10A": "10d", "10B": "5m",
        "11A": "11d", "11B": "6m",
        "12A": "12d", "12B": "7m",
    }
    return mapping.get(camelot, "")


def write_nml(tracks: list, playlist_name: str = "IDJLM Pro Export") -> str:
    """Encode a list of Track objects into Traktor NML XML format.

    Args:
        tracks: Track objects with .file_path, .display_title, .display_artist,
                .analyzed_bpm, .final_key, .suggested_cues, etc.
        playlist_name: Name for the playlist node.

    Returns:
        NML XML string with <?xml?> declaration.
    """
    root = ET.Element("NML")
    root.set("VERSION", "19")

    head = ET.SubElement(root, "HEAD")
    company = ET.SubElement(head, "COMPANY")
    company.set("NAME", "Native Instruments")
    company.set("VERSION", "1.0.0")

    collection = ET.SubElement(root, "COLLECTION")
    collection.set("ENTRIES", str(len(tracks)))

    for track in tracks:
        entry = ET.SubElement(collection, "ENTRY")

        primary_key = ET.SubElement(entry, "PRIMARYKEY")
        location = f"file://localhost{quote(track.file_path, safe='/:')}"
        primary_key.set("TYPE", "TRACK")
        primary_key.set("KEY", location)

        title = ET.SubElement(entry, "TITLE")
        title.text = track.display_title or "Unknown"

        artist = ET.SubElement(entry, "ARTIST")
        artist.text = track.display_artist or "Unknown"

        album = ET.SubElement(entry, "ALBUM")
        album.text = track.existing_album or ""

        genre_elem = ET.SubElement(entry, "GENRE")
        genre_elem.text = track.final_genre or ""

        info = ET.SubElement(entry, "INFO")

        bpm = ET.SubElement(info, "BPM")
        bpm_val = track.analyzed_bpm or 0
        bpm.set("BPM", f"{bpm_val:.2f}")

        key_elem = ET.SubElement(info, "KEY")
        traktor_key = _camelot_to_traktor_key(track.final_key)
        if traktor_key:
            key_elem.set("KEY", traktor_key)

        comment = ET.SubElement(info, "COMMENT")
        comment.text = track.final_comment or ""

        rank = ET.SubElement(info, "RANK")
        rank.set("RANK", "1")

        cues = getattr(track, "suggested_cues", None) or []
        for cue in cues:
            cue_elem = ET.SubElement(info, "CUE_V2")
            name = cue.get("label", f"Cue {cue.get('position_sec', 0):.1f}")
            start = cue.get("position_sec", 0)
            cue_type = cue.get("type", 0)
            cue_elem.set("NAME", name)
            cue_elem.set("START", f"{start:.3f}")
            cue_elem.set("TYPE", str(cue_type))

    xml_bytes = ET.tostring(root, encoding="utf-8")
    declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    return declaration + xml_bytes.decode("utf-8")
