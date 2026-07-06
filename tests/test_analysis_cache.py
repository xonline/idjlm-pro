"""Regression tests for B.3 analysis cache (issue #203).

Analysis cache keyed by file content hash ensures re-importing the same
library never re-analyses unchanged files — instant library reload.

Every test is synthetic (no real audio files) and tests the cache contract.
"""
import os
import pytest


class TestAnalysisCacheService:
    """AnalysisCache put/get/restore/clear contract."""

    def test_imports(self):
        from app.services.analysis_cache import (
            get, put, restore, compute_hash, clear,
            ANALYSIS_CACHE_FIELDS,
        )
        assert callable(get)
        assert callable(put)
        assert callable(restore)
        assert callable(compute_hash)
        assert callable(clear)
        assert isinstance(ANALYSIS_CACHE_FIELDS, list)

    def test_put_and_get_round_trip(self):
        from app.services.analysis_cache import get, put, clear
        from app.models.track import Track
        clear()
        t = Track(
            file_path="/test/song.mp3",
            filename="song.mp3",
            content_hash="abc123",
            analyzed_bpm=120.0,
            analyzed_key="8B",
            analyzed_energy=7,
            raw_rms=0.15,
            duration=240.0,
            bpm_corrected=False,
            bpm_confidence=85,
            key_confidence=72,
            vocal_flag="vocal",
            vocal_confidence=80,
            tempo_category="medium",
            analyzed_lufs=-12.5,
            analyzed_lufs_range=8.0,
            analyzed_true_peak=-1.2,
            waveform_data=[0.5, 0.3],
            waveform_peaks=[0.6, 0.4, 0.2],
            bpm_from_tags=False,
            analysis_done=True,
        )
        put(t)
        cached = get("abc123")
        assert cached is not None
        assert cached["analyzed_bpm"] == 120.0
        assert cached["analyzed_key"] == "8B"
        assert cached["analyzed_energy"] == 7
        assert cached["analysis_done"] is True

    def test_get_missing_hash_returns_none(self):
        from app.services.analysis_cache import get, clear
        clear()
        assert get("nonexistent") is None

    def test_get_empty_hash_returns_none(self):
        from app.services.analysis_cache import get
        assert get("") is None

    def test_restore_populates_track_fields(self):
        from app.services.analysis_cache import put, restore, clear
        from app.models.track import Track
        clear()
        t = Track(
            file_path="/cache/song.mp3",
            filename="song.mp3",
            content_hash="def456",
            analyzed_bpm=128.0,
            analyzed_key="10B",
            analyzed_energy=8,
            analysis_done=True,
        )
        put(t)

        fresh = Track(
            file_path="/cache/song.mp3",
            filename="song.mp3",
            content_hash="def456",
        )
        result = restore(fresh)
        assert result is True
        assert fresh.analyzed_bpm == 128.0
        assert fresh.analyzed_key == "10B"
        assert fresh.analyzed_energy == 8
        assert fresh.analysis_done is True

    def test_restore_no_hash_returns_false(self):
        from app.services.analysis_cache import restore
        from app.models.track import Track
        t = Track(file_path="/nohash.mp3", filename="nohash.mp3")
        assert restore(t) is False

    def test_restore_missing_hash_returns_false(self):
        from app.services.analysis_cache import restore, clear
        from app.models.track import Track
        clear()
        t = Track(
            file_path="/missing.mp3",
            filename="missing.mp3",
            content_hash="ZZZZ",
        )
        assert restore(t) is False

    def test_put_empty_hash_does_not_crash(self):
        from app.services.analysis_cache import put
        from app.models.track import Track
        t = Track(file_path="/empty.mp3", filename="empty.mp3", analyzed_bpm=100)
        put(t)

    def test_clear_empties_cache(self):
        from app.services.analysis_cache import get, put, clear
        from app.models.track import Track
        clear()
        t = Track(
            file_path="/clr.mp3",
            filename="clr.mp3",
            content_hash="clear",
            analyzed_bpm=140,
        )
        put(t)
        assert get("clear") is not None
        clear()
        assert get("clear") is None

    def test_compute_hash_for_file(self, tmp_path):
        from app.services.analysis_cache import compute_hash
        f = tmp_path / "test.mp3"
        f.write_text("fake audio content for hashing")
        h = compute_hash(str(f))
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_compute_hash_nonexistent_file_returns_empty(self):
        from app.services.analysis_cache import compute_hash
        assert compute_hash("/nonexistent/audio.mp3") == ""

    def test_analysis_saves_cache_only_on_success(self):
        from app.models.track import Track
        from app.services.analysis_cache import get, clear

        clear()
        t = Track(
            file_path="/nonexistent/for_cache.mp3",
            filename="for_cache.mp3",
            content_hash="cache_test_hash",
        )
        from app.services.analyzer import analyze_track
        result = analyze_track(t)
        assert result.error is not None

        cached = get("cache_test_hash")
        assert cached is None

    def test_analysis_early_return_on_analysis_done(self):
        from app.models.track import Track
        from app.services.analyzer import analyze_track
        from app.services.analysis_cache import clear

        clear()
        t = Track(
            file_path="/nonexistent/skip.mp3",
            filename="skip.mp3",
            content_hash="skip_hash",
            analyzed_bpm=120.0,
            analyzed_key="8B",
            analysis_done=True,
        )
        result = analyze_track(t)
        assert result.error is None
        assert result.analyzed_bpm == 120.0
        assert result.analysis_done is True


class TestScannerContentHash:
    """Scanner must compute content_hash during scan."""

    def test_scan_folder_sets_content_hash(self, tmp_path):
        from app.services.scanner import scan_folder

        mp3_dir = tmp_path / "music"
        mp3_dir.mkdir()
        f = mp3_dir / "track.mp3"
        f.write_text("fake mp3 bytes for hashing")

        tracks = scan_folder(str(mp3_dir))
        assert len(tracks) == 1
        track = tracks[0]
        assert track.content_hash is not None
        assert len(track.content_hash) == 64

    def test_content_hash_changes_when_file_changes(self, tmp_path):
        from app.services.scanner import scan_folder

        mp3_dir = tmp_path / "music2"
        mp3_dir.mkdir()
        f = mp3_dir / "track.mp3"
        f.write_text("version 1 content")

        tracks1 = scan_folder(str(mp3_dir))
        hash1 = tracks1[0].content_hash

        f.write_text("version 2 content — different")
        tracks2 = scan_folder(str(mp3_dir))
        hash2 = tracks2[0].content_hash

        assert hash1 != hash2

    def test_empty_folder_returns_empty_list(self, tmp_path):
        from app.services.scanner import scan_folder
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        assert scan_folder(str(empty_dir)) == []


class TestImportRestoresCache:
    """POST /api/import must restore cached analysis for unchanged files."""

    def test_import_restores_cached_analysis(self, client, tmp_path):
        from app.services.analysis_cache import put, clear
        from app.models.track import Track
        from app import get_track_store

        mp3_dir = tmp_path / "import_cache_test"
        mp3_dir.mkdir()
        f = mp3_dir / "track.mp3"
        f.write_text("cacheable audio content")

        clear()

        cache_track = Track(
            file_path=str(f),
            filename="track.mp3",
            content_hash="",
            analyzed_bpm=128.0,
            analyzed_key="11B",
            analyzed_energy=9,
            analysis_done=True,
        )
        from app.services.analysis_cache import compute_hash
        h = compute_hash(str(f))
        cache_track.content_hash = h
        put(cache_track)

        resp = client.post("/api/import", json={"folder_path": str(mp3_dir)})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1

        store = get_track_store()
        track = list(store.values())[0]
        assert track.analyzed_bpm == 128.0
        assert track.analyzed_key == "11B"
        assert track.analyzed_energy == 9
        assert track.analysis_done is True

    def test_import_new_file_has_no_cached_analysis(self, client, tmp_path):
        from app.services.analysis_cache import clear
        from app import get_track_store

        mp3_dir = tmp_path / "import_new_test"
        mp3_dir.mkdir()
        f = mp3_dir / "new_track.mp3"
        f.write_text("brand new content")
        clear()

        resp = client.post("/api/import", json={"folder_path": str(mp3_dir)})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1

        store = get_track_store()
        track = list(store.values())[0]
        assert track.analysis_done is False

    def test_import_partial_cache(self, client, tmp_path):
        from app.services.analysis_cache import put, clear
        from app.models.track import Track
        from app.services.analysis_cache import compute_hash
        from app import get_track_store

        mp3_dir = tmp_path / "import_partial_test"
        mp3_dir.mkdir()

        old_f = mp3_dir / "old_track.mp3"
        old_f.write_text("unchanged content")
        new_f = mp3_dir / "new_track.mp3"
        new_f.write_text("brand new content")

        clear()

        old_hash = compute_hash(str(old_f))
        cache_track = Track(
            file_path=str(old_f),
            filename="old_track.mp3",
            content_hash=old_hash,
            analyzed_bpm=100.0,
            analyzed_key="5A",
            analyzed_energy=5,
            analysis_done=True,
        )
        put(cache_track)

        resp = client.post("/api/import", json={"folder_path": str(mp3_dir)})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 2

        store = get_track_store()
        old_restored = [t for t in store.values() if "old_track" in t.filename][0]
        new_fresh = [t for t in store.values() if "new_track" in t.filename][0]

        assert old_restored.analyzed_bpm == 100.0
        assert old_restored.analysis_done is True

        assert new_fresh.analysis_done is False
        assert new_fresh.analyzed_bpm is None


class TestAnalyzeEndpointSkipsCached:
    """POST /api/analyze must skip tracks that already have analysis."""

    def test_analyze_cached_tracks_reports_progress(self, client, tmp_path):
        from app.services.analysis_cache import put, clear
        from app.models.track import Track
        from app.services.analysis_cache import compute_hash

        mp3_dir = tmp_path / "analyze_skip_test"
        mp3_dir.mkdir()
        f = mp3_dir / "cached.mp3"
        f.write_text("cached")

        clear()
        h = compute_hash(str(f))
        cache_track = Track(
            file_path=str(f),
            filename="cached.mp3",
            content_hash=h,
            analyzed_bpm=140.0,
            analyzed_key="1A",
            analyzed_energy=8,
            analysis_done=True,
        )
        put(cache_track)

        client.post("/api/import", json={"folder_path": str(mp3_dir)})
        resp = client.post("/api/analyze", json={})
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["total"] == 1
