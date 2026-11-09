"""Regression coverage for the v2 persistence boundary.

The large fixture is SQL-seeded so this test checks pagination/query shape,
not scanner throughput.  It never opens the operator's library database.
"""

import json
import sqlite3

import pytest

from app.services.v2_store import V2Store


@pytest.fixture
def store(tmp_path):
    return V2Store(str(tmp_path / "v2.sqlite"))


def add(store, name, **original):
    return store.upsert_item(
        path=f"/library/{name}.mp3", original={"title": name, **original}
    )


def test_reads_are_side_effect_free_and_family_filter_is_not_global(store):
    assert (
        store.list_items(cursor=None, limit=10, filters={}, sort="title:asc")["items"]
        == []
    )
    first, second = (
        add(store, "Alpha", existing_genre="Salsa"),
        add(store, "Bravo", existing_genre="Bachata"),
    )
    # Legacy text is evidence, not an automatically assigned v2 family.
    assert (
        store.list_items(
            cursor=None, limit=10, filters={"family_ids": ["salsa"]}, sort="title:asc"
        )["total"]
        == 0
    )
    store.save_prediction(
        {
            "item_id": first["id"],
            "model": {},
            "axes": {"music_family": {"label_ids": ["salsa"], "status": "proposed"}},
        }
    )
    page = store.list_items(
        cursor=None, limit=10, filters={"family_ids": ["salsa"]}, sort="title:asc"
    )
    assert [item["id"] for item in page["items"]] == [first["id"]]
    assert second["id"] not in [item["id"] for item in page["items"]]


def test_scope_preview_revisions_and_locked_decisions(store):
    item = add(store, "Locked")
    store.save_taxonomy({"labels": [{"id": "salsa"}, {"id": "bachata"}]}, 0)
    store.save_prediction(
        {
            "item_id": item["id"],
            "model": {},
            "axes": {"music_family": {"label_ids": ["salsa"], "status": "proposed"}},
        }
    )
    detail = store.get_item(item["id"])
    preview = store.create_preview(
        "review",
        {
            "fields": ["music_family"],
            "items": [
                {
                    "item_id": item["id"],
                    "revision": detail["revision"],
                    "axes": {"music_family": detail["axes"]["music_family"]},
                }
            ],
        },
    )
    claimed = store.consume_preview(preview["preview_id"], "review")
    assert claimed and store.consume_preview(preview["preview_id"], "review") is None
    assert store.save_decisions(
        claimed, [{"item_id": item["id"], "axis": "music_family", "action": "accept"}]
    ) == [item["id"]]
    locked_detail = store.get_item(item["id"])
    lock_preview = store.create_preview(
        "review",
        {
            "fields": ["music_family"],
            "items": [
                {
                    "item_id": item["id"],
                    "revision": locked_detail["revision"],
                    "axes": {"music_family": locked_detail["axes"]["music_family"]},
                }
            ],
        },
    )
    locked = store.consume_preview(lock_preview["preview_id"], "review")
    store.save_decisions(
        locked, [{"item_id": item["id"], "axis": "music_family", "action": "lock"}]
    )
    current = store.get_item(item["id"])
    overwrite = store.create_preview(
        "review",
        {
            "fields": ["music_family"],
            "items": [
                {
                    "item_id": item["id"],
                    "revision": current["revision"],
                    "axes": {"music_family": current["axes"]["music_family"]},
                }
            ],
        },
    )
    with pytest.raises(ValueError, match="locked_decision"):
        store.save_decisions(
            store.consume_preview(overwrite["preview_id"], "review"),
            [
                {
                    "item_id": item["id"],
                    "axis": "music_family",
                    "action": "correct",
                    "label_ids": ["bachata"],
                }
            ],
        )


def test_scope_rejects_empty_or_missing_ids_and_stale_preview(store):
    item = add(store, "Scope")
    for scope in (
        {"selection": "explicit", "item_ids": []},
        {"selection": "explicit", "item_ids": ["missing"]},
        {"selection": "all_filtered", "item_ids": [], "filter": {"query": "nope"}},
    ):
        with pytest.raises(ValueError):
            store.resolve_scope(scope)
    detail = store.get_item(item["id"])
    preview = store.create_preview(
        "review",
        {
            "fields": ["music_family"],
            "items": [
                {"item_id": item["id"], "revision": detail["revision"], "axes": {}}
            ],
        },
    )
    store.upsert_item(
        path="/library/Scope.mp3",
        item_id=item["id"],
        original={"title": "Scope changed"},
    )
    with pytest.raises(ValueError, match="stale_preview"):
        store.save_decisions(
            store.consume_preview(preview["preview_id"], "review"),
            [{"item_id": item["id"], "axis": "music_family", "action": "lock"}],
        )


def test_rescan_is_idempotent_and_prediction_keeps_audio_evidence(store):
    first = add(store, "Rescan", existing_comment="one raw string")
    same = store.upsert_item(
        path="/library/Rescan.mp3",
        item_id=first["id"],
        original={"title": "Rescan", "existing_comment": "one raw string"},
    )
    assert same["id"] == first["id"] and same["revision"] == first["revision"]
    before = store.get_item(first["id"])["revision"]
    store.save_prediction(
        {
            "item_id": first["id"],
            "model": {"artifact": "local"},
            "axes": {
                "music_family": {
                    "status": "candidate",
                    "candidates": [
                        {
                            "label_id": "salsa",
                            "raw_score": 0.71,
                            "evidence": [{"start_seconds": 20}],
                        }
                    ],
                    "reason": "rank only",
                    "section_disagreement": True,
                }
            },
        }
    )
    detail = store.get_item(first["id"])
    proposal = detail["axes"]["music_family"]["proposal"]
    assert detail["revision"] != before
    assert proposal["label_ids"] == []
    assert proposal["details"]["candidates"][0]["label_id"] == "salsa"
    # Same source readback stays stable; a changed tag snapshot advances only
    # the source revision while retaining the stable item ID.
    changed = store.upsert_item(
        path="/library/Rescan.mp3",
        item_id=first["id"],
        original={"title": "Rescan", "existing_comment": "changed"},
    )
    assert changed["id"] == first["id"] and changed["revision"] != detail["revision"]


def test_15k_library_page_has_bounded_response_and_select_count(store):
    store = V2Store(":memory:")
    now = "2026-01-01T00:00:00Z"
    with store._tx() as db:
        db.executemany(
            "INSERT INTO v2_items(item_id,file_path,source_revision,created_at,updated_at) VALUES(?,?,?,?,?)",
            [
                (f"item-{number:05d}", f"/library/{number:05d}.mp3", "", now, now)
                for number in range(15_000)
            ],
        )
        db.executemany(
            "INSERT INTO v2_item_originals(item_id,payload,title,title_norm,artist,artist_norm,existing_genre,raw_comment,raw_comment_norm,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    f"item-{number:05d}",
                    "{}",
                    f"Track {number:05d}",
                    f"track {number:05d}",
                    "Artist",
                    "artist",
                    "",
                    "",
                    "",
                    now,
                )
                for number in range(15_000)
            ],
        )
    statements = []
    store._conn.set_trace_callback(statements.append)
    page = store.list_items(cursor=None, limit=25, filters={}, sort="title:asc")
    store._conn.set_trace_callback(None)
    assert page["total"] == 15_000
    assert len(page["items"]) == 25 and page["next_cursor"]
    assert len(json.dumps(page)) < 20_000
    assert (
        len(
            [
                statement
                for statement in statements
                if statement.lstrip().upper().startswith("SELECT")
            ]
        )
        <= 3
    )


def test_import_job_can_durably_append_discovered_items(store):
    job = store.create_job("import", {"item_ids": []}, {"folder_path": "/library/a"})
    assert job["counts"]["total"] == 0
    item = add(store, "Imported")
    running = store.set_job_state(job["job_id"], "running")
    assert running
    changed = store.append_job_item(job["job_id"], item["id"])
    assert changed["counts"]["total"] == 1
    store.update_job_item(job["job_id"], item["id"], "running")
    done = store.update_job_item(job["job_id"], item["id"], "completed")
    assert done["counts"]["completed"] == 1


def test_write_history_is_bounded_and_hides_source_paths(store):
    item = add(store, "Written")
    store.record_write(
        item_id=item["id"],
        source_path="/library/Written.mp3",
        before_sha256="before",
        after_sha256="after",
        backup_path="/backup/Written",
        fields={"genre": "salsa"},
        status="written",
    )
    page = store.list_writes(limit=10)
    assert page["total"] == 1 and page["writes"][0]["fields"] == {"genre": "salsa"}
    assert "source_path" not in page["writes"][0]


def test_all_filtered_scope_is_frozen_into_preview(store):
    first = add(store, "First")
    frozen = store.resolve_scope(
        {"selection": "all_filtered", "item_ids": [], "filter": {}}
    )
    preview = store.create_preview(
        "write",
        {
            "items": [
                {"item_id": row["id"], "revision": row["revision"]} for row in frozen
            ]
        },
    )
    add(store, "Later")
    assert [row["item_id"] for row in preview["item_revisions"]] == [first["id"]]


def test_decision_axis_cardinality_and_analysis_outcomes_are_explicit(store):
    item = add(store, "Outcome")
    store.save_taxonomy(
        {
            "labels": [
                {"id": "salsa", "axis": "music_family"},
                {"id": "bachata", "axis": "music_family"},
                {"id": "salsa_romantica", "axis": "style"},
            ],
            "axes": {"music_family": {"cardinality": "single"}},
        },
        0,
    )
    detail = store.get_item(item["id"])
    preview = store.create_preview(
        "review",
        {
            "fields": ["music_family"],
            "items": [
                {"item_id": item["id"], "revision": detail["revision"], "axes": {}}
            ],
        },
    )
    claimed = store.consume_preview(preview["preview_id"], "review")
    with pytest.raises(ValueError, match="invalid_cardinality"):
        store.save_decisions(
            claimed,
            [
                {
                    "item_id": item["id"],
                    "axis": "music_family",
                    "action": "correct",
                    "label_ids": ["salsa", "bachata"],
                }
            ],
        )

    detail = store.get_item(item["id"])
    preview = store.create_preview(
        "review",
        {
            "fields": ["music_family"],
            "items": [
                {"item_id": item["id"], "revision": detail["revision"], "axes": {}}
            ],
        },
    )
    with pytest.raises(ValueError, match="invalid_label_axis"):
        store.save_decisions(
            store.consume_preview(preview["preview_id"], "review"),
            [
                {
                    "item_id": item["id"],
                    "axis": "music_family",
                    "action": "correct",
                    "label_ids": ["salsa_romantica"],
                }
            ],
        )

    store.record_analysis_outcome(
        {
            "item_id": item["id"],
            "status": "abstained",
            "reason": "out_of_domain",
            "feature": {"embedding": [0.1, 0.2], "cache_key": "cache"},
        }
    )
    detail = store.get_item(item["id"])
    assert detail["analysis"]["state"] == "abstained"
    assert "embedding" not in detail["analysis"]["details"]["feature"]
    page = store.list_items(
        cursor=None,
        limit=10,
        filters={"analysis_states": ["abstained"]},
        sort="title:asc",
    )
    assert [row["id"] for row in page["items"]] == [item["id"]]


def test_write_intent_is_durable_before_publish_and_reconcilable(store):
    item = add(store, "Intent")
    store.record_write_intent(
        write_id="write-1",
        item_id=item["id"],
        intent={
            "source_path": "/library/Intent.mp3",
            "source_sha256": "before",
            "backup_path": "/backup/Intent",
            "fields": {"genre": "Salsa"},
        },
    )
    pending = store.unfinished_write_intents()
    assert pending[0]["write_id"] == "write-1"
    resolved = store.reconcile_write_intent(
        write_id="write-1", status="written", after_sha256="after"
    )
    assert resolved["status"] == "written"
    assert store.unfinished_write_intents() == []
