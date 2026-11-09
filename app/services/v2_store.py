"""Additive, durable state for the v2 library workflow.

Reads never derive v2 records from legacy ``tracks``.  Import/bootstrap must
explicitly call ``upsert_item`` so stable item IDs are persisted once.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
AXES = {
    "music_family",
    "style",
    "dance_use",
    "production",
    "vocal_presence",
    "vocal_language",
    "instrument_cue",
    "comment",
    "comment_token",
    "custom_tag",
}
SINGLE_LABEL_AXES = {"music_family", "vocal_presence", "vocal_language"}
STATES = {"unreviewed", "needs_review", "ready", "conflict"}
TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"pausing", "cancelling", "completed", "interrupted"},
    "pausing": {"paused"},
    "paused": {"running", "cancelled"},
    "cancelling": {"cancelled"},
    "interrupted": {"queued", "running"},
}


def _now():
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _load(value, default):
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError):
        return default


def _text(value):
    return str(value or "").strip()


def _norm(value):
    return _text(value).casefold()


class V2Store:
    def __init__(self, db_path: str):
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            db_path, check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._schema()

    @contextmanager
    def _tx(self):
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    def _column(self, table, column, declaration):
        if column not in {
            r["name"] for r in self._conn.execute(f"PRAGMA table_info({table})")
        }:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def _schema(self):
        schema = """
        CREATE TABLE IF NOT EXISTS v2_items(item_id TEXT PRIMARY KEY,file_path TEXT NOT NULL UNIQUE,source_revision TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,original_revision INTEGER NOT NULL DEFAULT 0,proposal_revision INTEGER NOT NULL DEFAULT 0,decision_revision INTEGER NOT NULL DEFAULT 0,availability TEXT NOT NULL DEFAULT 'present',conflict INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS v2_item_originals(item_id TEXT PRIMARY KEY REFERENCES v2_items(item_id) ON DELETE CASCADE,payload TEXT NOT NULL,title TEXT NOT NULL DEFAULT '',title_norm TEXT NOT NULL DEFAULT '',artist TEXT NOT NULL DEFAULT '',artist_norm TEXT NOT NULL DEFAULT '',existing_genre TEXT NOT NULL DEFAULT '',raw_comment TEXT NOT NULL DEFAULT '',raw_comment_norm TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v2_comment_tokens(item_id TEXT NOT NULL REFERENCES v2_items(item_id) ON DELETE CASCADE,token TEXT NOT NULL,token_norm TEXT NOT NULL,PRIMARY KEY(item_id,token_norm));
        CREATE TABLE IF NOT EXISTS v2_predictions(prediction_id TEXT PRIMARY KEY,item_id TEXT NOT NULL REFERENCES v2_items(item_id),axis TEXT NOT NULL,label_ids TEXT NOT NULL,raw_score REAL,calibrated_confidence REAL,status TEXT NOT NULL,evidence TEXT NOT NULL,details TEXT NOT NULL DEFAULT '{}',model TEXT NOT NULL,taxonomy_version TEXT NOT NULL,feature_version TEXT NOT NULL,created_at TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS v2_active_proposals(item_id TEXT NOT NULL,axis TEXT NOT NULL,prediction_id TEXT NOT NULL REFERENCES v2_predictions(prediction_id),PRIMARY KEY(item_id,axis));
        CREATE TABLE IF NOT EXISTS v2_decisions(item_id TEXT NOT NULL REFERENCES v2_items(item_id),axis TEXT NOT NULL,label_ids TEXT NOT NULL,source TEXT NOT NULL,locked INTEGER NOT NULL DEFAULT 0,revision INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(item_id,axis));
        CREATE TABLE IF NOT EXISTS v2_decision_history(decision_id TEXT PRIMARY KEY,item_id TEXT NOT NULL,axis TEXT NOT NULL,label_ids TEXT NOT NULL,source TEXT NOT NULL,locked INTEGER NOT NULL,revision INTEGER NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v2_effective_labels(item_id TEXT NOT NULL REFERENCES v2_items(item_id) ON DELETE CASCADE,axis TEXT NOT NULL,label_id TEXT NOT NULL,source TEXT NOT NULL,PRIMARY KEY(item_id,axis,label_id));
        CREATE TABLE IF NOT EXISTS v2_previews(preview_id TEXT PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',consumed_at TEXT);
        CREATE TABLE IF NOT EXISTS v2_jobs(job_id TEXT PRIMARY KEY,kind TEXT NOT NULL,state TEXT NOT NULL,scope TEXT NOT NULL,config TEXT NOT NULL,counts TEXT NOT NULL,cursor TEXT,error_code TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v2_job_items(job_id TEXT NOT NULL REFERENCES v2_jobs(job_id) ON DELETE CASCADE,item_id TEXT NOT NULL REFERENCES v2_items(item_id),state TEXT NOT NULL DEFAULT 'queued',cursor TEXT,attempt INTEGER NOT NULL DEFAULT 0,error_code TEXT,started_at TEXT,finished_at TEXT,PRIMARY KEY(job_id,item_id));
        CREATE TABLE IF NOT EXISTS v2_job_events(job_id TEXT NOT NULL REFERENCES v2_jobs(job_id) ON DELETE CASCADE,sequence INTEGER NOT NULL,type TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(job_id,sequence));
        CREATE TABLE IF NOT EXISTS v2_taxonomy(singleton INTEGER PRIMARY KEY CHECK(singleton=1),document TEXT NOT NULL,revision INTEGER NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v2_views(view_id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE,definition TEXT NOT NULL,revision INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v2_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v2_exports(export_id TEXT PRIMARY KEY,profile TEXT NOT NULL,destination TEXT NOT NULL,route TEXT NOT NULL,state TEXT NOT NULL,manifest TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v2_write_ledger(write_id TEXT PRIMARY KEY,item_id TEXT NOT NULL REFERENCES v2_items(item_id),source_path TEXT NOT NULL,before_sha256 TEXT NOT NULL,after_sha256 TEXT,backup_path TEXT NOT NULL,fields TEXT NOT NULL,status TEXT NOT NULL,error_code TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v2_write_intents(write_id TEXT PRIMARY KEY REFERENCES v2_write_ledger(write_id) ON DELETE CASCADE,payload TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v2_feature_cache(cache_key TEXT PRIMARY KEY,record TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v2_analysis_outcomes(outcome_id TEXT PRIMARY KEY,item_id TEXT NOT NULL REFERENCES v2_items(item_id) ON DELETE CASCADE,status TEXT NOT NULL,reason TEXT,payload TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v2_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_v2_original_title ON v2_item_originals(title_norm,item_id);
        CREATE INDEX IF NOT EXISTS idx_v2_original_artist ON v2_item_originals(artist_norm,item_id);
        CREATE INDEX IF NOT EXISTS idx_v2_original_comment ON v2_item_originals(raw_comment_norm,item_id);
        CREATE INDEX IF NOT EXISTS idx_v2_label_axis ON v2_effective_labels(axis,label_id,item_id);
        CREATE INDEX IF NOT EXISTS idx_v2_prediction_axis ON v2_predictions(item_id,axis,revision DESC);
        CREATE INDEX IF NOT EXISTS idx_v2_write_item ON v2_write_ledger(item_id,created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_v2_event ON v2_job_events(job_id,sequence);
        CREATE INDEX IF NOT EXISTS idx_v2_analysis_item ON v2_analysis_outcomes(item_id,created_at DESC);
        """
        with self._lock:
            self._conn.executescript(schema)
            for name, spec in (
                ("revision", "INTEGER NOT NULL DEFAULT 1"),
                ("original_revision", "INTEGER NOT NULL DEFAULT 0"),
                ("proposal_revision", "INTEGER NOT NULL DEFAULT 0"),
                ("decision_revision", "INTEGER NOT NULL DEFAULT 0"),
                ("availability", "TEXT NOT NULL DEFAULT 'present'"),
                ("conflict", "INTEGER NOT NULL DEFAULT 0"),
            ):
                self._column("v2_items", name, spec)
            self._column("v2_predictions", "revision", "INTEGER NOT NULL DEFAULT 1")
            self._column("v2_predictions", "details", "TEXT NOT NULL DEFAULT '{}'")
            self._column("v2_previews", "consumed_at", "TEXT")
            self._conn.execute(
                "INSERT OR IGNORE INTO v2_meta VALUES('library_revision','0')"
            )

    def _bump(self, db):
        db.execute(
            "UPDATE v2_meta SET value=CAST(value AS INTEGER)+1 WHERE key='library_revision'"
        )

    def _library_revision(self):
        return int(
            self._conn.execute(
                "SELECT value FROM v2_meta WHERE key='library_revision'"
            ).fetchone()["value"]
        )

    @staticmethod
    def _revision(row):
        return f"r{int(row['revision'])}"

    def _touch(self, db, item_id, component):
        column = {
            "original": "original_revision",
            "proposal": "proposal_revision",
            "decision": "decision_revision",
        }[component]
        db.execute(
            f"UPDATE v2_items SET revision=revision+1,{column}={column}+1,updated_at=? WHERE item_id=?",
            (_now(), item_id),
        )
        self._bump(db)

    def upsert_item(
        self,
        *,
        path,
        original,
        item_id=None,
        source_revision=None,
        availability="present",
        conflict=False,
        comment_tokens=None,
    ):
        if not _text(path) or not isinstance(original, dict):
            raise ValueError("invalid_item")
        title = _text(
            original.get("existing_title")
            or original.get("title")
            or original.get("filename")
        )
        artist = _text(original.get("existing_artist") or original.get("artist"))
        genre = _text(original.get("existing_genre") or original.get("genre"))
        comment = _text(original.get("existing_comment") or original.get("comment"))
        if comment_tokens is not None and (
            not isinstance(comment_tokens, list)
            or any(not _text(x) for x in comment_tokens)
        ):
            raise ValueError("invalid_comment_tokens")
        now, payload = _now(), _dump(original)
        with self._tx() as db:
            row = db.execute(
                "SELECT * FROM v2_items WHERE item_id=? OR file_path=?", (item_id, path)
            ).fetchone()
            if (
                row
                and item_id
                and row["item_id"] != item_id
                and row["file_path"] == path
            ):
                raise ValueError("item_id_conflict")
            actual = row["item_id"] if row else (item_id or "item_" + uuid.uuid4().hex)
            prior = db.execute(
                "SELECT payload FROM v2_item_originals WHERE item_id=?", (actual,)
            ).fetchone()
            if row:
                db.execute(
                    "UPDATE v2_items SET file_path=?,source_revision=?,availability=?,conflict=?,updated_at=? WHERE item_id=?",
                    (
                        path,
                        _text(source_revision),
                        availability,
                        int(conflict),
                        now,
                        actual,
                    ),
                )
            else:
                db.execute(
                    "INSERT INTO v2_items(item_id,file_path,source_revision,created_at,updated_at,availability,conflict) VALUES(?,?,?,?,?,?,?)",
                    (
                        actual,
                        path,
                        _text(source_revision),
                        now,
                        now,
                        availability,
                        int(conflict),
                    ),
                )
            db.execute(
                "INSERT INTO v2_item_originals(item_id,payload,title,title_norm,artist,artist_norm,existing_genre,raw_comment,raw_comment_norm,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(item_id) DO UPDATE SET payload=excluded.payload,title=excluded.title,title_norm=excluded.title_norm,artist=excluded.artist,artist_norm=excluded.artist_norm,existing_genre=excluded.existing_genre,raw_comment=excluded.raw_comment,raw_comment_norm=excluded.raw_comment_norm,updated_at=excluded.updated_at",
                (
                    actual,
                    payload,
                    title,
                    _norm(title),
                    artist,
                    _norm(artist),
                    genre,
                    comment,
                    _norm(comment),
                    now,
                ),
            )
            if comment_tokens is not None:
                db.execute("DELETE FROM v2_comment_tokens WHERE item_id=?", (actual,))
                db.executemany(
                    "INSERT OR IGNORE INTO v2_comment_tokens VALUES(?,?,?)",
                    [(actual, _text(x), _norm(x)) for x in comment_tokens],
                )
            if not prior or prior["payload"] != payload:
                self._touch(db, actual, "original")
            out = db.execute(
                "SELECT * FROM v2_items WHERE item_id=?", (actual,)
            ).fetchone()
        return {"id": actual, "revision": self._revision(out), "path": path}

    def bootstrap_from_tracks(self, rows):
        if not isinstance(rows, list):
            raise ValueError("invalid_bootstrap")
        return [
            self.upsert_item(
                path=x.get("file_path") or x.get("path") or "",
                original=x.get("original") or x.get("payload") or {},
                item_id=x.get("item_id"),
                source_revision=x.get("source_revision"),
                availability=x.get("availability", "present"),
                conflict=bool(x.get("conflict")),
                comment_tokens=x.get("comment_tokens"),
            )
            for x in rows
            if isinstance(x, dict)
        ]

    def import_legacy_human_decisions(self, entries):
        """Preserve explicitly confirmed legacy choices without replacing v2 work.

        This is only called by the explicit migration action.  Pending legacy
        proposals are intentionally absent from ``entries``.  Existing v2
        decisions always win, making repeated bootstrap calls idempotent.
        """
        if not isinstance(entries, list):
            raise ValueError("invalid_legacy_decisions")
        saved, skipped = 0, 0
        with self._tx() as db:
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError("invalid_legacy_decisions")
                item_id, axis, label_ids = (
                    entry.get("item_id"),
                    entry.get("axis"),
                    entry.get("label_ids"),
                )
                if (
                    not isinstance(item_id, str)
                    or axis not in AXES
                    or not isinstance(label_ids, list)
                    or not label_ids
                ):
                    raise ValueError("invalid_legacy_decisions")
                if axis in SINGLE_LABEL_AXES and len(label_ids) != 1:
                    raise ValueError("invalid_legacy_decisions")
                if not db.execute(
                    "SELECT 1 FROM v2_items WHERE item_id=?", (item_id,)
                ).fetchone():
                    raise ValueError("unknown_item")
                if db.execute(
                    "SELECT 1 FROM v2_decisions WHERE item_id=? AND axis=?",
                    (item_id, axis),
                ).fetchone():
                    skipped += 1
                    continue
                now = _now()
                db.execute(
                    "INSERT INTO v2_decisions VALUES(?,?,?,?,?,?,?,?)",
                    (
                        item_id,
                        axis,
                        _dump(label_ids),
                        "legacy_confirmed_human",
                        1,
                        1,
                        now,
                        now,
                    ),
                )
                db.execute(
                    "INSERT INTO v2_decision_history VALUES(?,?,?,?,?,?,?,?)",
                    (
                        str(uuid.uuid4()),
                        item_id,
                        axis,
                        _dump(label_ids),
                        "legacy_confirmed_human",
                        1,
                        1,
                        now,
                    ),
                )
                self._refresh_labels(db, item_id, axis)
                self._touch(db, item_id, "decision")
                saved += 1
        return {"saved": saved, "skipped_existing_v2": skipped}

    def _cursor(self, cursor, key, direction):
        if not cursor:
            return None
        try:
            value = json.loads(base64.urlsafe_b64decode(str(cursor) + "==").decode())
            if value["k"] != key or value["d"] != direction:
                raise ValueError
            return value["v"], value["id"]
        except Exception:
            raise ValueError("invalid_cursor") from None

    def _make_cursor(self, key, direction, value, item_id):
        return (
            base64.urlsafe_b64encode(
                _dump({"k": key, "d": direction, "v": value, "id": item_id}).encode()
            )
            .decode()
            .rstrip("=")
        )

    def _filters(self, filters):
        if not isinstance(filters, dict):
            raise ValueError("invalid_filters")
        clauses, args = [], []
        q = _norm(filters.get("query"))
        if q:
            clauses.append(
                "(title_norm LIKE ? OR artist_norm LIKE ? OR raw_comment_norm LIKE ?)"
            )
            args += [f"%{q}%"] * 3
        for name, axis in (("family_ids", "music_family"), ("style_ids", "style")):
            values = filters.get(name, [])
            if not isinstance(values, list) or any(not _text(x) for x in values):
                raise ValueError("invalid_filters")
            if values:
                marks = ",".join("?" * len(values))
                clauses.append(
                    f"EXISTS (SELECT 1 FROM v2_effective_labels e WHERE e.item_id=r.item_id AND e.axis=? AND e.label_id IN ({marks}))"
                )
                args += [axis] + [_norm(x) for x in values]
        tokens = filters.get("comment_tokens", [])
        if not isinstance(tokens, list) or any(not _text(x) for x in tokens):
            raise ValueError("invalid_filters")
        if tokens:
            marks = ",".join("?" * len(tokens))
            values = [_norm(x) for x in tokens]
            clauses.append(
                f"(EXISTS (SELECT 1 FROM v2_comment_tokens c WHERE c.item_id=r.item_id AND c.token_norm IN ({marks})) OR EXISTS (SELECT 1 FROM v2_effective_labels e WHERE e.item_id=r.item_id AND e.axis IN ('comment','comment_token','custom_tag') AND e.label_id IN ({marks})))"
            )
            args += values + values
        if filters.get("raw_comment") is not None:
            if not isinstance(filters["raw_comment"], str):
                raise ValueError("invalid_filters")
            clauses.append("raw_comment_norm=?")
            args.append(_norm(filters["raw_comment"]))
        states = filters.get("review_states", [])
        if not isinstance(states, list) or any(x not in STATES for x in states):
            raise ValueError("invalid_filters")
        if states:
            clauses.append("review_state IN (%s)" % ",".join("?" * len(states)))
            args += states
        analysis_states = filters.get("analysis_states", [])
        valid_analysis = {
            "not_analyzed",
            "proposed",
            "abstained",
            "unsupported",
            "failed",
        }
        if not isinstance(analysis_states, list) or any(
            state not in valid_analysis for state in analysis_states
        ):
            raise ValueError("invalid_filters")
        if analysis_states:
            marks = ",".join("?" * len(analysis_states))
            clauses.append("analysis_state IN (%s)" % marks)
            args += analysis_states
        if "has_conflict" in filters:
            if not isinstance(filters["has_conflict"], bool):
                raise ValueError("invalid_filters")
            clauses.append("conflict=?")
            args.append(int(filters["has_conflict"]))
        return clauses, args

    def _base(self):
        return """WITH rows AS (SELECT i.*,o.payload,o.title,o.title_norm,o.artist,o.artist_norm,o.existing_genre,o.raw_comment,o.raw_comment_norm,df.label_ids family_decision,df.locked family_locked,ds.label_ids style_decision,ds.locked style_locked,pf.label_ids family_proposal,pf.status family_status,pf.model family_model,ps.label_ids style_proposal,ps.status style_status,ps.model style_model,(SELECT status FROM v2_write_ledger w WHERE w.item_id=i.item_id ORDER BY created_at DESC LIMIT 1) write_status,COALESCE((SELECT status FROM v2_analysis_outcomes a WHERE a.item_id=i.item_id ORDER BY created_at DESC,outcome_id DESC LIMIT 1),'not_analyzed') analysis_state,(SELECT reason FROM v2_analysis_outcomes a WHERE a.item_id=i.item_id ORDER BY created_at DESC,outcome_id DESC LIMIT 1) analysis_reason,CASE WHEN i.conflict=1 THEN 'conflict' WHEN df.item_id IS NOT NULL OR ds.item_id IS NOT NULL THEN 'ready' WHEN pf.prediction_id IS NOT NULL OR ps.prediction_id IS NOT NULL THEN 'needs_review' ELSE 'unreviewed' END review_state FROM v2_items i JOIN v2_item_originals o ON o.item_id=i.item_id LEFT JOIN v2_decisions df ON df.item_id=i.item_id AND df.axis='music_family' LEFT JOIN v2_decisions ds ON ds.item_id=i.item_id AND ds.axis='style' LEFT JOIN v2_active_proposals af ON af.item_id=i.item_id AND af.axis='music_family' LEFT JOIN v2_predictions pf ON pf.prediction_id=af.prediction_id LEFT JOIN v2_active_proposals ap ON ap.item_id=i.item_id AND ap.axis='style' LEFT JOIN v2_predictions ps ON ps.prediction_id=ap.prediction_id) """

    def _summary(self, r):
        def proposal(prefix):
            return (
                None
                if r[prefix + "_proposal"] is None
                else {
                    "label_ids": _load(r[prefix + "_proposal"], []),
                    "status": r[prefix + "_status"],
                    "model": _load(r[prefix + "_model"], {}),
                }
            )

        fd = None if r["family_decision"] is None else _load(r["family_decision"], [])
        sd = None if r["style_decision"] is None else _load(r["style_decision"], [])
        analysis_state = r["analysis_state"]
        return {
            "id": r["item_id"],
            "revision": self._revision(r),
            "title": r["title"] or "Untitled",
            "artist": r["artist"] or "Unknown",
            "existing": {"genre": r["existing_genre"], "comment": r["raw_comment"]},
            "proposed": {
                "music_family": {"label_ids": fd}
                if fd is not None
                else proposal("family") or {"label_ids": []},
                "style": {"label_ids": sd}
                if sd is not None
                else proposal("style") or {"label_ids": []},
            },
            "review_state": r["review_state"],
            "analysis": {"state": analysis_state, "reason": r["analysis_reason"]},
            "write_state": "written"
            if r["write_status"] == "written"
            else (r["write_status"] or "not_written"),
            "conflict": bool(r["conflict"]),
            "locked": bool(r["family_locked"] or r["style_locked"]),
        }

    def list_items(self, *, cursor, limit, filters, sort):
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise ValueError("invalid_limit") from None
        if not 1 <= limit <= 250:
            raise ValueError("invalid_limit")
        key, colon, direction = str(sort or "title:asc").partition(":")
        direction = direction if colon else "asc"
        columns = {"title": "title_norm", "artist": "artist_norm", "id": "item_id"}
        if key not in columns or direction not in {"asc", "desc"}:
            raise ValueError("invalid_sort")
        clauses, args = self._filters(filters)
        original_clauses, original_args = list(clauses), list(args)
        cur = self._cursor(cursor, key, direction)
        column = columns[key]
        if cur:
            op = ">" if direction == "asc" else "<"
            clauses.append(f"({column} {op} ? OR ({column}=? AND item_id {op} ?))")
            args += [cur[0], cur[0], cur[1]]
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        count_where = (
            (" WHERE " + " AND ".join(original_clauses)) if original_clauses else ""
        )
        with self._lock:
            total = self._conn.execute(
                self._base() + "SELECT COUNT(*) count FROM rows r" + count_where,
                original_args,
            ).fetchone()["count"]
            rows = self._conn.execute(
                self._base()
                + f"SELECT r.* FROM rows r{where} ORDER BY {column} {direction.upper()},item_id {direction.upper()} LIMIT ?",
                args + [limit + 1],
            ).fetchall()
        more, rows = len(rows) > limit, rows[:limit]
        return {
            "items": [self._summary(r) for r in rows],
            "next_cursor": self._make_cursor(
                key, direction, str(rows[-1][column]), rows[-1]["item_id"]
            )
            if more
            else None,
            "revision": self._library_revision(),
            "total": total,
        }

    def get_item(self, item_id):
        with self._lock:
            item = self._conn.execute(
                "SELECT * FROM v2_items WHERE item_id=?", (item_id,)
            ).fetchone()
            origin = self._conn.execute(
                "SELECT payload FROM v2_item_originals WHERE item_id=?", (item_id,)
            ).fetchone()
            if not item or not origin:
                return None
            axes = {}
            for axis in AXES:
                p = self._conn.execute(
                    "SELECT p.* FROM v2_active_proposals a JOIN v2_predictions p ON p.prediction_id=a.prediction_id WHERE a.item_id=? AND a.axis=?",
                    (item_id, axis),
                ).fetchone()
                d = self._conn.execute(
                    "SELECT * FROM v2_decisions WHERE item_id=? AND axis=?",
                    (item_id, axis),
                ).fetchone()
                if p or d:
                    axes[axis] = {
                        "proposal": None
                        if not p
                        else {
                            "label_ids": _load(p["label_ids"], []),
                            "status": p["status"],
                            "raw_score": p["raw_score"],
                            "calibrated_confidence": p["calibrated_confidence"],
                            "evidence": _load(p["evidence"], []),
                            "details": _load(p["details"], {}),
                            "model": _load(p["model"], {}),
                            "taxonomy_version": p["taxonomy_version"],
                            "feature_version": p["feature_version"],
                            "revision": p["revision"],
                        },
                        "decision": None
                        if not d
                        else {
                            "label_ids": _load(d["label_ids"], []),
                            "source": d["source"],
                            "locked": bool(d["locked"]),
                            "revision": d["revision"],
                        },
                    }
            outcome = self._conn.execute(
                "SELECT status,reason,payload,created_at FROM v2_analysis_outcomes WHERE item_id=? ORDER BY created_at DESC,outcome_id DESC LIMIT 1",
                (item_id,),
            ).fetchone()
        analysis = (
            {"state": "not_analyzed"}
            if not outcome
            else {
                "state": outcome["status"],
                "reason": outcome["reason"],
                "details": _load(outcome["payload"], {}),
                "created_at": outcome["created_at"],
            }
        )
        return {
            "id": item_id,
            "revision": self._revision(item),
            "path": item["file_path"],
            "original": _load(origin["payload"], {}),
            "axes": axes,
            "analysis": analysis,
            "revisions": {
                "source": item["original_revision"],
                "proposals": item["proposal_revision"],
                "decisions": item["decision_revision"],
            },
            "availability": item["availability"],
            "conflict": bool(item["conflict"]),
        }

    def resolve_scope(self, scope):
        if not isinstance(scope, dict) or scope.get("selection") not in {
            "explicit",
            "all_filtered",
        }:
            raise ValueError("invalid_scope")
        if scope["selection"] == "explicit":
            ids = scope.get("item_ids")
            if not isinstance(ids, list) or not ids:
                raise ValueError("empty_scope")
            if len(set(ids)) != len(ids) or any(
                not isinstance(x, str) or not x for x in ids
            ):
                raise ValueError("invalid_scope")
            items = [self.get_item(x) for x in ids]
            if any(x is None for x in items):
                raise ValueError("unknown_item")
            return items
        if scope.get("item_ids") not in (None, []):
            raise ValueError("invalid_scope")
        if not isinstance(scope.get("filter"), dict):
            raise ValueError("invalid_scope")
        # A read transaction freezes all pages into one explicit scope instead
        # of allowing concurrent import/review activity to alter the selection.
        out = []
        cursor = None
        with self._tx():
            while True:
                page = self.list_items(
                    cursor=cursor, limit=250, filters=scope["filter"], sort="id:asc"
                )
                out += [self.get_item(x["id"]) for x in page["items"]]
                cursor = page["next_cursor"]
                if not cursor:
                    break
        if not out:
            raise ValueError("empty_scope")
        return out

    def _refresh_labels(self, db, item_id, axis):
        d = db.execute(
            "SELECT label_ids FROM v2_decisions WHERE item_id=? AND axis=?",
            (item_id, axis),
        ).fetchone()
        p = (
            None
            if d
            else db.execute(
                "SELECT p.label_ids,p.status FROM v2_active_proposals a JOIN v2_predictions p ON p.prediction_id=a.prediction_id WHERE a.item_id=? AND a.axis=?",
                (item_id, axis),
            ).fetchone()
        )
        labels = (
            _load((d or p or {"label_ids": "[]"})["label_ids"], [])
            if d
            or (
                p
                and p["status"]
                not in {"unknown", "abstained", "unsupported", "candidate"}
            )
            else []
        )
        db.execute(
            "DELETE FROM v2_effective_labels WHERE item_id=? AND axis=?",
            (item_id, axis),
        )
        db.executemany(
            "INSERT INTO v2_effective_labels VALUES(?,?,?,?)",
            [
                (item_id, axis, _norm(x), "decision" if d else "proposal")
                for x in labels
                if _text(x)
            ],
        )

    def save_prediction(self, record):
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("axes"), dict)
            or not self.get_item(record.get("item_id"))
        ):
            raise ValueError("invalid_prediction")
        saved = []
        with self._tx() as db:
            for axis, value in record["axes"].items():
                if axis not in AXES or not isinstance(value, dict):
                    raise ValueError("invalid_prediction")
                labels = value.get("label_ids", [])
                if not isinstance(labels, list) or any(not _text(x) for x in labels):
                    raise ValueError("invalid_prediction")
                pid = str(uuid.uuid4())
                rev = (
                    db.execute(
                        "SELECT proposal_revision FROM v2_items WHERE item_id=?",
                        (record["item_id"],),
                    ).fetchone()["proposal_revision"]
                    + 1
                )
                db.execute(
                    "INSERT INTO v2_predictions(prediction_id,item_id,axis,label_ids,raw_score,calibrated_confidence,status,evidence,details,model,taxonomy_version,feature_version,created_at,revision) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        pid,
                        record["item_id"],
                        axis,
                        _dump(labels),
                        value.get("raw_score"),
                        value.get("calibrated_confidence"),
                        value.get("status", "candidate"),
                        _dump(value.get("evidence", [])),
                        _dump(value),
                        _dump(record.get("model", {})),
                        str(record.get("taxonomy_version", "1")),
                        str(record.get("feature_version", "1")),
                        _now(),
                        rev,
                    ),
                )
                db.execute(
                    "INSERT INTO v2_active_proposals VALUES(?,?,?) ON CONFLICT(item_id,axis) DO UPDATE SET prediction_id=excluded.prediction_id",
                    (record["item_id"], axis, pid),
                )
                self._refresh_labels(db, record["item_id"], axis)
                self._touch(db, record["item_id"], "proposal")
                saved.append(pid)
        return saved

    def record_analysis_outcome(self, record):
        """Append a non-decision analysis result, including abstentions/failures.

        The audio worker can be retried; outcomes are history, never a label
        pointer.  Embeddings are already held by the feature cache and are
        omitted here to avoid duplicating a large vector for every attempt.
        """
        if not isinstance(record, dict) or not isinstance(record.get("item_id"), str):
            raise ValueError("invalid_analysis_outcome")
        status = str(record.get("status") or "failed")
        if status not in {"proposed", "abstained", "unsupported", "failed"}:
            raise ValueError("invalid_analysis_outcome")
        if not self.get_item(record["item_id"]):
            raise ValueError("unknown_item")
        payload = dict(record)
        feature = payload.get("feature")
        if isinstance(feature, dict):
            feature = dict(feature)
            feature.pop("embedding", None)
            payload["feature"] = feature
        with self._tx() as db:
            db.execute(
                "INSERT INTO v2_analysis_outcomes VALUES(?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    record["item_id"],
                    status,
                    _text(record.get("reason")) or None,
                    _dump(payload),
                    _now(),
                ),
            )
        return {"item_id": record["item_id"], "status": status}

    def create_preview(self, kind, payload):
        if (
            kind not in {"review", "write", "export", "restore"}
            or not isinstance(payload, dict)
            or not isinstance(payload.get("items", []), list)
        ):
            raise ValueError("invalid_preview")
        body = dict(payload)
        snapshots = []
        entries = body.get("items", [])
        if not entries and kind == "export":
            entries = [
                {"item_id": x.get("item_id")}
                for x in body.get("manifest", [])
                if isinstance(x, dict) and x.get("item_id")
            ]
        for entry in entries:
            item = (
                self.get_item(entry.get("item_id")) if isinstance(entry, dict) else None
            )
            if not item or (
                entry.get("revision") and entry["revision"] != item["revision"]
            ):
                raise ValueError("stale_preview")
            snapshots.append({"item_id": item["id"], "revision": item["revision"]})
        body["items"] = entries
        body["item_revisions"] = snapshots
        pid = str(uuid.uuid4())
        now = _now()
        expiry = (
            (datetime.now(timezone.utc) + timedelta(hours=1))
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        with self._tx() as db:
            db.execute(
                "INSERT INTO v2_previews(preview_id,kind,payload,expires_at,created_at,status) VALUES(?,?,?,?,?,?)",
                (pid, kind, _dump(body), expiry, now, "active"),
            )
        return {"preview_id": pid, "expires_at": expiry, **body}

    def consume_preview(self, preview_id, kind):
        with self._tx() as db:
            row = db.execute(
                "SELECT payload FROM v2_previews WHERE preview_id=? AND kind=? AND status='active' AND expires_at>?",
                (preview_id, kind, _now()),
            ).fetchone()
            if not row:
                return None
            changed = db.execute(
                "UPDATE v2_previews SET status='consumed',consumed_at=? WHERE preview_id=? AND kind=? AND status='active'",
                (_now(), preview_id, kind),
            ).rowcount
            return _load(row["payload"], {}) if changed == 1 else None

    def save_decisions(self, preview, decisions):
        allowed = (
            {
                x.get("item_id"): x.get("revision")
                for x in preview.get("item_revisions", [])
                if isinstance(x, dict)
            }
            if isinstance(preview, dict)
            else {}
        )
        if not allowed or not isinstance(decisions, list) or not decisions:
            raise ValueError("invalid_decisions")
        fields = set(preview.get("fields") or [])
        if not fields:
            fields = {
                axis
                for entry in preview.get("items", [])
                if isinstance(entry, dict)
                for axis in (entry.get("axes") or {})
            }
        if any(
            not isinstance(x, dict)
            or x.get("item_id") not in allowed
            or x.get("axis") not in fields
            or x.get("axis") not in AXES
            or x.get("action")
            not in {"accept", "correct", "add", "remove", "lock", "unlock"}
            for x in decisions
        ):
            raise ValueError("invalid_decisions")
        preview_proposals = {
            (entry.get("item_id"), axis): data.get("proposal")
            for entry in preview.get("items", [])
            if isinstance(entry, dict)
            for axis, data in (entry.get("axes") or {}).items()
            if isinstance(data, dict)
        }
        with self._lock:
            tax = self._conn.execute(
                "SELECT document FROM v2_taxonomy WHERE singleton=1"
            ).fetchone()
        document = _load(tax["document"], {}) if tax else {}
        labels = [
            x
            for x in document.get("labels", [])
            if isinstance(x, dict) and _text(x.get("id"))
        ]
        known = {_norm(x["id"]): _text(x.get("axis")) for x in labels}
        configured_single = {
            _text(axis)
            for axis, config in (document.get("axes") or {}).items()
            if isinstance(config, dict) and config.get("cardinality") == "single"
        }
        single_axes = SINGLE_LABEL_AXES | configured_single

        def validate_labels(axis, values):
            if not isinstance(values, list) or any(
                not _text(value) for value in values
            ):
                raise ValueError("invalid_decisions")
            if axis in single_axes and len(values) > 1:
                raise ValueError("invalid_cardinality")
            for value in values:
                label_axis = known.get(_norm(value))
                # Personal labels are deliberately scoped by the decision axis.
                # They cannot be inferred and are never silently cross-mapped.
                if label_axis is None:
                    if not _norm(value).startswith("personal:"):
                        raise ValueError("invalid_label")
                # Older user taxonomy documents lacked an axis field.  They
                # are accepted as legacy vocabulary; all v2/default labels
                # are axis-scoped and receive the strict check.
                elif label_axis and label_axis != axis:
                    raise ValueError("invalid_label_axis")

        with self._tx() as db:
            stale = [
                i
                for i, r in allowed.items()
                if not (
                    row := db.execute(
                        "SELECT * FROM v2_items WHERE item_id=?", (i,)
                    ).fetchone()
                )
                or self._revision(row) != r
            ]
            if stale:
                raise ValueError("stale_preview")
            saved = []
            for x in decisions:
                current = db.execute(
                    "SELECT * FROM v2_decisions WHERE item_id=? AND axis=?",
                    (x["item_id"], x["axis"]),
                ).fetchone()
                labels = _load(current["label_ids"], []) if current else []
                supplied = x.get("label_ids", [])
                validate_labels(x["axis"], supplied)
                if current and current["locked"] and x["action"] != "unlock":
                    raise ValueError("locked_decision")
                proposal = preview_proposals.get((x["item_id"], x["axis"]))
                active = db.execute(
                    "SELECT p.* FROM v2_active_proposals a JOIN v2_predictions p ON p.prediction_id=a.prediction_id WHERE a.item_id=? AND a.axis=?",
                    (x["item_id"], x["axis"]),
                ).fetchone()
                if x["action"] == "accept":
                    if (
                        not proposal
                        or not active
                        or proposal.get("revision") != active["revision"]
                        or proposal.get("status")
                        in {"unknown", "abstained", "unsupported", "candidate"}
                    ):
                        raise ValueError("stale_preview")
                    expected = _load(active["label_ids"], [])
                    if supplied and supplied != expected:
                        raise ValueError("invalid_decisions")
                    validate_labels(x["axis"], expected)
                    labels = expected
                elif x["action"] in {"correct", "add", "remove"}:
                    validate_labels(x["axis"], supplied)
                if x["action"] == "add":
                    labels = list(dict.fromkeys(labels + supplied))
                elif x["action"] == "remove":
                    labels = [v for v in labels if v not in set(supplied)]
                elif x["action"] == "correct":
                    labels = supplied
                elif x["action"] == "lock" and not current:
                    if not active:
                        raise ValueError("missing_proposal")
                    labels = _load(active["label_ids"], [])
                    validate_labels(x["axis"], labels)
                validate_labels(x["axis"], labels)
                locked = (
                    True
                    if x["action"] in {"lock", "correct"}
                    else False
                    if x["action"] == "unlock"
                    else bool(current["locked"])
                    if current
                    else False
                )
                source = (
                    "correction"
                    if x["action"] in {"correct", "add", "remove"}
                    else x["action"]
                )
                revision = (current["revision"] if current else 0) + 1
                now = _now()
                db.execute(
                    "INSERT INTO v2_decisions VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(item_id,axis) DO UPDATE SET label_ids=excluded.label_ids,source=excluded.source,locked=excluded.locked,revision=excluded.revision,updated_at=excluded.updated_at",
                    (
                        x["item_id"],
                        x["axis"],
                        _dump(labels),
                        source,
                        int(locked),
                        revision,
                        current["created_at"] if current else now,
                        now,
                    ),
                )
                db.execute(
                    "INSERT INTO v2_decision_history VALUES(?,?,?,?,?,?,?,?)",
                    (
                        str(uuid.uuid4()),
                        x["item_id"],
                        x["axis"],
                        _dump(labels),
                        source,
                        int(locked),
                        revision,
                        now,
                    ),
                )
                self._refresh_labels(db, x["item_id"], x["axis"])
                self._touch(db, x["item_id"], "decision")
                if x["item_id"] not in saved:
                    saved.append(x["item_id"])
        return saved

    def taxonomy(self, default):
        with self._lock:
            row = self._conn.execute(
                "SELECT document,revision FROM v2_taxonomy WHERE singleton=1"
            ).fetchone()
        return (
            {"document": _load(row["document"], default), "revision": row["revision"]}
            if row
            else {"document": default, "revision": 0}
        )

    def save_taxonomy(self, document, expected_revision):
        with self._tx() as db:
            row = db.execute(
                "SELECT revision FROM v2_taxonomy WHERE singleton=1"
            ).fetchone()
            current = row["revision"] if row else 0
            if not isinstance(document, dict) or current != expected_revision:
                raise ValueError("stale_taxonomy")
            db.execute(
                "INSERT INTO v2_taxonomy VALUES(1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET document=excluded.document,revision=excluded.revision,updated_at=excluded.updated_at",
                (_dump(document), current + 1, _now()),
            )
        return {"document": document, "revision": current + 1}

    def views(self):
        with self._lock:
            rows = self._conn.execute("SELECT * FROM v2_views ORDER BY name").fetchall()
        return [
            {
                "id": r["view_id"],
                "name": r["name"],
                "definition": _load(r["definition"], {}),
                "revision": r["revision"],
            }
            for r in rows
        ]

    def save_view(self, data):
        if (
            not isinstance(data, dict)
            or not _text(data.get("name"))
            or not isinstance(data.get("definition"), dict)
        ):
            raise ValueError("invalid_view")
        ident = str(data.get("id") or uuid.uuid4())
        now = _now()
        with self._tx() as db:
            db.execute(
                "INSERT INTO v2_views VALUES(?,?,?,?,?,?) ON CONFLICT(view_id) DO UPDATE SET name=excluded.name,definition=excluded.definition,revision=v2_views.revision+1,updated_at=excluded.updated_at",
                (ident, _text(data["name"]), _dump(data["definition"]), 1, now, now),
            )
        return next(x for x in self.views() if x["id"] == ident)

    def settings(self):
        with self._lock:
            return {
                r["key"]: _load(r["value"], None)
                for r in self._conn.execute("SELECT * FROM v2_settings")
            }

    def save_settings(self, values):
        if not isinstance(values, dict):
            raise ValueError("invalid_settings")
        with self._tx() as db:
            db.executemany(
                "INSERT INTO v2_settings VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                [(k, _dump(v), _now()) for k, v in values.items()],
            )
        return self.settings()

    def create_export(self, profile, destination, route, manifest):
        if (
            not isinstance(profile, dict)
            or not _text(destination)
            or not _text(route)
            or not isinstance(manifest, list)
        ):
            raise ValueError("invalid_export")
        ident = str(uuid.uuid4())
        now = _now()
        with self._tx() as db:
            db.execute(
                "INSERT INTO v2_exports VALUES(?,?,?,?,?,?,?,?)",
                (
                    ident,
                    _dump(profile),
                    destination,
                    route,
                    "Prepared",
                    _dump(manifest),
                    now,
                    now,
                ),
            )
        return self.export(ident)

    def export(self, ident):
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM v2_exports WHERE export_id=?", (ident,)
            ).fetchone()
        return (
            None
            if not r
            else {
                "export_id": r["export_id"],
                "profile": _load(r["profile"], {}),
                "destination": r["destination"],
                "route": r["route"],
                "state": r["state"],
                "manifest": _load(r["manifest"], []),
            }
        )

    def update_export(self, ident, state, manifest=None):
        with self._tx() as db:
            r = db.execute(
                "SELECT manifest FROM v2_exports WHERE export_id=?", (ident,)
            ).fetchone()
            if not r:
                return None
            db.execute(
                "UPDATE v2_exports SET state=?,manifest=?,updated_at=? WHERE export_id=?",
                (
                    state,
                    _dump(_load(r["manifest"], []) if manifest is None else manifest),
                    _now(),
                    ident,
                ),
            )
        return self.export(ident)

    def checkpoint_export_item(self, export_id, job_id, outcome):
        """Atomically retain a staged output before marking its job item done.

        A restart therefore sees the recorded output checksum/identity and
        never treats an already copied item as a fresh unknown destination.
        """
        if not isinstance(outcome, dict) or not _text(outcome.get("item_id")):
            raise ValueError("invalid_export_checkpoint")
        item_id = str(outcome["item_id"])
        state = (
            "completed"
            if outcome.get("status") in {"copied", "unchanged"}
            else "failed"
        )
        with self._tx() as db:
            exported = db.execute(
                "SELECT manifest FROM v2_exports WHERE export_id=?", (export_id,)
            ).fetchone()
            item = db.execute(
                "SELECT 1 FROM v2_job_items WHERE job_id=? AND item_id=?",
                (job_id, item_id),
            ).fetchone()
            if not exported or not item:
                raise ValueError("unknown_export_checkpoint")
            manifest = _load(exported["manifest"], [])
            replaced = False
            updated = []
            for entry in manifest:
                if isinstance(entry, dict) and entry.get("item_id") == item_id:
                    updated.append(dict(outcome))
                    replaced = True
                else:
                    updated.append(entry)
            if not replaced:
                raise ValueError("unknown_export_item")
            now = _now()
            db.execute(
                "UPDATE v2_exports SET manifest=?,updated_at=? WHERE export_id=?",
                (_dump(updated), now, export_id),
            )
            db.execute(
                "UPDATE v2_job_items SET state=?,error_code=?,finished_at=? WHERE job_id=? AND item_id=?",
                (
                    state,
                    None
                    if state == "completed"
                    else str(outcome.get("status") or "export_failed"),
                    now,
                    job_id,
                    item_id,
                ),
            )
            counts = {
                r["state"]: r["count"]
                for r in db.execute(
                    "SELECT state,COUNT(*) count FROM v2_job_items WHERE job_id=? GROUP BY state",
                    (job_id,),
                )
            }
            summary = {
                "total": sum(counts.values()),
                "queued": counts.get("queued", 0),
                "running": counts.get("running", 0),
                "completed": counts.get("completed", 0),
                "failed": counts.get("failed", 0),
            }
            db.execute(
                "UPDATE v2_jobs SET counts=?,updated_at=? WHERE job_id=?",
                (_dump(summary), now, job_id),
            )
            self._event(
                db,
                job_id,
                "item_" + state,
                {
                    "item_id": item_id,
                    "counts": summary,
                    "error_code": None
                    if state == "completed"
                    else outcome.get("status"),
                },
            )
        return self.export(export_id)

    def latest_export(self, destination, profile_hash=None):
        """Return the newest local manifest for a destination/profile, read-only."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT export_id,profile FROM v2_exports WHERE destination=? ORDER BY created_at DESC,export_id DESC",
                (destination,),
            ).fetchall()
        for row in rows:
            profile = _load(row["profile"], {})
            digest = profile.get("hash") if isinstance(profile, dict) else None
            digest = digest or hashlib.sha256(_dump(profile).encode()).hexdigest()
            if profile_hash is None or digest == profile_hash:
                return self.export(row["export_id"])
        return None

    def known_export_manifest(self, destination):
        """Latest owned output per item across profiles, for safe profile switches."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT manifest FROM v2_exports WHERE destination=? ORDER BY created_at DESC,export_id DESC",
                (destination,),
            ).fetchall()
        known = {}
        for row in rows:
            for entry in _load(row["manifest"], []):
                if (
                    isinstance(entry, dict)
                    and entry.get("item_id")
                    and entry.get("output_sha256")
                ):
                    known.setdefault(str(entry["item_id"]), entry)
        return list(known.values())

    def export_destinations(self):
        """All owned staging roots, used to keep rescans from re-importing copies."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT destination FROM v2_exports"
            ).fetchall()
        return [str(row["destination"]) for row in rows if _text(row["destination"])]

    def record_write_intent(self, *, write_id, item_id, intent):
        """Journal a verified backup/staged write before source publication."""
        if not isinstance(intent, dict) or not all(
            _text(intent.get(key))
            for key in ("source_path", "source_sha256", "backup_path")
        ):
            raise ValueError("invalid_write_intent")
        if not self.get_item(item_id):
            raise ValueError("unknown_item")
        with self._tx() as db:
            if db.execute(
                "SELECT 1 FROM v2_write_ledger WHERE write_id=?", (write_id,)
            ).fetchone():
                raise ValueError("duplicate_write_intent")
            now = _now()
            db.execute(
                "INSERT INTO v2_write_ledger VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    write_id,
                    item_id,
                    str(intent["source_path"]),
                    str(intent["source_sha256"]),
                    None,
                    str(intent["backup_path"]),
                    _dump(intent.get("fields") or {}),
                    "publishing",
                    None,
                    now,
                    now,
                ),
            )
            db.execute(
                "INSERT INTO v2_write_intents VALUES(?,?,?)",
                (write_id, _dump(intent), now),
            )
        return {"write_id": write_id, "status": "publishing"}

    def unfinished_write_intents(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT l.write_id,l.item_id,l.source_path,l.before_sha256,l.backup_path,l.fields,l.status,i.payload FROM v2_write_ledger l JOIN v2_write_intents i ON i.write_id=l.write_id WHERE l.status='publishing'"
            ).fetchall()
        return [
            {
                "write_id": row["write_id"],
                "item_id": row["item_id"],
                "source_path": row["source_path"],
                "before_sha256": row["before_sha256"],
                "backup_path": row["backup_path"],
                "fields": _load(row["fields"], {}),
                "intent": _load(row["payload"], {}),
                **_load(row["payload"], {}),
            }
            for row in rows
        ]

    def reconcile_write_intent(
        self, write_id, outcome=None, *, status=None, after_sha256=None, error_code=None
    ):
        if isinstance(outcome, dict):
            status = outcome.get("status")
            after_sha256 = outcome.get("after_sha256")
            error_code = outcome.get("error_code")
        if status not in {"written", "failed", "recovery_required"}:
            raise ValueError("invalid_write_reconciliation")
        with self._tx() as db:
            current = db.execute(
                "SELECT item_id FROM v2_write_ledger WHERE write_id=? AND status='publishing'",
                (write_id,),
            ).fetchone()
            if not current:
                return None
            db.execute(
                "UPDATE v2_write_ledger SET status=?,after_sha256=?,error_code=?,updated_at=? WHERE write_id=?",
                (status, after_sha256, error_code, _now(), write_id),
            )
            if status == "recovery_required":
                db.execute(
                    "UPDATE v2_items SET conflict=1 WHERE item_id=?",
                    (current["item_id"],),
                )
                self._bump(db)
        return self.write_record(write_id)

    def finalize_write_intent(self, *, write_id, item_id, outcome):
        """Complete a journaled write, or retain a pre-publish backup failure."""
        if not isinstance(outcome, dict):
            raise ValueError("invalid_write")
        backup_path = outcome.get("backup_path")
        with self._tx() as db:
            prior = db.execute(
                "SELECT 1 FROM v2_write_ledger WHERE write_id=?", (write_id,)
            ).fetchone()
            status = (
                "written"
                if outcome.get("status") == "published_verified"
                else str(outcome.get("status") or "failed")
            )
            now = _now()
            if prior:
                db.execute(
                    "UPDATE v2_write_ledger SET after_sha256=?,fields=?,status=?,error_code=?,updated_at=? WHERE write_id=?",
                    (
                        outcome.get("after_sha256"),
                        _dump(outcome.get("fields") or {}),
                        status,
                        outcome.get("error_code"),
                        now,
                        write_id,
                    ),
                )
            elif backup_path and _text(outcome.get("before_sha256")):
                db.execute(
                    "INSERT INTO v2_write_ledger VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        write_id,
                        item_id,
                        str(outcome.get("source_path") or ""),
                        str(outcome["before_sha256"]),
                        outcome.get("after_sha256"),
                        str(backup_path),
                        _dump(outcome.get("fields") or {}),
                        status,
                        outcome.get("error_code"),
                        now,
                        now,
                    ),
                )
            else:
                raise ValueError("missing_write_intent")
            if status in {"conflict", "recovery_required"}:
                db.execute("UPDATE v2_items SET conflict=1 WHERE item_id=?", (item_id,))
                self._bump(db)
        return {"write_id": write_id, "status": status}

    def record_write(
        self,
        *,
        item_id,
        source_path,
        before_sha256,
        after_sha256,
        backup_path,
        fields,
        status,
        error_code=None,
    ):
        if (
            not self.get_item(item_id)
            or not isinstance(fields, dict)
            or not all(
                _text(x) for x in (source_path, before_sha256, backup_path, status)
            )
        ):
            raise ValueError("invalid_write")
        ident = str(uuid.uuid4())
        now = _now()
        with self._tx() as db:
            db.execute(
                "INSERT INTO v2_write_ledger VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ident,
                    item_id,
                    source_path,
                    before_sha256,
                    after_sha256,
                    backup_path,
                    _dump(fields),
                    status,
                    error_code,
                    now,
                    now,
                ),
            )
            if status in {"conflict", "recovery_required"}:
                db.execute("UPDATE v2_items SET conflict=1 WHERE item_id=?", (item_id,))
                self._bump(db)
        return {"write_id": ident, "status": status}

    def write_record(self, ident):
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM v2_write_ledger WHERE write_id=?", (ident,)
            ).fetchone()
        return (
            None
            if not r
            else {k: _load(r[k], {}) if k == "fields" else r[k] for k in r.keys()}
        )

    def list_writes(self, cursor=None, limit=100):
        try:
            limit = int(limit)
            offset = int(cursor or 0)
        except (TypeError, ValueError):
            raise ValueError("invalid_cursor") from None
        if not 1 <= limit <= 250 or offset < 0:
            raise ValueError("invalid_cursor")
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) n FROM v2_write_ledger"
            ).fetchone()["n"]
            rows = self._conn.execute(
                "SELECT * FROM v2_write_ledger ORDER BY created_at DESC,write_id DESC LIMIT ? OFFSET ?",
                (limit + 1, offset),
            ).fetchall()
        more, rows = len(rows) > limit, rows[:limit]
        writes = [
            {
                "write_id": r["write_id"],
                "item_id": r["item_id"],
                "status": r["status"],
                "error_code": r["error_code"],
                "fields": _load(r["fields"], {}),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
        return {
            "items": writes,
            "writes": writes,
            "next_cursor": str(offset + limit) if more else None,
            "total": total,
        }

    def _event(self, db, job_id, type_, payload):
        seq = db.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 n FROM v2_job_events WHERE job_id=?",
            (job_id,),
        ).fetchone()["n"]
        db.execute(
            "INSERT INTO v2_job_events VALUES(?,?,?,?,?)",
            (job_id, seq, type_, _dump(payload), _now()),
        )
        return seq

    def create_job(self, kind, scope, config):
        ids = scope.get("item_ids") if isinstance(scope, dict) else None
        allows_empty = kind in {"import", "model_download"}
        if (
            not _text(kind)
            or not isinstance(ids, list)
            or (not ids and not allows_empty)
            or len(set(ids)) != len(ids)
            or not isinstance(config, dict)
        ):
            raise ValueError("invalid_job")
        with self._tx() as db:
            rows = []
            for offset in range(0, len(ids), 900):
                part = ids[offset : offset + 900]
                if part:
                    rows.extend(
                        db.execute(
                            "SELECT * FROM v2_items WHERE item_id IN (%s)"
                            % ",".join("?" * len(part)),
                            part,
                        ).fetchall()
                    )
            if len(rows) != len(ids):
                raise ValueError("unknown_item")
            taxonomy = db.execute(
                "SELECT revision FROM v2_taxonomy WHERE singleton=1"
            ).fetchone()
            frozen = {
                "item_ids": ids,
                "item_revisions": [
                    {"item_id": r["item_id"], "revision": self._revision(r)}
                    for r in rows
                ],
                "taxonomy_revision": taxonomy["revision"] if taxonomy else 0,
            }
            ident = str(uuid.uuid4())
            now = _now()
            counts = {
                "total": len(ids),
                "queued": len(ids),
                "running": 0,
                "completed": 0,
                "failed": 0,
            }
            db.execute(
                "INSERT INTO v2_jobs VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    ident,
                    kind,
                    "queued",
                    _dump(frozen),
                    _dump(config),
                    _dump(counts),
                    None,
                    None,
                    now,
                    now,
                ),
            )
            db.executemany(
                "INSERT INTO v2_job_items(job_id,item_id,state) VALUES(?,?,?)",
                [(ident, x, "queued") for x in ids],
            )
            self._event(db, ident, "job_queued", {"state": "queued", "counts": counts})
        return self.job(ident)

    def append_job_item(self, job_id, item_id):
        """Durably add an import-discovered item without recreating its job."""
        with self._tx() as db:
            job = db.execute(
                "SELECT state FROM v2_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if not job or job["state"] not in {
                "queued",
                "running",
                "pausing",
                "paused",
            }:
                raise ValueError("invalid_job")
            if not db.execute(
                "SELECT 1 FROM v2_items WHERE item_id=?", (item_id,)
            ).fetchone():
                raise ValueError("unknown_item")
            db.execute(
                "INSERT OR IGNORE INTO v2_job_items(job_id,item_id,state) VALUES(?,?,?)",
                (job_id, item_id, "queued"),
            )
            counts = {
                r["state"]: r["count"]
                for r in db.execute(
                    "SELECT state,COUNT(*) count FROM v2_job_items WHERE job_id=? GROUP BY state",
                    (job_id,),
                )
            }
            summary = {
                "total": sum(counts.values()),
                "queued": counts.get("queued", 0),
                "running": counts.get("running", 0),
                "completed": counts.get("completed", 0),
                "failed": counts.get("failed", 0),
            }
            db.execute(
                "UPDATE v2_jobs SET counts=?,updated_at=? WHERE job_id=?",
                (_dump(summary), _now(), job_id),
            )
            self._event(
                db, job_id, "item_queued", {"item_id": item_id, "counts": summary}
            )
        return self.job(job_id)

    def job(self, ident):
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM v2_jobs WHERE job_id=?", (ident,)
            ).fetchone()
        return (
            None
            if not r
            else {
                "job_id": r["job_id"],
                "kind": r["kind"],
                "state": r["state"],
                "scope": _load(r["scope"], {}),
                "config": _load(r["config"], {}),
                "counts": _load(r["counts"], {}),
                "cursor": r["cursor"],
                "error_code": r["error_code"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "resumable": r["state"] in {"queued", "paused", "interrupted"},
            }
        )

    def list_jobs(self, cursor=None, limit=100):
        try:
            limit = max(1, min(int(limit), 250))
            offset = max(0, int(cursor or 0))
        except (TypeError, ValueError):
            raise ValueError("invalid_cursor") from None
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) n FROM v2_jobs").fetchone()["n"]
            ids = [
                r["job_id"]
                for r in self._conn.execute(
                    "SELECT job_id FROM v2_jobs ORDER BY created_at DESC,job_id DESC LIMIT ? OFFSET ?",
                    (limit + 1, offset),
                )
            ]
        more = len(ids) > limit
        ids = ids[:limit]
        return {
            "items": [self.job(x) for x in ids],
            "next_cursor": str(offset + limit) if more else None,
            "total": total,
        }

    def set_job_state(self, ident, state):
        with self._tx() as db:
            r = db.execute(
                "SELECT state FROM v2_jobs WHERE job_id=?", (ident,)
            ).fetchone()
            if not r or state not in TRANSITIONS.get(r["state"], set()):
                return None
            db.execute(
                "UPDATE v2_jobs SET state=?,updated_at=? WHERE job_id=?",
                (state, _now(), ident),
            )
            self._event(db, ident, "state_changed", {"state": state})
        return self.job(ident)

    def event(self, ident, type_, payload):
        with self._tx() as db:
            if not db.execute(
                "SELECT 1 FROM v2_jobs WHERE job_id=?", (ident,)
            ).fetchone():
                raise ValueError("unknown_job")
            return self._event(db, ident, type_, payload)

    def events(self, ident, after=0, limit=250):
        try:
            after = max(0, int(after))
            limit = max(1, min(int(limit), 250))
        except (TypeError, ValueError):
            raise ValueError("invalid_cursor") from None
        with self._lock:
            job = self._conn.execute(
                "SELECT state,counts FROM v2_jobs WHERE job_id=?", (ident,)
            ).fetchone()
            rows = self._conn.execute(
                "SELECT * FROM v2_job_events WHERE job_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                (ident, after, limit),
            ).fetchall()
        if not job:
            return []
        snapshot = {
            "job_id": ident,
            "state": job["state"],
            "counts": _load(job["counts"], {}),
        }
        return [
            {
                **snapshot,
                "sequence": r["sequence"],
                "type": r["type"],
                "created_at": r["created_at"],
                **_load(r["payload"], {}),
            }
            for r in rows
        ]

    def update_job_item(self, job_id, item_id, state, cursor=None, error_code=None):
        if state not in {"queued", "running", "completed", "failed", "cancelled"}:
            raise ValueError("invalid_job_item")
        with self._tx() as db:
            old = db.execute(
                "SELECT * FROM v2_job_items WHERE job_id=? AND item_id=?",
                (job_id, item_id),
            ).fetchone()
            if not old:
                raise ValueError("unknown_job_item")
            now = _now()
            db.execute(
                "UPDATE v2_job_items SET state=?,cursor=?,attempt=attempt+?,error_code=?,started_at=COALESCE(started_at,?),finished_at=? WHERE job_id=? AND item_id=?",
                (
                    state,
                    cursor,
                    int(state == "running" and old["state"] != "running"),
                    error_code,
                    now,
                    now if state in {"completed", "failed", "cancelled"} else None,
                    job_id,
                    item_id,
                ),
            )
            counts = {
                r["state"]: r["count"]
                for r in db.execute(
                    "SELECT state,COUNT(*) count FROM v2_job_items WHERE job_id=? GROUP BY state",
                    (job_id,),
                )
            }
            total = sum(counts.values())
            summary = {
                "total": total,
                "queued": counts.get("queued", 0),
                "running": counts.get("running", 0),
                "completed": counts.get("completed", 0),
                "failed": counts.get("failed", 0),
            }
            db.execute(
                "UPDATE v2_jobs SET counts=?,cursor=?,updated_at=? WHERE job_id=?",
                (_dump(summary), cursor, _now(), job_id),
            )
            self._event(
                db,
                job_id,
                "item_" + state,
                {"item_id": item_id, "counts": summary, "error_code": error_code},
            )
        return self.job(job_id)

    def job_items(self, job_id, cursor=None, limit=100):
        limit = max(1, min(int(limit), 250))
        offset = int(cursor or 0)
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) n FROM v2_job_items WHERE job_id=?", (job_id,)
            ).fetchone()["n"]
            rows = self._conn.execute(
                "SELECT * FROM v2_job_items WHERE job_id=? ORDER BY item_id LIMIT ? OFFSET ?",
                (job_id, limit + 1, offset),
            ).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": [dict(r) for r in rows],
            "next_cursor": str(offset + limit) if more else None,
            "total": total,
        }

    def recover_interrupted_jobs(self):
        with self._tx() as db:
            ids = [
                r["job_id"]
                for r in db.execute(
                    "SELECT job_id FROM v2_jobs WHERE state IN ('running','pausing','cancelling')"
                )
            ]
            for ident in ids:
                db.execute(
                    "UPDATE v2_jobs SET state='interrupted',updated_at=? WHERE job_id=?",
                    (_now(), ident),
                )
                self._event(db, ident, "interrupted", {"state": "interrupted"})
        return [self.job(x) for x in ids]

    def get_feature(self, cache_key):
        with self._lock:
            r = self._conn.execute(
                "SELECT record FROM v2_feature_cache WHERE cache_key=?", (cache_key,)
            ).fetchone()
        return _load(r["record"], {}) if r else None

    def put_feature(self, record):
        if not isinstance(record, dict) or not _text(record.get("cache_key")):
            raise ValueError("invalid_feature")
        now = _now()
        with self._tx() as db:
            db.execute(
                "INSERT INTO v2_feature_cache VALUES(?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET record=excluded.record,updated_at=excluded.updated_at",
                (record["cache_key"], _dump(record), now, now),
            )
        return record
