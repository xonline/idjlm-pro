"""Phase G regression tests — analysis cancellation (issue #214).

Cancelling an analysis run used to be cosmetic: POST /api/progress/<op>/cancel
popped the SSE queue so the browser stopped listening, but the multiprocessing
pool kept churning through every remaining track and `_analyze_lock` stayed
held until it drained. On a 10k-track library that meant a "cancelled" run kept
all cores busy for minutes and every subsequent /api/analyze returned 429.

These tests pin the contract: a cancel signal must (a) be observable by the
worker loop, (b) stop the pool without draining the queue, and (c) leave the
analyze lock free so the next run can start immediately.
"""
import queue
import threading

import pytest

from app.models.track import Track


def _make_track(path):
    return Track(file_path=path, filename=path.rsplit("/", 1)[-1])


class TestCancelRegistry:
    def test_cancel_events_registry_exists(self):
        """The app exposes a cancel-event registry alongside progress queues."""
        from app import get_cancel_events

        events = get_cancel_events()
        assert hasattr(events, "get")

    def test_cancel_route_sets_the_event(self, client):
        """POST /api/progress/<op>/cancel must SET the event, not just drop the queue."""
        from app import get_cancel_events, get_progress_queues

        op_id = "test-cancel-op"
        get_progress_queues()[op_id] = queue.Queue()
        ev = threading.Event()
        get_cancel_events()[op_id] = ev

        resp = client.post(f"/api/progress/{op_id}/cancel")

        assert resp.status_code == 200
        assert ev.is_set(), "cancel endpoint did not signal the worker pool"


class TestBatchHonoursCancellation:
    def test_batch_bails_out_when_cancelled_before_start(self):
        """A pre-set cancel event must short-circuit before any audio is touched.

        The paths below do not exist — if analyze_tracks_batch tries to analyze
        them instead of honouring the cancel flag, it would do real file I/O.
        """
        from app.services.analyzer import analyze_tracks_batch

        paths = [f"/nonexistent/track{i}.mp3" for i in range(5)]
        store = {p: _make_track(p) for p in paths}
        q = queue.Queue()
        cancel = threading.Event()
        cancel.set()

        analyzed, errors = analyze_tracks_batch(
            paths, store, progress_queue=q, cancel_event=cancel
        )

        assert analyzed == 0
        assert errors == []

        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        assert msgs, "no terminal event emitted on cancellation"
        assert msgs[-1].get("done") is True
        assert msgs[-1].get("cancelled") is True

    def test_batch_accepts_cancel_event_kwarg(self):
        """Signature contract — callers pass a cancel_event through."""
        import inspect

        from app.services.analyzer import analyze_tracks_batch

        params = inspect.signature(analyze_tracks_batch).parameters
        assert "cancel_event" in params


def _wait_until(predicate, timeout=15.0, interval=0.05):
    """Bounded wait — returns True if predicate held before the timeout."""
    waited = 0.0
    while waited < timeout:
        if predicate():
            return True
        threading.Event().wait(interval)
        waited += interval
    return predicate()


class TestCancelReleasesLock:
    def test_analyze_lock_free_after_cancelled_run(self, client):
        """A cancelled run must not hold the analyze lock (else the next run 429s).

        The suite runs under pytest-randomly, so an unrelated test's daemon
        analysis thread may still hold the lock when this starts. Wait for it
        rather than asserting on it — the contract under test is that *our*
        cancelled run releases the lock, not that no one else ever holds it.
        """
        from app.routes.import_routes import _analyze_lock

        if not _wait_until(lambda: not _analyze_lock.locked()):
            pytest.skip("analyze lock held by a concurrent test run")

        resp = client.post("/api/analyze", json={"track_paths": []})
        if resp.status_code == 429:
            pytest.skip("another analysis started concurrently")
        assert resp.status_code == 202
        body = resp.get_json()
        op_id = body["op_id"]

        # An empty store takes the sequential zero-iteration path and would
        # free the lock without any pool ever running — that is a trivial pass,
        # not evidence. Skip honestly rather than pretend we covered it.
        if body["total"] <= 1:
            pytest.skip("empty track store — parallel pool path not exercised")

        client.post(f"/api/progress/{op_id}/cancel")

        # The worker thread must observe the cancel, tear the pool down, and
        # release the lock. Before the fix this stayed held until every track
        # in the library had been analyzed.
        assert _wait_until(lambda: not _analyze_lock.locked()), (
            "analyze lock still held after cancel — next /api/analyze would 429"
        )
