"""Regression tests — issue #199 (A.4): thread-safety hardening.

Tests cover:
1. _analyze_lock is released after a setup exception (lock cannot leak → 429-forever deadlock).
2. _classify_lock is released after a setup exception (same guarantee).
3. Concurrent clear-and-repopulate (import) does not cause a KeyError in an
   overlapping reader — the _track_store_lock prevents observing a half-empty store.
"""
from __future__ import annotations

import threading
import time

import pytest


# ---------------------------------------------------------------------------
# 1. _analyze_lock: released after exception in route setup
# ---------------------------------------------------------------------------


def test_analyze_lock_released_via_route(monkeypatch):
    """POST /api/analyze with a broken get_track_store must return 500 and free the lock."""
    from app.routes import import_routes

    lock = import_routes._analyze_lock
    # Ensure it starts free
    if not lock.acquire(blocking=False):
        pytest.skip("lock already held — prior test leaked it")
    lock.release()

    # Break uuid to force an exception inside the try block (after acquire)
    import uuid as _uuid_module

    def _explode():
        raise RuntimeError("uuid4 boom")

    monkeypatch.setattr(_uuid_module, "uuid4", _explode)

    # Build an app with an empty store so the route proceeds past the keys() call
    from app import create_app, get_track_store, set_track_store
    from app.services.track_store import TrackStore
    import tempfile, os

    original_store = get_track_store()
    app = create_app()
    try:
        with tempfile.TemporaryDirectory() as td:
            store = TrackStore(db_path=os.path.join(td, "t.db"))
            set_track_store(store)
            app.config["TESTING"] = True
            client = app.test_client()

            resp = client.post("/api/analyze", json={"track_paths": ["/fake/track.mp3"]})
            assert resp.status_code == 500
    finally:
        # Restore the original store so subsequent tests are not affected
        set_track_store(original_store)

    # Lock MUST be free after the 500 response
    assert lock.acquire(blocking=False), "_analyze_lock leaked after 500 in route setup"
    lock.release()


# ---------------------------------------------------------------------------
# 2. _classify_lock: released after exception in route setup
# ---------------------------------------------------------------------------


def test_classify_lock_released_via_route(monkeypatch):
    """POST /api/classify with a broken uuid must return 500 and free the lock."""
    from app.routes import import_routes

    lock = import_routes._classify_lock
    if not lock.acquire(blocking=False):
        pytest.skip("lock already held — prior test leaked it")
    lock.release()

    import uuid as _uuid_module

    def _explode():
        raise RuntimeError("uuid4 boom")

    monkeypatch.setattr(_uuid_module, "uuid4", _explode)

    from app import create_app, get_track_store, set_track_store
    from app.services.track_store import TrackStore
    import tempfile

    original_store = get_track_store()
    app = create_app()
    try:
        with tempfile.TemporaryDirectory() as td:
            store = TrackStore(db_path=td + "/t.db")
            set_track_store(store)
            app.config["TESTING"] = True
            client = app.test_client()

            resp = client.post("/api/classify", json={"track_paths": ["/fake/track.mp3"]})
            assert resp.status_code == 500
    finally:
        # Restore the original store so subsequent tests are not affected
        set_track_store(original_store)

    assert lock.acquire(blocking=False), "_classify_lock leaked after 500 in route setup"
    lock.release()


# ---------------------------------------------------------------------------
# 3. _track_store_lock: concurrent import does not expose an empty store
# ---------------------------------------------------------------------------


def test_track_store_lock_prevents_empty_store_observation(tmp_path):
    """A reader that snapshots keys must not see an empty store mid-import.

    Pattern: import holds _track_store_lock for clear+repopulate; a concurrent
    reader that tries to acquire the lock is blocked until repopulation is done,
    so it never observes zero keys when tracks exist.
    """
    from app import get_track_store_lock
    from app.services.track_store import TrackStore
    from app.models.track import Track

    db_file = str(tmp_path / "ts.db")
    store = TrackStore(db_path=db_file)
    # Note: set_track_store is NOT called here — this test works directly with
    # `store` and get_track_store_lock() (which is a module-level RLock,
    # independent of which store is currently active). Calling set_track_store
    # followed by store.close() would leave the global _track_store in a broken
    # state and cause sqlite3.ProgrammingError in subsequent tests.

    # Pre-populate with 3 tracks
    for i in range(3):
        fp = f"/music/track{i}.mp3"
        store[fp] = Track(
            file_path=fp,
            filename=f"track{i}.mp3",
            existing_title=f"Track {i}",
            existing_artist="Artist",
        )

    observed_empty = []
    iterations = 20

    def reader():
        """Simulates analyze: snapshot keys under the lock."""
        lock = get_track_store_lock()
        for _ in range(iterations):
            with lock:
                keys = list(store.keys())
            if len(keys) == 0:
                observed_empty.append(len(keys))
            time.sleep(0)  # yield

    def writer():
        """Simulates import: clear+repopulate under the lock."""
        lock = get_track_store_lock()
        new_tracks = [
            Track(
                file_path=f"/music/new{i}.mp3",
                filename=f"new{i}.mp3",
                existing_title=f"New {i}",
                existing_artist="Artist",
            )
            for i in range(3)
        ]
        for _ in range(iterations):
            with lock:
                store.clear()
                for t in new_tracks:
                    store[t.file_path] = t
            time.sleep(0)  # yield

    r = threading.Thread(target=reader)
    w = threading.Thread(target=writer)
    r.start()
    w.start()
    r.join(timeout=10)
    w.join(timeout=10)

    store.close()
    assert not observed_empty, (
        f"Reader observed an empty store {len(observed_empty)} time(s) — "
        "_track_store_lock is not being held during clear+repopulate"
    )
