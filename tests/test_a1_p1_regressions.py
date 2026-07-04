"""Regression tests for BUGS-FOUND.md P1 bugs (issue #196, A.1).

Each test must FAIL if the corresponding bug regresses. Source:
    ~/projects/idjlm/tests/BUGS-FOUND.md (initial bug report)
    ~/.claude/plans/2026-07-04-idjlm-backend-plan.md (Phase A.1)

P1 bug summary:
    BUG-001   Backend route /api/classify/start does not exist;
              the real route is /api/classify.
    BUG-002   stat-analyzed (American) vs stat-analysed (British) DOM id mismatch
              in navigation.js vs templates/index.html.
    BUG-003   health-analyzed vs health-analysed DOM id mismatch in pipeline.js
              vs templates/index.html.
    BUG-004   review.js bulk-approve handler called .forEach on the JSON object
              {approved: N} returned by /api/review/bulk-approve.
    BUG-005   review.js write-tags handler called .forEach on the async op_id
              JSON {op_id, total} returned by /api/review/write.

These tests assert the *currently correct* state and will fail loudly if any of
the five bugs regresses. The bug report itself is kept in BUGS-FOUND.md as a
historical record.
"""
import os
import re

import pytest

# ---------------------------------------------------------------------------
# BUG-001  Backend must expose /api/classify (not /api/classify/start)
# ---------------------------------------------------------------------------
class TestClassifyRouteExists:
    """The async classification endpoint is /api/classify.

    Background (BUGS-FOUND.md):
        Bug claimed:   POST /api/classify/start returned 404.
        Reality:       POST /api/classify exists.  /api/classify/start never did.
        Caller (library.js:141) hits /api/classify correctly.

    These tests fail if anyone renames the route to /api/classify/start again,
    or if anyone tries to ship a "matched-route" that only exposes the
    not-yet-implemented /api/classify/start path.
    """

    def test_classify_route_accepts_post(self, client):
        """POST /api/classify must respond 202 (accepted) or 5xx — never 404."""
        resp = client.post("/api/classify", json={})
        assert resp.status_code != 404, (
            "/api/classify should be a valid route. Got 404 — did someone "
            "rename it to /api/classify/start?"
        )
        assert resp.status_code in (202, 400, 429, 500), (
            f"Unexpected status {resp.status_code} for /api/classify"
        )

    def test_classify_start_route_does_not_exist(self, client):
        """POST /api/classify/start must be 404 (it was never implemented).

        Locks in the BUG-001 / BUG-012 fix: route is /api/classify only.
        """
        resp = client.post("/api/classify/start", json={})
        assert resp.status_code == 404, (
            "If /api/classify/start exists, callers will silently get a "
            "different code path. Must stay 404."
        )

    def test_response_shape_op_id_total(self, client):
        """Successful /api/classify returns {op_id, total}."""
        resp = client.post("/api/classify", json={"track_paths": []})
        if resp.status_code == 202:
            data = resp.get_json()
            assert "op_id" in data, (
                "Successful /api/classify must return {op_id, total}."
            )
            assert "total" in data


# ---------------------------------------------------------------------------
# BUG-002  navigation.js stat-* DOM ids must match templates/index.html
# ---------------------------------------------------------------------------
class TestNavigationStatIdsMatch:
    """JS getElementById('stat-*') must equal HTML id='stat-*' exactly.

    Bug BUG-002: navigation.js read stat-analyzed (American) but the template
    used stat-analysed (British). Stats bar never updated.
    """

    STAT_IDS = ("stat-total", "stat-analysed", "stat-classified", "stat-approved")

    def _read_navigation_js(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "app", "static", "modules",
            "navigation.js",
        )
        with open(path) as f:
            return f.read()

    def _read_template(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "index.html",
        )
        with open(path) as f:
            return f.read()

    @pytest.mark.parametrize("dom_id", STAT_IDS)
    def test_navigation_js_references_id(self, dom_id):
        """Every stat-* id in JS must be referenced via getElementById or el()."""
        js = self._read_navigation_js()
        # Match getElementById('...') OR the el('...') helper defined in this file.
        # The latter resolves to getElementById at runtime.
        pattern = (
            r"(?:getElementById\(['\"]|el\(['\"])"
            + re.escape(dom_id)
            + r"['\"]"
        )
        assert re.search(pattern, js), (
            f"navigation.js does not reference '{dom_id}' via getElementById "
            or f"el(). Bug regression — stats will silently not update."
        )

    @pytest.mark.parametrize("dom_id", STAT_IDS)
    def test_template_contains_id(self, dom_id):
        """Every stat-* id must exist in templates/index.html."""
        html = self._read_template()
        assert f'id="{dom_id}"' in html, (
            f"templates/index.html missing id=\"{dom_id}\""
        )

    def test_no_american_stat_analyzed_in_navigation_js(self):
        """BUG-002 regression guard.

        The old buggy code used 'stat-analyzed' (American spelling). Lock it out.
        """
        js = self._read_navigation_js()
        assert "stat-analyzed" not in js, (
            "BUG-002 regression: navigation.js must not reference 'stat-analyzed' "
            "(American). Use 'stat-analysed' (British) to match templates/index.html."
        )


# ---------------------------------------------------------------------------
# BUG-003  pipeline.js health-* DOM ids must match templates/index.html
# ---------------------------------------------------------------------------
class TestPipelineHealthIdsMatch:
    """JS getElementById('health-*') must equal HTML id='health-*' exactly.

    Bug BUG-003: pipeline.js read health-analyzed (American), template used
    health-analysed (British). Stats & Library tab threw TypeError on load.
    """

    HEALTH_IDS = (
        "health-total", "health-analysed", "health-classified",
        "health-approved", "health-written", "health-duplicates",
    )

    def _read_pipeline_js(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "app", "static", "modules",
            "pipeline.js",
        )
        with open(path) as f:
            return f.read()

    def _read_template(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "index.html",
        )
        with open(path) as f:
            return f.read()

    @pytest.mark.parametrize("dom_id", HEALTH_IDS)
    def test_pipeline_js_references_id(self, dom_id):
        """Every health-* id referenced in JS must match a getElementById call."""
        js = self._read_pipeline_js()
        assert re.search(
            r"getElementById\(['\"]" + re.escape(dom_id) + r"['\"]\)",
            js,
        ), (
            f"pipeline.js does not reference getElementById('{dom_id}')"
        )

    @pytest.mark.parametrize("dom_id", HEALTH_IDS)
    def test_template_contains_id(self, dom_id):
        """Every health-* id must exist in templates/index.html."""
        html = self._read_template()
        assert f'id="{dom_id}"' in html, (
            f"templates/index.html missing id=\"{dom_id}\""
        )

    def test_no_american_health_analyzed_in_pipeline_js(self):
        """BUG-003 regression guard."""
        js = self._read_pipeline_js()
        assert "health-analyzed" not in js, (
            "BUG-003 regression: pipeline.js must not reference 'health-analyzed' "
            "(American). Use 'health-analysed' (British) to match templates/index.html."
        )


# ---------------------------------------------------------------------------
# BUG-004  review.js bulk-approve must NOT call .forEach() on the JSON response
# ---------------------------------------------------------------------------
class TestReviewBulkApproveContract:
    """/api/review/bulk-approve returns {approved:int} — never an array.

    Bug BUG-004: review.js called result.forEach() on the response. That
    threw `TypeError: result.forEach is not a function`.

    This guard:
      1) Asserts the API contract (backend returns object, not array).
      2) Asserts review.js does NOT contain a result.forEach pattern.
    """

    def test_bulk_approve_returns_object_with_approved_count(self, client):
        """/api/review/bulk-approve returns {approved: int}, never a list."""
        resp = client.post("/api/review/bulk-approve", json={"min_confidence": 80})
        assert resp.status_code == 200, (
            f"Expected 200 from /api/review/bulk-approve, got {resp.status_code}"
        )
        data = resp.get_json()
        assert isinstance(data, dict), (
            f"/api/review/bulk-approve must return a JSON object, got {type(data).__name__}"
        )
        assert "approved" in data, (
            "Response shape changed: must contain key 'approved'."
        )
        assert isinstance(data["approved"], int), (
            f"'approved' must be int, got {type(data['approved']).__name__}"
        )

    def test_review_js_has_no_result_forEach(self):
        """Belt-and-braces: review.js must not iterate the response as an array."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "app", "static", "modules",
            "review.js",
        )
        with open(path) as f:
            content = f.read()

        # The BUG-004 / BUG-005 patterns both fail this assertion:
        #   `result.forEach` or `res.forEach` where res is the API reply.
        for bad in ("result.forEach", "res.forEach", "response.forEach"):
            assert bad not in content, (
                f"BUG-004/005 regression: review.js still contains `{bad}` — "
                "this throws TypeError on a JSON object response."
            )


# ---------------------------------------------------------------------------
# BUG-005  review.js write-tags must consume async op_id response (no forEach)
# ---------------------------------------------------------------------------
class TestReviewWriteTagsContract:
    """/api/review/write returns {op_id, total} async — never an array.

    Bug BUG-005: review.js called result.forEach on the async 202 response.
    Same root cause as BUG-004 but a separate code path. The bug is silenced
    by the outer try/catch.

    This test:
      1) Asserts the backend contract.
      2) Asserts review.js never blindly .forEach's the write response.
    """

    def test_write_returns_op_id_payload_when_no_lock_active(self, client):
        """/api/review/write returns {op_id, total} async shape (or 429 if busy)."""
        resp = client.post("/api/review/write", json={})
        assert resp.status_code in (202, 429), (
            f"Unexpected /api/review/write status {resp.status_code}; "
            "expected 202 (accepted, with op_id) or 429 (already in progress)."
        )
        if resp.status_code == 202:
            data = resp.get_json()
            assert isinstance(data, dict)
            assert "op_id" in data and "total" in data

    def test_review_js_handles_write_response_without_forEach(self):
        """The Write Tags handler must consume {op_id, total} as an object."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "app", "static", "modules",
            "review.js",
        )
        with open(path) as f:
            content = f.read()

        # The bulk-approve block must NOT do result.forEach(...)
        # The write block must use result.op_id (object access), not result.forEach.
        assert "result.forEach" not in content, (
            "BUG-004 or BUG-005 regressed: review.js contains `result.forEach`."
        )
        # Sanity check: the write handler must use result.op_id
        assert "result.op_id" in content, (
            "review.js write-tags handler should consume result.op_id (object access)."
        )


# ---------------------------------------------------------------------------
# Combined BUG-001/012 doc crosscheck
# ---------------------------------------------------------------------------
class TestBugFoundDocRouteNote:
    """BUGS-FOUND.md is the historical record. Verify it documents the correct
    state (route is /api/classify, not /api/classify/start)."""

    def test_bug001_describes_correct_route(self):
        path = os.path.join(
            os.path.dirname(__file__), "BUGS-FOUND.md",
        )
        with open(path) as f:
            content = f.read()
        # BUG-001 should describe the fix and not perpetuate the wrong route.
        assert "BUG-001" in content
        # The doc should NOT instruct callers to use /api/classify/start as a
        # real endpoint. The "correct" route across the doc must be /api/classify.
        lower = content.lower()
        assert "/api/classify/start" in lower  # bug is still documented
        assert "correct endpoint is `post /api/classify`" in lower or "correct route is `/api/classify`" in lower, (
            "BUGS-FOUND.md BUG-001/012 description must clearly state the "
            "correct route is /api/classify (not /api/classify/start)."
        )
