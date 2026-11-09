"""Narrow, verified tag writer used by v2 explicit write jobs.

Only MP3 is enabled. Other scanned formats remain read/preview-only until each
format has its own round-trip evidence.  A complete original-byte backup is a
hard precondition, unlike the legacy writer.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Mapping

from mutagen.id3 import COMM, ID3, TCON
from mutagen.mp3 import MP3

MANAGED_COMMENT_DESC = "IDJLM"
MANAGED_COMMENT_LANG = "eng"


class SafeTagWriteError(RuntimeError):
    pass


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def decoded_audio_identity(path: str | Path) -> dict[str, int | str]:
    """Hash all decoded PCM before a source-file publish, without buffering it."""
    try:
        import numpy as np
        import soundfile as sf
        digest = hashlib.sha256()
        frames = 0
        with sf.SoundFile(str(path), "r") as stream:
            while True:
                block = stream.read(262_144, dtype="float32", always_2d=True)
                if len(block) == 0:
                    break
                digest.update(np.asarray(block, dtype="<f4", order="C").tobytes())
                frames += len(block)
            if not frames:
                raise ValueError("no decoded frames")
            return {"decoded_pcm_sha256": digest.hexdigest(), "sample_rate_hz": stream.samplerate,
                    "channels": stream.channels, "decoded_frames": frames, "decoder": "soundfile"}
    except Exception as exc:
        raise SafeTagWriteError("audio_identity_failed") from exc


def backup_original(source_path: str, backup_root: str, write_id: str) -> str:
    source = Path(source_path)
    target_dir = Path(backup_root) / write_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / (source.name + ".original")
    try:
        shutil.copy2(source, target)
    except OSError as exc:
        raise SafeTagWriteError("backup_failed") from exc
    if sha256_file(str(target)) != sha256_file(str(source)):
        raise SafeTagWriteError("backup_verification_failed")
    return str(target)


def _managed_comment(tags) -> str | None:
    frame = tags.get(f"COMM:{MANAGED_COMMENT_DESC}:{MANAGED_COMMENT_LANG}")
    if frame and getattr(frame, "text", None):
        return str(frame.text[0])
    return None


def read_mp3_fields(path: str | Path, fields: Mapping[str, str | None]) -> dict[str, str | None]:
    """Read only the managed MP3 fields for crash-recovery reconciliation."""
    if Path(path).suffix.lower() != ".mp3":
        raise SafeTagWriteError("unsupported_format")
    try:
        tags = MP3(str(path), ID3=ID3).tags or {}
        values = {
            "genre": str(tags.get("TCON").text[0]) if tags.get("TCON") and getattr(tags.get("TCON"), "text", None) else None,
            "comment": _managed_comment(tags),
        }
    except Exception as exc:
        raise SafeTagWriteError("readback_failed") from exc
    return {key: values.get(key) for key in fields}


def write_mp3(path: str, fields: Mapping[str, str | None]) -> dict:
    """Apply selected fields and re-read exactly those fields.

    Raw/non-managed COMM frames are never deleted or parsed.  A requested
    detailed value is written only into our named ``COMM:IDJLM:eng`` frame,
    which makes ownership and future removal unambiguous.
    """
    if Path(path).suffix.lower() != ".mp3":
        raise SafeTagWriteError("unsupported_format")
    try:
        audio = MP3(path, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
        tags = audio.tags
        if "genre" in fields and fields["genre"] is not None:
            tags["TCON"] = TCON(encoding=3, text=[str(fields["genre"])])
        if "comment" in fields and fields["comment"] is not None:
            tags[f"COMM:{MANAGED_COMMENT_DESC}:{MANAGED_COMMENT_LANG}"] = COMM(
                encoding=3, lang=MANAGED_COMMENT_LANG, desc=MANAGED_COMMENT_DESC,
                text=[str(fields["comment"])],
            )
        audio.save(v2_version=4)
    except Exception as exc:
        raise SafeTagWriteError("write_failed") from exc

    result = read_mp3_fields(path, fields)
    for key, value in fields.items():
        if value is not None and result.get(key) != str(value):
            raise SafeTagWriteError("readback_mismatch")
    return result
