import time
import threading
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def v2_client(tmp_path, monkeypatch):
    monkeypatch.setenv("IDJLM_USER_DATA_DIR", str(tmp_path / "state"))
    from app import create_app

    application = create_app()
    application.config.update(TESTING=True)
    return application.test_client()


def _wait_for_job(client, job_id):
    for _ in range(100):
        response = client.get(f"/api/v2/jobs/{job_id}")
        assert response.status_code == 200
        job = response.get_json()
        if job["state"] in {"completed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def _scope(item_id):
    return {"selection": "explicit", "item_ids": [item_id]}


def test_additive_import_preserves_decision_across_folders_and_rescan(
    v2_client, tmp_path
):
    folder_a, folder_b = tmp_path / "A", tmp_path / "B"
    folder_a.mkdir()
    folder_b.mkdir()
    (folder_a / "a.mp3").write_bytes(b"a placeholder audio file")
    (folder_b / "b.mp3").write_bytes(b"b placeholder audio file")

    first = v2_client.post(
        "/api/v2/library/import-jobs", json={"folder_path": str(folder_a)}
    )
    assert first.status_code == 202
    assert (
        _wait_for_job(v2_client, first.get_json()["job_id"])["counts"]["completed"] == 1
    )
    library = v2_client.get("/api/v2/library/items").get_json()
    assert library["total"] == 1
    a_id = library["items"][0]["id"]

    taxonomy = v2_client.get("/api/v2/taxonomy").get_json()
    saved = v2_client.put(
        "/api/v2/taxonomy",
        json={
            "document": taxonomy["document"],
            "expected_revision": taxonomy["revision"],
        },
    )
    assert saved.status_code == 200
    preview = v2_client.post(
        "/api/v2/reviews/previews", json={"scope": _scope(a_id)}
    ).get_json()
    decision = v2_client.post(
        "/api/v2/reviews/decisions",
        json={
            "preview_id": preview["preview_id"],
            "decisions": [
                {
                    "item_id": a_id,
                    "axis": "music_family",
                    "action": "correct",
                    "label_ids": ["salsa"],
                }
            ],
        },
    )
    assert decision.status_code == 200

    second = v2_client.post(
        "/api/v2/library/import-jobs", json={"folder_path": str(folder_b)}
    )
    assert second.status_code == 202
    _wait_for_job(v2_client, second.get_json()["job_id"])
    rescan = v2_client.post(
        "/api/v2/library/import-jobs", json={"folder_path": str(folder_a)}
    )
    assert rescan.status_code == 202
    _wait_for_job(v2_client, rescan.get_json()["job_id"])

    library = v2_client.get("/api/v2/library/items").get_json()
    assert library["total"] == 2
    detail = v2_client.get(f"/api/v2/items/{a_id}").get_json()
    assert detail["axes"]["music_family"]["decision"]["label_ids"] == ["salsa"]

    # A source folder cannot double as an export staging root.  Surface this
    # ordinary picker mistake as an actionable preflight error, never a 500.
    unsafe_destination = v2_client.post(
        "/api/v2/exports/previews",
        json={"scope": _scope(a_id), "destination": str(folder_a)},
    )
    assert unsafe_destination.status_code == 400
    assert unsafe_destination.get_json() == {
        "error": "destination_contains_source",
        "detail": "Choose a staging folder outside the source music folders",
    }


def test_mutation_guards_reject_empty_scope_bypass_and_cross_site(v2_client, tmp_path):
    path = tmp_path / "track.mp3"
    path.write_bytes(b"placeholder")
    imported = v2_client.post(
        "/api/v2/library/import-jobs", json={"folder_path": str(tmp_path)}
    )
    _wait_for_job(v2_client, imported.get_json()["job_id"])
    item_id = v2_client.get("/api/v2/library/items").get_json()["items"][0]["id"]

    assert (
        v2_client.post(
            "/api/v2/writes/previews",
            json={"scope": {"selection": "explicit", "item_ids": []}},
        ).status_code
        == 400
    )
    assert (
        v2_client.post(
            "/api/v2/jobs", json={"kind": "write", "scope": _scope(item_id)}
        ).status_code
        == 409
    )
    assert (
        v2_client.post(
            "/api/v2/writes/previews",
            json={"scope": _scope(item_id)},
            headers={"Origin": "https://example.invalid"},
        ).status_code
        == 403
    )
    assert (
        v2_client.post(
            "/api/v2/writes/previews", data="{}", content_type="text/plain"
        ).status_code
        == 415
    )
    assert v2_client.post("/api/review/write", json={}).status_code == 410
    assert (
        v2_client.post(
            "/api/organise/backups/no-such-legacy-backup/restore", json={}
        ).status_code
        == 410
    )


def test_model_setup_is_gated_when_audio_runtime_is_not_bundled(v2_client, monkeypatch):
    from app.routes import v2_routes
    from app.services import audio_classification

    monkeypatch.setattr(
        audio_classification,
        "audio_runtime_status",
        lambda: {"available": False, "reason": "missing runtime", "missing": ["torch"]},
    )
    with v2_routes._workers_lock:
        v2_routes._model_status_cache.update(
            {"checked_at": 0.0, "value": {"state": "unknown"}}
        )
    model = v2_client.get("/api/v2/models").get_json()["model"]
    assert model["state"] == "runtime_unavailable"
    refused = v2_client.post("/api/v2/models/jobs", json={"action": "install"})
    assert (
        refused.status_code == 409
        and refused.get_json()["error"] == "runtime_unavailable"
    )
    with v2_routes._workers_lock:
        v2_routes._model_status_cache.update(
            {"checked_at": 0.0, "value": {"state": "unknown"}}
        )


def test_review_preview_is_single_use(v2_client, tmp_path):
    (tmp_path / "track.mp3").write_bytes(b"placeholder")
    imported = v2_client.post(
        "/api/v2/library/import-jobs", json={"folder_path": str(tmp_path)}
    )
    _wait_for_job(v2_client, imported.get_json()["job_id"])
    item_id = v2_client.get("/api/v2/library/items").get_json()["items"][0]["id"]
    taxonomy = v2_client.get("/api/v2/taxonomy").get_json()
    assert (
        v2_client.put(
            "/api/v2/taxonomy",
            json={
                "document": taxonomy["document"],
                "expected_revision": taxonomy["revision"],
            },
        ).status_code
        == 200
    )
    preview = v2_client.post(
        "/api/v2/reviews/previews", json={"scope": _scope(item_id)}
    ).get_json()
    first = v2_client.post(
        "/api/v2/reviews/decisions",
        json={
            "preview_id": preview["preview_id"],
            "decisions": [
                {
                    "item_id": item_id,
                    "axis": "music_family",
                    "action": "correct",
                    "label_ids": ["salsa"],
                }
            ],
        },
    )
    assert first.status_code == 200
    repeated = v2_client.post(
        "/api/v2/reviews/decisions",
        json={
            "preview_id": preview["preview_id"],
            "decisions": [
                {
                    "item_id": item_id,
                    "axis": "music_family",
                    "action": "correct",
                    "label_ids": ["salsa"],
                }
            ],
        },
    )
    assert repeated.status_code == 409


def test_fresh_default_taxonomy_allows_first_manual_correction_and_stales_write_preview(
    v2_client, tmp_path
):
    (tmp_path / "track.mp3").write_bytes(b"placeholder")
    imported = v2_client.post(
        "/api/v2/library/import-jobs", json={"folder_path": str(tmp_path)}
    )
    _wait_for_job(v2_client, imported.get_json()["job_id"])
    item_id = v2_client.get("/api/v2/library/items").get_json()["items"][0]["id"]
    review = v2_client.post(
        "/api/v2/reviews/previews", json={"scope": _scope(item_id)}
    ).get_json()
    corrected = v2_client.post(
        "/api/v2/reviews/decisions",
        json={
            "preview_id": review["preview_id"],
            "decisions": [
                {
                    "item_id": item_id,
                    "axis": "music_family",
                    "action": "correct",
                    "label_ids": ["salsa"],
                }
            ],
        },
    )
    assert corrected.status_code == 200

    write = v2_client.post(
        "/api/v2/writes/previews", json={"scope": _scope(item_id), "fields": ["genre"]}
    ).get_json()
    taxonomy = v2_client.get("/api/v2/taxonomy").get_json()
    changed = dict(taxonomy["document"])
    changed["version"] = 2
    assert (
        v2_client.put(
            "/api/v2/taxonomy",
            json={"document": changed, "expected_revision": taxonomy["revision"]},
        ).status_code
        == 200
    )
    stale = v2_client.post(
        "/api/v2/writes/commit",
        json={"preview_id": write["preview_id"], "confirm": True},
    )
    assert stale.status_code == 409


def test_resume_pages_past_250_completed_items_without_reclassification(tmp_path):
    from app.routes import v2_routes
    from app.services.v2_store import V2Store

    store = V2Store(str(tmp_path / "jobs.sqlite"))
    ids = []
    for index in range(300):
        item = store.upsert_item(
            path=f"/library/{index}.mp3", original={"title": str(index)}
        )
        ids.append(item["id"])
    job = store.create_job("classify", {"item_ids": ids}, {"model_id": "fake"})
    store.set_job_state(job["job_id"], "running")
    for item_id in ids[:250]:
        store.update_job_item(job["job_id"], item_id, "completed")

    calls = []

    class Result:
        def __init__(self, item_id):
            self.item_id = item_id

        def to_service_payload(self):
            return {
                "item_id": self.item_id,
                "status": "proposed",
                "axes": {
                    "music_family": {"label_ids": ["salsa"], "status": "proposed"}
                },
                "model": {},
                "feature_version": "test",
            }

    class Engine:
        def classify_item(self, item_id, path, model_id):
            calls.append(item_id)
            return Result(item_id)

    v2_routes._run_classify_job(store, job["job_id"], Engine())
    assert len(calls) == 50
    assert store.job(job["job_id"])["counts"]["completed"] == 300


def test_audio_scheduler_serializes_two_queued_jobs(monkeypatch):
    from app.routes import v2_routes

    active, maximum, finished = [0], [0], threading.Event()
    calls = []

    class Store:
        pass

    store = Store()

    def fake_run(received_store, job_id, engine):
        assert received_store is store
        active[0] += 1
        maximum[0] = max(maximum[0], active[0])
        time.sleep(0.03)
        calls.append(job_id)
        active[0] -= 1
        with v2_routes._workers_lock:
            v2_routes._workers.discard(job_id)
        if len(calls) == 2:
            finished.set()

    monkeypatch.setattr(v2_routes, "_run_classify_job", fake_run)
    assert v2_routes._start_classify_worker("serial-one", store)
    assert v2_routes._start_classify_worker("serial-two", store)
    assert finished.wait(2)
    assert maximum == [1]


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg is required for disposable MP3 fixture",
)
def test_api_verified_write_restore_and_export_readback(v2_client, tmp_path):
    """Exercise the real route/worker contracts, not only helper functions."""
    source = tmp_path / "journey.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100:duration=0.25",
            "-c:a",
            "libmp3lame",
            str(source),
        ],
        check=True,
    )
    original_bytes = source.read_bytes()
    imported = v2_client.post(
        "/api/v2/library/import-jobs", json={"folder_path": str(tmp_path)}
    )
    assert (
        _wait_for_job(v2_client, imported.get_json()["job_id"])["state"] == "completed"
    )
    item_id = v2_client.get("/api/v2/library/items").get_json()["items"][0]["id"]

    family = v2_client.post(
        "/api/v2/reviews/previews",
        json={"scope": _scope(item_id), "fields": ["music_family"]},
    ).get_json()
    assert (
        v2_client.post(
            "/api/v2/reviews/decisions",
            json={
                "preview_id": family["preview_id"],
                "decisions": [
                    {
                        "item_id": item_id,
                        "axis": "music_family",
                        "action": "correct",
                        "label_ids": ["salsa"],
                    }
                ],
            },
        ).status_code
        == 200
    )
    style = v2_client.post(
        "/api/v2/reviews/previews", json={"scope": _scope(item_id), "fields": ["style"]}
    ).get_json()
    assert (
        v2_client.post(
            "/api/v2/reviews/decisions",
            json={
                "preview_id": style["preview_id"],
                "decisions": [
                    {
                        "item_id": item_id,
                        "axis": "style",
                        "action": "correct",
                        "label_ids": ["salsa_romantica"],
                    }
                ],
            },
        ).status_code
        == 200
    )

    preview = v2_client.post(
        "/api/v2/writes/previews",
        json={"scope": _scope(item_id), "fields": ["genre", "comment"]},
    ).get_json()
    assert preview["storage"]["enough_space"] is True
    write = v2_client.post(
        "/api/v2/writes/commit",
        json={"preview_id": preview["preview_id"], "confirm": True},
    )
    assert write.status_code == 202
    assert (
        _wait_for_job(v2_client, write.get_json()["job_id"])["counts"]["completed"] == 1
    )
    history = v2_client.get("/api/v2/writes").get_json()["items"]
    assert history[0]["status"] == "written"

    restore_preview = v2_client.post(
        "/api/v2/restores/previews", json={"write_id": history[0]["write_id"]}
    )
    assert restore_preview.status_code == 201
    restored = v2_client.post(
        "/api/v2/restores/commit",
        json={"preview_id": restore_preview.get_json()["preview_id"], "confirm": True},
    )
    assert restored.status_code == 200
    assert source.read_bytes() == original_bytes

    staging = tmp_path / "staging"
    export_preview = v2_client.post(
        "/api/v2/exports/previews",
        json={
            "scope": _scope(item_id),
            "destination": str(staging),
            "profile": {"name": "djay_extended_genre"},
            "route": "direct_cable",
        },
    )
    assert export_preview.status_code == 201
    exported = v2_client.post(
        "/api/v2/exports/commit",
        json={"preview_id": export_preview.get_json()["preview_id"], "confirm": True},
    )
    assert exported.status_code == 202
    assert (
        _wait_for_job(v2_client, exported.get_json()["job"]["job_id"])["counts"][
            "completed"
        ]
        == 1
    )
    manifest = v2_client.get(
        f"/api/v2/exports/{exported.get_json()['export']['export_id']}"
    ).get_json()["manifest"]
    assert manifest[0]["verified_fields"] == {
        "genre": "Salsa, Salsa Romántica",
        "comment": "Salsa Romántica",
    }
    # A common Music/TaggedExports layout must not import its own staged copy.
    rescan = v2_client.post(
        "/api/v2/library/import-jobs", json={"folder_path": str(tmp_path)}
    )
    assert _wait_for_job(v2_client, rescan.get_json()["job_id"])["state"] == "completed"
    assert v2_client.get("/api/v2/library/items").get_json()["total"] == 1

    # A tag-only source edit keeps the path-backed item/decisions but must
    # turn its existing owned staged copy into an explicit replacement.
    from app.services.safe_tag_writer import write_mp3

    write_mp3(str(source), {"genre": "Retagged source", "comment": "source edit"})
    retag_scan = v2_client.post(
        "/api/v2/library/import-jobs", json={"folder_path": str(tmp_path)}
    )
    assert (
        _wait_for_job(v2_client, retag_scan.get_json()["job_id"])["state"]
        == "completed"
    )
    changed = v2_client.post(
        "/api/v2/exports/previews",
        json={
            "scope": _scope(item_id),
            "destination": str(staging),
            "profile": {"name": "djay_extended_genre"},
            "route": "direct_cable",
        },
    )
    assert changed.status_code == 201
    assert changed.get_json()["report"]["manifest"][0]["status"] == "changed"
