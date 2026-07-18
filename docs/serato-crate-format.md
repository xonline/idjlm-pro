# Serato .crate Format — Implementation Notes

**Source:** [Mixxx Wiki — Serato Database Format](https://github.com/mixxxdj/mixxx/wiki/Serato-Database-Format)
**Parser ref:** [Kerrick Staley's gist](https://gist.github.com/kerrickstaley/8eb04988c02fa7c62e75c4c34c04cf02)
**Implemented:** Issue #347 (E.1 — 2026-07-16)
**Files:**
- `app/services/serato_writer.py` — core writer + `parse_crate()` parser
- `app/routes/export_routes.py` — `/api/export/serato-crate` route
- `app/static/modules/sync-center.js` — Sync Center Serato card (Export Crate button)
- `tests/test_phase_e.py::TestSeratoWriter` — 10 tests (roundtrip, edge cases, structure)

## Format

Tag-based binary, not JSON/XML. Each tag: `[4-char ASCII ID][4-byte BE uint32 length][data]`.

| Prefix | Encoding | Meaning |
|--------|----------|---------|
| `o*` | Nested struct | Container of sub-records |
| `t*` | UTF-16-BE | Text string |
| `p*` | UTF-16-BE | File path (relative to drive root) |
| `u*` | BE uint32 | Unsigned integer |
| `s*` | BE int32 | Signed integer |
| `b*` | Raw bytes | Byte value |

## Tags Used

| Tag | Encoding | Purpose |
|-----|----------|---------|
| `vrsn` | UTF-16-BE | Version: `1.0/Serato ScratchLive Crate` |
| `osrt` | struct | Sort order, contains `brev \x00` |
| `brev` | 1 byte | Unknown, `\x00` |
| `ovct` | struct | View column definition, contains `tvcn` + `tvcw` |
| `tvcn` | UTF-16-BE | Column name (key, artist, song, bpm, playCount, length, added) |
| `tvcw` | UTF-16-BE | Column width (always `0` = auto) |
| `otrk` | struct | Track entry container, contains `ptrk` |
| `ptrk` | UTF-16-BE | Track file path (relative or last-2-components) |

## Important Notes

1. **Crate name is NOT stored** in the file — it's derived from the `.crate` filename.
2. **Metadata (BPM, key, genre) is NOT stored** in `.crate` files. Only track paths.
   Serato stores per-track metadata in `database V2` and per-file ID3 GEOB tags.
3. **Relative paths:** Tracks are stored relative to the music drive root (e.g.
   `Music/Genre/Artist - Track.mp3`). When `base_path` is provided, paths are
   relative to it. Otherwise, the last two path components are used.

## Writer API

```python
from app.services.serato_writer import write_crate, parse_crate, track_count

# Write tracks to .crate bytes
crate_bytes = write_crate(tracks, base_path="/Music")

# Parse for validation
parsed = parse_crate(crate_bytes)  # list of (tag, decoded_value) tuples

# Quick track count
count = track_count(crate_bytes)
```

## Structure Example

```
vrsn  → "1.0/Serato ScratchLive Crate"
osrt  → brev \x00
ovct  → tvcn "key", tvcw "0"
ovct  → tvcn "artist", tvcw "0"
ovct  → tvcn "song", tvcw "0"
ovct  → tvcn "bpm", tvcw "0"
ovct  → tvcn "playCount", tvcw "0"
ovct  → tvcn "length", tvcw "0"
ovct  → tvcn "added", tvcw "0"
otrk  → ptrk "House/Track 1 - Artist - Title.mp3"
otrk  → ptrk "Techno/Track 2 - Artist - Title.mp3"
```

## Verification

- 10 unit tests covering: roundtrip write+parse, relative paths, empty crate,
  special characters, last-2-part default, column defs, track order, track_count
- Export endpoint: `GET /api/export/serato-crate` returns `application/octet-stream`
- Sync Center card shows "Export Crate" button linking to the endpoint
- Screenshot: `~/docs/screenshots/idjlm-sync-center.png`
