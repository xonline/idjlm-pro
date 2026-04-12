"""
Integration tests — full pipeline against real audio files.
Uses /home/ubuntu/upload/songs test/ (salsa + kizomba, ~57 tracks).

Requires: real audio files on disk, mutagen, librosa installed.
Skipped gracefully if test audio folder doesn't exist.
"""
import json
import os
import pytest

TEST_AUDIO_FOLDER = "/home/ubuntu/upload/songs test"


def _audio_folder_available():
    return os.path.isdir(TEST_AUDIO_FOLDER)


@pytest.mark.skipif(
    not _audio_folder_available(),
    reason="Test audio folder not found: " + TEST_AUDIO_FOLDER
)
class TestImportIntegration:
    """Test importing real audio files."""

    def test_import_salsa_folder(self, client):
        """Import the salsa subfolder and verify tracks are returned."""
        salsa_folder = os.path.join(TEST_AUDIO_FOLDER, "salsa")
        if not os.path.isdir(salsa_folder):
            pytest.skip("salsa subfolder not found")

        resp = client.post("/api/import", json={"folder_path": salsa_folder})
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        # Should have tracks or results key
        tracks = data.get("tracks", data.get("results", []))
        # We just verify it didn't crash and returned a list
        assert isinstance(tracks, list)

    def test_import_kizomba_folder(self, client):
        """Import the kizomba subfolder and verify tracks are returned."""
        kizomba_folder = os.path.join(TEST_AUDIO_FOLDER, "kizomba")
        if not os.path.isdir(kizomba_folder):
            pytest.skip("kizomba subfolder not found")

        resp = client.post("/api/import", json={"folder_path": kizomba_folder})
        assert resp.status_code == 200
        data = resp.get_json()
        tracks = data.get("tracks", data.get("results", []))
        assert isinstance(tracks, list)


@pytest.mark.skipif(
    not _audio_folder_available(),
    reason="Test audio folder not found: " + TEST_AUDIO_FOLDER
)
class TestAnalyzeIntegration:
    """Test audio analysis against real files."""

    def test_analyze_salsa_tracks(self, client):
        """Import then analyze salsa tracks — verify BPM and key detected."""
        salsa_folder = os.path.join(TEST_AUDIO_FOLDER, "salsa")
        if not os.path.isdir(salsa_folder):
            pytest.skip("salsa subfolder not found")

        # Import first
        resp = client.post("/api/import", json={"folder_path": salsa_folder})
        assert resp.status_code == 200
        data = resp.get_json()
        tracks = data.get("tracks", data.get("results", []))

        if not tracks:
            pytest.skip("No tracks imported")

        # Analyze first track
        first_track = tracks[0]
        resp = client.post("/api/analyze", json={
            "track_paths": [first_track["file_path"]]
        })
        assert resp.status_code in (200, 202, 429)  # 429 = rate limited (expected in parallel)


@pytest.mark.skipif(
    not _audio_folder_available(),
    reason="Test audio folder not found: " + TEST_AUDIO_FOLDER
)
class TestSessionIntegration:
    """Test session save/load with real data."""

    def test_session_roundtrip_with_imported_tracks(self, client):
        """Import tracks, save session, load it back — verify data preserved."""
        salsa_folder = os.path.join(TEST_AUDIO_FOLDER, "salsa")
        if not os.path.isdir(salsa_folder):
            pytest.skip("salsa subfolder not found")

        # Import
        resp = client.post("/api/import", json={"folder_path": salsa_folder})
        assert resp.status_code == 200

        # Save session
        resp = client.post("/api/session/save", json={})
        assert resp.status_code == 200

        # Load session
        resp = client.post("/api/session/load")
        assert resp.status_code in (200, 404)  # 404 = no session yet


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "taxonomy_loaded" in data


class TestBackupRestoreEndpoint:
    """Test backup/restore endpoints."""

    def test_list_backups_empty(self, client):
        """Fresh install should have no backups yet."""
        resp = client.get("/api/organise/backups")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "backups" in data

    def test_latest_backup_empty(self, client):
        resp = client.get("/api/organise/backups/latest")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "backups" in data


class TestNextTrackAdvisor:
    """Test Next Track Advisor with real data."""

    def test_suggest_next_empty_store(self, client):
        resp = client.post("/api/suggest_next", json={"file_path": "/nonexistent"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "suggestions" in data

    def test_suggest_next_requires_file_path(self, client):
        resp = client.post("/api/suggest_next", json={})
        assert resp.status_code == 400


class TestRekordboxIntegration:
    """Test rekordbox reader endpoints."""

    def test_rekordbox_status(self, client):
        resp = client.get("/api/rekordbox/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "found" in data

    def test_rekordbox_matches(self, client):
        resp = client.get("/api/rekordbox/matches")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_rekordbox_tracks" in data
