"""Phase G (#214): incremental import must reach the watch-folder inbox.

G.2 shipped scan_folder_incremental() but only /api/import used it. The two
watch-folder entrypoints still bypassed it:

  * /api/watch/start called the full scan_folder(), re-reading tags, re-hashing
    and re-fingerprinting every file already in the store.
  * /api/watch/poll hand-rolled its Track objects and never set file_mtime /
    file_size, so an inbox track looked "changed" to every later incremental
    scan — the inbox silently defeated incremental import.

These pin both, plus the stale-path hazard in watch/start.
"""
import os
import tempfile

import pytest

from app import create_app, get_track_store, set_track_store
from app.services.track_store import TrackStore
from app.services.watcher import WatcherState


@pytest.fixture
def isolated_client(tmp_path):
    """App + test client backed by an empty, throwaway TrackStore."""
    original_store = get_track_store()
    app = create_app()
    app.config["TESTING"] = True
    store = TrackStore(db_path=str(tmp_path / "tracks.db"))
    set_track_store(store)
    try:
        yield app.test_client(), store
    finally:
        set_track_store(original_store)
        WatcherState.new_files = []


def _make_audio(folder, name="track.mp3", content="fake audio bytes"):
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / name
    f.write_text(content)
    return str(f)


class TestWatchPollFeedsIncrementalImport:
    """The regression that actually mattered: inbox tracks defeating G.2."""

    def test_polled_track_is_seen_as_unchanged_by_later_incremental_scan(
        self, isolated_client, tmp_path, monkeypatch
    ):
        client, store = isolated_client
        music = tmp_path / "music"
        path = _make_audio(music)

        # Simulate the watcher detecting the file, then poll it into the store.
        WatcherState.new_files = [path]
        resp = client.get("/api/watch/poll")
        assert resp.status_code == 200
        assert len(resp.get_json()["tracks"]) == 1
        assert path in store

        # A later incremental scan of that folder must REUSE the polled track,
        # not rescan it. Before the fix, file_mtime was None => always "changed".
        #
        # Reuse is asserted by spying on the expensive path rather than by
        # object identity: a TrackStore returns a fresh wrapper on every read,
        # so `scanned is store[path]` is False even on a correct reuse.
        from app.services import scanner

        calls = []
        real_scan_single = scanner._scan_single_file
        monkeypatch.setattr(
            scanner,
            "_scan_single_file",
            lambda fp, fn, sfx: (calls.append(fp), real_scan_single(fp, fn, sfx))[1],
        )

        tracks, stale, unchanged = scanner.scan_folder_incremental(str(music), store)

        assert len(tracks) == 1
        assert stale == []
        assert calls == [], "polled track was re-scanned, not reused"
        assert unchanged == {path}

    def test_poll_stamps_mtime_and_size(self, isolated_client, tmp_path):
        client, store = isolated_client
        path = _make_audio(tmp_path / "music")

        WatcherState.new_files = [path]
        assert client.get("/api/watch/poll").status_code == 200

        track = store[path]
        st = os.stat(path)
        assert track.file_mtime == st.st_mtime
        assert track.file_size == st.st_size


class TestWatchStartIsIncremental:
    def test_second_start_skips_unchanged_files(self, isolated_client, tmp_path):
        client, store = isolated_client
        music = tmp_path / "music"
        _make_audio(music, "a.mp3")
        _make_audio(music, "b.mp3", content="different bytes")

        first = client.post("/api/watch/start", json={"folder_path": str(music)})
        assert first.status_code == 200
        assert first.get_json()["existing_tracks_added"] == 2

        # Nothing changed on disk — a re-start must reuse both, add none.
        second = client.post("/api/watch/start", json={"folder_path": str(music)})
        assert second.status_code == 200
        body = second.get_json()
        assert body["existing_tracks_added"] == 0
        assert body["skipped"] == 2

    def test_start_does_not_evict_tracks_outside_the_watched_folder(
        self, isolated_client, tmp_path
    ):
        """scan_folder_incremental reports every store path outside folder_path
        as stale. The track store is global, so acting on that here would delete
        the imported library whenever a subfolder is watched. watch/start must
        stay add-only.
        """
        client, store = isolated_client

        library = tmp_path / "library"
        library_track = _make_audio(library, "library.mp3")
        inbox = tmp_path / "inbox"
        _make_audio(inbox, "new.mp3", content="inbox bytes")

        # Seed the store with the library (canonical import path).
        assert client.post(
            "/api/import", json={"folder_path": str(library)}
        ).status_code == 200
        assert library_track in store

        # Now watch an unrelated folder. The library must survive.
        assert client.post(
            "/api/watch/start", json={"folder_path": str(inbox)}
        ).status_code == 200

        assert library_track in store, "watching another folder evicted the library"
        assert len(store) == 2


class TestReimportAgainstRealTrackStore:
    """The production store is a TrackStore (app/__init__.py), not a dict.

    G.2's incremental import reused Track objects out of the store and then
    wrote every one of them straight back. Against a plain dict that is a
    harmless no-op, which is all the original tests exercised. Against a real
    TrackStore, `.get()` returns a _PersistingTrack wrapper and `__setitem__`
    rejects it — so the SECOND import of any folder returned HTTP 500 and
    incremental import was dead on arrival in the shipped app.
    """

    def test_second_import_does_not_500(self, isolated_client, tmp_path):
        client, store = isolated_client
        music = tmp_path / "music"
        _make_audio(music, "a.mp3")

        assert client.post(
            "/api/import", json={"folder_path": str(music)}
        ).status_code == 200

        second = client.post("/api/import", json={"folder_path": str(music)})
        assert second.status_code == 200, second.get_json()
        assert second.get_json()["count"] == 1


class TestImportReportsSkipped:
    def test_reimport_reports_skipped_count(self, isolated_client, tmp_path):
        client, store = isolated_client
        music = tmp_path / "music"
        _make_audio(music, "a.mp3")
        _make_audio(music, "b.mp3", content="other bytes")

        first = client.post("/api/import", json={"folder_path": str(music)}).get_json()
        assert first["count"] == 2
        assert first["scanned"] == 2
        assert first["skipped"] == 0

        # Re-import with nothing changed: every track is skipped.
        second = client.post("/api/import", json={"folder_path": str(music)}).get_json()
        assert second["count"] == 2
        assert second["skipped"] == 2
        assert second["scanned"] == 0
        assert second["stale_removed"] == 0

    def test_touching_one_file_rescans_only_that_file(self, isolated_client, tmp_path):
        client, store = isolated_client
        music = tmp_path / "music"
        a = _make_audio(music, "a.mp3")
        _make_audio(music, "b.mp3", content="other bytes")

        client.post("/api/import", json={"folder_path": str(music)})

        # Change one file's content (and therefore its size + mtime).
        with open(a, "w") as f:
            f.write("mutated audio bytes, definitely a different length")

        body = client.post("/api/import", json={"folder_path": str(music)}).get_json()
        assert body["scanned"] == 1, "only the touched file should be re-scanned"
        assert body["skipped"] == 1
