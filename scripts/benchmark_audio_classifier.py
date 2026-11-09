#!/usr/bin/env python3
"""Evaluate the local audio candidate on a grouped, audio-only JSONL manifest.

The manifest requires id, path, label_id, split (train/dev/calibration/test),
and group_id.  It never uploads audio.  Fit per-class gates only from the
calibration split; the final test labels are read only for reporting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.audio_classification import AudioClassificationEngine


REQUIRED = {"id", "path", "label_id", "split", "group_id"}


def load_manifest(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            missing = REQUIRED - set(row)
            if missing:
                raise ValueError(f"manifest row {number} misses {', '.join(sorted(missing))}")
            if row["split"] not in {"train", "dev", "calibration", "test"}:
                raise ValueError(f"manifest row {number} has invalid split")
            rows.append(row)
    groups: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        groups[str(row["group_id"])].add(str(row["split"]))
    leaked = [group for group, splits in groups.items() if len(splits) > 1]
    if leaked:
        raise ValueError("group leakage across splits: " + ", ".join(leaked[:10]))
    if not rows:
        raise ValueError("manifest has no rows")
    return rows


def manifest_digest(rows: list[dict[str, Any]]) -> str:
    value = [{key: row[key] for key in ("id", "label_id", "split", "group_id")} for row in rows]
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def raw_score(payload: dict[str, Any], label_id: str) -> float:
    candidates = payload["axes"]["music_family"]["candidates"]
    for candidate in candidates:
        if candidate["label_id"] == label_id:
            return float(candidate["raw_score"])
    raise ValueError(f"model does not expose label {label_id}")


def fit_calibration(rows: list[dict[str, Any]], predictions: dict[str, dict[str, Any]],
                    gate_min_precision: float | None = None) -> dict[str, Any]:
    try:
        from sklearn.linear_model import LogisticRegression
    except ImportError as exc:
        raise RuntimeError("scikit-learn is required to fit calibration; it is not needed for inference.") from exc
    labels = sorted({str(row["label_id"]) for row in rows})
    calibration = [row for row in rows if row["split"] == "calibration"]
    if not calibration:
        raise ValueError("a calibration split is required; test data cannot fit gates")
    profile = {"version": "platt-v1", "fit_split": "calibration", "dataset_manifest_sha256": manifest_digest(rows),
               "labels": {}, "gate_selection": {"split": "calibration", "minimum_precision": gate_min_precision}}
    for label in labels:
        y = [int(row["label_id"] == label) for row in calibration]
        if len(set(y)) != 2:
            raise ValueError(f"calibration needs positive and negative examples for {label}")
        x = [[raw_score(predictions[row["id"]], label)] for row in calibration]
        classifier = LogisticRegression(C=1.0, max_iter=1000).fit(x, y)
        values = {"coefficient": float(classifier.coef_[0][0]), "intercept": float(classifier.intercept_[0])}
        if gate_min_precision is not None:
            probabilities = classifier.predict_proba(x)[:, 1].tolist()
            viable = []
            for threshold in sorted(set(probabilities)):
                selected = [actual for actual, probability in zip(y, probabilities) if probability >= threshold]
                if selected and sum(selected) / len(selected) >= gate_min_precision:
                    viable.append(threshold)
            if viable:
                # Lowest valid threshold maximizes calibration-set coverage at the requested precision.
                values["threshold"] = min(viable)
        profile["labels"][label] = values
    return profile


def report(rows: list[dict[str, Any]], predictions: dict[str, dict[str, Any]], split: str) -> dict[str, Any]:
    selected = [row for row in rows if row["split"] == split]
    labels = sorted({str(row["label_id"]) for row in selected})
    outcomes = []
    for row in selected:
        candidates = predictions[row["id"]]["axes"]["music_family"]["candidates"]
        predicted = candidates[0]["label_id"]
        outcomes.append((str(row["label_id"]), predicted))
    per_label = {}
    for label in labels:
        tp = sum(actual == label and predicted == label for actual, predicted in outcomes)
        fp = sum(actual != label and predicted == label for actual, predicted in outcomes)
        fn = sum(actual == label and predicted != label for actual, predicted in outcomes)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        per_label[label] = {"support": sum(actual == label for actual, _ in outcomes), "precision": precision, "recall": recall,
                            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
    return {"split": split, "rows": len(selected), "accuracy": sum(actual == predicted for actual, predicted in outcomes) / len(outcomes) if outcomes else None,
            "macro_f1": sum(value["f1"] for value in per_label.values()) / len(per_label) if per_label else None,
            "per_class": per_label}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--model-id", default="laion-clap-htsat-unfused")
    parser.add_argument("--calibration-out", type=Path)
    parser.add_argument("--gate-min-precision", type=float,
                        help="optional per-class precision gate fitted from calibration rows only (0..1)")
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()
    if args.gate_min_precision is not None and not 0 < args.gate_min_precision <= 1:
        parser.error("--gate-min-precision must be in (0, 1]")
    if args.gate_min_precision is not None and not args.calibration_out:
        parser.error("--gate-min-precision requires --calibration-out")
    rows = load_manifest(args.manifest)
    engine = AudioClassificationEngine()
    predictions = {}
    for row in rows:
        result = engine.classify_item(str(row["id"]), row["path"], args.model_id).to_service_payload()
        if result["status"] == "failed":
            raise RuntimeError(f"{row['id']}: {result['reason']}")
        predictions[str(row["id"])] = result
    profile = fit_calibration(rows, predictions, args.gate_min_precision) if args.calibration_out else None
    if args.calibration_out:
        args.calibration_out.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output = {"manifest_sha256": manifest_digest(rows), "dev": report(rows, predictions, "dev"), "test": report(rows, predictions, "test")}
    rendered = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.report_out:
        args.report_out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
