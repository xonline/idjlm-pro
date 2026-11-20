"""Local staging-copy helpers for the v2 export workflow.

The helpers deliberately do not know about iPads or djay. They prepare a
verifiable local folder only; a later user action can report transfer or
in-app verification without this code pretending either occurred.
"""
from __future__ import annotations

import hashlib
import errno
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.services.safe_format_writer import SafeFormatWriteError, capability_for, write_copy


# A tagged staging copy can grow slightly. Each approved value is capped below,
# and this covers container tag overhead plus filesystem allocation variance.
_COPY_RESERVE_BYTES = 64 * 1024
_MAX_TAG_VALUE_BYTES = 16 * 1024


class SafeExportError(RuntimeError):
    """A copy could not safely be planned or completed."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[\\/\x00]", "_", name).strip()
    return cleaned or "untitled"


def target_name(source_path: str, item_id: str) -> str:
    """Stable staging location, independent of export order or selected subset."""
    return str(Path("media") / _safe_name(item_id) / _safe_name(Path(source_path).name))


def destination_is_safe(destination: str | Path, sources: Iterable[str | Path]) -> Path:
    """Reject a staging root that would contain any source audio file."""
    root = Path(destination).expanduser().resolve(strict=False)
    if root.exists() and not root.is_dir():
        raise SafeExportError("destination_not_directory")
    for source_value in sources:
        source = Path(source_value).resolve(strict=False)
        try:
            source.relative_to(root)
        except ValueError:
            continue
        raise SafeExportError("destination_contains_source")
    return root


def _within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _revision(entry: dict) -> dict:
    """Only values that alter a staged result participate in incrementality."""
    return {
        "source_sha256": entry["source_sha256"],
        "audio_identity": entry.get("audio_identity"),
        "metadata_revision": entry.get("metadata_revision"),
        "profile_hash": entry.get("profile_hash"),
        "tag_fields": entry.get("tag_fields"),
    }


def _approved_tag_fields(entry: Mapping[str, Any]) -> dict[str, str] | None:
    """Return the profile's explicit standard fields, without inventing tags."""
    fields = entry.get("tag_fields")
    if fields is None:
        return None
    if not isinstance(fields, Mapping) or not fields:
        raise SafeExportError("invalid_tag_fields")
    if set(fields) - {"genre", "comment"}:
        raise SafeExportError("invalid_tag_fields")
    if any(not isinstance(value, str) or (value != "" and not value.strip()) or len(value.encode("utf-8")) > _MAX_TAG_VALUE_BYTES
           for value in fields.values()):
        raise SafeExportError("invalid_tag_fields")
    return dict(fields)


def preflight(destination: str | Path, entries: list[dict], previous_manifest: Iterable[dict] = ()) -> dict:
    """Build a local-only incremental manifest and space estimate.

    A target is reusable only when its verified output checksum, source/audio
    identity, metadata revision and export profile all match a prior manifest.
    An unrelated destination file is a conflict; it is never overwritten.
    """
    source_paths = [entry["source_path"] for entry in entries if entry.get("source_path")]
    root = destination_is_safe(destination, source_paths)
    previous = {str(row.get("item_id")): row for row in previous_manifest if row.get("item_id")}
    manifest: list[dict] = []
    media_bytes = 0
    reserve_bytes = 0
    for entry in entries:
        item_id = str(entry["item_id"])
        source = Path(entry["source_path"])
        if not source.is_file():
            manifest.append({"item_id": item_id, "source_path": str(source), "status": "missing_media"})
            continue
        source_sha = sha256_file(source)
        current = dict(entry, source_sha256=source_sha)
        try:
            tag_fields = _approved_tag_fields(entry)
        except SafeExportError:
            manifest.append({"item_id": item_id, "source_path": str(source), "status": "invalid_tag_fields"})
            continue
        relative = target_name(str(source), item_id)
        target = root / relative
        record = {
            "item_id": item_id,
            "source_path": str(source),
            "source_sha256": source_sha,
            "audio_identity": entry.get("audio_identity"),
            "metadata_revision": entry.get("metadata_revision"),
            "profile_hash": entry.get("profile_hash"),
            "target_path": str(target),
            "relative_path": relative,
            "bytes": source.stat().st_size,
            "status": "new",
        }
        if tag_fields:
            capability = capability_for(source)
            record["tag_fields"] = tag_fields
            record["write_capability"] = capability.as_dict()
            # A profile cannot be honestly previewed as writable when its
            # adapter/decoder is absent. Keep its reason in the manifest rather
            # than attempting a byte-only copy without the approved labels.
            if capability.status != "copy_write_supported":
                record["status"] = "write_unsupported"
        if not _within(root, target):
            raise SafeExportError("invalid_target_path")
        old = previous.get(item_id)
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_file() or not old:
                record["status"] = "destination_conflict"
            else:
                actual = sha256_file(target)
                if actual != old.get("output_sha256"):
                    record["status"] = "destination_conflict"
                elif _revision(current) == {key: old.get(key) for key in _revision(current)}:
                    record["status"] = "unchanged"
                    record["output_sha256"] = actual
                    for key in ("source_audio_identity", "verified_fields", "comment_storage"):
                        if key in old:
                            record[key] = old[key]
                else:
                    # A known prior output may be deliberately replaced by a
                    # later commit. Preflight keeps that distinction explicit.
                    record["status"] = "changed"
                    record["previous_output_sha256"] = actual
        if record["status"] == "new":
            # New copies are published as a hard link from the verified temp;
            # only one data copy is present at peak.
            media_bytes += record["bytes"]
            reserve_bytes += _COPY_RESERVE_BYTES
        elif record["status"] == "changed":
            # Replacement keeps a verified owned backup while a full temporary
            # result exists, so the peak is two file copies.
            media_bytes += 2 * record["bytes"]
            reserve_bytes += _COPY_RESERVE_BYTES
        manifest.append(record)
    usage = shutil.disk_usage(root if root.exists() else root.parent)
    required_bytes = media_bytes + reserve_bytes
    return {
        "destination": str(root), "manifest": manifest, "source_count": len(entries),
        "copy_count": sum(1 for row in manifest if row["status"] in {"new", "changed"}),
        "missing_count": sum(1 for row in manifest if row["status"] == "missing_media"),
        "write_unsupported_count": sum(1 for row in manifest if row["status"] == "write_unsupported"),
        "conflict_count": sum(1 for row in manifest if row["status"] == "destination_conflict"),
        "bytes_to_copy": required_bytes, "media_bytes": media_bytes, "reserve_bytes": reserve_bytes,
        "free_bytes": usage.free, "enough_space": usage.free >= required_bytes,
    }


def _copy_to_temporary(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.partial")
    try:
        with source.open("rb") as src, temporary.open("xb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
            dst.flush()
            os.fsync(dst.fileno())
        shutil.copystat(source, temporary)
        return temporary
    except Exception as exc:
        # This file was created by this invocation and has never been
        # published, so cleanup does not discard user-owned material.
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise SafeExportError("copy_failed") from exc


def _publish_no_clobber(temporary: Path, target: Path, root: Path) -> None:
    """Publish a new target atomically without replacing an existing file."""
    if not _within(root, target) or target.exists() or target.is_symlink():
        raise SafeExportError("destination_conflict")
    try:
        # Both paths share a directory, so link is atomic and fails if another
        # process created the target after the check. It also avoids `replace`.
        os.link(temporary, target)
    except FileExistsError as exc:
        raise SafeExportError("destination_conflict") from exc
    except OSError as exc:
        # exFAT/FAT volumes have no hard links. Preserve no-overwrite behavior
        # with an exclusive target create, verified bytes, and cleanup of only
        # this invocation's partial target.
        if exc.errno not in {errno.EPERM, errno.EOPNOTSUPP, errno.EXDEV}:
            raise SafeExportError("copy_publish_failed") from exc
        created = False
        published = False
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created = True
            with temporary.open("rb") as src, os.fdopen(descriptor, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            if sha256_file(target) != sha256_file(temporary):
                raise SafeExportError("copy_verification_failed")
            published = True
        except FileExistsError as fallback_exc:
            raise SafeExportError("destination_conflict") from fallback_exc
        except OSError as fallback_exc:
            raise SafeExportError("copy_publish_failed") from fallback_exc
        finally:
            if created and not published:
                try:
                    target.unlink(missing_ok=True)
                except OSError:
                    pass
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _backup_known_target(target: Path, root: Path, item_id: str, expected_sha256: str) -> Path:
    """Keep a verified copy of an owned staged target before replacement."""
    if target.is_symlink() or not target.is_file() or sha256_file(target) != expected_sha256:
        raise SafeExportError("destination_conflict")
    backup = root / ".idjlm-export-backups" / item_id / f"{target.name}.{uuid.uuid4().hex}.before"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup)
    if sha256_file(backup) != expected_sha256:
        raise SafeExportError("replacement_backup_failed")
    return backup


def _replace_known_target(temporary: Path, target: Path, root: Path, entry: dict) -> str:
    """Replace only a manifest-owned target whose exact old bytes still exist."""
    expected = entry.get("previous_output_sha256")
    if not expected or not _within(root, target):
        raise SafeExportError("destination_conflict")
    backup = _backup_known_target(target, root, str(entry["item_id"]), expected)
    # Verify again immediately before publication; the staging folder is local
    # but another process can still alter its target between preview and commit.
    if target.is_symlink() or not target.is_file() or sha256_file(target) != expected:
        raise SafeExportError("destination_conflict")
    try:
        os.replace(temporary, target)
    except OSError as exc:
        raise SafeExportError("copy_publish_failed") from exc
    return str(backup)


def copy_manifest(manifest: list[dict], *, replace_known: bool = False) -> list[dict]:
    """Copy a preview manifest with explicit, guarded replacement support.

    New files use no-clobber publication. A changed file is replaced only when
    the caller explicitly confirms replacement and the current target still
    equals the previewed manifest checksum; a full owned-target backup is kept.
    """
    result: list[dict] = []
    for entry in manifest:
        outcome = dict(entry)
        if entry.get("status") in {"unchanged", "missing_media", "destination_conflict", "write_unsupported", "invalid_tag_fields"}:
            result.append(outcome)
            continue
        if entry.get("status") == "changed" and not replace_known:
            outcome["status"] = "replacement_required"
            result.append(outcome)
            continue
        if entry.get("status") not in {"new", "changed"}:
            outcome["status"] = "invalid_manifest"
            result.append(outcome)
            continue
        source, target = Path(entry["source_path"]), Path(entry["target_path"])
        try:
            root = target.parents[2]  # <staging>/media/<item-id>/<filename>
            if not source.is_file() or sha256_file(source) != entry.get("source_sha256"):
                outcome["status"] = "stale_source"
            elif entry["status"] == "new" and (target.exists() or target.is_symlink() or not _within(root, target)):
                outcome["status"] = "destination_conflict"
            else:
                tag_fields = entry.get("tag_fields")
                if tag_fields:
                    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.partial")
                    write_result = write_copy(source, temporary, tag_fields)
                    outcome["source_audio_identity"] = write_result["source_audio_identity"]
                    outcome["verified_fields"] = write_result["fields"]
                    outcome["comment_storage"] = write_result.get("comment_storage")
                else:
                    temporary = _copy_to_temporary(source, target)

                output_sha = sha256_file(temporary)
                if entry["status"] == "changed":
                    outcome["replacement_backup_path"] = _replace_known_target(temporary, target, root, entry)
                    if sha256_file(target) != output_sha:
                        outcome["status"] = "copy_verification_failed"
                    else:
                        outcome["status"] = "copied"
                        outcome["output_sha256"] = output_sha
                else:
                    _publish_no_clobber(temporary, target, root)
                    outcome["status"] = "copied"
                    outcome["output_sha256"] = output_sha
        except SafeFormatWriteError as exc:
            outcome["status"] = exc.code
        except SafeExportError as exc:
            outcome["status"] = str(exc)
        except OSError:
            outcome["status"] = "copy_failed"
        result.append(outcome)
    return result
