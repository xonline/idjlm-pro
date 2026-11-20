"""Data-boundary checks for the local-only benchmark CLI."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


_SCRIPT = Path(__file__).parents[1] / "scripts" / "benchmark_audio_classifier.py"
_SPEC = importlib.util.spec_from_file_location("benchmark_audio_classifier", _SCRIPT)
assert _SPEC and _SPEC.loader
benchmark = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(benchmark)


def _manifest(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _row(audio: Path, **changes):
    value = {"id": "one", "path": str(audio), "label_id": "salsa", "split": "calibration", "group_id": "track-a"}
    value.update(changes)
    return value


def test_manifest_rejects_duplicate_ids_and_audio_group_leakage(tmp_path):
    audio = tmp_path / "tone.wav"
    audio.write_bytes(b"fixture")
    duplicate_ids = _manifest(tmp_path / "ids.jsonl", [_row(audio), _row(audio)])
    with pytest.raises(ValueError, match="duplicate ids"):
        benchmark.load_manifest(duplicate_ids)

    distinct_groups = _manifest(tmp_path / "paths.jsonl", [_row(audio), _row(audio, id="two", group_id="track-b")])
    with pytest.raises(ValueError, match="multiple groups"):
        benchmark.load_manifest(distinct_groups)


def test_calibration_never_fits_a_test_only_label():
    rows = [
        {"id": "a", "label_id": "salsa", "split": "calibration", "group_id": "a"},
        {"id": "b", "label_id": "bachata", "split": "calibration", "group_id": "b"},
        {"id": "c", "label_id": "boogaloo", "split": "test", "group_id": "c"},
    ]
    predictions = {row["id"]: {"axes": {"music_family": {"candidates": [
        {"label_id": "salsa", "raw_score": 0.8}, {"label_id": "bachata", "raw_score": 0.2}, {"label_id": "boogaloo", "raw_score": 0.1}
    ]}}} for row in rows}
    profile = benchmark.fit_calibration(rows, predictions)
    assert set(profile["labels"]) == {"salsa", "bachata"}


def test_report_separates_raw_rank_from_review_coverage():
    rows = [{"id": "one", "label_id": "salsa", "split": "test", "group_id": "one"}]
    predictions = {"one": {"axes": {"music_family": {
        "status": "unsupported", "candidates": [{"label_id": "salsa", "raw_score": 0.9}],
    }}}}
    result = benchmark.report(rows, predictions, "test")
    assert result["raw_top1_accuracy"] == 1.0
    assert result["review_coverage"] == 0.0
    assert result["reviewed_raw_top1_accuracy"] is None
