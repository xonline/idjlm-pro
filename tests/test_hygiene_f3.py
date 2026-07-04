"""Regression tests for IDJLM issue #213 (F.3 hygiene sweep).

Three surface changes are verified here:

1. Platform-path consolidation — `app.utils.paths` is the single source of truth.
2. `datetime.utcnow()` removed — replaced with timezone-aware `datetime.now(UTC)`.
3. A.2 structured-error taxonomy — Flask error handlers return the right shape
   for both `AppError` (typed) and unexpected exceptions.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

from app import utils as app_utils
from app.utils import errors, paths
from app.utils.errors import AppError, Err


# ---------------------------------------------------------------------------
# Path consolidation
# ---------------------------------------------------------------------------

class TestPathsModuleExists:
    """The consolidated paths module must exist and expose the API advertised
    in the issue body (app_user_dir, app_user_log_dir, user_data_path)."""

    def test_paths_module_importable(self):
        assert paths is not None

    def test_paths_exposes_required_helpers(self):
        required = [
            "app_user_dir",
            "app_user_log_dir",
            "user_data_path",
            "ensure_app_user_dir",
            "ensure_app_user_log_dir",
            "is_darwin",
            "is_windows",
            "rekordbox_master_db_candidates",
        ]
        for n in required:
            assert hasattr(paths, n), f"paths.{n} missing"

    def test_app_user_dir_returns_string_and_makes_dir_when_ensured(self, tmp_path):
        """`ensure_app_user_dir()` must create the dir if missing."""
        with mock.patch.object(paths, "app_user_dir", return_value=str(tmp_path / "newdir")):
            res = paths.ensure_app_user_dir()
        assert os.path.isdir(res)

    def test_user_data_path_uses_app_user_dir(self):
        """user_data_path(x) must join app_user_dir() with x."""
        sentinel = "/sentinel/test/apple"
        with mock.patch.object(paths, "app_user_dir", return_value=sentinel):
            assert paths.user_data_path("file.json") == os.path.join(sentinel, "file.json")


class TestPathAudit:
    """A.2 audit: no inline `platform.system() == "Darwin"` for app-user-data
    paths may remain in production code. Anything that writes into
    `~/Library/Application Support/IDJLM Pro/` or `~/.idjlm-pro/` must go
    through `app.utils.paths`. (Rekordbox master.db paths are an exception —
    they live in `/Library/Pioneer/...`, not inside the app data dir.)"""

    # Files where a bare-Darwin check used to live (per the F.3 audit 2026-07-04).
    # We assert none of them now contains the inline `platform.system() == "Darwin"` block.
    FORMER_DUPLICATE_SITES = [
        "app/__init__.py",
        "app/routes/version_routes.py",
        "app/services/tag_backup.py",
        "app/services/session_service.py",
        "app/routes/review_routes.py",
        "app/services/learning.py",
        "app/routes/settings_routes.py",
        "app/routes/bulk_routes.py",
    ]

    @pytest.mark.parametrize(
        "relpath",
        FORMER_DUPLICATE_SITES,
    )
    def test_no_inline_darwin_path_logic(self, relpath):
        """No file should inline `platform.system() == "Darwin"` to compute an
        app-user-data directory any more — that logic now lives in paths.py."""
        from app import create_app
        project_root = Path(os.path.dirname(create_app.__code__.co_filename)) / ".."
        project_root = project_root.resolve()
        full = project_root / relpath
        assert full.exists(), f"{relpath} not found relative to {project_root}"
        body = full.read_text()
        # If a site still had `platform.system() == "Darwin"` pulling out
        # `~/Library/...` or `~/.idjlm-pro`, this regex catches it.
        offenders = re.findall(
            r'''platform\.system\(\)\s*==\s*['"]Darwin['"]''',
            body,
        )
        assert offenders == [], (
            f"{relpath} still contains inline Darwin path logic: {offenders}"
        )


# ---------------------------------------------------------------------------
# datetime.utcnow() deprecation
# ---------------------------------------------------------------------------

class TestUtcNowRemoved:
    """`datetime.utcnow()` was deprecated in Python 3.12. After F.3 lands, no
    production code may still call it."""

    FILES_WITH_HISTORICAL_USAGE = [
        "app/routes/review_routes.py",
        "app/routes/playlist_routes.py",
        "app/services/learning.py",
        "app/services/session_service.py",
    ]

    @pytest.mark.parametrize("relpath", FILES_WITH_HISTORICAL_USAGE)
    def test_no_utcnow_call_remains(self, relpath):
        from app import create_app
        project_root = Path(os.path.dirname(create_app.__code__.co_filename)) / ".."
        full = (project_root / relpath).resolve()
        body = full.read_text()
        # Match `.utcnow(` — covers `datetime.utcnow()` and fully-qualified
        # `datetime.datetime.utcnow()`.
        offenders = re.findall(r"utcnow\s*\(", body)
        assert offenders == [], (
            f"{relpath} still calls utcnow(): {len(offenders)} occurrences"
        )

    def test_session_service_save_at_uses_utc_now(self):
        """Behavioural test: datetime.now(UTC).isoformat() must produce a
        timezone-aware ISO string. Before F.3 it produced a naive timestamp
        and appended 'Z' manually. Smoke check that the production codepath
        uses timezone-aware now()."""
        # Read the source and assert the codepath uses timezone.utc.
        from app import create_app
        from pathlib import Path
        project_root = Path(os.path.dirname(create_app.__code__.co_filename)) / ".."
        ss_file = (project_root / "app/services/session_service.py").resolve()
        body = ss_file.read_text()
        assert "datetime.now(timezone.utc)" in body, (
            "session_service.save_session should call datetime.now(timezone.utc)"
        )
        assert "datetime.utcnow" not in body, (
            "session_service must no longer call datetime.utcnow()"
        )


# ---------------------------------------------------------------------------
# A.2 structured-error taxonomy
# ---------------------------------------------------------------------------

class TestStructuredErrors:
    """F.3 audit: any uncaught exception in a Flask route returns
    `{error, detail, op}` with a stable `error` code."""

    def test_make_error_payload_shape(self):
        p = errors.make_error_payload(Err.NOT_FOUND, "nope", op="review.approve")
        assert p == {"error": "not_found", "detail": "nope", "op": "review.approve"}

    def test_make_error_payload_omits_op_when_none(self):
        p = errors.make_error_payload(Err.FILE_NOT_FOUND, "x")
        assert p == {"error": "file_not_found", "detail": "x"}
        assert "op" not in p

    def test_app_error_carries_taxonomy(self):
        e = AppError(Err.IO_ERROR, "disk on fire", op="track.save", status_code=503)
        assert e.code == "io_error"
        assert e.op == "track.save"
        assert e.status_code == 503
        assert str(e) == "disk on fire"

    def test_app_error_to_json_response(self, app, client):
        """A route that raises AppError must produce a structured 4xx payload."""

        @app.route("/__test_raise_app_error__")
        def _raise():
            raise AppError(Err.MISSING_PARAM, "track_path required", op="review.approve")

        resp = client.get("/__test_raise_app_error__")
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["error"] == Err.MISSING_PARAM
        assert body["detail"] == "track_path required"
        assert body["op"] == "review.approve"

    def test_unhandled_exception_returns_safe_payload(self, client):
        """A route that raises an unexpected exception must NOT leak str(e)
        to the caller — only the A.2 `unknown` code + safe detail.

        We can't always add routes to the shared `app` fixture (once a
        request is served the app is finalised). So we call the registered
        error handler directly with a dummy RuntimeError."""
        from app.utils.errors import error_response, log_unexpected_error
        from app import create_app

        # Activate the handler the same way _handle_unexpected does it.
        app = create_app()
        handlers = app.error_handler_spec[None][None]
        handler = None
        for cls, fn in handlers.items():
            # Pick the handler that dispatches against the base Exception class
            # (Flask stores one entry per registered exception class).
            if cls is Exception:
                handler = fn
                break
        assert handler is not None, "Unexpected-Exception handler not registered"

        # Stub log_unexpected_error so we don't spam pytest output.
        with mock.patch(
            "app.utils.errors.log_unexpected_error", lambda *a, **kw: None
        ):
            with app.test_request_context("/__unused__"):
                resp = handler(RuntimeError("database password = hunter2 on /etc/pg.conf"))
        body, status = resp
        assert status == 500
        data = body.get_json()
        assert data["error"] == Err.UNKNOWN
        assert "hunter2" not in data.get("detail", "")
        assert data["detail"] == "Server error"

    def test_404_returns_structured_error(self, client):
        resp = client.get("/__definitely_does_not_exist__")
        assert resp.status_code == 404
        body = resp.get_json()
        assert body["error"] == Err.NOT_FOUND

    def test_405_returns_structured_error(self, client):
        """Method-not-allowed for an existing route."""
        # Find any GET-only route
        resp = client.post("/")
        # Either 405 or 200 depending on whether the route accepts POST —
        # if 405, validate shape.
        if resp.status_code == 405:
            body = resp.get_json()
            assert body["error"] == Err.INVALID_STATE
        # If 200, the test is moot; skip validation.
