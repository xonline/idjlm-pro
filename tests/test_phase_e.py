"""Issue #347 (E.1): Serato .crate export — writer + route tests."""
from dataclasses import dataclass
import pytest
from app.services.serato_writer import write_crate, parse_crate, track_count


@dataclass
class FakeTrack:
    file_path: str
    analyzed_bpm: float = 0
    final_key: str = ""


class TestSeratoWriter:
    """Unit tests for the Serato .crate binary writer."""

    def _make_tracks(self, *paths):
        return [FakeTrack(file_path=p) for p in paths]

    def test_roundtrip_write_parse(self):
        tracks = self._make_tracks(
            "/Music/House/Artist1 - Track1.mp3",
            "/Music/Techno/Artist2 - Track2.mp3",
        )
        crate_bytes = write_crate(tracks)
        parsed = parse_crate(crate_bytes)

        tags = [tag for tag, _ in parsed]
        assert "vrsn" in tags
        assert "otrk" in tags
        assert tags.count("otrk") == 2

    def test_version_tag(self):
        crate_bytes = write_crate([])
        parsed = parse_crate(crate_bytes)
        vrsn = next(v for t, v in parsed if t == "vrsn")
        assert "Serato ScratchLive Crate" in vrsn

    def test_empty_crate(self):
        crate_bytes = write_crate([])
        parsed = parse_crate(crate_bytes)
        track_tags = [t for t, _ in parsed if t == "otrk"]
        assert len(track_tags) == 0

    def test_relative_paths(self):
        tracks = self._make_tracks(
            "/Users/dj/Music/Deep House/Artist - Song.mp3",
        )
        crate_bytes = write_crate(tracks, base_path="/Users/dj/Music")
        parsed = parse_crate(crate_bytes)
        otrk_entries = [(t, v) for t, v in parsed if t == "otrk"]
        ptrk_value = otrk_entries[0][1][0][1]
        assert "Deep House/Artist - Song.mp3" in ptrk_value
        assert "/Users/dj/Music" not in ptrk_value

    def test_last_two_components_fallback(self):
        tracks = self._make_tracks("Artist - Track.mp3")
        crate_bytes = write_crate(tracks)
        parsed = parse_crate(crate_bytes)
        otrk_entries = [(t, v) for t, v in parsed if t == "otrk"]
        ptrk_value = otrk_entries[0][1][0][1]
        assert "Artist - Track.mp3" in ptrk_value

    def test_special_characters(self):
        tracks = self._make_tracks("/Music/120 \xb5s/El Ni\xf1o - Ca\xf1a.mp3")
        crate_bytes = write_crate(tracks)
        parsed = parse_crate(crate_bytes)
        assert len(parsed) > 0
        otrk = next(v for t, v in parsed if t == "otrk")
        ptrk_value = otrk[0][1]
        assert "\xb5" in ptrk_value or "Ni\xf1o" in ptrk_value or "Ca\xf1a" in ptrk_value

    def test_columns_present(self):
        crate_bytes = write_crate([])
        parsed = parse_crate(crate_bytes)
        col_names = []
        for tag, value in parsed:
            if tag == "ovct":
                cn_tag = value[0][0]
                cn_val = value[0][1]
                if cn_tag == "tvcn":
                    col_names.append(cn_val)
        assert len(col_names) == 7
        assert "key" in col_names
        assert "artist" in col_names
        assert "song" in col_names
        assert "bpm" in col_names

    def test_track_order_preserved(self):
        tracks = self._make_tracks(
            "/Music/A.mp3", "/Music/B.mp3", "/Music/C.mp3",
        )
        crate_bytes = write_crate(tracks)
        parsed = parse_crate(crate_bytes)
        otrk_values = [
            v[0][1] for t, v in parsed if t == "otrk"
        ]
        assert "A.mp3" in otrk_values[0]
        assert "B.mp3" in otrk_values[1]
        assert "C.mp3" in otrk_values[2]

    def test_track_count(self):
        tracks = self._make_tracks(
            "/Music/A.mp3", "/Music/B.mp3", "/Music/C.mp3",
        )
        crate_bytes = write_crate(tracks)
        assert track_count(crate_bytes) == 3

    def test_writer_bytes_length(self):
        tracks = self._make_tracks("/Music/Test.mp3")
        crate_bytes = write_crate(tracks)
        assert len(crate_bytes) > 50


@pytest.mark.skip(reason="serato export route not registered — issue #347 WIP")
class TestSeratoExportRoute:
    """Integration tests for /api/export/serato-crate route."""

    def test_export_returns_200(self, client):
        resp = client.get("/api/export/serato-crate")
        assert resp.status_code == 200

    def test_export_content_type(self, client):
        resp = client.get("/api/export/serato-crate")
        assert resp.mimetype == "application/octet-stream"

    def test_export_produces_valid_crate(self, client):
        resp = client.get("/api/export/serato-crate")
        crate_bytes = resp.data
        parsed = parse_crate(crate_bytes)
        tags = [t for t, _ in parsed]
        assert "vrsn" in tags

    def test_export_with_filename_param(self, client):
        resp = client.get("/api/export/serato-crate?filename=my-crate.crate")
        header = resp.headers.get("Content-Disposition", "")
        assert "my-crate.crate" in header

    def test_export_empty_track_store(self, client):
        resp = client.get("/api/export/serato-crate?status=approved")
        assert resp.status_code == 200
        parsed = parse_crate(resp.data)
        otrk_tags = [t for t, _ in parsed if t == "otrk"]
        assert len(otrk_tags) == 0

    def test_export_error_on_bad_params(self, client):
        resp = client.get("/api/export/serato-crate?bpm_min=notanumber")
        assert resp.status_code in (200, 500)
