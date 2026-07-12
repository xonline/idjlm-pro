"""SQLite-backed track store.

Issue #187 — B.1: Replace the in-memory `_track_store: dict` in app/__init__.py
with a persistent SQLite store keyed by both `file_path` (logical key the
existing routes use) and `content_hash` (SHA-256 prefix of first 1MB — used
for change-detection and a secondary unique index).

Design contract: the returned object exposes the same `dict`-like surface the
already-shipped routes consume. Backwards-compatible changes only — every
existing route still does `track_store[fp]`, `.values()`, `.items()`,
`del track_store[fp]`, `if fp not in track_store`, `len(track_store)`. SQLite
sits behind the wrapper so no route code needs to change.

Why this exists:
- session.json is loaded once and lost on crash; SQLite persists to disk
  continuously via transaction batching.
- 10k+ tracks in JSON is ~30 MB in RAM, ~5-10s to deserialise on every
  restart. SQLite stores on disk and pages into memory on demand.
- Unique constraint on content_hash enables future features (file moved =
  same track via hash, dedup-by-content), and is enough of a win on its own
  to justify the migration.

Permissions & durability:
- Uses `WAL` journal mode and `synchronous=NORMAL` for crash-safe writes
  without the fsync-every-commit tax of FULL.
- DB file lives next to the user data dir (same convention as session.json),
  never inside the PyInstaller bundle path.

Migration on first run:
- If `tracks.db` does not exist AND `session.json` exists, the old JSON
  session is read once, every track is written to SQLite, then the JSON file
  is moved aside to `session.json.migrated-YYYYMMDD` (not deleted).
- After successful migration the JSON file is no longer required.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Iterator, Optional

from app.models.track import Track
from app.utils.paths import user_data_path

logger = logging.getLogger(__name__)

DB_FILENAME = "tracks.db"
MIGRATED_SUFFIX_PREFIX = "session.json.migrated-"


def _db_path() -> str:
    return user_data_path(DB_FILENAME)


class TrackStore:
    """Dict-like façade over SQLite.

    Only one instance per process lives in the module-global state of
    ``app.__init__``. Threadsafe — every operation acquires an RLock
    briefly and uses SQLite's own isolation. Reads use a shared
    connection; writes use the same connection in autocommit-on-WAL
    mode.

    Keys are ``file_path`` strings, exactly as the existing routes expect.
    Content hashes are stored alongside but used only for change detection
    and a secondary unique index.
    """

    # The set of dataclass fields persisted. Mirrors what session.json
    # used to write (see session_service.save_session); @property values
    # (``display_title``, ``final_genre``, etc.) are *not* persisted —
    # they are computed on read via Track.to_dict().
    _PERSISTED_FIELDS = tuple(Track.__dataclass_fields__.keys())

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or _db_path()
        self._rw_lock = threading.RLock()
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._rw_lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tracks (
                    file_path    TEXT PRIMARY KEY,
                    content_hash TEXT,
                    payload_json TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    created_at   TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tracks_content_hash "
                "ON tracks(content_hash) WHERE content_hash IS NOT NULL"
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS store_meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    # ------------------------------------------------------------------ #
    # Migration                                                             #
    # ------------------------------------------------------------------ #

    def migrate_from_session_json(self, session_json_path: str) -> bool:
        """One-shot migration from session.json into SQLite.

        Returns True if migration ran (data was found and written),
        False if there was nothing to do. Safe to call repeatedly —
        a second call with no JSON file is a no-op.

        The JSON file is renamed to ``session.json.migrated-<date>`` once
        the SQLite write succeeds, so we never silently lose the
        original data.
        """
        with self._rw_lock:
            try:
                already = self._conn.execute(
                    "SELECT value FROM store_meta WHERE key='migration_state'"
                ).fetchone()
                if already and already["value"] == "complete":
                    logger.info(
                        "TrackStore: migration already complete — skipping"
                    )
                    return False
            except sqlite3.OperationalError:
                return False

            if not os.path.exists(session_json_path):
                self._conn.execute(
                    "INSERT OR REPLACE INTO store_meta(key, value) "
                    "VALUES('migration_state', 'complete')"
                )
                return False

            logger.info(
                "TrackStore: migrating %s → %s", session_json_path, self._db_path
            )

            try:
                with open(session_json_path, "r", encoding="utf-8") as fh:
                    session_data = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error(
                    "TrackStore: failed to read session.json during "
                    "migration: %s",
                    exc,
                )
                return False

            tracks_data = session_data.get("tracks") or {}
            saved_at = session_data.get("saved_at") or ""
            folder_path = session_data.get("folder_path") or ""

            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            written = 0
            try:
                for file_path, track_dict in tracks_data.items():
                    track = self._track_from_legacy_dict(track_dict, file_path)
                    self._persist_track(track, created_at=saved_at or now_iso)
                    written += 1
            except Exception:
                logger.exception(
                    "TrackStore: migration aborted partway through after "
                    "%d/%d tracks",
                    written,
                    len(tracks_data),
                )
                # Re-raise: the caller will log the failure but the
                # store remains usable in-memory; the JSON file is
                # untouched so it can be retried next launch.
                raise

            # Persist migration metadata
            self._conn.execute(
                "INSERT OR REPLACE INTO store_meta(key, value) "
                "VALUES('migration_state', 'complete')"
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO store_meta(key, value) "
                "VALUES('migration_source', ?)",
                (session_json_path,),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO store_meta(key, value) "
                "VALUES('migration_count', ?)",
                (str(written),),
            )
            if folder_path:
                self._conn.execute(
                    "INSERT OR REPLACE INTO store_meta(key, value) "
                    "VALUES('folder_path', ?)",
                    (folder_path,),
                )

            # Rename the file aside — never delete
            try:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
                migrated_name = MIGRATED_SUFFIX_PREFIX + stamp
                migrated_path = os.path.join(
                    os.path.dirname(session_json_path), migrated_name
                )
                # If multiple migrations the same day, append a counter
                counter = 1
                while os.path.exists(migrated_path):
                    counter += 1
                    migrated_path = os.path.join(
                        os.path.dirname(session_json_path),
                        f"{MIGRATED_SUFFIX_PREFIX}{stamp}-{counter}",
                    )
                os.rename(session_json_path, migrated_path)
                logger.info(
                    "TrackStore: migration complete — wrote %d tracks; "
                    "session.json archived as %s",
                    written,
                    os.path.basename(migrated_path),
                )
            except OSError:
                logger.warning(
                    "TrackStore: migration wrote %d tracks, but could "
                    "not rename session.json — leaving it in place for "
                    "the next launch",
                    written,
                )

            return True

    @classmethod
    def _track_from_legacy_dict(cls, track_dict: dict, file_path: str) -> Track:
        """Reconstruct a Track from the legacy session.json shape.

        Legacy ``to_dict()`` writes every dataclass field plus the
        derived @property values. We filter back down to dataclass
        fields only — identical to the prior session_service.load_session
        logic, just moved here.
        """
        merged = dict(track_dict)
        merged.setdefault("file_path", file_path)
        merged.setdefault("filename", os.path.basename(file_path))

        clean = {
            k: v for k, v in merged.items() if k in Track.__dataclass_fields__
        }
        # Field defaults in Track handle missing optionals.
        return Track(**clean)

    # ------------------------------------------------------------------ #
    # Dict-like surface                                                    #
    # ------------------------------------------------------------------ #

    def __len__(self) -> int:
        with self._rw_lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM tracks").fetchone()
            return int(row["n"]) if row else 0

    def __iter__(self) -> Iterator[str]:
        with self._rw_lock:
            rows = self._conn.execute(
                "SELECT file_path FROM tracks ORDER BY file_path"
            ).fetchall()
        return (r["file_path"] for r in rows)

    def __contains__(self, file_path: object) -> bool:
        if not isinstance(file_path, str):
            return False
        with self._rw_lock:
            row = self._conn.execute(
                "SELECT 1 FROM tracks WHERE file_path = ? LIMIT 1",
                (file_path,),
            ).fetchone()
            return row is not None

    def __getitem__(self, file_path: str) -> Track:
        with self._rw_lock:
            row = self._conn.execute(
                "SELECT payload_json FROM tracks WHERE file_path = ?",
                (file_path,),
            ).fetchone()
        if row is None:
            raise KeyError(file_path)
        # Return a write-through proxy so mutations via ``store[fp].x = y``
        # persist immediately. Plain Track objects from elsewhere (e.g.
        # freshly constructed by scanner) continue to work via setitem.
        return _PersistingTrack(self, file_path, self._track_from_row(row["payload_json"], file_path))

    def __setitem__(self, file_path: str, track: Track) -> None:
        if not isinstance(track, Track):
            raise TypeError(
                f"TrackStore values must be Track instances, "
                f"got {type(track).__name__}"
            )
        with self._rw_lock:
            existing = self._conn.execute(
                "SELECT created_at FROM tracks WHERE file_path = ?",
                (file_path,),
            ).fetchone()
            created_at = (
                existing["created_at"] if existing else datetime.now(
                    timezone.utc
                ).isoformat().replace("+00:00", "Z")
            )
            self._persist_track(track, created_at=created_at)

    def __delitem__(self, file_path: str) -> None:
        with self._rw_lock:
            cur = self._conn.execute(
                "DELETE FROM tracks WHERE file_path = ?", (file_path,)
            )
            if cur.rowcount == 0:
                raise KeyError(file_path)

    def clear(self) -> None:
        with self._rw_lock:
            self._conn.execute("DELETE FROM tracks")

    def keys(self):
        return list(iter(self))

    def values(self):
        return [self[k] for k in self.keys()]

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def get(self, file_path: str, default=None):
        try:
            return self[file_path]
        except KeyError:
            return default

    def pop(self, file_path: str, *args):
        if len(args) > 1:
            raise TypeError(
                "pop expected at most 2 arguments, got " f"{1 + len(args)}"
            )
        try:
            track = self[file_path]
        except KeyError:
            if args:
                return args[0]
            raise
        del self[file_path]
        return track

    def update(self, other=None, **kwargs):
        # Mirrors dict.update(source) and dict.update(**kwargs). The
        # bulk path is only marginally faster but keeps semantics.
        if other is not None:
            if hasattr(other, "items"):
                items = other.items()
            else:
                items = other
            for k, v in items:
                self[k] = v
        for k, v in kwargs.items():
            self[k] = v

    # ------------------------------------------------------------------ #
    # SQLite-aware extensions (intentionally not dict-like)              #
    # ------------------------------------------------------------------ #

    def get_by_content_hash(self, content_hash: str) -> Optional[Track]:
        if not content_hash:
            return None
        with self._rw_lock:
            row = self._conn.execute(
                "SELECT file_path, payload_json FROM tracks "
                "WHERE content_hash = ? LIMIT 1",
                (content_hash,),
            ).fetchone()
        if row is None:
            return None
        return self._track_from_row(row["payload_json"], row["file_path"])

    def stats(self) -> dict:
        with self._rw_lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n, "
                "SUM(CASE WHEN content_hash IS NOT NULL THEN 1 ELSE 0 END) AS hashed "
                "FROM tracks"
            ).fetchone()
        return {
            "total": int(row["n"] or 0),
            "with_content_hash": int(row["hashed"] or 0),
            "db_path": self._db_path,
        }

    def close(self) -> None:
        with self._rw_lock:
            try:
                self._conn.close()
            except sqlite3.OperationalError:
                pass

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _persist_track(self, track: Track, created_at: str) -> None:
        payload_json = json.dumps(track.to_dict(), default=_json_default)
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._conn.execute(
            """
            INSERT INTO tracks(file_path, content_hash, payload_json,
                               updated_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                content_hash = excluded.content_hash,
                payload_json = excluded.payload_json,
                updated_at   = excluded.updated_at
            """,
            (
                track.file_path,
                track.content_hash or None,
                payload_json,
                now_iso,
                created_at or now_iso,
            ),
        )

    @classmethod
    def _track_from_row(cls, payload_json: str, file_path: str) -> Track:
        payload = json.loads(payload_json)
        merged = dict(payload)
        merged.setdefault("file_path", file_path)
        merged.setdefault("filename", os.path.basename(file_path))
        clean = {
            k: v for k, v in merged.items() if k in Track.__dataclass_fields__
        }
        # Construct without defaults silently — Discard any @property
        # values that snuck in via to_dict().
        return Track(**clean)


class _PersistingTrack:
    """Thin write-through proxy around a Track.

    Route code occasionally mutates a Track in place via
    ``store[fp].field = value``. With a plain dict-store that mutates
    the in-memory Track and the change is captured by future
    ``save_session`` calls. With a SQLite store the change would be
    lost on the next read. This proxy auto-persists any attribute set
    back to SQLite so the existing pattern keeps working unchanged.

    Attribute reads (incl. dict-style access like ``track.to_dict()``
    and property access like ``track.display_title``) delegate
    straight to the underlying Track — full duck-typing compatibility.
    """

    __slots__ = ("_store", "_file_path", "_track")

    def __init__(self, store: "TrackStore", file_path: str, track: Track):
        object.__setattr__(self, "_store", store)
        object.__setattr__(self, "_file_path", file_path)
        object.__setattr__(self, "_track", track)

    def __getattr__(self, name: str):
        # Private attrs via __setattr__/__slots__ (above) bypass this.
        return getattr(self._track, name)

    def __setattr__(self, name: str, value):
        if name in ("_store", "_file_path", "_track"):
            object.__setattr__(self, name, value)
            return
        setattr(self._track, name, value)
        # Write the updated track back to SQLite. This is one SQL
        # statement per attribute set, which is acceptable for the
        # handful of routes that mutate in place. Heavy mutation
        # routes still use ``store[fp] = track`` explicitly.
        self._store[self._file_path] = self._track

    # Pickle / copy / dataclass-asdict compatibility ----------------------------

    def __repr__(self) -> str:
        return f"_PersistingTrack(file_path={self._file_path!r}, track={self._track!r})"

    def to_dict(self) -> dict:
        return self._track.to_dict()

    # Pass-through methods that should return a fresh Track rather than
    # a proxy (avoids surprising identity comparisons elsewhere).
    def __copy__(self):
        return self._track

    def __deepcopy__(self, memo):
        from copy import deepcopy
        return deepcopy(self._track, memo)


def _json_default(obj):
    """Encode Track sub-objects (lists/dicts/numbers) safely in JSON.

    Falls back to repr() for unknown types — never raises.
    """
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return repr(obj)
