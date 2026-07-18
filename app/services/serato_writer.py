"""Serato .crate binary format writer and parser.

Produces tag-based binary crate files compatible with Serato DJ / Scratch Live.
Each tag: [4-char ASCII ID][4-byte BE uint32 length][data].
Strings encoded as UTF-16-BE, integers as big-endian uint32.

Format reference: https://github.com/mixxxdj/mixxx/wiki/Serato-Database-Format
Parser adapted from: https://gist.github.com/kerrickstaley/8eb04988c02fa7c62e75c4c34c04cf02
"""
import logging
import struct
from pathlib import Path

logger = logging.getLogger(__name__)


# -- Encoding primitives ------------------------------------------------------

def _encode_tag(tag_id: str, data: bytes) -> bytes:
    return tag_id.encode("ascii") + struct.pack(">I", len(data)) + data


def _encode_ustring(s: str) -> bytes:
    return s.encode("utf-16-be")


def _encode_unsigned(v: int) -> bytes:
    return struct.pack(">I", v)


def _encode_struct(items: list) -> bytes:
    payload = b""
    for tag_id, value in items:
        if tag_id == "vrsn":
            encoded = _encode_ustring(value)
        elif tag_id in ("sbav", "brev"):
            encoded = value if isinstance(value, bytes) else bytes([value])
        elif tag_id[0] == "o":
            encoded = _encode_struct(value)
        elif tag_id[0] in ("t", "p"):
            encoded = _encode_ustring(value)
        elif tag_id[0] == "u":
            encoded = _encode_unsigned(value)
        else:
            encoded = value if isinstance(value, bytes) else str(value).encode("utf-8")
        payload += _encode_tag(tag_id, encoded)
    return payload


# -- Decoding / parsing (roundtrip validation) --------------------------------

def _decode_struct(data: bytes) -> list:
    ret = []
    i = 0
    while i < len(data):
        tag = data[i:i+4].decode("ascii")
        length = struct.unpack(">I", data[i+4:i+8])[0]
        value = data[i+8:i+8+length]
        value = _decode_value(value, tag=tag)
        ret.append((tag, value))
        i += 8 + length
    return ret


def _decode_value(data: bytes, tag: str = None):
    _tag_decoders_full = {"vrsn": _decode_ustring, "sbav": _noop}
    _tag_decoders_first = {"o": _decode_struct, "t": _decode_ustring, "p": _decode_ustring, "u": _decode_unsigned, "b": _noop}
    if tag in _tag_decoders_full:
        return _tag_decoders_full[tag](data)
    return _tag_decoders_first.get(tag[0], _noop)(data)


def _decode_ustring(data: bytes) -> str:
    return data.decode("utf-16-be")


def _decode_unsigned(data: bytes) -> int:
    return struct.unpack(">I", data)[0]


def _noop(data: bytes):
    return data


def parse_crate(data: bytes) -> list:
    """Parse a .crate binary blob into a list of (tag, decoded_value) tuples."""
    return _decode_struct(data)


# -- Path helpers -------------------------------------------------------------

def _relative_path(file_path: str, base_path: str = "") -> str:
    if base_path and file_path.startswith(base_path):
        return str(Path(file_path).relative_to(base_path))
    p = Path(file_path)
    if len(p.parts) >= 2:
        return str(Path(*p.parts[-2:]))
    return p.name


# -- Column definitions -------------------------------------------------------

def _build_columns() -> list:
    """Build default browser column definitions.
    Returns o*vct/t*cn/t*cw tag tuples matching Serato's default columns.
    """
    columns = ["key", "artist", "song", "bpm", "playCount", "length", "added"]
    return [("ovct", [("tvcn", col), ("tvcw", "0")]) for col in columns]


# -- Public API ---------------------------------------------------------------

def write_crate(tracks: list, base_path: str = "", crate_name: str = "") -> bytes:
    """Encode a list of Track objects into the Serato .crate binary format.

    Args:
        tracks: List of objects with a .file_path attribute (Track model).
        base_path: Optional common root to make paths relative to.
        crate_name: Optional name (not embedded in format, but used for logger).

    Returns:
        Raw bytes of the .crate file, ready to write to disk.
    """
    crate_data = [
        ("vrsn", "1.0/Serato ScratchLive Crate"),
        ("osrt", [("brev", b"\x00")]),
    ]
    crate_data.extend(_build_columns())

    for track in tracks:
        track_path = _relative_path(track.file_path, base_path)
        track_entries = [("ptrk", track_path)]
        if hasattr(track, "analyzed_bpm") and track.analyzed_bpm:
            track_entries.append(("ubpm", int(round(track.analyzed_bpm * 100))))
        if hasattr(track, "final_key") and track.final_key:
            track_entries.append(("tcom", track.final_key))
        crate_data.append(("otrk", track_entries))

    result = _encode_struct(crate_data)

    logger.info(
        "Serato .crate written: %d tracks%s%s",
        len(tracks),
        f", base_path={base_path}" if base_path else "",
        f", name={crate_name}" if crate_name else "",
    )

    return result


def track_count(crate_bytes: bytes) -> int:
    """Return the number of track entries in a serialised .crate file."""
    parsed = parse_crate(crate_bytes)
    return sum(1 for tag, _ in parsed if tag == "otrk")
