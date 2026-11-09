from pathlib import Path
import shutil
import subprocess

import pytest
from app.services.safe_tag_writer import sha256_file
from app.services.v2_write_ops import (
    commit_mp3_write,
    reconcile_pending_writes,
    restore_original,
)
from app.services.v2_store import V2Store


def test_write_requires_matching_preview_checksum_before_backup(tmp_path):
    source = tmp_path / "one.mp3"
    source.write_bytes(b"before")
    calls = []
    result = commit_mp3_write(
        source_path=str(source),
        expected_sha256="wrong",
        fields={"genre": "Salsa"},
        backup_root=str(tmp_path / "backups"),
        backup=lambda *args: calls.append(args),
        writer=lambda *_: {},
    )
    assert result["status"] == "conflict"
    assert not calls


def test_write_records_verified_backup_then_restore_is_checksum_guarded(tmp_path):
    source = tmp_path / "one.mp3"
    source.write_bytes(b"before")
    before = sha256_file(source)

    def fake_writer(path, fields):
        Path(path).write_bytes(b"after")
        return dict(fields)

    identity = lambda _path: {
        "decoded_pcm_sha256": "same",
        "sample_rate_hz": 44_100,
        "channels": 2,
        "decoded_frames": 1,
    }
    intents = []
    result = commit_mp3_write(
        source_path=str(source),
        expected_sha256=before,
        fields={"genre": "Salsa"},
        backup_root=str(tmp_path / "backups"),
        writer=fake_writer,
        audio_identity=identity,
        record_intent=intents.append,
    )
    assert result["status"] == "published_verified"
    assert Path(result["backup_path"]).read_bytes() == b"before"
    assert intents[0]["source_sha256"] == before
    assert ".idjlm-pending.mp3" in intents[0]["temporary_path"]

    restored = restore_original(
        source_path=str(source),
        backup_path=result["backup_path"],
        expected_current_sha256=result["after_sha256"],
        expected_original_sha256=before,
    )
    assert restored["status"] == "restored"
    assert source.read_bytes() == b"before"


def test_pre_publish_failure_never_changes_source_bytes(tmp_path):
    source = tmp_path / "one.mp3"
    source.write_bytes(b"before")
    before = sha256_file(source)

    def broken_writer(path, _fields):
        Path(path).write_bytes(b"broken-temp")
        raise RuntimeError("cannot read back")

    result = commit_mp3_write(
        source_path=str(source),
        expected_sha256=before,
        fields={"genre": "Salsa"},
        backup_root=str(tmp_path / "backups"),
        writer=broken_writer,
        audio_identity=lambda _path: {"pcm": "same"},
    )

    assert result["status"] == "failed"
    assert source.read_bytes() == b"before"
    assert not list(tmp_path.glob(".one.*.idjlm-pending.mp3"))


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg creates disposable MP3 fixture"
)
def test_real_mp3_write_keeps_decoded_pcm_and_publishes_only_after_intent(tmp_path):
    source = tmp_path / "one.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100:duration=0.25",
            "-c:a",
            "libmp3lame",
            str(source),
        ],
        check=True,
    )
    before = sha256_file(source)
    intents = []

    result = commit_mp3_write(
        source_path=str(source),
        expected_sha256=before,
        fields={"genre": "Salsa", "comment": "Salsa"},
        backup_root=str(tmp_path / "backups"),
        record_intent=intents.append,
    )

    assert result["status"] == "published_verified"
    assert result["before_sha256"] != result["after_sha256"]
    assert result["source_audio_identity"] == result["staged_audio_identity"]
    assert intents[0]["backup_path"] == result["backup_path"]


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg creates disposable MP3 fixture"
)
def test_restart_reconciles_published_intent_without_rewriting_media(tmp_path):
    source = tmp_path / "restart.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=330:sample_rate=44100:duration=0.25",
            "-c:a",
            "libmp3lame",
            str(source),
        ],
        check=True,
    )
    store = V2Store(str(tmp_path / "state.sqlite"))
    item = store.upsert_item(path=str(source), original={"title": "Restart"})
    before = sha256_file(source)

    result = commit_mp3_write(
        source_path=str(source),
        expected_sha256=before,
        fields={"genre": "Salsa"},
        backup_root=str(tmp_path / "backups"),
        write_id="restart-write",
        record_intent=lambda intent: store.record_write_intent(
            write_id="restart-write", item_id=item["id"], intent=intent
        ),
    )
    assert result["status"] == "published_verified"
    # Simulate a process death after atomic publish and before route finalization.
    outcomes = reconcile_pending_writes(store)
    assert outcomes[0]["status"] == "written"
    assert store.write_record("restart-write")["status"] == "written"
