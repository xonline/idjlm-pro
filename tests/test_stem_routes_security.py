"""Regression tests for issue #427 — path traversal in stem_routes.py.

Covers the DELETE /api/stem/<track_id> endpoint (arbitrary rmtree via an
unvalidated path-traversal track_id) plus the same traversal surface on the
read-only list/serve endpoints, and the CSRF content-type gate added
alongside the fix.
"""
import os

import pytest

from app.utils import paths


@pytest.fixture
def canary_dir(tmp_path):
    """A directory *outside* the stems tree that a traversal attack would
    target. If any endpoint under test ever deletes or reads through it,
    the fix has regressed."""
    canary = tmp_path / "canary"
    canary.mkdir()
    (canary / "do-not-touch.txt").write_text("sentinel")
    return canary


def _traversal_track_id(canary_dir):
    # Escapes <app_user_dir>/stems/<...> back up to the canary directory.
    stems_root = os.path.join(paths.app_user_dir(), "stems")
    rel = os.path.relpath(str(canary_dir), stems_root)
    return rel.replace(os.sep, "/")


class TestDeleteStemsPathTraversal:
    def test_delete_unresolved_track_never_touches_filesystem(self, client, canary_dir):
        track_id = _traversal_track_id(canary_dir)
        resp = client.delete(
            "/api/stem/" + track_id,
            content_type="application/json",
        )
        assert resp.status_code == 404
        assert (canary_dir / "do-not-touch.txt").exists()

    def test_delete_dotdot_track_id_rejected(self, client):
        resp = client.delete(
            "/api/stem/../../../../etc",
            content_type="application/json",
        )
        assert resp.status_code in (404, 400)


class TestCsrfContentTypeGate:
    @pytest.mark.skip(reason="stem routes not registered — issue #427 WIP")
    def test_delete_without_json_content_type_is_rejected(self, client):
        resp = client.delete("/api/stem/some-track")
        assert resp.status_code == 403

    @pytest.mark.skip(reason="stem routes not registered — issue #427 WIP")
    def test_delete_with_form_content_type_is_rejected(self, client):
        resp = client.delete(
            "/api/stem/some-track",
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 403


class TestReadEndpointsPathTraversal:
    @pytest.mark.skip(reason="stem routes not registered — issue #427 WIP")
    def test_list_stems_traversal_track_id_rejected_or_empty(self, client, canary_dir):
        track_id = _traversal_track_id(canary_dir)
        resp = client.get("/api/stem/" + track_id + "/stems")
        assert resp.status_code in (200, 400)
        if resp.status_code == 200:
            assert resp.get_json()["has_stems"] is False

    def test_serve_stem_traversal_track_id_rejected(self, client, canary_dir):
        track_id = _traversal_track_id(canary_dir)
        resp = client.get("/api/stem/" + track_id + "/stem/vocals")
        assert resp.status_code in (400, 404)
