"""
rekordbox SQLite database reader.
Reads tracks from rekordbox's master.db to cross-reference with IDJLM library.
"""
import os
import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _find_rekordbox_db() -> Optional[str]:
    """Find rekordbox master.db in common locations."""
    import platform
    candidates = []

    if platform.system() == "Darwin":
        candidates = [
            os.path.expanduser("~/Library/Pioneer/rekordbox/master.db"),
            os.path.expanduser("~/Library/Pioneer/rekordbox3/master.db"),
        ]
    elif platform.system() == "Windows":
        appdata = os.environ.get("APPDATA", "")
        candidates = [
            os.path.join(appdata, "Pioneer", "rekordbox", "master.db"),
            os.path.join(appdata, "Pioneer", "rekordbox3", "master.db"),
        ]

    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def read_rekordbox_library() -> list[dict]:
    """
    Read tracks from rekordbox's SQLite database.
    Returns list of dicts with: path, title, artist, bpm, key, genre, year, rating, play_count
    """
    db_path = _find_rekordbox_db()
    if not db_path:
        logger.info("rekordbox database not found")
        return []

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                djbd_track_id,
                strPath as path,
                strTitle as title,
                strArtist as artist,
                dBPM as bpm,
                strKey as key,
                strGenre as genre,
                strComment as comment,
                nRating as rating,
                nPlayCount as play_count,
                nDuration as duration,
                nYear as year
            FROM djbd_content_table
            WHERE strPath IS NOT NULL
            LIMIT 10000
        """)
        rows = cursor.fetchall()
        conn.close()

        tracks = []
        for row in rows:
            tracks.append({
                "path": row["path"],
                "title": row["title"],
                "artist": row["artist"],
                "bpm": row["bpm"],
                "key": row["key"],
                "genre": row["genre"],
                "comment": row["comment"],
                "rating": row["rating"],
                "play_count": row["play_count"],
                "duration": row["duration"],
                "year": row["year"],
            })
        return tracks

    except sqlite3.OperationalError as e:
        logger.debug("rekordbox schema may differ: %s", e)
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            logger.debug("rekordbox tables: %s", tables)
            conn.close()
        except Exception:
            pass
        return []
    except Exception as e:
        logger.exception("Error reading rekordbox database")
        return []


def match_rekordbox_tracks(idjlm_store: dict) -> dict:
    """
    Match rekordbox tracks to IDJLM tracks by file path.
    Returns dict: { idjlm_path: rekordbox_data }
    """
    rb_tracks = read_rekordbox_library()
    if not rb_tracks:
        return {}

    rb_by_path = {}
    for t in rb_tracks:
        path = t.get("path", "")
        if path:
            normalized = os.path.normpath(path).lower()
            rb_by_path[normalized] = t

    matches = {}
    for idjlm_path in idjlm_store:
        normalized = os.path.normpath(idjlm_path).lower()
        if normalized in rb_by_path:
            matches[idjlm_path] = rb_by_path[normalized]

    return matches
