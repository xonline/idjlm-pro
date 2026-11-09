"""Durable local API for the redesigned library workflow.

The surface is deliberately explicit: library reads do not create records,
selection scopes cannot fall back to the whole library, and all file mutations
use a consumed revision-bound preview.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from flask import Blueprint, Response, jsonify, request, send_file

bp = Blueprint("v2", __name__, url_prefix="/api/v2")
_workers_lock = threading.RLock()
_workers: set[str] = set()
_classify_queue: queue.Queue[tuple[object, str]] = queue.Queue()
_classify_scheduler: threading.Thread | None = None
_audio_engines: dict[int, object] = {}
_model_status_cache: dict[str, object] = {
    "checked_at": 0.0,
    "value": {"state": "unknown"},
}


@bp.before_request
def require_local_json_mutation():
    """Keep local file actions out of cross-site form posts.

    A missing Origin is allowed for the packaged desktop shell and command-line
    smoke tests. Browser requests that provide an Origin must be loopback.
    """
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if not request.is_json:
            return _error(
                "json_required", "Mutating v2 requests must use application/json", 415
            )
        origin = request.headers.get("Origin")
        if origin:
            host = (urlparse(origin).hostname or "").casefold()
            if host not in {"localhost", "127.0.0.1", "::1"}:
                return _error(
                    "origin_denied",
                    "Local file actions are available only from the local app",
                    403,
                )


def _v2():
    from app import get_v2_store

    store = get_v2_store()
    if store is None:
        raise RuntimeError("v2 store unavailable")
    return store


def _body() -> dict:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _error(code: str, detail: str, status: int = 400):
    return jsonify({"error": code, "detail": detail}), status


def _filters() -> dict:
    raw = request.args.get("filters", "{}")
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("invalid_filters") from None
    if not isinstance(value, dict):
        raise ValueError("invalid_filters")
    return value


def _scope(data: dict) -> dict:
    source = data.get("scope")
    if not isinstance(source, dict):
        # Compatibility is intentionally narrow: callers must make selection
        # explicit, so an empty request can never write/export every item.
        source = {
            "selection": data.get("selection"),
            "item_ids": data.get("item_ids"),
            "filter": data.get("filter"),
        }
    return {
        "selection": source.get("selection"),
        "item_ids": source.get("item_ids"),
        "filter": source.get("filter"),
    }


def _resolved(data: dict):
    try:
        return _v2().resolve_scope(_scope(data))
    except ValueError as exc:
        raise ValueError(str(exc)) from None


def _preview_is_current(preview: dict) -> bool:
    store = _v2()
    for snapshot in preview.get("item_revisions", []):
        item = (
            store.get_item(snapshot.get("item_id"))
            if isinstance(snapshot, dict)
            else None
        )
        if not item or item["revision"] != snapshot.get("revision"):
            return False
    expected_taxonomy = preview.get("taxonomy_revision")
    if (
        expected_taxonomy is not None
        and store.taxonomy(_default_taxonomy())["revision"] != expected_taxonomy
    ):
        return False
    return True


def _ensure_default_taxonomy() -> None:
    """Persist canonical defaults before a mutation validates label IDs."""
    store = _v2()
    current = store.taxonomy(_default_taxonomy())
    if current["revision"] == 0:
        try:
            store.save_taxonomy(_default_taxonomy(), 0)
        except ValueError:
            pass


def _source_revision(track) -> str:
    return ":".join(
        str(value or "")
        for value in (
            getattr(track, "file_mtime", None),
            getattr(track, "file_size", None),
            getattr(track, "content_hash", None),
        )
    )


def _default_taxonomy() -> dict:
    # Stable IDs are independent from legacy display spelling. Raw legacy tags
    # remain original evidence and aliases, rather than silently becoming labels.
    labels = [
        ("salsa", "Salsa", "music_family", ["Salsa"]),
        ("bachata", "Bachata", "music_family", ["Bachata"]),
        ("kizomba", "Kizomba", "music_family", ["Kizomba"]),
        ("kompa", "Kompa", "music_family", ["Kompa", "Kumpa", "Compas"]),
        (
            "cha_cha",
            "Cha-cha",
            "music_family",
            ["Cha Cha", "Cha-cha-cha", "cha_cha_cha"],
        ),
        ("boogaloo", "Latin Boogaloo", "music_family", ["Boogaloo", "Latin Boogaloo"]),
        # Semba is a neighbouring family/hard negative for Kizomba, never a
        # Kizomba substyle.  It remains manual vocabulary until evaluated.
        ("semba", "Semba", "music_family", ["Semba"]),
        (
            "salsa_romantica",
            "Salsa Romántica",
            "style",
            ["Romántica", "Salsa Romantica"],
        ),
        ("salsa_dura", "Salsa Dura", "style", ["Dura", "Salsa Dura"]),
        ("timba", "Timba", "style", ["Timba"]),
        (
            "bachata_traditional",
            "Bachata Tradicional",
            "style",
            ["Dominicana/Tradicional"],
        ),
        ("bachata_dominicana", "Bachata Dominicana", "style", ["Dominicana"]),
        ("bachata_moderna", "Bachata Moderna", "style", ["Moderna"]),
        ("bachata_urbana", "Bachata Urbana", "style", ["Remix/Urbana"]),
        ("kizomba_classica", "Kizomba Clássica", "style", ["Kizomba Classica"]),
        ("ghetto_zouk", "Ghetto Zouk", "style", ["Ghetto Zouk"]),
        ("tarraxinha", "Tarraxinha", "style", ["Tarraxinha"]),
        ("urban_kiz", "Urban Kiz", "style", ["Urban Kiz"]),
        ("tarraxo", "Tarraxo", "dance_use", ["Tarraxo"]),
        ("douceur", "Douceur", "dance_use", ["Douceur"]),
        ("bachata_sensual", "Bachata Sensual", "dance_use", ["Sensual"]),
        # These aliases preserve raw experimental ranking provenance but do
        # not turn one combined/instrument cue into automatic human labels.
        (
            "charanga",
            "Charanga",
            "instrument_cue",
            ["Charanga", "charanga_arrangement"],
        ),
        (
            "bachata_influenced",
            "Bachata influenced",
            "production",
            ["English lyrics remix"],
        ),
    ]
    return {
        "version": 1,
        "axes": {
            "music_family": {"cardinality": "single"},
            "vocal_presence": {"cardinality": "single"},
            "vocal_language": {"cardinality": "single"},
        },
        "labels": [
            {
                "id": key,
                "display_name": text,
                "axis": axis,
                "status": "vocabulary_only",
                "aliases": aliases,
            }
            for key, text, axis, aliases in labels
        ],
        "palette": {
            "raw_comment_tokens": [
                "classica",
                "cubana",
                "dura / brava",
                "latin jazz",
                "mambo",
                "romantica",
                "timba",
                "tropical",
                "afro",
                "instrumental",
                "boogaloo",
                "charanga",
                "english,fusion",
                "guaguanco",
                "guajira",
                "on1",
                "pachanga",
                "rumba",
                "son",
                "swap",
                "live",
                "choke",
                "tempo changed",
                "????",
                "descasgar",
                "cumbia",
                "breaks",
            ]
        },
        "auto_approval": {
            "enabled": False,
            "reason": "no evaluated calibration profile",
        },
    }


def _model_status(force: bool = False) -> dict:
    """Cache local verification so Settings does not rehash model files per view."""
    now = time.monotonic()
    with _workers_lock:
        if not force and now - float(_model_status_cache["checked_at"]) < 60:
            return dict(_model_status_cache["value"])
    try:
        from app.services.audio_classification import (
            ModelInstaller,
            DEFAULT_MODEL_ID,
            audio_runtime_status,
        )

        runtime = audio_runtime_status()
        if not runtime["available"]:
            value = {
                "state": "runtime_unavailable",
                "model_id": DEFAULT_MODEL_ID,
                "reason": runtime["reason"],
                "missing": runtime["missing"],
            }
            with _workers_lock:
                _model_status_cache.update({"checked_at": now, "value": value})
            return dict(value)
        ModelInstaller().verify_installed(DEFAULT_MODEL_ID)
        value = {"state": "installed", "model_id": DEFAULT_MODEL_ID}
    except Exception as exc:
        value = {"state": "unavailable", "reason": str(exc)[:200]}
    with _workers_lock:
        _model_status_cache.update({"checked_at": now, "value": value})
    return dict(value)


def _raw_comments(original: dict) -> list[dict]:
    records = []
    for key, raw in (original.get("custom_tags") or {}).items():
        if not str(key).startswith("COMM:"):
            continue
        try:
            values = json.loads(raw)
        except (TypeError, ValueError):
            values = [raw]
        if isinstance(values, list):
            records.append({"frame": key, "values": [str(value) for value in values]})
    return records


def _managed_comment(original: dict) -> str | None:
    raw = (original.get("custom_tags") or {}).get("COMM:IDJLM:eng")
    if raw is None:
        return None
    try:
        values = json.loads(raw)
        return str(values[0]) if isinstance(values, list) and values else None
    except (TypeError, ValueError):
        return str(raw)


def _managed_tokens(comment: str | None) -> list[str]:
    if not isinstance(comment, str) or not comment.startswith("IDJLMv1:"):
        return []
    try:
        data = json.loads(comment.removeprefix("IDJLMv1:"))
        values = data.get("tokens", [])
        return [str(value) for value in values] if isinstance(values, list) else []
    except (TypeError, ValueError):
        return []


def _write_backup_root(store) -> Path:
    """Use an explicit local backup location when configured, never prune it."""
    configured = store.settings().get("write_backup_dir")
    if isinstance(configured, str) and configured.strip():
        return Path(configured).expanduser()
    from app.utils.paths import app_user_dir

    return Path(app_user_dir()) / "write-backups-v2"


def _existing_parent(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _write_storage_preflight(entries: list[dict], backup_root: Path) -> dict:
    """Report backup and temporary-copy space before a source write job."""
    backup_bytes = 0
    temp_by_device: dict[int, dict] = {}
    for entry in entries:
        if entry.get("status") != "ready":
            continue
        source = Path(entry["path"])
        size = source.stat().st_size
        backup_bytes += size
        parent = _existing_parent(source.parent)
        device = parent.stat().st_dev
        group = temp_by_device.setdefault(
            device, {"path": str(parent), "required_bytes": 0}
        )
        group["required_bytes"] += size
    backup_parent = _existing_parent(backup_root)
    backup_free = shutil.disk_usage(backup_parent).free
    # Each source needs a sibling temporary until atomic replacement.  The
    # original remains in place, so this is additional free space, not size.
    temporary = []
    enough = backup_free >= backup_bytes
    for group in temp_by_device.values():
        group["free_bytes"] = shutil.disk_usage(group["path"]).free
        group["enough_space"] = group["free_bytes"] >= group["required_bytes"]
        enough = enough and group["enough_space"]
        temporary.append(group)
    return {
        "backup_root": str(backup_root),
        "backup_bytes": backup_bytes,
        "backup_free_bytes": backup_free,
        "temporary_filesystems": temporary,
        "required_bytes": backup_bytes
        + sum(item["required_bytes"] for item in temporary),
        "enough_space": enough,
    }


def _encode_tokens(values: list[str]) -> str:
    return "IDJLMv1:" + json.dumps(
        {"tokens": values}, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


def _label_display_map() -> dict[str, str]:
    document = _v2().taxonomy(_default_taxonomy())["document"]
    return {
        str(label.get("id")): str(label.get("display_name") or label.get("id"))
        for label in document.get("labels", [])
        if isinstance(label, dict) and label.get("id")
    }


def _decision_labels(entry: dict, axis: str) -> list[str]:
    decision = ((entry.get("axes") or {}).get(axis) or {}).get("decision") or {}
    values = decision.get("label_ids") or []
    return [str(value) for value in values]


def _export_tag_fields(
    entry: dict, profile: dict, labels: dict[str, str]
) -> tuple[dict[str, str], dict]:
    """Map accepted decisions to copy-only interoperable tag values."""
    family = _decision_labels(entry, "music_family")
    styles = _decision_labels(entry, "style")
    details = (
        styles
        + _decision_labels(entry, "dance_use")
        + _decision_labels(entry, "production")
        + _decision_labels(entry, "instrument_cue")
        + _decision_labels(entry, "comment")
        + _decision_labels(entry, "comment_token")
        + _decision_labels(entry, "custom_tag")
    )
    family_text = labels.get(family[0], family[0]) if family else ""
    detail_texts = [labels.get(value, value) for value in details]
    raw_comment = str(entry["original"].get("existing_comment") or "").strip()
    managed = _managed_comment(entry["original"])
    literal_tokens = _managed_tokens(managed)
    comment_parts = [
        part for part in [raw_comment, *detail_texts, *literal_tokens] if part
    ]
    name = str(profile.get("name", "broad_genre_raw_comment"))
    if name == "djay_extended_genre":
        genre_parts = [
            part
            for part in [family_text, *[labels.get(value, value) for value in styles]]
            if part
        ]
        genre = ", ".join(dict.fromkeys(genre_parts))
    else:
        genre = (
            family_text or str(entry["original"].get("existing_genre") or "").strip()
        )
    fields = {}
    if genre:
        fields["genre"] = genre
    if comment_parts:
        # Explicit human-readable standard Comment on the *copy*. We neither
        # split nor change the source's raw COMMENT frames.
        fields["comment"] = " | ".join(dict.fromkeys(comment_parts))
    return fields, {
        "genre": genre or None,
        "comment": fields.get("comment"),
        "profile": name,
    }


def _refresh_item_from_path(
    store, item_id: str, path: str, preserve: dict | None = None
):
    """Re-read actual tags after a verified write or restore without losing decisions."""
    from app.services.scanner import _scan_single_file

    track = _scan_single_file(path, Path(path).name, Path(path).suffix.lower())
    original = track.to_dict()
    if preserve:
        original["source_observations"] = preserve.get("source_observations") or {
            "existing_genre": preserve.get("existing_genre"),
            "existing_comment": preserve.get("existing_comment"),
            "custom_tags": preserve.get("custom_tags") or {},
        }
    return store.upsert_item(
        path=path,
        item_id=item_id,
        original=original,
        source_revision=_source_revision(track),
        availability="present" if os.path.isfile(path) else "missing",
        conflict=bool(track.error),
    )


def _write_fields(
    entry: dict, selected: list[str], override: dict | None
) -> tuple[dict, dict]:
    override = override if isinstance(override, dict) else {}
    original, axes = entry["original"], entry.get("axes") or {}
    family = ((axes.get("music_family") or {}).get("decision") or {}).get(
        "label_ids"
    ) or []
    details = []
    for axis in (
        "style",
        "dance_use",
        "production",
        "instrument_cue",
        "comment",
        "comment_token",
        "custom_tag",
    ):
        details.extend(
            ((axes.get(axis) or {}).get("decision") or {}).get("label_ids") or []
        )
    labels = _label_display_map()
    managed = _managed_comment(original)
    after = {
        "genre": str(
            override.get(
                "genre",
                labels.get(str(family[0]), str(family[0]))
                if family
                else original.get("existing_genre") or "",
            )
        ),
        "comment": override.get(
            "comment",
            _encode_tokens([labels.get(str(value), str(value)) for value in details])
            if details
            else managed,
        ),
    }
    token_change = override.get("comment_tokens")
    if isinstance(token_change, dict):
        values = token_change.get("values")
        action = token_change.get("action")
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value for value in values
        ):
            raise ValueError("invalid_comment_tokens")
        current = _managed_tokens(managed)
        if action == "replace":
            current = values
        elif action == "add":
            current = list(dict.fromkeys(current + values))
        elif action == "remove":
            current = [value for value in current if value not in set(values)]
        else:
            raise ValueError("invalid_comment_tokens")
        after["comment"] = _encode_tokens(current)
    fields = {field: after.get(field) for field in selected}
    provenance = {
        "raw_comments": _raw_comments(original),
        "managed_comment": managed,
        "managed_tokens": _managed_tokens(managed),
    }
    return fields, provenance


@bp.get("/library/items")
def library_items():
    try:
        return jsonify(
            _v2().list_items(
                cursor=request.args.get("cursor"),
                limit=request.args.get("limit", 100),
                filters=_filters(),
                sort=request.args.get("sort", "title:asc"),
            )
        )
    except ValueError as exc:
        return _error(str(exc), "Invalid library page or filters")


def _legacy_label_id(
    value: object, axis: str, document: dict
) -> tuple[str, dict | None]:
    """Resolve a confirmed legacy display value without normalising raw tags.

    Unknown legacy vocabulary becomes a visible, axis-scoped personal label;
    the source observation remains untouched in ``original`` either way.
    """
    text = str(value or "").strip()
    if not text:
        return "", None
    wanted = text.casefold()
    for label in document.get("labels", []):
        if not isinstance(label, dict) or label.get("axis") != axis:
            continue
        candidates = [
            label.get("id"),
            label.get("display_name"),
            *(label.get("aliases") or []),
        ]
        if any(
            str(candidate or "").strip().casefold() == wanted
            for candidate in candidates
        ):
            return str(label["id"]), None
    ident = (
        "personal:" + hashlib.sha256(f"{axis}\0{text}".encode("utf-8")).hexdigest()[:16]
    )
    return ident, {
        "id": ident,
        "display_name": text,
        "axis": axis,
        "status": "legacy_manual_vocabulary",
        "aliases": [text],
    }


@bp.get("/library/migration-status")
def library_migration_status():
    """Read-only status for the opt-in legacy inventory migration."""
    from app import get_track_store

    legacy = len(get_track_store())
    v2_count = _v2().list_items(cursor=None, limit=1, filters={}, sort="id:asc")[
        "total"
    ]
    return jsonify(
        {
            "legacy_track_count": legacy,
            "v2_item_count": v2_count,
            "bootstrap_available": legacy > 0,
            "migration_required": legacy > 0 and v2_count == 0,
        }
    )


@bp.post("/library/bootstrap")
def library_bootstrap():
    """Opt in to an additive, repeatable import of the existing legacy view."""
    from app import get_track_store

    _ensure_default_taxonomy()
    store = _v2()
    taxonomy = store.taxonomy(_default_taxonomy())
    document = dict(taxonomy["document"])
    document["labels"] = list(document.get("labels") or [])
    rows = []
    confirmed: list[tuple[str, str, str]] = []
    for path, track in get_track_store().items():
        record = track.to_dict()
        status = str(record.get("review_status") or "").casefold()
        # Pending/skipped legacy proposals are evidence only.  Only a legacy
        # approval or edit is carried forward as a locked human decision.
        axes = []
        if status in {"approved", "edited"}:
            for axis, value in (
                ("music_family", record.get("final_genre")),
                ("style", record.get("final_subgenre")),
            ):
                if value is None or not str(value).strip():
                    continue
                label_id, new_label = _legacy_label_id(value, axis, document)
                if new_label:
                    document["labels"].append(new_label)
                axes.append((axis, label_id))
            record["legacy_migration"] = {
                "review_status": status,
                "confirmed_human": True,
            }
        else:
            record["legacy_migration"] = {
                "review_status": status or "unknown",
                "confirmed_human": False,
            }
        rows.append(
            {
                "path": path,
                "original": record,
                "source_revision": _source_revision(track),
                "availability": "present" if os.path.isfile(path) else "missing",
            }
        )
    try:
        if document != taxonomy["document"]:
            taxonomy = store.save_taxonomy(document, taxonomy["revision"])
        saved = store.bootstrap_from_tracks(rows)
        by_path = {entry["path"]: entry["id"] for entry in saved}
        for path, track in get_track_store().items():
            record = track.to_dict()
            if str(record.get("review_status") or "").casefold() not in {
                "approved",
                "edited",
            }:
                continue
            for axis, value in (
                ("music_family", record.get("final_genre")),
                ("style", record.get("final_subgenre")),
            ):
                if value is None or not str(value).strip():
                    continue
                label_id, _unused = _legacy_label_id(value, axis, document)
                confirmed.append((by_path[path], axis, label_id))
        decision_result = store.import_legacy_human_decisions(
            [
                {"item_id": item_id, "axis": axis, "label_ids": [label_id]}
                for item_id, axis, label_id in confirmed
            ]
        )
    except ValueError as exc:
        return _error(str(exc), "Could not initialise the local v2 inventory")
    return jsonify(
        {
            "count": len(saved),
            "items": saved,
            "decisions": decision_result,
            "taxonomy_revision": taxonomy["revision"],
        }
    ), 201


def _run_import_job(store, job_id: str, folder_path: str):
    """Add one folder without clearing other imported folders or decisions."""
    try:
        from app.services.scanner import SUPPORTED_EXTENSIONS, _scan_single_file

        root = Path(folder_path).expanduser().resolve(strict=True)
        excluded_roots = [_write_backup_root(store).resolve(strict=False)]
        for destination in store.export_destinations():
            try:
                excluded_roots.append(
                    Path(destination).expanduser().resolve(strict=False)
                )
            except OSError:
                continue

        def excluded(path: Path) -> bool:
            try:
                resolved = path.resolve(strict=False)
                return any(
                    resolved == blocked or blocked in resolved.parents
                    for blocked in excluded_roots
                )
            except OSError:
                return False

        for directory, _dirs, filenames in os.walk(root):
            directory_path = Path(directory)
            # Prune whole owned-copy/backup trees before walking their files.
            _dirs[:] = [name for name in _dirs if not excluded(directory_path / name)]
            if excluded(directory_path):
                continue
            for filename in sorted(filenames):
                if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                state = (store.job(job_id) or {}).get("state")
                if state in {"pausing", "cancelling"}:
                    _finish_stopped_job(store, job_id)
                    return
                path = str(Path(directory) / filename)
                track = _scan_single_file(path, filename, Path(filename).suffix.lower())
                original = track.to_dict()
                # A root is weak import provenance only. It cannot silently
                # become a genre label or rewrite raw Genre/COMM observations.
                original["import_root"] = str(root)
                saved = store.upsert_item(
                    path=path,
                    original=original,
                    source_revision=_source_revision(track),
                    availability="present" if os.path.isfile(path) else "missing",
                    conflict=bool(track.error),
                )
                store.append_job_item(job_id, saved["id"])
                store.update_job_item(job_id, saved["id"], "running")
                store.update_job_item(
                    job_id,
                    saved["id"],
                    "failed" if track.error else "completed",
                    error_code=track.error,
                )
        if (store.job(job_id) or {}).get("state") == "running":
            store.set_job_state(job_id, "completed")
    except Exception as exc:
        try:
            store.event(
                job_id, "job_error", {"code": "import_failed", "detail": str(exc)[:200]}
            )
            if (store.job(job_id) or {}).get("state") == "running":
                store.set_job_state(job_id, "interrupted")
        except Exception:
            pass
    finally:
        with _workers_lock:
            _workers.discard(job_id)


def _start_import_worker(store, job_id: str, folder_path: str):
    with _workers_lock:
        if job_id in _workers:
            return False
        _workers.add(job_id)
    threading.Thread(
        target=_run_import_job,
        args=(store, job_id, folder_path),
        name=f"idjlm-import-{job_id[:8]}",
        daemon=True,
    ).start()
    return True


@bp.post("/library/import-jobs")
def library_import_job():
    data = _body()
    folder = data.get("folder_path")
    if not isinstance(folder, str) or not folder.strip():
        return _error("folder_path_required", "Choose a readable local music folder")
    try:
        root = Path(folder).expanduser().resolve(strict=True)
    except OSError:
        return _error("folder_not_found", "The selected folder is unavailable")
    if not root.is_dir() or not os.access(root, os.R_OK):
        return _error("folder_unreadable", "The selected folder is not readable")
    store = _v2()
    try:
        job = store.create_job("import", {"item_ids": []}, {"folder_path": str(root)})
        job = store.set_job_state(job["job_id"], "running")
        _start_import_worker(store, job["job_id"], str(root))
        return jsonify(job), 202
    except ValueError as exc:
        return _error(str(exc), "Could not begin the additive import")


@bp.get("/items/<item_id>")
def item(item_id: str):
    found = _v2().get_item(item_id)
    if not found:
        return _error("not_found", "Unknown item", 404)
    path = found.pop("path", "")
    found["audio_available"] = bool(
        path and os.path.isfile(path) and os.access(path, os.R_OK)
    )
    found["audio_url"] = (
        f"/api/v2/items/{item_id}/audio" if found["audio_available"] else None
    )
    found["raw_comments"] = _raw_comments(found.get("original") or {})
    found["managed_comment"] = _managed_comment(found.get("original") or {})
    found["managed_tokens"] = _managed_tokens(found["managed_comment"])
    return jsonify(found)


@bp.get("/items/<item_id>/audio")
def item_audio(item_id: str):
    found = _v2().get_item(item_id)
    path = found.get("path") if found else None
    mime_types = {
        ".mp3": "audio/mpeg",
        ".flac": "audio/flac",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".aiff": "audio/aiff",
        ".aif": "audio/aiff",
    }
    suffix = Path(path).suffix.lower() if path else ""
    if not path:
        return _error("not_found", "Unknown item", 404)
    if suffix not in mime_types:
        return _error(
            "unsupported_format", "No safe playback adapter for this file", 409
        )
    if not os.path.isfile(path) or not os.access(path, os.R_OK):
        return _error("missing_media", "Imported media is unavailable", 404)
    return send_file(
        path, mimetype=mime_types[suffix], conditional=True, as_attachment=False
    )


@bp.post("/reviews/previews")
def review_preview():
    data = _body()
    try:
        entries = _resolved(data)
    except ValueError as exc:
        return _error(str(exc), "Choose one or more tracks before reviewing")
    fields = data.get("fields") or ["music_family", "style"]
    if not isinstance(fields, list):
        return _error("invalid_fields", "fields must be a list")
    items = [
        {
            "item_id": entry["id"],
            "revision": entry["revision"],
            "before": {
                "genre": entry["original"].get("existing_genre"),
                "comment": entry["original"].get("existing_comment"),
            },
            "axes": {axis: entry.get("axes", {}).get(axis, {}) for axis in fields},
        }
        for entry in entries
    ]
    try:
        return jsonify(
            _v2().create_preview(
                "review",
                {
                    "items": items,
                    "fields": fields,
                    "taxonomy_revision": _v2().taxonomy(_default_taxonomy())[
                        "revision"
                    ],
                },
            )
        ), 201
    except ValueError as exc:
        return _error(str(exc), "A selected track changed; refresh the preview", 409)


@bp.post("/reviews/decisions")
def review_decisions():
    data = _body()
    preview = _v2().consume_preview(str(data.get("preview_id", "")), "review")
    if not preview:
        return _error(
            "stale_preview", "Preview expired, was used, or was not found", 409
        )
    if not _preview_is_current(preview):
        return _error(
            "stale_preview", "A track or taxonomy changed; refresh the preview", 409
        )
    _ensure_default_taxonomy()
    try:
        saved = _v2().save_decisions(preview, data.get("decisions"))
    except ValueError as exc:
        return _error(
            str(exc),
            "Review decisions could not be applied",
            409 if str(exc) == "stale_preview" else 400,
        )
    return jsonify({"saved_item_ids": saved, "count": len(saved)})


@bp.route("/taxonomy", methods=["GET", "PUT"])
def taxonomy():
    if request.method == "GET":
        return jsonify(_v2().taxonomy(_default_taxonomy()))
    data = _body()
    document = data.get("document")
    if not isinstance(document, dict) or not isinstance(document.get("labels"), list):
        return _error("invalid_taxonomy", "document.labels must be a list")
    try:
        return jsonify(
            _v2().save_taxonomy(document, int(data.get("expected_revision", 0)))
        )
    except ValueError:
        return _error("stale_taxonomy", "Reload the taxonomy before saving", 409)


@bp.route("/views", methods=["GET", "PUT"])
def views():
    if request.method == "GET":
        return jsonify({"views": _v2().views()})
    try:
        return jsonify(_v2().save_view(_body()))
    except ValueError as exc:
        return _error(str(exc), "A saved view needs a name and definition")


@bp.route("/settings", methods=["GET", "PUT"])
def settings():
    model = _model_status()
    capabilities = {
        "in_place_write_formats": ["mp3"],
        "copy_write_formats": ["mp3", "flac", "m4a", "aiff", "aif", "wav", "ogg"],
        "device_sync": False,
        "cloud_required": False,
        "model_installed": model["state"] == "installed",
    }
    if request.method == "GET":
        return jsonify(
            {"values": _v2().settings(), "capabilities": capabilities, "model": model}
        )
    values = _body().get("values")
    try:
        return jsonify(
            {"values": _v2().save_settings(values), "capabilities": capabilities}
        )
    except ValueError as exc:
        return _error(str(exc), "values must be an object")


def _run_model_install_job(store, job_id: str, action: str, model_id: str):
    try:
        from app.services.audio_classification import ModelInstaller

        installer = ModelInstaller()
        if action == "verify":
            installer.verify_installed(model_id)
        else:

            def progress(message: str):
                if (store.job(job_id) or {}).get("state") in {"pausing", "cancelling"}:
                    raise RuntimeError("model_job_cancel_requested")
                store.event(job_id, "model_progress", {"message": message})

            installer.install(model_id, progress=progress)
        _model_status(force=True)
        if (store.job(job_id) or {}).get("state") == "running":
            store.set_job_state(job_id, "completed")
    except Exception as exc:
        try:
            store.event(
                job_id,
                "job_error",
                {"code": "model_setup_failed", "detail": str(exc)[:200]},
            )
            if (store.job(job_id) or {}).get("state") in {"pausing", "cancelling"}:
                _finish_stopped_job(store, job_id)
            elif (store.job(job_id) or {}).get("state") == "running":
                store.set_job_state(job_id, "interrupted")
        except Exception:
            pass
    finally:
        with _workers_lock:
            _workers.discard(job_id)


@bp.get("/models")
def models():
    return jsonify({"model": _model_status()})


@bp.post("/models/jobs")
def model_job():
    data = _body()
    action = data.get("action")
    if action not in {"install", "repair", "verify"}:
        return _error("invalid_model_action", "Use install, repair, or verify")
    model_id = data.get("model_id", "laion-clap-htsat-unfused")
    if not isinstance(model_id, str) or not model_id:
        return _error("invalid_model", "Choose a known local model")
    if _model_status().get("state") == "runtime_unavailable":
        return _error(
            "runtime_unavailable",
            "This build does not include the local audio runtime",
            409,
        )
    store = _v2()
    try:
        job = store.create_job(
            "model_download", {"item_ids": []}, {"action": action, "model_id": model_id}
        )
        job = store.set_job_state(job["job_id"], "running")
        with _workers_lock:
            _workers.add(job["job_id"])
        threading.Thread(
            target=_run_model_install_job,
            args=(store, job["job_id"], action, model_id),
            name=f"idjlm-model-{job['job_id'][:8]}",
            daemon=True,
        ).start()
        return jsonify(job), 202
    except ValueError as exc:
        return _error(str(exc), "Could not start local model setup")


def _job_entries(store, job: dict) -> list[dict]:
    item_ids = (job.get("scope") or {}).get("item_ids") or []
    return [entry for item_id in item_ids if (entry := store.get_item(item_id))]


def _all_job_items(store, job_id: str) -> list[dict]:
    rows, cursor = [], None
    while True:
        page = store.job_items(job_id, cursor=cursor, limit=250)
        rows.extend(page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            return rows


def _finish_stopped_job(store, job_id: str):
    state = (store.job(job_id) or {}).get("state")
    if state == "pausing":
        store.set_job_state(job_id, "paused")
    elif state == "cancelling":
        for row in _all_job_items(store, job_id):
            if row["state"] == "queued":
                store.update_job_item(job_id, row["item_id"], "cancelled")
        store.set_job_state(job_id, "cancelled")


def _run_classify_job(store, job_id: str, engine=None):
    try:
        from app.services.audio_classification import AudioClassificationEngine
        from app.services.v2_job_runner import JobCancelled, run_audio_classification

        job = store.job(job_id)
        if not job:
            return
        entries = []
        status_by_id = {
            row["item_id"]: row["state"] for row in _all_job_items(store, job_id)
        }
        for entry in _job_entries(store, job):
            if status_by_id.get(entry["id"]) != "completed":
                entries.append(entry)
        if not entries:
            store.set_job_state(job_id, "completed")
            return
        # A single scheduler owns the engine at a time. Its V2 feature cache
        # uses verified decoded-audio/cache keys, not mutable tag file bytes.
        engine = engine or AudioClassificationEngine(feature_cache=store)

        def persist(payload):
            status = payload.get("status")
            # Retain every attempted result (including abstentions and decode
            # failures) so the library distinguishes analyzed-unknown from
            # never analyzed.  This never creates a decision or approval.
            store.record_analysis_outcome(payload)
            if status == "proposed" and payload.get("axes"):
                store.save_prediction(payload)
                store.update_job_item(job_id, payload["item_id"], "completed")
            elif status == "abstained":
                store.update_job_item(
                    job_id,
                    payload["item_id"],
                    "completed",
                    error_code=payload.get("reason"),
                )
            else:
                store.update_job_item(
                    job_id,
                    payload["item_id"],
                    "failed",
                    error_code=payload.get("reason"),
                )

        def progress(kind, payload):
            store.event(job_id, kind, payload)

        def should_stop():
            return (store.job(job_id) or {}).get("state") in {"pausing", "cancelling"}

        def started(item_id):
            store.update_job_item(job_id, item_id, "running")

        try:
            run_audio_classification(
                entries=entries,
                model_id=str(job["config"].get("model_id", "laion-clap-htsat-unfused")),
                engine=engine,
                persist=persist,
                progress=progress,
                should_stop=should_stop,
                started=started,
            )
        except JobCancelled:
            _finish_stopped_job(store, job_id)
            return
        if (store.job(job_id) or {}).get("state") == "running":
            store.set_job_state(job_id, "completed")
        else:
            _finish_stopped_job(store, job_id)
    except Exception as exc:
        try:
            store.event(
                job_id,
                "job_error",
                {"code": "classification_worker_failed", "detail": str(exc)[:200]},
            )
            if (store.job(job_id) or {}).get("state") == "running":
                store.set_job_state(job_id, "interrupted")
        except Exception:
            pass
    finally:
        with _workers_lock:
            _workers.discard(job_id)


def _classify_scheduler_loop():
    while True:
        store, job_id = _classify_queue.get()
        try:
            key = id(store)
            engine = _audio_engines.get(key)
            if engine is None:
                from app.services.audio_classification import AudioClassificationEngine

                engine = AudioClassificationEngine(feature_cache=store)
                _audio_engines[key] = engine
            _run_classify_job(store, job_id, engine)
        except Exception as exc:
            try:
                store.event(
                    job_id,
                    "job_error",
                    {
                        "code": "classification_scheduler_failed",
                        "detail": str(exc)[:200],
                    },
                )
                if (store.job(job_id) or {}).get("state") == "running":
                    store.set_job_state(job_id, "interrupted")
            except Exception:
                pass
            with _workers_lock:
                _workers.discard(job_id)
        finally:
            _classify_queue.task_done()


def _start_classify_worker(job_id: str, store=None):
    """Queue at most one resident audio model worker for this process."""
    global _classify_scheduler
    store = store or _v2()
    with _workers_lock:
        if job_id in _workers:
            return False
        _workers.add(job_id)
        if _classify_scheduler is None or not _classify_scheduler.is_alive():
            _classify_scheduler = threading.Thread(
                target=_classify_scheduler_loop,
                name="idjlm-audio-scheduler",
                daemon=True,
            )
            _classify_scheduler.start()
        _classify_queue.put((store, job_id))
    return True


@bp.route("/jobs", methods=["GET", "POST"])
def jobs():
    if request.method == "GET":
        try:
            return jsonify(
                _v2().list_jobs(
                    cursor=request.args.get("cursor"),
                    limit=request.args.get("limit", 100),
                )
            )
        except (ValueError, AttributeError) as exc:
            return _error("jobs_unavailable", str(exc), 503)
    data = _body()
    if data.get("kind") != "classify":
        return _error(
            "unsupported_job",
            "Only local audio classification jobs are available from v2 today",
            409,
        )
    try:
        source_job_id = data.get("source_job_id")
        if source_job_id:
            source = _v2().job(str(source_job_id))
            if not source or source["kind"] != "import":
                return _error(
                    "invalid_source_job",
                    "source_job_id must name a completed import job",
                )
            entries = []
            for row in _all_job_items(_v2(), str(source_job_id)):
                if row["state"] == "completed" and (
                    entry := _v2().get_item(row["item_id"])
                ):
                    entries.append(entry)
            if not entries:
                return _error(
                    "empty_scope", "That import job has no completed tracks to classify"
                )
        else:
            entries = _resolved(data)
        job = _v2().create_job(
            "classify",
            {"item_ids": [entry["id"] for entry in entries]},
            {
                "model_id": data.get("model_id", "laion-clap-htsat-unfused"),
                "axes": data.get("axes") or ["music_family"],
            },
        )
        job = _v2().set_job_state(job["job_id"], "running")
        _start_classify_worker(job["job_id"])
        return jsonify(job), 202
    except ValueError as exc:
        return _error(
            str(exc), "Choose a non-empty valid scope before starting classification"
        )


@bp.get("/jobs/<job_id>")
def job(job_id: str):
    found = _v2().job(job_id)
    return (jsonify(found), 200) if found else _error("not_found", "Unknown job", 404)


@bp.get("/jobs/<job_id>/items")
def job_items(job_id: str):
    if not _v2().job(job_id):
        return _error("not_found", "Unknown job", 404)
    try:
        return jsonify(
            _v2().job_items(
                job_id, request.args.get("cursor"), request.args.get("limit", 100)
            )
        )
    except ValueError:
        return _error("invalid_cursor", "Invalid job item cursor")


@bp.post("/jobs/<job_id>/<action>")
def job_action(job_id: str, action: str):
    state = {"pause": "pausing", "resume": "running", "cancel": "cancelling"}.get(
        action
    )
    if not state:
        return _error("invalid_action", "Use pause, resume, or cancel")
    current = _v2().job(job_id)
    if not current:
        return _error("not_found", "Unknown job", 404)
    if action == "resume" and current["kind"] not in {
        "classify",
        "import",
        "write",
        "export",
    }:
        return _error(
            "resume_unavailable",
            "This job cannot safely resume after interruption",
            409,
        )
    updated = _v2().set_job_state(job_id, state)
    if not updated:
        return _error("invalid_state", "Job cannot take that action now", 409)
    if action == "resume":
        store = _v2()
        if updated["kind"] == "classify":
            _start_classify_worker(job_id, store)
        elif updated["kind"] == "import":
            _start_import_worker(
                store, job_id, str(updated["config"].get("folder_path", ""))
            )
        elif updated["kind"] == "write" and isinstance(
            updated["config"].get("preview"), dict
        ):
            _start_write_worker(job_id, updated["config"]["preview"], store)
        elif updated["kind"] == "export":
            export = store.export(str(updated["config"].get("export_id", "")))
            if export:
                _start_export_worker(
                    job_id,
                    export["export_id"],
                    export["manifest"],
                    bool(updated["config"].get("replace_known")),
                    store,
                )
            else:
                store.set_job_state(job_id, "interrupted")
                return _error(
                    "resume_unavailable", "Export manifest is unavailable", 409
                )
    return jsonify(updated), 202


@bp.get("/jobs/<job_id>/events")
def job_events(job_id: str):
    if not _v2().job(job_id):
        return _error("not_found", "Unknown job", 404)
    try:
        after = int(
            request.headers.get("Last-Event-ID", request.args.get("after", "0")) or 0
        )
    except ValueError:
        return _error("invalid_cursor", "Last-Event-ID must be numeric")
    events = _v2().events(job_id, after, 250)
    stream = "".join(
        f"id: {event['sequence']}\nevent: progress\ndata: {json.dumps(event)}\n\n"
        for event in events
    )
    return Response(stream, mimetype="text/event-stream")


@bp.post("/writes/previews")
def write_preview():
    data = _body()
    selected = data.get("fields") or ["genre", "comment"]
    if not isinstance(selected, list) or not set(selected).issubset(
        {"genre", "comment"}
    ):
        return _error(
            "unsupported_field",
            "Only Genre and owned Comment are writable in-place today",
        )
    overrides = data.get("field_overrides") or {}
    default_override = data.get("default_override") or {}
    if not isinstance(overrides, dict) or not isinstance(default_override, dict):
        return _error(
            "invalid_overrides",
            "Overrides must be objects keyed by item ID or shared default_override",
        )
    try:
        entries = _resolved(data)
        items = []
        for entry in entries:
            path = entry["path"]
            override = dict(default_override)
            override.update(overrides.get(entry["id"]) or {})
            fields, provenance = _write_fields(entry, selected, override)
            status = "ready"
            before_sha = None
            if not os.path.isfile(path):
                status = "missing_media"
            elif Path(path).suffix.lower() != ".mp3":
                status = "unsupported_format"
            else:
                from app.services.safe_tag_writer import sha256_file

                before_sha = sha256_file(path)
            items.append(
                {
                    "item_id": entry["id"],
                    "revision": entry["revision"],
                    "path": path,
                    "status": status,
                    "before_sha256": before_sha,
                    "fields": {
                        key: {
                            "before": entry["original"].get(f"existing_{key}"),
                            "after": value,
                        }
                        for key, value in fields.items()
                    },
                    "provenance": provenance,
                }
            )
        backup_root = _write_backup_root(_v2())
        storage = _write_storage_preflight(items, backup_root)
        return jsonify(
            _v2().create_preview(
                "write",
                {
                    "items": items,
                    "fields": selected,
                    "storage": storage,
                    "taxonomy_revision": _v2().taxonomy(_default_taxonomy())[
                        "revision"
                    ],
                },
            )
        ), 201
    except ValueError as exc:
        return _error(str(exc), "Could not prepare this write preview")


def _run_write_job(store, job_id: str, preview: dict):
    try:
        from app.services.v2_write_ops import commit_mp3_write
        import uuid

        root = str(_write_backup_root(store))
        states = {row["item_id"]: row["state"] for row in _all_job_items(store, job_id)}
        for record in preview["items"]:
            if states.get(record["item_id"]) == "completed":
                continue
            if (store.job(job_id) or {}).get("state") in {"pausing", "cancelling"}:
                _finish_stopped_job(store, job_id)
                return
            item_id = record["item_id"]
            if record["status"] != "ready":
                store.update_job_item(
                    job_id, item_id, "failed", error_code=record["status"]
                )
                continue
            write_id = str(uuid.uuid4())

            def record_intent(intent):
                store.record_write_intent(
                    write_id=write_id, item_id=item_id, intent=intent
                )

            outcome = commit_mp3_write(
                source_path=record["path"],
                expected_sha256=record["before_sha256"],
                fields={key: value["after"] for key, value in record["fields"].items()},
                backup_root=root,
                write_id=write_id,
                record_intent=record_intent,
            )
            if outcome.get("backup_path"):
                stored = store.finalize_write_intent(
                    write_id=write_id, item_id=item_id, outcome=outcome
                )
                outcome["ledger_write_id"] = stored["write_id"]
            if outcome["status"] == "published_verified":
                # Capture current source tags after read-back while retaining
                # the initial raw observations as provenance.
                item = store.get_item(item_id)
                prior = dict(item["original"])
                refreshed = _refresh_item_from_path(
                    store, item_id, record["path"], prior
                )
                # Keep the raw imported COMMENT intact while recording only
                # the named owned block's literal palette tokens for filters.
                latest = store.get_item(refreshed["id"])
                store.upsert_item(
                    path=record["path"],
                    item_id=item_id,
                    original=latest["original"],
                    source_revision=outcome["after_sha256"],
                    comment_tokens=_managed_tokens(
                        outcome.get("fields", {}).get("comment")
                    ),
                )
            store.update_job_item(
                job_id,
                item_id,
                "completed" if outcome["status"] == "published_verified" else "failed",
                error_code=outcome.get("error_code"),
            )
            store.event(
                job_id,
                "write_outcome",
                {
                    "item_id": item_id,
                    "status": outcome["status"],
                    "write_id": outcome.get("ledger_write_id"),
                },
            )
        if (store.job(job_id) or {}).get("state") == "running":
            store.set_job_state(job_id, "completed")
    finally:
        with _workers_lock:
            _workers.discard(job_id)


def _start_write_worker(job_id: str, preview: dict, store=None):
    store = store or _v2()
    with _workers_lock:
        if job_id in _workers:
            return False
        _workers.add(job_id)
    threading.Thread(
        target=_run_write_job,
        args=(store, job_id, preview),
        name=f"idjlm-write-{job_id[:8]}",
        daemon=True,
    ).start()
    return True


@bp.post("/writes/commit")
def write_commit():
    data = _body()
    if data.get("confirm") is not True:
        return _error(
            "confirmation_required", "Set confirm to true after reviewing the diff"
        )
    preview = _v2().consume_preview(str(data.get("preview_id", "")), "write")
    if not preview:
        return _error(
            "stale_preview", "Preview expired, was used, or was not found", 409
        )
    if not _preview_is_current(preview):
        return _error(
            "stale_preview", "A track or taxonomy changed; refresh the preview", 409
        )
    if not preview.get("storage", {}).get("enough_space"):
        return _error(
            "insufficient_space",
            "The configured backup or source filesystem lacks space for the verified write",
            409,
        )
    ids = [entry["item_id"] for entry in preview["items"]]
    job = _v2().create_job(
        "write",
        {"item_ids": ids},
        {"preview_id": data.get("preview_id"), "preview": preview},
    )
    job = _v2().set_job_state(job["job_id"], "running")
    _start_write_worker(job["job_id"], preview, _v2())
    return jsonify(job), 202


@bp.get("/writes")
def write_list():
    try:
        return jsonify(
            _v2().list_writes(
                request.args.get("cursor"), request.args.get("limit", 100)
            )
        )
    except ValueError:
        return _error("invalid_cursor", "Invalid restore history cursor")


@bp.get("/writes/<write_id>")
def write_status(write_id: str):
    found = _v2().write_record(write_id)
    return (jsonify(found), 200) if found else _error("not_found", "Unknown write", 404)


@bp.post("/restores/previews")
def restore_preview():
    data = _body()
    record = _v2().write_record(str(data.get("write_id", "")))
    if not record:
        return _error("not_found", "Unknown write", 404)
    item = _v2().get_item(record["item_id"])
    if not item:
        return _error("not_found", "Original item is unavailable", 404)
    payload = {
        "items": [
            {
                "item_id": item["id"],
                "revision": item["revision"],
                "write_id": record["write_id"],
                "source_path": record["source_path"],
                "backup_path": record["backup_path"],
                "expected_current_sha256": record["after_sha256"],
                "expected_original_sha256": record["before_sha256"],
            }
        ],
        "taxonomy_revision": _v2().taxonomy(_default_taxonomy())["revision"],
    }
    try:
        return jsonify(_v2().create_preview("restore", payload)), 201
    except ValueError as exc:
        return _error(str(exc), "Could not create restore preview")


@bp.post("/restores/commit")
def restore_commit():
    data = _body()
    if data.get("confirm") is not True:
        return _error(
            "confirmation_required", "Set confirm to true after reviewing the restore"
        )
    preview = _v2().consume_preview(str(data.get("preview_id", "")), "restore")
    if not preview:
        return _error(
            "stale_preview", "Restore preview expired, was used, or was not found", 409
        )
    if not _preview_is_current(preview):
        return _error(
            "stale_preview", "A track or taxonomy changed; refresh the preview", 409
        )
    from app.services.v2_write_ops import restore_original

    outcomes = []
    for entry in preview["items"]:
        outcome = restore_original(
            source_path=entry["source_path"],
            backup_path=entry["backup_path"],
            expected_current_sha256=entry["expected_current_sha256"],
            expected_original_sha256=entry["expected_original_sha256"],
        )
        if outcome["status"] == "restored":
            current = _v2().get_item(entry["item_id"])
            _refresh_item_from_path(
                _v2(),
                entry["item_id"],
                entry["source_path"],
                current["original"] if current else None,
            )
            _v2().record_write(
                item_id=entry["item_id"],
                source_path=entry["source_path"],
                before_sha256=outcome["before_sha256"],
                after_sha256=outcome["after_sha256"],
                backup_path=entry["backup_path"],
                fields={"restore_of": entry["write_id"]},
                status="restored",
            )
        outcomes.append({"item_id": entry["item_id"], **outcome})
    return jsonify({"outcomes": outcomes})


@bp.post("/exports/previews")
def export_preview():
    data = _body()
    destination = data.get("destination")
    if not isinstance(destination, str) or not destination.strip():
        return _error("destination_required", "Choose a local staging folder")
    profile = data.get("profile") or {"name": "broad_genre_raw_comment"}
    if not isinstance(profile, dict):
        return _error("invalid_profile", "profile must be an object")
    profile_hash = hashlib.sha256(
        json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    profile["hash"] = profile_hash
    try:
        from app.services.safe_export import preflight

        entries = _resolved(data)
        # ``safe_export.preflight`` persists a resolved root. Use the exact
        # same canonical form for ownership lookup so a later relative/symlink
        # spelling still recognizes its own staged target as changed.
        destination_root = str(Path(destination).expanduser().resolve(strict=False))
        prior = _v2().known_export_manifest(destination_root)
        labels = _label_display_map()
        raw_entries = []
        for entry in entries:
            tag_fields, tag_preview = _export_tag_fields(entry, profile, labels)
            raw_entries.append(
                {
                    "item_id": entry["id"],
                    "source_path": entry["path"],
                    "metadata_revision": json.dumps(
                        entry.get("revisions", {}), sort_keys=True
                    ),
                    "profile_hash": profile_hash,
                    "tag_fields": tag_fields,
                    "tag_preview": tag_preview,
                }
            )
        report = preflight(destination, raw_entries, prior)
        items = [
            {"item_id": entry["id"], "revision": entry["revision"]} for entry in entries
        ]
        return jsonify(
            _v2().create_preview(
                "export",
                {
                    "items": items,
                    "profile": profile,
                    "route": data.get("route", "direct_cable"),
                    "report": report,
                    "taxonomy_revision": _v2().taxonomy(_default_taxonomy())[
                        "revision"
                    ],
                },
            )
        ), 201
    except ValueError as exc:
        return _error(str(exc), "Could not prepare this export")
    except Exception as exc:
        # Safe-export validation is an expected local preflight outcome, not a
        # server fault.  Import lazily with the exporter above so base installs
        # can still open the library without optional format dependencies.
        from app.services.safe_export import SafeExportError

        if isinstance(exc, SafeExportError):
            messages = {
                "destination_contains_source": (
                    "Choose a staging folder outside the source music folders"
                ),
                "destination_not_directory": "Choose a folder for staged copies",
                "invalid_tag_fields": "Refresh the export preview before continuing",
                "invalid_target_path": "Choose a valid local staging folder",
            }
            return _error(str(exc), messages.get(str(exc), "Could not prepare this export"))
        raise


def _run_export_job(
    store, job_id: str, export_id: str, manifest: list[dict], replace_known: bool
):
    try:
        from app.services.safe_export import copy_manifest

        states = {row["item_id"]: row["state"] for row in _all_job_items(store, job_id)}
        for entry in manifest:
            if states.get(entry["item_id"]) == "completed":
                continue
            if (store.job(job_id) or {}).get("state") in {"pausing", "cancelling"}:
                _finish_stopped_job(store, job_id)
                return
            row = copy_manifest([entry], replace_known=replace_known)[0]
            # Manifest output ownership and durable job completion are one
            # SQLite checkpoint. A pause/crash after this point can resume
            # without copying or losing this already-published file.
            store.checkpoint_export_item(export_id, job_id, row)
            states[entry["item_id"]] = (
                "completed" if row["status"] in {"copied", "unchanged"} else "failed"
            )
        outcomes = (store.export(export_id) or {}).get("manifest", [])
        state = (
            "Prepared"
            if all(row["status"] in {"copied", "unchanged"} for row in outcomes)
            else "Failed"
        )
        store.update_export(export_id, state, outcomes)
        if (store.job(job_id) or {}).get("state") == "running":
            store.set_job_state(job_id, "completed")
    finally:
        with _workers_lock:
            _workers.discard(job_id)


def _start_export_worker(
    job_id: str, export_id: str, manifest: list[dict], replace_known: bool, store=None
):
    store = store or _v2()
    with _workers_lock:
        if job_id in _workers:
            return False
        _workers.add(job_id)
    threading.Thread(
        target=_run_export_job,
        args=(store, job_id, export_id, manifest, replace_known),
        name=f"idjlm-export-{job_id[:8]}",
        daemon=True,
    ).start()
    return True


@bp.post("/exports/commit")
def export_commit():
    data = _body()
    if data.get("confirm") is not True:
        return _error(
            "confirmation_required", "Set confirm to true after reviewing the export"
        )
    preview = _v2().consume_preview(str(data.get("preview_id", "")), "export")
    if not preview:
        return _error(
            "stale_preview", "Export preview expired, was used, or was not found", 409
        )
    if not _preview_is_current(preview):
        return _error(
            "stale_preview", "A track or taxonomy changed; refresh the preview", 409
        )
    report = preview["report"]
    if not report.get("enough_space"):
        return _error(
            "insufficient_space",
            "The selected staging folder does not have enough free space",
            409,
        )
    exported = _v2().create_export(
        preview["profile"], report["destination"], preview["route"], report["manifest"]
    )
    job = _v2().create_job(
        "export",
        {"item_ids": [entry["item_id"] for entry in preview["items"]]},
        {
            "export_id": exported["export_id"],
            "preview_id": data.get("preview_id"),
            "replace_known": bool(data.get("replace_known")),
        },
    )
    job = _v2().set_job_state(job["job_id"], "running")
    _start_export_worker(
        job["job_id"],
        exported["export_id"],
        report["manifest"],
        bool(data.get("replace_known")),
        _v2(),
    )
    return jsonify({"job": job, "export": exported}), 202


@bp.get("/exports/<export_id>")
def export_status(export_id: str):
    found = _v2().export(export_id)
    return (
        (jsonify(found), 200) if found else _error("not_found", "Unknown export", 404)
    )


@bp.post("/exports/<export_id>/transfer")
def export_transfer(export_id: str):
    data = _body()
    state = data.get("state")
    allowed = {
        "Transferred (user-confirmed)",
        "Transfer unverified",
        "Verified in djay",
    }
    if state not in allowed:
        return _error(
            "invalid_transfer_state", "Choose a truthful external transfer state"
        )
    evidence = data.get("evidence")
    if state == "Verified in djay" and (
        not isinstance(evidence, str) or not evidence.strip()
    ):
        return _error(
            "verification_evidence_required", "Record what was verified in djay"
        )
    export = _v2().export(export_id)
    if not export:
        return _error("not_found", "Unknown export", 404)
    manifest = list(export["manifest"])
    manifest.append(
        {
            "transfer_state": state,
            "evidence": evidence if isinstance(evidence, str) else None,
        }
    )
    return jsonify(_v2().update_export(export_id, state, manifest))
