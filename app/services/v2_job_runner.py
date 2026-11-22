"""Small durable-job worker adapters for the redesign routes.

This module owns no Flask state and never makes a classifier result an approval.
Routes inject persistence callbacks so interrupted work remains recoverable in
SQLite rather than only in a thread's memory.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any


class JobCancelled(RuntimeError):
    pass


def run_audio_classification(
    *,
    entries: Iterable[dict[str, Any]],
    model_id: str,
    engine: Any,
    persist: Callable[[dict[str, Any]], None],
    progress: Callable[[str, dict[str, Any]], None],
    should_stop: Callable[[], bool],
    started: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """Run selected items one at a time, persisting every outcome.

    ``should_stop`` is checked between whole files only. A write never occurs
    here, and successful audio rankings remain review-required proposals.
    """
    counts = {"completed": 0, "failed": 0, "abstained": 0}
    for entry in entries:
        if should_stop():
            raise JobCancelled("cancelled before next item")
        item_id = str(entry["id"])
        path = Path(entry["path"])
        if started:
            started(item_id)
        result = engine.classify_item(item_id, path, model_id=model_id)
        payload = result.to_service_payload()
        persist(payload)
        state = str(payload.get("status") or "failed")
        if state == "proposed":
            counts["completed"] += 1
            progress("item_completed", {"item_id": item_id, "status": "proposed"})
        elif state == "abstained":
            counts["abstained"] += 1
            progress("item_abstained", {"item_id": item_id, "reason": payload.get("reason")})
        else:
            counts["failed"] += 1
            progress("item_failed", {"item_id": item_id, "reason": payload.get("reason")})
    return counts
