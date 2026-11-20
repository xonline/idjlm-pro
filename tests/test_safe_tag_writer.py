from pathlib import Path
import pytest

from app.services.safe_tag_writer import backup_original, read_mp3_fields, sha256_file


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
