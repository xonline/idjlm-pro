"""Copy-only Genre and IDJLM-comment adapters for non-MP3 containers.

The caller owns original-byte backup and any in-place replacement.  This module
only writes a newly staged copy, then verifies requested tags and decoded audio
identity. The source remains untouched; the export profile deliberately
replaces the staging copy's standard Comment while preserving unrelated fields.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from mutagen import File as MutagenFile
from mutagen.id3 import COMM, ID3, TCON
from mutagen.mp4 import MP4


class SafeFormatWriteError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class FormatCapability:
    extension: str
    status: str
    reason: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {"extension": self.extension, "status": self.status, "reason": self.reason}


_ID3_EXTENSIONS = {".mp3", ".wav", ".wave", ".aif", ".aiff"}
_VORBIS_EXTENSIONS = {".flac", ".ogg", ".oga"}
_MP4_EXTENSIONS = {".m4a", ".mp4"}
# The exported Comment is deliberately a *standard* container field.  The
# profile builder supplies its fully previewed human-readable value (including
# any preserved source text it chooses to carry forward).  Named IDJLM fields
# are not used as an interoperability claim.
_VORBIS_COMMENT_KEY = "comment"
_MP4_COMMENT_KEY = "\xa9cmt"
_ID3_COMMENT_KEY = "COMM::eng"


def _comment_storage(extension: str) -> str:
    if extension in _VORBIS_EXTENSIONS:
        return "vorbis_COMMENT"
    if extension in _MP4_EXTENSIONS:
        return "mp4_©cmt"
    return "id3_COMM_empty_description_eng"


def capability_for(path: str | Path) -> FormatCapability:
    extension = Path(path).suffix.lower()
    if extension in _ID3_EXTENSIONS | _VORBIS_EXTENSIONS:
        return FormatCapability(extension, "copy_write_supported")
    if extension in _MP4_EXTENSIONS:
        if shutil.which("ffmpeg"):
            return FormatCapability(extension, "copy_write_supported")
        return FormatCapability(extension, "decoder_unavailable", "M4A copy verification needs a bundled local decoder.")
    if extension == ".aac":
        return FormatCapability(extension, "unsupported", "Raw AAC has no safely supported tag round-trip adapter.")
    return FormatCapability(extension, "unsupported", "No safe format adapter is installed for this container.")


def _decoded_audio_identity(path: Path) -> dict[str, str]:
    """Hash decoded PCM without retaining audio in memory.

    libsndfile ships with the sidecar for FLAC/Ogg/AIFF/WAV. M4A falls back to
    a bundled decoder when one is available; it is otherwise safely gated.
    """
    try:
        import numpy as np
        import soundfile as sf
        with sf.SoundFile(str(path), "r") as stream:
            digest = hashlib.sha256()
            frames = 0
            while True:
                block = stream.read(262_144, dtype="float32", always_2d=True)
                if len(block) == 0:
                    break
                digest.update(np.asarray(block, dtype="<f4", order="C").tobytes())
                frames += len(block)
            if not frames:
                raise ValueError("decoded audio has no frames")
            return {"decoder": "soundfile", "decoded_pcm_sha256": digest.hexdigest(),
                    "sample_rate_hz": str(stream.samplerate), "channels": str(stream.channels),
                    "decoded_frames": str(frames)}
    except Exception:
        pass
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SafeFormatWriteError("decoder_unavailable", "Cannot verify staged audio without the packaged decoder.")
    command = [ffmpeg, "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0", "-acodec", "pcm_f32le", "-f", "f32le", "-"]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        raise SafeFormatWriteError("decoder_unavailable", f"Cannot start local decoder: {exc}") from exc
    assert process.stdout is not None
    digest = hashlib.sha256()
    for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
        digest.update(chunk)
    stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
    if process.wait() != 0:
        raise SafeFormatWriteError("audio_decode_failed", f"Cannot verify staged audio: {stderr.strip() or 'decoder failed'}")
    return {"decoder": "ffmpeg-pcm_f32le", "decoded_pcm_sha256": digest.hexdigest()}


def _validate_fields(fields: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(fields, Mapping):
        raise SafeFormatWriteError("invalid_fields", "Requested fields must be a mapping.")
    unexpected = set(fields) - {"genre", "comment"}
    if unexpected:
        raise SafeFormatWriteError("invalid_fields", "Unsupported fields: " + ", ".join(sorted(unexpected)))
    clean = {}
    for key, value in fields.items():
        # Exact empty is an approved clear. Omit a key to retain the value in
        # the staged source copy; whitespace-only values are invalid.
        if not isinstance(value, str) or (value != "" and not value.strip()):
            raise SafeFormatWriteError("invalid_fields", f"{key} must be a string (empty explicitly clears it).")
        clean[key] = value
    if not clean:
        raise SafeFormatWriteError("invalid_fields", "At least one managed field is required.")
    return clean


def _write_vorbis(audio: Any, fields: Mapping[str, str]) -> None:
    if audio.tags is None:
        audio.add_tags()
    if "genre" in fields:
        if fields["genre"]:
            audio["genre"] = [fields["genre"]]
        else:
            audio.pop("genre", None)
    if "comment" in fields:
        if fields["comment"]:
            audio[_VORBIS_COMMENT_KEY] = [fields["comment"]]
        else:
            audio.pop(_VORBIS_COMMENT_KEY, None)
    audio.save()


def _write_mp4(audio: MP4, fields: Mapping[str, str]) -> None:
    if audio.tags is None:
        audio.add_tags()
    if "genre" in fields:
        if fields["genre"]:
            audio["\xa9gen"] = [fields["genre"]]
        else:
            audio.pop("\xa9gen", None)
    if "comment" in fields:
        if fields["comment"]:
            audio[_MP4_COMMENT_KEY] = [fields["comment"]]
        else:
            audio.pop(_MP4_COMMENT_KEY, None)
    audio.save()


def _write_id3(audio: Any, fields: Mapping[str, str]) -> None:
    if audio.tags is None:
        audio.add_tags()
    tags: ID3 = audio.tags
    if "genre" in fields:
        if fields["genre"]:
            tags["TCON"] = TCON(encoding=3, text=[fields["genre"]])
        else:
            tags.delall("TCON")
    if "comment" in fields:
        # Standard blank-description COMM stays interoperable. Other existing
        # COMM frames (for example a user's description-specific raw comment)
        # remain on the staged copy and the source is never modified.
        if fields["comment"]:
            tags[_ID3_COMMENT_KEY] = COMM(encoding=3, lang="eng", desc="", text=[fields["comment"]])
        else:
            tags.delall(_ID3_COMMENT_KEY)
    audio.save()


def _read_managed(path: Path) -> dict[str, str | None]:
    extension = path.suffix.lower()
    audio = MutagenFile(str(path), easy=False)
    if audio is None:
        raise SafeFormatWriteError("unsupported_format", "Mutagen could not reopen the staged file.")
    if extension in _VORBIS_EXTENSIONS:
        return {
            "genre": (audio.get("genre") or [None])[0],
            "comment": (audio.get(_VORBIS_COMMENT_KEY) or [None])[0],
        }
    if extension in _MP4_EXTENSIONS:
        return {"genre": (audio.get("\xa9gen") or [None])[0],
                "comment": (audio.get(_MP4_COMMENT_KEY) or [None])[0]}
    tags = audio.tags
    genre = tags.get("TCON").text[0] if tags and tags.get("TCON") else None
    comment_frame = tags.get(_ID3_COMMENT_KEY) if tags else None
    comment = comment_frame.text[0] if comment_frame and getattr(comment_frame, "text", None) else None
    return {"genre": genre, "comment": comment}


def write_copy(source: str | Path, destination: str | Path, fields: Mapping[str, Any]) -> dict[str, Any]:
    """Create and verify a tagged staging copy without changing ``source``."""
    source_path, destination_path = Path(source), Path(destination)
    capability = capability_for(source_path)
    if capability.status != "copy_write_supported":
        code = "decoder_unavailable" if capability.status == "decoder_unavailable" else "unsupported_format"
        raise SafeFormatWriteError(code, capability.reason or "Unsupported audio format.")
    requested = _validate_fields(fields)
    if not source_path.is_file():
        raise SafeFormatWriteError("source_missing", "Source file does not exist or is not a regular file.")
    if source_path.resolve() == destination_path.resolve():
        raise SafeFormatWriteError("unsafe_destination", "Staged destination must differ from the source file.")
    if destination_path.exists():
        raise SafeFormatWriteError("destination_exists", "Staged destination already exists; it will not be overwritten.")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    original_identity = _decoded_audio_identity(source_path)
    created = False
    try:
        shutil.copy2(source_path, destination_path)
        created = True
        audio = MutagenFile(str(destination_path), easy=False)
        if audio is None:
            raise SafeFormatWriteError("unsupported_format", "Mutagen could not open the staged file.")
        extension = source_path.suffix.lower()
        if extension in _VORBIS_EXTENSIONS:
            _write_vorbis(audio, requested)
        elif extension in _MP4_EXTENSIONS:
            _write_mp4(audio, requested)
        else:
            _write_id3(audio, requested)
        verified_fields = _read_managed(destination_path)
        if any(verified_fields[key] != (None if value == "" else value) for key, value in requested.items()):
            raise SafeFormatWriteError("readback_failed", "Staged tags did not match the requested values.")
        staged_identity = _decoded_audio_identity(destination_path)
        if staged_identity != original_identity:
            raise SafeFormatWriteError("audio_identity_changed", "Tag write changed decoded audio; staged copy was rejected.")
    except SafeFormatWriteError:
        if created:
            destination_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if created:
            destination_path.unlink(missing_ok=True)
        raise SafeFormatWriteError("tag_write_failed", f"Could not write staged tags: {exc}") from exc
    return {"status": "written_verified", "verified": True, "source_audio_identity": original_identity,
            "fields": verified_fields, "destination": str(destination_path), "format": capability.extension,
            "comment_storage": _comment_storage(capability.extension) if "comment" in requested else None}
