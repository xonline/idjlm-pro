#!/usr/bin/env python3
"""Bounded local reliability check for the V2 catalogue at library scale.

This creates only temporary synthetic MP3 paths and an isolated
``IDJLM_USER_DATA_DIR``.  It does not analyse audio, download a model, write
source tags, or represent M3/device performance.  The timed API work is
repeated so the JSON report records medians and ranges rather than a single
noisy measurement.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _samples(runs, operation):
    values = []
    for _ in range(runs):
        started = time.perf_counter()
        result = operation()
        values.append(time.perf_counter() - started)
        if hasattr(result, "status_code") and result.status_code >= 400:
            raise RuntimeError(
                f"unexpected API status {result.status_code}: {result.get_json()}"
            )
    return {
        "runs": runs,
        "median_seconds": statistics.median(values),
        "range_seconds": [min(values), max(values)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=int, default=15_000)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()
    if not 1 <= args.items <= 20_000 or not 1 <= args.runs <= 10:
        parser.error("--items must be 1..20000 and --runs must be 1..10")

    # This must precede importing app, whose path constants are resolved on
    # import.  A temporary directory also makes accidental personal-library
    # access impossible for this harness.
    root = Path(tempfile.mkdtemp(prefix="idjlm-v2-catalog-"))
    os.environ["IDJLM_USER_DATA_DIR"] = str(root / "state")
    from app import create_app, get_v2_store

    app = create_app()
    app.config.update(TESTING=True)
    client, store = app.test_client(), get_v2_store()
    now = "2026-11-19T00:00:00Z"
    synthetic_media_root = root / "synthetic-media"
    with store._tx() as db:
        db.executemany(
            "INSERT INTO v2_items(item_id,file_path,source_revision,created_at,updated_at) VALUES(?,?,?,?,?)",
            [
                (
                    f"item-{i:05d}",
                    str(synthetic_media_root / f"{i:05d}.mp3"),
                    "",
                    now,
                    now,
                )
                for i in range(args.items)
            ],
        )
        db.executemany(
            "INSERT INTO v2_item_originals(item_id,payload,title,title_norm,artist,artist_norm,existing_genre,raw_comment,raw_comment_norm,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    f"item-{i:05d}",
                    "{}",
                    f"Track {i:05d}",
                    f"track {i:05d}",
                    "Synthetic",
                    "synthetic",
                    "",
                    "",
                    "",
                    now,
                )
                for i in range(args.items)
            ],
        )
        db.executemany(
            "INSERT INTO v2_effective_labels(item_id,axis,label_id,source) VALUES(?,?,?,?)",
            [
                (
                    f"item-{i:05d}",
                    "music_family",
                    "salsa" if i % 2 == 0 else "bachata",
                    "synthetic",
                )
                for i in range(args.items)
            ],
        )

    base = "/api/v2/library/items?limit=100&sort=title%3Aasc"
    filtered = (
        base + "&" + urlencode({"filters": json.dumps({"family_ids": ["salsa"]})})
    )
    page = _samples(args.runs, lambda: client.get(base))
    selected = _samples(args.runs, lambda: client.get(filtered))
    first = client.get(filtered).get_json()
    if first["total"] != (args.items + 1) // 2 or len(first["items"]) != min(
        100, first["total"]
    ):
        raise RuntimeError(
            "page/filter result did not contain the expected synthetic catalogue"
        )

    scope = {
        "selection": "all_filtered",
        "item_ids": [],
        "filter": {"family_ids": ["salsa"]},
    }

    def resolve_expected(selection, expected_count):
        entries = store.resolve_scope(selection)
        if len(entries) != expected_count:
            raise RuntimeError(
                f"scope returned {len(entries)} items, expected {expected_count}"
            )
        return entries

    full_scope = {"selection": "all_filtered", "item_ids": [], "filter": {}}
    resolved_full_scope = _samples(
        args.runs, lambda: resolve_expected(full_scope, args.items)
    )
    resolved_filtered_scope = _samples(
        args.runs, lambda: resolve_expected(scope, first["total"])
    )
    review = client.post("/api/v2/reviews/previews", json={"scope": scope})
    if review.status_code != 201:
        raise RuntimeError(f"review preview failed: {review.get_json()}")
    frozen = review.get_json()
    if len(frozen["item_revisions"]) != first["total"]:
        raise RuntimeError("all-filtered preview did not freeze every matching item")

    # These request paths are deliberately media-free: a missing synthetic
    # path is reported as such by the preview and cannot tag or copy any
    # source. They still exercise the production all-filtered selection,
    # frozen snapshot, and manifest payload size at scale.
    preview_scope = {
        "selection": "all_filtered",
        "item_ids": [],
        "filter": {"family_ids": ["salsa"]},
    }
    write = client.post(
        "/api/v2/writes/previews",
        json={"scope": preview_scope, "fields": ["genre"]},
    )
    if write.status_code != 201:
        raise RuntimeError(f"write preview failed: {write.get_json()}")
    write_payload = write.get_json()
    if len(write_payload["items"]) != first["total"]:
        raise RuntimeError("write preview did not bind every selected item")

    export = client.post(
        "/api/v2/exports/previews",
        json={
            "scope": preview_scope,
            "destination": str(root / "staging"),
            "profile": {"name": "broad_genre_raw_comment"},
        },
    )
    if export.status_code != 201:
        raise RuntimeError(f"export preview failed: {export.get_json()}")
    export_payload = export.get_json()
    if export_payload["report"]["missing_count"] != first["total"]:
        raise RuntimeError(
            "export preview did not report every missing synthetic source"
        )

    ids = [row["item_id"] for row in frozen["item_revisions"]]
    job = store.create_job("classify", {"item_ids": ids}, {"model_id": "synthetic"})
    if not store.set_job_state(job["job_id"], "running"):
        raise RuntimeError("could not start synthetic durable job")
    recovered = store.recover_interrupted_jobs()
    if job["job_id"] not in {entry["job_id"] for entry in recovered}:
        raise RuntimeError("restart recovery did not mark the running job interrupted")
    if not store.set_job_state(job["job_id"], "running"):
        raise RuntimeError("interrupted synthetic job could not resume")

    report = {
        "kind": "synthetic_linux_catalog_reliability",
        "items": args.items,
        "filter_matches": first["total"],
        "page": page,
        "filtered_page": selected,
        "all_filtered_scope": resolved_full_scope,
        "filtered_scope": resolved_filtered_scope,
        "frozen_scope_items": len(frozen["item_revisions"]),
        "write_preview_items": len(write_payload["items"]),
        "export_preview_missing_items": export_payload["report"]["missing_count"],
        "durable_restart_job_items": store.job_items(job["job_id"], limit=1)["total"],
        "limits": [
            "SQL-seeded synthetic metadata; this does not measure scanner, source writes, staged copies, or audio-model throughput.",
            "Linux host result only; it is not an M3, accuracy, device-transfer, or 15k completion-time claim.",
        ],
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report_out:
        args.report_out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
