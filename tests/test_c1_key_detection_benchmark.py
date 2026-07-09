"""
Regression tests for issue #204 (IDJLM C.1: key-detection benchmark harness).

Covers three properties:
  1. Dataset integrity: the ground-truth maker produces 100+ clips across all
     24 keys, every Camelot label matches the production CAMELOT_MAJOR/MINOR
     mapping.
  2. Harness correctness: run_benchmark returns results for every registered
     detector; accuracy numbers are sane (0-100, totals match).
  3. Target gate (the actual ship decision): the production detector accuracy
     >= 80% on the labelled set. Bonus assertion: no alternative detector
     beats current by >= 10 pts (so the plan's adopt-if-10pt-gain rule holds).

The fast variant uses n_variants_per_key=2 (= 48 clips) which keeps test time
under ~30s on this machine; a separate test asserts the FULL set has 100+ clips
without re-running all detectors on it.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.key_detection import benchmark
from tests.key_detection.ground_truth_dataset import (
    KEYS,
    generate_ground_truth_dataset,
    dataset_summary,
)
from app.services.analyzer import CAMELOT_MAJOR, CAMELOT_MINOR


# ---------------------------------------------------------------------------
# Dataset integrity
# ---------------------------------------------------------------------------

def test_keys_table_camelot_codes_match_production_mapping():
    assert len(KEYS) == 24, f"Expected 24 keys, got {len(KEYS)}"

    seen = set()
    for pc, mode, camelot, _name in KEYS:
        mapping = CAMELOT_MINOR if mode == "minor" else CAMELOT_MAJOR
        assert mapping[pc] == camelot, (
            f"Camelot mismatch for pc={pc} mode={mode}: "
            f"production={mapping[pc]} dataset={camelot}"
        )
        # Every Camelot code is unique — no accidental duplicates like v1 had
        assert camelot not in seen, f"Duplicate Camelot code {camelot} in KEYS"
        seen.add(camelot)

    assert len(seen) == 24


def test_dataset_meets_100_track_threshold():
    dataset = generate_ground_truth_dataset(n_variants_per_key=5, duration=4.0)
    summary = dataset_summary(dataset)
    assert summary["total_clips"] >= 100, (
        f"Ground-truth set must be 100+ clips (got {summary['total_clips']})"
    )
    assert summary["keys_covered"] == 24


def test_dataset_smaller_variant_only_uses_valid_camelots():
    dataset = generate_ground_truth_dataset(n_variants_per_key=1, duration=2.0)
    valid = set()
    for d in (CAMELOT_MAJOR, CAMELOT_MINOR):
        valid.update(d.values())
    for ex in dataset:
        assert ex["ground_truth_camelot"] in valid, (
            f"Invalid Camelot {ex['ground_truth_camelot']!r}"
        )
        assert 0 <= ex["ground_truth_pc"] <= 11
        assert ex["ground_truth_mode"] in ("major", "minor")


# ---------------------------------------------------------------------------
# Harness correctness (quick — uses small dataset)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def small_dataset():
    return generate_ground_truth_dataset(n_variants_per_key=1, duration=3.0)


@pytest.fixture(scope="module")
def small_results(small_dataset):
    return benchmark.run_benchmark(small_dataset)


def test_benchmark_runs_every_detector(small_results):
    registered = [n for n, _, _ in benchmark.DETECTORS]
    assert sorted(small_results.keys()) == sorted(registered)


def test_benchmark_accuracy_in_range(small_results):
    for name, info in small_results.items():
        acc = info["accuracy_percent"]
        assert 0.0 <= acc <= 100.0, f"{name} accuracy out of range: {acc}"
        assert info["exact_match_count"] + info["tonic_only_count"] + \
            info["relative_only_count"] <= info["total"]


def test_benchmark_evidence_file_written(tmp_path):
    dataset = generate_ground_truth_dataset(n_variants_per_key=1, duration=2.0)
    results = benchmark.run_benchmark(dataset)
    summary = dataset_summary(dataset)
    out = tmp_path / "evidence.json"
    path = benchmark.save_evidence(results, summary, evidence_path=str(out))
    blob = json.loads(open(path).read())
    assert blob["issue"] == "#204 IDJLM C.1 key-detection benchmark"
    assert "results" in blob
    assert "dataset" in blob
    assert "essentia_registered" in blob


# ---------------------------------------------------------------------------
# Target gate: production detector accuracy on labelled set (medium test)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def medium_dataset():
    return generate_ground_truth_dataset(n_variants_per_key=2, duration=4.0)


@pytest.fixture(scope="module")
def medium_results(medium_dataset):
    return benchmark.run_benchmark(medium_dataset)


def test_production_detector_meets_80pct_target(medium_results):
    acc = medium_results["current"]["accuracy_percent"]
    assert acc >= 80.0, (
        f"Production key-detection accuracy {acc:.1f}% below 80% target. "
        "Detector upgrade required (see issue #204 gating rule)."
    )


def test_best_alternative_does_not_beat_current_by_10pts(medium_results):
    current_acc = medium_results["current"]["accuracy_percent"]
    others = [(n, r["accuracy_percent"]) for n, r in medium_results.items() if n != "current"]
    if not others:
        pytest.skip("No alternative detectors registered")
    best_alt = max(o for o in others)
    if best_alt[1] >= current_acc + 10:
        pytest.fail(
            f"{best_alt[0]} beats current by {best_alt[1] - current_acc:.1f} pts "
            f"(>=10 threshold) — production detector should be upgraded per the plan gate."
        )


def test_krumhansl_variants_within_bounds(medium_results):
    for name, r in medium_results.items():
        if name == "current":
            continue
        # All Krumhansl variants should hit >=80% on labelled Latin set
        assert r["accuracy_percent"] >= 80.0, (
            f"{name} below 80% ({r['accuracy_percent']:.1f}%) — implementation regression."
        )
