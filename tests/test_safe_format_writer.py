"""Round-trip checks for staging-only non-MP3 tag adapters."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen import File as MutagenFile
from mutagen.id3 import COMM, TIT2

from app.services.safe_format_writer import SafeFormatWriteError, capability_for, write_copy


FORMATS = [
    ("flac", "flac"), ("ogg", "libvorbis"), ("wav", "pcm_s16le"),
    ("aiff", "pcm_s16be"), ("m4a", "alac"),
]


def _make_tone(path: Path, codec: str) -> None:
    subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
        "sine=frequency=440:sample_rate=44100:duration=0.25", "-c:a", codec, str(path),
    ], check=True)


def _seed_unmanaged_tags(path: Path) -> None:
    audio = MutagenFile(str(path), easy=False)
    suffix = path.suffix
    if suffix in {".flac", ".ogg"}:
        audio["title"] = ["Keep title"]
        audio["comment"] = ["keep, literal", "another user comment"]
    elif suffix == ".m4a":
        audio["\xa9nam"] = ["Keep title"]
        audio["----:example.org:USER_NOTE"] = [b"keep, literal"]
    else:
        if audio.tags is None:
            audio.add_tags()
        audio.tags["TIT2"] = TIT2(encoding=3, text=["Keep title"])
        audio.tags["COMM:user:eng"] = COMM(encoding=3, lang="eng", desc="user", text=["keep, literal"])
    audio.save()


def _unmanaged_tags(path: Path):
    audio = MutagenFile(str(path), easy=False)
    suffix = path.suffix
    if suffix in {".flac", ".ogg"}:
        return tuple(audio.get("title", [])), tuple(audio.get("comment", []))
    if suffix == ".m4a":
        return tuple(audio.get("\xa9nam", [])), tuple(audio.get("----:example.org:USER_NOTE", []))
    return tuple(audio.tags["TIT2"].text), tuple(audio.tags["COMM:user:eng"].text)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required for disposable fixture decoding")
@pytest.mark.parametrize(("extension", "codec"), FORMATS)
def test_staged_copy_round_trip_preserves_unmanaged_tags_and_audio(tmp_path, extension, codec):
    source = tmp_path / f"source.{extension}"
    staged = tmp_path / f"staged.{extension}"
    _make_tone(source, codec)
    _seed_unmanaged_tags(source)
    source_bytes = source.read_bytes()
    unmanaged_before = _unmanaged_tags(source)

    result = write_copy(source, staged, {"genre": "Salsa", "comment": "Salsa Romántica"})

    assert result["status"] == "written_verified"
    assert result["verified"] is True
    assert result["fields"] == {"genre": "Salsa", "comment": "Salsa Romántica"}
    assert result["source_audio_identity"]["decoded_pcm_sha256"]
    assert source.read_bytes() == source_bytes
    staged_unmanaged = _unmanaged_tags(staged)
    # The export profile owns standard Vorbis COMMENT, while source bytes keep
    # every raw value. Other unrelated fields remain intact on the staged copy.
    if extension in {"flac", "ogg"}:
        assert staged_unmanaged[0] == unmanaged_before[0]
    else:
        assert staged_unmanaged == unmanaged_before
    reopened = MutagenFile(str(staged), easy=False)
    if extension in {"flac", "ogg"}:
        assert reopened["comment"] == ["Salsa Romántica"]
    elif extension == "m4a":
        assert reopened["\xa9cmt"] == ["Salsa Romántica"]
    else:
        assert reopened.tags["COMM::eng"].text == ["Salsa Romántica"]


def test_aac_is_explicitly_unsupported():
    capability = capability_for("song.aac")
    assert capability.status == "unsupported"
    assert "AAC" in capability.reason


def test_m4a_is_gated_when_no_local_decoder(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.safe_format_writer.shutil.which", lambda _: None)
    capability = capability_for("song.m4a")

    assert capability.status == "decoder_unavailable"
    with pytest.raises(SafeFormatWriteError, match="bundled local decoder") as error:
        write_copy(tmp_path / "source.m4a", tmp_path / "staged.m4a", {"genre": "Salsa"})
    assert error.value.code == "decoder_unavailable"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required for disposable MP3 fixture")
def test_empty_tag_value_explicitly_clears_only_the_standard_staged_field(tmp_path):
    source = tmp_path / "source.mp3"
    tagged = tmp_path / "tagged.mp3"
    cleared = tmp_path / "cleared.mp3"
    _make_tone(source, "libmp3lame")

    write_copy(source, tagged, {"genre": "Salsa", "comment": "Salsa"})
    result = write_copy(tagged, cleared, {"comment": ""})

    assert result["fields"] == {"genre": "Salsa", "comment": None}
    assert MutagenFile(str(cleared), easy=False).tags.get("COMM::eng") is None
    assert MutagenFile(str(cleared), easy=False).tags["TCON"].text == ["Salsa"]
