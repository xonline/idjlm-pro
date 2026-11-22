from pathlib import Path
import shutil
import subprocess

import pytest
from mutagen.id3 import COMM, ID3
from mutagen.mp3 import MP3

from app.services.safe_tag_writer import (
    MANAGED_COMMENT_DESC,
    MANAGED_COMMENT_LANG,
    backup_original,
    read_mp3_fields,
    sha256_file,
    write_mp3,
)


def test_backup_is_complete_byte_copy(tmp_path):
    source = tmp_path / "track.mp3"
    source.write_bytes(b"original-audio-and-tags")
    backup = Path(backup_original(str(source), str(tmp_path / "backups"), "write-1"))
    assert backup.read_bytes() == source.read_bytes()
    assert sha256_file(backup) == sha256_file(source)


def test_read_fields_rejects_non_mp3_without_mutating(tmp_path):
    source = tmp_path / "track.wav"
    source.write_bytes(b"original")
    with pytest.raises(Exception, match="unsupported_format"):
        read_mp3_fields(source, {"genre": "Salsa"})
    assert source.read_bytes() == b"original"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required for disposable MP3 fixture")
def test_explicit_empty_values_clear_owned_fields_without_touching_raw_comments(tmp_path):
    source = tmp_path / "clear-owned-fields.mp3"
    subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
        "sine=frequency=440:sample_rate=44100:duration=0.25", "-c:a", "libmp3lame", str(source),
    ], check=True)
    write_mp3(str(source), {"genre": "Salsa", "comment": "owned tag"})
    audio = MP3(str(source), ID3=ID3)
    audio.tags["COMM:user:eng"] = COMM(encoding=3, lang="eng", desc="user", text=["raw comment"])
    audio.save(v2_version=4)

    # Omitting comment retains its owned value, while an explicit empty/null
    # value removes only that managed field.
    write_mp3(str(source), {"genre": "Bachata"})
    result = write_mp3(str(source), {"genre": "", "comment": None})

    assert result == {"genre": None, "comment": None}
    reopened = MP3(str(source), ID3=ID3).tags
    assert reopened.get("TCON") is None
    assert reopened.get(f"COMM:{MANAGED_COMMENT_DESC}:{MANAGED_COMMENT_LANG}") is None
    assert reopened["COMM:user:eng"].text == ["raw comment"]
