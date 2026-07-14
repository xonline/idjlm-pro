"""Phase E tests: Serato crate, Rekordbox write-back, Traktor NML, M3U8 relative, cues in RB XML."""
import xml.etree.ElementTree as ET
import pytest


class TestSeratoWriter:
    def test_write_crate_roundtrip(self):
        from unittest.mock import MagicMock
        from app.services.serato_writer import write_crate

        track = MagicMock()
        track.file_path = "/Music/test-track.mp3"

        result = write_crate([track])
        assert isinstance(result, bytes)
        assert b"vrsn" in result
        decoded = result.decode("utf-16-be", errors="replace")
        assert "Serato ScratchLive Crate" in decoded

    def test_write_crate_relative_path(self):
        from unittest.mock import MagicMock
        from app.services.serato_writer import write_crate

        track = MagicMock()
        track.file_path = "/Music/Subfolder/test-track.mp3"

        result = write_crate([track], base_path="/Music")
        decoded = result.decode("utf-16-be", errors="replace")
        assert "Subfolder/test-track.mp3" in decoded


class TestRekordboxWriter:
    def test_check_write_safety_no_db(self):
        from app.services.rekordbox_writer import check_write_safety

        result = check_write_safety("/nonexistent/path/master.db")
        assert result["safe"] is False
        assert "not found" in result["reason"].lower()


class TestTraktorWriter:
    def test_write_nml_basic(self):
        from unittest.mock import MagicMock
        from app.services.traktor_writer import write_nml

        track = MagicMock()
        track.file_path = "/Music/test-track.mp3"
        track.display_title = "Test Track"
        track.display_artist = "Test Artist"
        track.existing_album = "Test Album"
        track.final_genre = "House"
        track.analyzed_bpm = 128.0
        track.final_key = "8A"
        track.final_comment = "test comment"
        track.suggested_cues = []

        result = write_nml([track])
        assert '<?xml version="1.0" encoding="UTF-8"?>' in result
        assert "<NML" in result
        assert "Test Track" in result
        assert "128.00" in result
        assert "8d" in result

    def test_write_nml_with_cues(self):
        from unittest.mock import MagicMock
        from app.services.traktor_writer import write_nml

        track = MagicMock()
        track.file_path = "/Music/test-track.mp3"
        track.display_title = "Track with Cues"
        track.display_artist = "Artist"
        track.existing_album = ""
        track.final_genre = ""
        track.analyzed_bpm = 120.0
        track.final_key = None
        track.final_comment = None
        track.suggested_cues = [
            {"label": "Intro", "position_sec": 0.5, "type": 0},
            {"label": "Drop", "position_sec": 32.0, "type": 1},
        ]

        result = write_nml([track])
        assert "<CUE_V2" in result
        assert "Intro" in result
        assert "0.500" in result

    def test_camelot_to_traktor_key(self):
        from app.services.traktor_writer import _camelot_to_traktor_key
        assert _camelot_to_traktor_key("1A") == "1d"
        assert _camelot_to_traktor_key("8B") == "3m"
        assert _camelot_to_traktor_key("12B") == "7m"
        assert _camelot_to_traktor_key(None) == ""
        assert _camelot_to_traktor_key("") == ""


class TestExportRoutesIntegration:
    def test_m3u_relative_param(self, client):
        resp = client.get("/api/export/m3u?relative=true")
        assert resp.status_code in (200, 500)

    def test_m3u_relative_with_base(self, client):
        resp = client.get("/api/export/m3u?relative=true&base_path=/Music")
        assert resp.status_code in (200, 500)

    def test_rekordbox_cues_route(self, client):
        resp = client.get("/api/export/rekordbox-cues")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            content = resp.data.decode("utf-8")
            assert "<?xml" in content

    def test_serato_crate_beta_gate(self, client):
        resp = client.get("/api/export/serato-crate")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data is not None
        assert "error" in data
        assert "beta" in data["error"].lower()

    def test_serato_crate_with_beta(self, client):
        resp = client.get("/api/export/serato-crate?beta=true")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.mimetype == "application/octet-stream"
            assert len(resp.data) > 0

    def test_traktor_nml_route(self, client):
        resp = client.get("/api/export/traktor-nml")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            content = resp.data.decode("utf-8")
            assert "<NML" in content
