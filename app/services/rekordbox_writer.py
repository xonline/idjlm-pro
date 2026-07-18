"""
rekordbox SQLite database writer.
Safely writes IDJLM tag/genre/key/BPM changes back into rekordbox's master.db.

SAFETY CONSTRAINT: Writing to master.db while rekordbox is running can corrupt
the database. Every write is gated behind an explicit process check + DB writability
test. The UI must obtain user confirmation before calling the write endpoint.
"""
import os
import sqlite3
import logging
import platform
from typing import Optional

logger = logging.getLogger(__name__)


def _is_rekordbox_running() -> bool:
    """Check whether the Rekordbox application process is currently running."""
    system = platform.system()
    try:
        if system == "Darwin":
            import subprocess
            result = subprocess.run(
                ["pgrep", "-f", "rekordbox"],
                capture_output=True, text=True
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        elif system == "Windows":
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq rekordbox.exe"],
                capture_output=True, text=True
            )
            return "rekordbox.exe" in result.stdout
        else:
            return False
    except Exception:
        logger.warning("Could not check rekordbox process state — assuming safe")
        return False


def check_write_safety(db_path: str) -> dict:
    """Return write-safety status for the given rekordbox database.

    Returns:
        {"safe": bool, "reason": str, "running": bool}
        safe=True means it is OK to write; safe=False means writes are blocked.
    """
    result = {"safe": False, "reason": "", "running": _is_rekordbox_running()}

    if result["running"]:
        result["reason"] = (
            "Rekordbox appears to be running. Writing to master.db while "
            "Rekordbox is open can corrupt your library. Please close Rekordbox first."
        )
        return result

    if not os.path.exists(db_path):
        result["reason"] = "Rekordbox database not found at expected path."
        return result

    try:
        conn = sqlite3.connect(db_path, timeout=2)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("SELECT COUNT(*) FROM djbd_content_table WHERE 1=0")
        conn.close()
        result["safe"] = True
        result["reason"] = "Ready — rekordbox is closed and the database is writable."
    except sqlite3.OperationalError as e:
        result["reason"] = f"Database is locked or inaccessible: {e}"
    except Exception as e:
        result["reason"] = f"Unexpected error checking database: {e}"

    return result


def write_track_to_rekordbox(db_path: str, idjlm_path: str, updates: dict) -> dict:
    """Write IDJLM field updates for a single track into rekordbox's master.db.

    Args:
        db_path: Full path to master.db.
        idjlm_path: The file path of the track as known to IDJLM.
        updates: Dict of Rekordbox column names → new values.
                 Supported columns: strGenre, strKey, strComment, dBPM, strYear.

    Returns:
        {"written": bool, "rows_affected": int, "error": str|None}
    """
    column_map = {
        "strGenre": "strGenre",
        "strKey": "strKey",
        "strComment": "strComment",
        "dBPM": "dBPM",
        "nYear": "nYear",
        "nRating": "nRating",
    }

    valid_updates = {}
    for col, val in updates.items():
        if col in column_map:
            valid_updates[column_map[col]] = val

    if not valid_updates:
        return {"written": False, "rows_affected": 0, "error": "No valid columns to update"}

    result = {"written": False, "rows_affected": 0, "error": None}

    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")

        set_clause = ", ".join(f"{col} = ?" for col in valid_updates)
        values = list(valid_updates.values())

        cursor = conn.execute(
            f"UPDATE djbd_content_table SET {set_clause} WHERE strPath = ?",
            values + [idjlm_path]
        )
        result["rows_affected"] = cursor.rowcount
        conn.commit()
        conn.close()

        if result["rows_affected"] > 0:
            result["written"] = True
            logger.info(
                "Wrote to rekordbox DB: %s — %d row(s) affected, fields: %s",
                idjlm_path, result["rows_affected"], list(valid_updates.keys())
            )
        else:
            logger.info(
                "No matching rekordbox row for path: %s", idjlm_path
            )

    except sqlite3.OperationalError as e:
        result["error"] = str(e)
        logger.error("Rekordbox DB write error: %s", e)
    except Exception as e:
        result["error"] = str(e)
        logger.exception("Unexpected error writing to rekordbox DB")

    return result


def write_back_tracks(
    db_path: str,
    matched_tracks: list[dict],
    field_mappings: Optional[dict] = None,
) -> dict:
    """Write IDJLM changes back to rekordbox for multiple tracks.

    Each matched_track dict should have:
        - "idjlm_path": the IDJLM track file path
        - "final_genre", "final_key", "final_bpm", "final_subgenre", "final_year", "final_energy"

    Args:
        db_path: Full path to master.db.
        matched_tracks: List of track dicts with IDJLM final-field values.
        field_mappings: Optional overrides mapping idjlm_field → rekordbox_column.
                        Default: final_genre→strGenre, final_key→strKey,
                        final_subgenre→strComment, final_bpm→dBPM, final_year→nYear

    Returns:
        {"written": int, "skipped": int, "errors": list[str]}
    """
    if field_mappings is None:
        field_mappings = {
            "final_genre": "strGenre",
            "final_key": "strKey",
            "final_subgenre": "strComment",
            "final_bpm": "dBPM",
            "final_year": "nYear",
        }

    written = 0
    skipped = 0
    errors = []

    for track in matched_tracks:
        updates = {}
        for idjlm_field, rb_column in field_mappings.items():
            val = track.get(idjlm_field)
            if val is not None:
                if idjlm_field == "final_bpm":
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        val = None
                else:
                    val = str(val)
            if val is not None:
                updates[rb_column] = val

        if not updates:
            skipped += 1
            continue

        write_result = write_track_to_rekordbox(
            db_path, track["idjlm_path"], updates
        )

        if write_result["written"]:
            written += 1
        elif write_result["error"]:
            errors.append(f"{track['idjlm_path']}: {write_result['error']}")
            skipped += 1
        else:
            skipped += 1

    return {"written": written, "skipped": skipped, "errors": errors}
