from pathlib import Path
import shutil
import subprocess
from collections import namedtuple

import pytest

from app.services.safe_export import SafeExportError, copy_manifest, preflight


def test_preflight_is_incremental_with_stable_paths_and_no_overwrite(tmp_path):
    source = tmp_path / "source" / "one.mp3"
    source.parent.mkdir()
    source.write_bytes(b"audio-one")
    destination = tmp_path / "staging"
    entry = {"item_id": "item_one", "source_path": str(source), "metadata_revision": "one", "profile_hash": "profile-a"}

    initial = preflight(destination, [entry])
    assert initial["copy_count"] == 1
    copied = copy_manifest(initial["manifest"])
    assert copied[0]["status"] == "copied"
    assert copied[0]["relative_path"] == "media/item_one/one.mp3"

    unchanged = preflight(destination, [entry], copied)
    assert unchanged["manifest"][0]["status"] == "unchanged"

    changed = preflight(destination, [{**entry, "metadata_revision": "two"}], copied)
    assert changed["manifest"][0]["status"] == "changed"
    assert copy_manifest(changed["manifest"])[0]["status"] == "replacement_required"
    replaced = copy_manifest(changed["manifest"], replace_known=True)
    assert replaced[0]["status"] == "copied"
    assert Path(replaced[0]["replacement_backup_path"]).is_file()

    target = Path(replaced[0]["target_path"])
    target.write_bytes(b"not the source")
    conflict = preflight(destination, [entry], replaced)
    assert conflict["manifest"][0]["status"] == "destination_conflict"


def test_preflight_rejects_destination_containing_source(tmp_path):
    source = tmp_path / "music" / "one.mp3"
    source.parent.mkdir()
    source.write_bytes(b"audio")

    with pytest.raises(SafeExportError, match="destination_contains_source"):
        preflight(source.parent, [{"item_id": "item_one", "source_path": str(source)}])


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required for disposable MP3 fixture")
def test_tagged_staged_copy_has_verified_output_hash_and_decoded_identity(tmp_path):
    source = tmp_path / "source" / "one.mp3"
    source.parent.mkdir()
    subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
        "sine=frequency=440:sample_rate=44100:duration=0.25", "-c:a", "libmp3lame", str(source),
    ], check=True)
    original = source.read_bytes()
    entry = {
        "item_id": "item_one", "source_path": str(source), "metadata_revision": "one",
        "profile_hash": "profile-a", "tag_fields": {"genre": "Salsa", "comment": "Source note | Salsa"},
    }

    plan = preflight(tmp_path / "staging", [entry])
    assert plan["manifest"][0]["write_capability"]["status"] == "copy_write_supported"
    copied = copy_manifest(plan["manifest"])

    outcome = copied[0]
    assert outcome["status"] == "copied"
    assert outcome["output_sha256"] != outcome["source_sha256"]
    assert outcome["verified_fields"] == entry["tag_fields"]
    assert outcome["source_audio_identity"]["decoded_pcm_sha256"]
    assert outcome["comment_storage"] == "id3_COMM_empty_description_eng"
    assert source.read_bytes() == original
    assert preflight(tmp_path / "staging", [entry], copied)["manifest"][0]["status"] == "unchanged"

    profile_only = {**entry, "profile_hash": "profile-b"}
    changed_plan = preflight(tmp_path / "staging", [profile_only], copied)
    assert changed_plan["manifest"][0]["status"] == "changed"
    changed = copy_manifest(changed_plan["manifest"], replace_known=True)[0]
    assert changed["status"] == "copied"
    assert Path(changed["replacement_backup_path"]).is_file()
    assert changed["verified_fields"] == profile_only["tag_fields"]
    assert changed["source_audio_identity"] == outcome["source_audio_identity"]

    changed_entry = {**profile_only, "tag_fields": {"genre": "Salsa", "comment": "Source note | Salsa Dura"}}
    decision_plan = preflight(tmp_path / "staging", [changed_entry], [changed])
    assert decision_plan["manifest"][0]["status"] == "changed"
    decision = copy_manifest(decision_plan["manifest"], replace_known=True)[0]
    assert decision["verified_fields"] == changed_entry["tag_fields"]
    assert decision["output_sha256"] != changed["output_sha256"]


def test_preflight_does_not_offer_a_tagged_raw_aac_copy(tmp_path):
    source = tmp_path / "source.aac"
    source.write_bytes(b"not-a-real-aac")

    plan = preflight(tmp_path / "staging", [{
        "item_id": "item_one", "source_path": str(source),
        "tag_fields": {"genre": "Salsa"},
    }])

    assert plan["manifest"][0]["status"] == "write_unsupported"
    assert plan["manifest"][0]["write_capability"]["status"] == "unsupported"


def test_changed_preflight_reserves_backup_and_temporary_space(tmp_path, monkeypatch):
    source = tmp_path / "source.mp3"
    source.write_bytes(b"audio" * 10)
    destination = tmp_path / "staging"
    entry = {"item_id": "item_one", "source_path": str(source), "metadata_revision": "one", "profile_hash": "a"}
    first = preflight(destination, [entry])
    copied = copy_manifest(first["manifest"])

    # Make the existing output manifest-owned, then ask for a changed profile.
    changed_entry = {**entry, "profile_hash": "b"}
    normal = preflight(destination, [changed_entry], copied)
    required = normal["bytes_to_copy"]
    DiskUsage = namedtuple("DiskUsage", "total used free")
    monkeypatch.setattr("app.services.safe_export.shutil.disk_usage", lambda _path: DiskUsage(required, 0, required - 1))
    constrained = preflight(destination, [changed_entry], copied)

    assert constrained["manifest"][0]["status"] == "changed"
    assert constrained["media_bytes"] == 2 * source.stat().st_size
    assert constrained["reserve_bytes"] >= 64 * 1024
    assert constrained["enough_space"] is False
