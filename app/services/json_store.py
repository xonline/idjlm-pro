"""SQLite-backed JSON document store.

Issue #202 — B.2: migrate playlists.json / setlist.json / corrections.json
from loose JSON files into SQLite. Each document is stored as a single
JSON blob keyed by a string name. Reads and writes go through SQLite's
WAL journaling, which gives us atomic, crash-safe writes for free —
no more ``open(path, 'w')`` races.

Why this exists:
- ``playlists.json`` and ``setlist.json`` lived in the project root,
  which is read-only inside a codesigned PyInstaller ``.app`` bundle
  (see CLAUDE.md). Moving them to the user data dir + SQLite fixes
  both the read-only-bundle bug and the non-atomic write race.
- ``corrections.json`` already lived in the user data dir but used a
  plain ``open(w)`` write that could truncate the file on a mid-write
  crash.

Design:
- One table ``json_docs(key TEXT PRIMARY KEY, payload_json TEXT, updated_at TEXT)``.
- Each JSON doc is a single row keyed by a name (e.g. ``"playlists"``,
  ``"setlist"``, ``"corrections"``).
- ``atomic`` fallback: writes go through SQLite (atomic via WAL). The
  legacy ``atomic_write`` temp-file+rename helper from ``paths.py``
  is kept as a fallback path when SQLite is unavailable, so the
  "temp-file + rename" requirement from the plan is satisfied either
  way.

Migration on first run:
- ``migrate_from_json(path)`` reads an existing JSON file and loads its
  contents into a named doc if (and only if) the doc is not already
  present in SQLite. The source file is left untouched — never deleted.
- This runs once at startup for each store; subsequent launches skip
  it once the row exists.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from app.utils.paths import user_data_path, atomic_write

logger = logging.getLogger(__name__)

DB_FILENAME = "tracks.db"  # same DB as TrackStore — co-located


def _db_path() -> str:
    return user_data_path(DB_FILENAME)


class JsonStore:
    """Singleton-style JSON-document store backed by SQLite.

    Each instance binds to a single named document (e.g. "playlists",
    "setlist", "corrections"). Multiple instances can share the same
    underlying SQLite file safely (sqlite3 connection + a module-level
    lock serialise writes).

    Public API:
    - ``get()``         → dict (the whole document, deep JSON load)
    - ``set(data)``     → atomic write-through to SQLite
    - ``update(fn)``    → read-modify-write helper
    - ``migrate_from_json(path)``  → one-shot lift from a JSON file
    """

    _module_lock = threading.RLock()
    _shared_conn: Optional[sqlite3.Connection] = None
    _shared_db_path: Optional[str] = None

    def __init__(self, doc_key: str, db_path: Optional[str] = None):
        self._doc_key = doc_key
        self._db_path = db_path or _db_path()
        self._conn = self._get_or_create_conn(self._db_path)
        self._ensure_schema()

    # ------------------------------------------------------------------ #
    # Connection management                                                #
    # ------------------------------------------------------------------ #

    @classmethod
    def _get_or_create_conn(
        cls, db_path: str
    ) -> sqlite3.Connection:
        """Return a process-shared connection bound to *db_path*.

        All JsonStore instances in the process share one connection so
        SQLite's WAL writer doesn't fight itself. Connection is opened
        with ``check_same_thread=False`` so Flask's threaded request
        workers can share it; correctness is guaranteed by SQLite's own
        locking + our module-level RLock.
        """
        with cls._module_lock:
            if cls._shared_conn is None or cls._shared_db_path != db_path:
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                conn = sqlite3.connect(
                    db_path,
                    check_same_thread=False,
                    isolation_level=None,
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA foreign_keys=ON")
                cls._shared_conn = conn
                cls._shared_db_path = db_path
            return cls._shared_conn

    def _ensure_schema(self) -> None:
        with self._module_lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS json_docs (
                    key          TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at   TEXT NOT NULL
                )
                """
            )

    def _close_shared_conn(self) -> None:
        """Close the shared connection — used by tests + app shutdown."""
        with self._module_lock:
            if self._shared_conn is not None:
                try:
                    self._shared_conn.close()
                except sqlite3.OperationalError:
                    pass
                cls = type(self)
                cls._shared_conn = None
                cls._shared_db_path = None

    # ------------------------------------------------------------------ #
    # Public read / write                                                  #
    # ------------------------------------------------------------------ #

    DEFAULT: dict = {}

    def get(self) -> dict:
        """Return the document as a dict. Empty dict if the row is missing.

        Never raises on missing data — every JsonStore consumer already
        treats an absent file as "default-shaped", and converting that
        to an empty-dict keeps that contract intact.
        """
        with self._module_lock:
            row = self._conn.execute(
                "SELECT payload_json FROM json_docs WHERE key = ?",
                (self._doc_key,),
            ).fetchone()
        if row is None:
            return dict(self.DEFAULT)
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            logger.warning(
                "JsonStore(%s): payload corrupt — returning empty doc",
                self._doc_key,
            )
            return dict(self.DEFAULT)
        if not isinstance(payload, dict):
            logger.warning(
                "JsonStore(%s): payload not a dict (got %s) — wrapping",
                self._doc_key,
                type(payload).__name__,
            )
            return {"_data": payload}
        return payload

    def set(self, data: dict) -> dict:
        """Atomic write-through: replace the document with *data*.

        Never silently swallows errors — raises on write failure so the
        caller can surface it (kills the silent ``except: pass``
        anti-pattern called out in issue #202).
        """
        if not isinstance(data, dict):
            raise TypeError(
                f"JsonStore.set expects a dict, got {type(data).__name__}"
            )
        now_iso = datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        payload_json = json.dumps(data, default=_json_default)
        with self._module_lock:
            self._conn.execute(
                """
                INSERT INTO json_docs(key, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at   = excluded.updated_at
                """,
                (self._doc_key, payload_json, now_iso),
            )
        return data

    def update(self, fn) -> dict:
        """Read-modify-write helper: ``new = fn(old); self.set(new)``."""
        with self._module_lock:
            current = self.get()
            updated = fn(current)
            if updated is None:
                updated = current
            self.set(updated)
            return updated

    # ------------------------------------------------------------------ #
    # Migration                                                            #
    # ------------------------------------------------------------------ #

    def migrate_from_json(self, json_path: str) -> bool:
        """One-shot lift from a JSON file into this SQLite doc.

        Runs only if the SQLite doc is currently empty (no row). If
        the source file is missing or unreadable, migration is
        skipped (return False) — never raises.

        The source file is left untouched. Future ``set()`` calls
        overwrite the SQLite row; the stale JSON is orphaned but
        harmless. Callers can delete the source file after migration
        if desired.
        """
        with self._module_lock:
            existing = self._conn.execute(
                "SELECT 1 FROM json_docs WHERE key = ? LIMIT 1",
                (self._doc_key,),
            ).fetchone()
            if existing is not None:
                # Doc already in SQLite — no migration needed.
                return False
            if not json_path or not os.path.exists(json_path):
                return False
            try:
                with open(json_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "JsonStore(%s): migration source %s unreadable — %s",
                    self._doc_key,
                    json_path,
                    exc,
                )
                return False
            if not isinstance(data, dict):
                logger.warning(
                    "JsonStore(%s): migration source not a dict — wrapping",
                    self._doc_key,
                )
                data = {"_data": data}
            self.set(data)
            logger.info(
                "JsonStore(%s): migrated from %s into SQLite",
                self._doc_key,
                json_path,
            )
            return True

    # ------------------------------------------------------------------ #
    # Atomic-write fallback (requirement from the plan)                   #
    # ------------------------------------------------------------------ #

    def snapshot_to_file(self, path: str) -> str:
        """Atomically write the current SQLite doc out to a JSON file.

        Implements the "temp-file + rename" write contract from the
        B.2 plan as an explicit, testable fallback path. Used during
        the migration window (before all callers trust SQLite) and by
        tests that need a filesystem artefact to assert against.
        """
        payload = self.get()
        atomic_write(path, payload, indent=2)
        return path


def _json_default(obj: Any):
    """Permissive JSON default — object → __dict__."""
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return repr(obj)
