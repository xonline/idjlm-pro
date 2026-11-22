"""Revision-bound MP3 write and restore primitives for v2 routes."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from app.services.safe_tag_writer import SafeTagWriteError, backup_original, decoded_audio_identity, read_mp3_fields, sha256_file, write_mp3


class WriteConflictError(RuntimeError):
    pass


def reconcile_pending_writes(store: Any) -> list[dict]:
    """Read-only crash reconciliation for durable pre-publish write intents.

    ``store`` supplies ``unfinished_write_intents()`` and consumes each outcome
    with ``reconcile_write_intent(write_id, outcome)``. No recovery path edits
    source bytes: only the verified backup route can restore them later.
    """
    outcomes: list[dict] = []
    for intent in store.unfinished_write_intents():
        write_id = str(intent.get("write_id", ""))
        source, backup = Path(str(intent.get("source_path", ""))), Path(str(intent.get("backup_path", "")))
        before = str(intent.get("source_sha256", ""))
        outcome: dict[str, Any] = {"write_id": write_id}
        try:
            if not write_id or not source.is_file() or not backup.is_file() or sha256_file(backup) != before:
                outcome.update(status="recovery_required", error_code="backup_verification_failed")
            else:
                current = sha256_file(source)
                if current == before:
                    outcome.update(status="failed", error_code="publish_not_completed", before_sha256=before)
                elif (decoded_audio_identity(source) == intent.get("staged_audio_identity")
                      and read_mp3_fields(source, intent.get("fields") or {}) == intent.get("readback")):
                    outcome.update(status="written", before_sha256=before, after_sha256=current,
                                   source_audio_identity=intent.get("staged_audio_identity"))
                else:
                    outcome.update(status="recovery_required", error_code="publish_reconciliation_mismatch",
                                   before_sha256=before, after_sha256=current)
        except (OSError, SafeTagWriteError):
            outcome.update(status="recovery_required", error_code="reconciliation_read_failed")
        store.reconcile_write_intent(write_id, outcome)
        outcomes.append(outcome)
    return outcomes


def commit_mp3_write(
    *, source_path: str, expected_sha256: str, fields: Mapping[str, str | None], backup_root: str,
    write_id: str | None = None, backup: Callable[[str, str, str], str] = backup_original,
    writer: Callable[[str, Mapping[str, str | None]], dict] = write_mp3,
    record_intent: Callable[[dict[str, Any]], None] | None = None,
    audio_identity: Callable[[str | Path], dict] = decoded_audio_identity,
) -> dict:
    """Back up, verify a sibling temporary, then atomically publish one MP3.

    The caller persists the returned record even on failure so a verified backup
    remains discoverable after an interrupted batch.
    """
    source = Path(source_path)
    write_id = write_id or uuid.uuid4().hex
    if source.suffix.lower() != ".mp3":
        return {"write_id": write_id, "status": "unsupported_format", "error_code": "unsupported_format"}
    if not source.is_file():
        return {"write_id": write_id, "status": "missing_media", "error_code": "missing_media"}
    before = sha256_file(source)
    if before != expected_sha256:
        return {"write_id": write_id, "status": "conflict", "before_sha256": before, "error_code": "source_changed"}
    backup_path: str | None = None
    temporary = source.with_name(f".{source.stem}.{write_id}.idjlm-pending{source.suffix}")
    published = False
    try:
        source_identity = audio_identity(source)
        backup_path = backup(str(source), backup_root, write_id)
        if sha256_file(backup_path) != before:
            raise SafeTagWriteError("source_changed")
        shutil.copy2(source, temporary)
        observed = writer(str(temporary), fields)
        staged_identity = audio_identity(temporary)
        if staged_identity != source_identity:
            raise SafeTagWriteError("audio_identity_changed")
        if sha256_file(source) != before:
            raise SafeTagWriteError("source_changed")
        intent = {"write_id": write_id, "source_path": str(source), "source_sha256": before,
                  "backup_path": backup_path, "temporary_path": str(temporary), "fields": dict(fields),
                  "readback": observed, "source_audio_identity": source_identity,
                  "staged_audio_identity": staged_identity}
        if record_intent:
            record_intent(intent)
        if sha256_file(source) != before:
            raise SafeTagWriteError("source_changed")
        os.replace(temporary, source)
        published = True
        after = sha256_file(source)
        if audio_identity(source) != source_identity:
            raise SafeTagWriteError("audio_identity_changed")
        return {
            "write_id": write_id, "status": "published_verified", "before_sha256": before,
            "after_sha256": after, "backup_path": backup_path, "fields": dict(fields), "readback": observed,
            "source_audio_identity": source_identity, "staged_audio_identity": staged_identity,
        }
    except SafeTagWriteError as exc:
        return {
            "write_id": write_id, "status": "recovery_required" if published else "failed",
            "before_sha256": before, "backup_path": backup_path, "fields": dict(fields), "error_code": str(exc),
        }
    except OSError:
        return {
            "write_id": write_id, "status": "recovery_required" if published else "failed",
            "before_sha256": before, "backup_path": backup_path, "fields": dict(fields), "error_code": "write_failed",
        }
    except Exception:
        return {
            "write_id": write_id, "status": "recovery_required" if published else "failed",
            "before_sha256": before, "backup_path": backup_path, "fields": dict(fields), "error_code": "write_failed",
        }
    finally:
        if not published:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def restore_original(*, source_path: str, backup_path: str, expected_current_sha256: str, expected_original_sha256: str) -> dict:
    """Restore exact original bytes only if both ledger checks still match."""
    source, backup = Path(source_path), Path(backup_path)
    if not source.is_file() or not backup.is_file():
        return {"status": "missing_media", "error_code": "missing_media"}
    current = sha256_file(source)
    if current != expected_current_sha256:
        return {"status": "conflict", "error_code": "source_changed"}
    if sha256_file(backup) != expected_original_sha256:
        return {"status": "backup_invalid", "error_code": "backup_verification_failed"}
    temporary = source.with_name(f".{source.name}.{uuid.uuid4().hex}.restore")
    try:
        shutil.copy2(backup, temporary)
        if sha256_file(temporary) != expected_original_sha256:
            return {"status": "backup_invalid", "error_code": "backup_verification_failed"}
        os.replace(temporary, source)
        if sha256_file(source) != expected_original_sha256:
            return {"status": "recovery_required", "error_code": "restore_readback_failed"}
        return {"status": "restored", "before_sha256": current, "after_sha256": expected_original_sha256}
    except OSError:
        return {"status": "recovery_required", "error_code": "restore_failed"}
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
