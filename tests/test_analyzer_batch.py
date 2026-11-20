"""Process-boundary regressions for legacy batch audio analysis."""
from __future__ import annotations

import multiprocessing

from app.models.track import Track
from app.services import analyzer


def test_batch_analysis_uses_bounded_spawn_workers(monkeypatch, tmp_path):
    """Native audio libraries must not run through an inherited fork process."""
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    tracks = {
        str(first): Track(file_path=str(first), filename=first.name),
        str(second): Track(file_path=str(second), filename=second.name),
    }
    calls: dict[str, object] = {}

    class FakePool:
        def __init__(self, *, processes):
            calls["processes"] = processes

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def imap_unordered(self, _worker, items):
            for file_path, _genre in items:
                yield {
                    "file_path": file_path,
                    "analyzed_bpm": 120.0,
                    "analyzed_key": "8A",
                    "raw_rms": 0.1,
                    "duration": 1.0,
                }

    class FakeContext:
        Pool = FakePool

    def fake_get_context(name):
        calls["context"] = name
        return FakeContext()

    monkeypatch.setattr(multiprocessing, "get_context", fake_get_context)
    monkeypatch.setattr(multiprocessing, "Pool", FakePool)
    monkeypatch.setattr(analyzer, "_postprocess_analysis", lambda _track: None)

    analyzed, errors = analyzer.analyze_tracks_batch(list(tracks), tracks, num_workers=99)

    assert (analyzed, errors) == (2, [])
    assert calls == {"context": "spawn", "processes": 1}
    assert all(track.analysis_done for track in tracks.values())
