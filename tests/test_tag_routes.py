"""Tests for custom tags backend (TXXX read/write + tag CRUD/filter API)."""
import json
import os
import tempfile
from unittest import mock

import pytest
from mutagen.id3 import ID3, TXXX
from mutagen.mp3 import MP3

from app.models.track import Track
from app.services.tag_writer import write_tags


# ---------------------------------------------------------------------------
# Track model: custom_tags field
# ---------------------------------------------------------------------------
class TestTrackCustomTags:
    def test_custom_tags_default_empty(self):
        track = Track(file_path="/dummy.mp3", filename="dummy.mp3")
        assert track.custom_tags == {}

    def test_custom_tags_init(self):
        track = Track(
            file_path="/dummy.mp3", filename="dummy.mp3",
            custom_tags={"MyTag": "MyValue", "Key2": "Val2"}
        )
        assert track.custom_tags == {"MyTag": "MyValue", "Key2": "Val2"}

    def test_custom_tags_in_to_dict(self):
        track = Track(
            file_path="/dummy.mp3", filename="dummy.mp3",
            custom_tags={"Color": "Red"}
        )
        d = track.to_dict()
        assert "custom_tags" in d
        assert d["custom_tags"] == {"Color": "Red"}


# ---------------------------------------------------------------------------
# Tag CRUD API
# ---------------------------------------------------------------------------
class TestTagCRUDRoutes:
    """Test the dedicated tag CRUD endpoints (app/routes/tag_routes.py)."""

    @pytest.fixture(autouse=True)
    def _seed_tracks(self, app):
        """Add tracks with custom tags to the in-memory store.
        Uses relative paths (no leading /) to avoid Flask URL encoding issues."""
        from app import get_track_store
        store = get_track_store()
        store.clear()
        store["path/a.mp3"] = Track(
            file_path="path/a.mp3", filename="a.mp3",
            custom_tags={"GenreTag": "Salsa", "Rating": "5"},
        )
        store["path/b.mp3"] = Track(
            file_path="path/b.mp3", filename="b.mp3",
            custom_tags={"GenreTag": "Bachata", "Rating": "4"},
        )
        store["path/c.mp3"] = Track(
            file_path="path/c.mp3", filename="c.mp3",
            custom_tags={},
        )
        store["path/d.mp3"] = Track(
            file_path="path/d.mp3", filename="d.mp3",
        )
        yield
        store.clear()

    def test_list_tag_keys(self, client):
        resp = client.get("/api/tags")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "keys" in data
        assert "counts" in data
        assert sorted(data["keys"]) == ["GenreTag", "Rating"]
        assert data["counts"]["GenreTag"] == 2
        assert data["counts"]["Rating"] == 2
        assert data["total_tracks_with_tags"] == 2

    def test_get_tracks_by_tag_key(self, client):
        resp = client.get("/api/tags/GenreTag")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 2
        assert data["key"] == "GenreTag"
        paths = {t["file_path"] for t in data["tracks"]}
        assert paths == {"path/a.mp3", "path/b.mp3"}

    def test_get_tracks_by_tag_key_value(self, client):
        resp = client.get("/api/tags/GenreTag?value=Salsa")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1
        assert data["value"] == "Salsa"
        assert data["tracks"][0]["file_path"] == "path/a.mp3"

    def test_get_tracks_by_tag_no_match(self, client):
        resp = client.get("/api/tags/NonExistent")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 0

    def test_get_track_tags(self, client):
        resp = client.get("/api/tracks/path%2Fa.mp3/tags")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["custom_tags"] == {"GenreTag": "Salsa", "Rating": "5"}

    def test_get_track_tags_not_found(self, client):
        resp = client.get("/api/tracks/path%2Fnonexist.mp3/tags")
        assert resp.status_code == 404

    def test_set_track_tag(self, client):
        resp = client.put(
            "/api/tracks/path%2Fa.mp3/tags",
            json={"key": "Mood", "value": "Energetic"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "Mood" in data["custom_tags"]
        assert data["custom_tags"]["Mood"] == "Energetic"

    def test_set_track_tag_bulk(self, client):
        resp = client.put(
            "/api/tracks/path%2Fa.mp3/tags",
            json={"tags": {"TagA": "A", "TagB": "B"}}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["custom_tags"]["TagA"] == "A"
        assert data["custom_tags"]["TagB"] == "B"

    def test_set_track_tag_remove_by_empty_value(self, client):
        resp = client.put(
            "/api/tracks/path%2Fa.mp3/tags",
            json={"key": "Rating", "value": ""}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "Rating" not in data["custom_tags"]

    def test_set_track_tag_not_found(self, client):
        resp = client.put(
            "/api/tracks/path%2Fnonexist.mp3/tags",
            json={"key": "X", "value": "Y"}
        )
        assert resp.status_code == 404

    def test_set_track_tag_missing_body(self, client):
        resp = client.put(
            "/api/tracks/path%2Fa.mp3/tags",
            json={}
        )
        assert resp.status_code == 400

    def test_delete_track_tag(self, client):
        resp = client.delete("/api/tracks/path%2Fa.mp3/tags/Rating")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "Rating" not in data["custom_tags"]
        assert data["removed"] == "Rating"

    def test_delete_track_tag_not_found_track(self, client):
        resp = client.delete("/api/tracks/path%2Fnope.mp3/tags/X")
        assert resp.status_code == 404

    def test_delete_track_tag_not_found_key(self, client):
        resp = client.delete("/api/tracks/path%2Fa.mp3/tags/Nope")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tag filter on GET /api/tracks
# ---------------------------------------------------------------------------
class TestTagFilterOnList:
    @pytest.fixture(autouse=True)
    def _seed(self, app):
        from app import get_track_store
        store = get_track_store()
        store.clear()
        store["p/a.mp3"] = Track(
            file_path="p/a.mp3", filename="a.mp3",
            custom_tags={"Mood": "Happy", "BPMTag": "120"},
        )
        store["p/b.mp3"] = Track(
            file_path="p/b.mp3", filename="b.mp3",
            custom_tags={"Mood": "Sad", "BPMTag": "80"},
        )
        store["p/c.mp3"] = Track(
            file_path="p/c.mp3", filename="c.mp3",
            custom_tags={},
        )
        yield
        store.clear()

    def test_filter_by_tag_key(self, client):
        resp = client.get("/api/tracks?tag_key=Mood")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 2
        paths = {t["file_path"] for t in data["tracks"]}
        assert paths == {"p/a.mp3", "p/b.mp3"}

    def test_filter_by_tag_key_value(self, client):
        resp = client.get("/api/tracks?tag_key=Mood&tag_value=Happy")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["tracks"][0]["file_path"] == "p/a.mp3"

    def test_filter_by_tag_no_match(self, client):
        resp = client.get("/api/tracks?tag_key=Mood&tag_value=Unknown")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 0

    def test_filter_by_tag_key_no_tag(self, client):
        resp = client.get("/api/tracks?tag_key=NonExistent")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 0


# ---------------------------------------------------------------------------
# Search includes custom_tags values
# ---------------------------------------------------------------------------
class TestTagSearch:
    @pytest.fixture(autouse=True)
    def _seed(self, app):
        from app import get_track_store
        store = get_track_store()
        store.clear()
        store["p/a.mp3"] = Track(
            file_path="p/a.mp3", filename="a.mp3",
            existing_title="Song A",
            custom_tags={"Mood": "Euphoric", "MyTag": "Salsa2024"},
        )
        store["p/b.mp3"] = Track(
            file_path="p/b.mp3", filename="b.mp3",
            existing_title="Song B",
        )
        yield
        store.clear()

    def test_search_custom_tag_value(self, client):
        resp = client.get("/api/tracks/search?q=Euphoric")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1
        assert data["tracks"][0]["file_path"] == "p/a.mp3"

    def test_search_custom_tag_value_partial(self, client):
        resp = client.get("/api/tracks/search?q=Salsa")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1
        assert data["tracks"][0]["file_path"] == "p/a.mp3"


# ---------------------------------------------------------------------------
# TXXX read/write via scanner + tag_writer (with real temp MP3 files)
# ---------------------------------------------------------------------------
class TestTXXXReadWrite:
    @pytest.fixture(scope="session")
    def _test_mp3_base(self):
        """Create a minimal valid MP3 file once per session using ffmpeg."""
        import subprocess
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        # Generate 0.5s of silence at 44100Hz, mono, 128kbps
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-t", "0.5", "-b:a", "128k", path],
            capture_output=True, check=True
        )
        yield path
        try:
            os.unlink(path)
        except OSError:
            pass

    @pytest.fixture
    def temp_mp3(self, _test_mp3_base):
        """Add custom TXXX frames to the base MP3 file (copy so each test gets fresh copy)."""
        import shutil
        from mutagen.id3 import ID3, TIT2, TPE1, TXXX

        path = _test_mp3_base + ".test.mp3"
        shutil.copy2(_test_mp3_base, path)

        try:
            audio = MP3(path, ID3=ID3)

            audio.tags["TIT2"] = TIT2(encoding=3, text=["Test Title"])
            audio.tags["TPE1"] = TPE1(encoding=3, text=["Test Artist"])
            audio.tags["TXXX:MyTag"] = TXXX(encoding=3, desc="MyTag", text=["MyValue"])
            audio.tags["TXXX:Rating"] = TXXX(encoding=3, desc="Rating", text=["5"])
            audio.tags["TXXX:INITIALKEY"] = TXXX(encoding=3, desc="INITIALKEY", text=["8B"])

            audio.save(v2_version=4)

            yield path
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_scanner_reads_txxx(self, temp_mp3):
        from app.services.scanner import _read_id3_tags
        tags = _read_id3_tags(temp_mp3)
        assert "custom_tags" in tags
        assert tags["custom_tags"]["MyTag"] == "MyValue"
        assert tags["custom_tags"]["Rating"] == "5"
        # INITIALKEY should be excluded from custom_tags (managed internally)
        assert "INITIALKEY" not in tags["custom_tags"]

    def test_scanner_reads_standard_tags(self, temp_mp3):
        from app.services.scanner import _read_id3_tags
        tags = _read_id3_tags(temp_mp3)
        assert tags["title"] == "Test Title"
        assert tags["artist"] == "Test Artist"

    def test_scanner_builds_track_with_custom_tags(self, temp_mp3):
        from app.services.scanner import scan_folder
        # Use a dedicated directory so we only scan our test file
        folder = os.path.dirname(temp_mp3)
        # Filter to only files with our suffix to avoid picking up unrelated files
        tracks = [t for t in scan_folder(folder) if t.file_path == temp_mp3]
        assert len(tracks) > 0
        track = tracks[0]
        assert track.custom_tags.get("MyTag") == "MyValue"
        assert track.custom_tags.get("Rating") == "5"

    def test_tag_writer_writes_txxx(self, temp_mp3):
        track = Track(
            file_path=temp_mp3,
            filename=os.path.basename(temp_mp3),
            custom_tags={"Mood": "Happy", "BPMTag": "120"},
        )
        write_tags(track)
        assert track.tags_written is True

        # Verify by re-reading
        audio = MP3(temp_mp3, ID3=ID3)
        mood_frame = audio.tags.get("TXXX:Mood")
        assert mood_frame is not None
        assert str(mood_frame.text[0]) == "Happy"

        bpm_frame = audio.tags.get("TXXX:BPMTag")
        assert bpm_frame is not None
        assert str(bpm_frame.text[0]) == "120"

    def test_tag_writer_removes_stale_txxx(self, temp_mp3):
        """When a custom tag is removed from the track, its TXXX frame should be deleted."""
        # First write with some tags
        track = Track(
            file_path=temp_mp3,
            filename=os.path.basename(temp_mp3),
            custom_tags={"KeepTag": "KeepValue", "RemoveTag": "RemoveValue"},
        )
        write_tags(track)
        assert track.tags_written is True

        # Now remove RemoveTag and write again
        track.custom_tags.pop("RemoveTag")
        write_tags(track)

        # Verify RemoveTag TXXX is gone
        audio = MP3(temp_mp3, ID3=ID3)
        assert audio.tags.get("TXXX:KeepTag") is not None
        assert audio.tags.get("TXXX:RemoveTag") is None


# ---------------------------------------------------------------------------
# Session serialization includes custom_tags
# ---------------------------------------------------------------------------
class TestTagSessionRoundtrip:
    def test_session_save_load_custom_tags(self, app, tmp_path):
        from app import get_track_store
        store = get_track_store()
        store.clear()
        track = Track(
            file_path="test/song.mp3", filename="song.mp3",
            custom_tags={"Mood": "Chill", "Era": "2020s"},
        )
        store["test/song.mp3"] = track

        from app.services.session_service import save_session, load_session
        from unittest.mock import patch

        session_path = str(tmp_path / "session.json")
        with patch("app.services.session_service.SESSION_FILE", session_path):
            save_session(store)
            loaded_store, meta = load_session()

        assert loaded_store is not None
        loaded = loaded_store["test/song.mp3"]
        assert loaded.custom_tags == {"Mood": "Chill", "Era": "2020s"}
        assert loaded.file_path == "test/song.mp3"
