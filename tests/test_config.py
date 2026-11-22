"""App creation and route registration tests."""
import pytest

from app import create_app


def test_create_app_does_not_raise():
    """create_app() returns a Flask instance without raising."""
    app = create_app()
    assert app is not None
    assert app.config is not None


def test_startup_recovers_interrupted_jobs_once_before_requests(tmp_path, monkeypatch):
    from app import get_v2_store
    from app.services.v2_store import V2Store
    from app.utils.paths import user_data_path

    monkeypatch.setenv("IDJLM_USER_DATA_DIR", str(tmp_path / "state"))
    (tmp_path / "state").mkdir()
    prior = V2Store(user_data_path("tracks.db"))
    job = prior.create_job("import", {"item_ids": []}, {})
    prior.set_job_state(job["job_id"], "running")
    prior._conn.close()
    calls = []
    recover = V2Store.recover_interrupted_jobs

    def counted(self):
        calls.append(self)
        return recover(self)

    monkeypatch.setattr(V2Store, "recover_interrupted_jobs", counted)
    app = create_app()

    assert len(calls) == 1
    assert get_v2_store().job(job["job_id"])["state"] == "interrupted"
    assert app.test_client().get(f"/api/v2/jobs/{job['job_id']}").status_code == 200
    assert len(calls) == 1


def test_expected_blueprint_routes_registered():
    """All expected API prefixes are present in the URL map."""
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    # Every registered blueprint should contribute at least one route
    expected_routes = [
        "/api/import",
        "/api/tracks",
        "/api/review/approve",
        "/api/taxonomy",
        "/api/settings",
        "/api/audio",
        "/api/session/exists",
        "/api/watch/status",
        "/api/export/m3u",
        "/api/duplicates/scan",
        "/api/progress/",           # prefix match -- has op_id param
        "/api/setlist",
        "/api/setplan/arcs",
        "/api/analyze/latin",
        "/api/library/health",
        "/api/validate/keys",
        "/api/tags",                # custom tags CRUD (TXXX backend)
    ]

    for route in expected_routes:
        assert any(r.startswith(route) for r in rules), (
            f"Expected route starting with '{route}' not found. "
            f"Registered rules: {sorted(rules)}"
        )
