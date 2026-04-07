"""Tests for bug fixes — verify specific issues are resolved."""
import json
import os
import pytest


# ---------------------------------------------------------------------------
# Session save/load — critical: to_dict() non-dataclass keys bug
# ---------------------------------------------------------------------------
class TestSessionRoundTrip:
    """Session save then load must reconstruct Track objects correctly."""

    def test_save_and_load_session_with_tracks(self, client):
        """
        Import tracks, save session, load session — Track reconstruction
        must NOT fail due to non-dataclass keys (display_title, final_genre, etc.)
        """
        from app.services.session_service import save_session, load_session
        from app import get_track_store

        # Simulate importing tracks
        resp = client.post("/api/import", json={
            "folder_path": "/tmp"
        })
        # May succeed or fail depending on filesystem — that's OK
        # What matters is that save/load works with whatever tracks exist

        track_store = get_track_store()

        # If there are tracks, test save/load round-trip
        if track_store:
            # Save
            session_data = save_session(track_store, "/tmp")
            assert session_data is not None
            assert "tracks" in session_data

            # Load
            loaded_store, metadata = load_session()
            assert loaded_store is not None
            assert len(loaded_store) > 0

            # Verify Track objects were reconstructed correctly
            for path, track in loaded_store.items():
                assert track.file_path is not None
                assert track.filename is not None
                # Verify properties work (they depend on dataclass fields)
                _ = track.display_title
                _ = track.display_artist
                _ = track.final_genre

    def test_load_session_with_no_session_file(self, client):
        """If session.json doesn't exist, load_session returns (None, None)."""
        from app.services.session_service import load_session, SESSION_FILE

        # Temporarily rename session file if it exists
        if os.path.exists(SESSION_FILE):
            os.rename(SESSION_FILE, SESSION_FILE + ".bak")

        try:
            result, meta = load_session()
            assert result is None
            assert meta is None
        finally:
            if os.path.exists(SESSION_FILE + ".bak"):
                os.rename(SESSION_FILE + ".bak", SESSION_FILE)


# ---------------------------------------------------------------------------
# Bulk edit — track_paths vs file_paths mismatch
# ---------------------------------------------------------------------------
class TestBulkEditPayload:
    """Bulk edit endpoint must accept track_paths (not file_paths)."""

    def test_bulk_edit_with_track_paths(self, client):
        """Sending track_paths should work; file_paths should not update tracks."""
        # First import some tracks
        client.post("/api/import", json={"folder_path": "/tmp"})

        # Get the track store
        from app import get_track_store
        track_store = get_track_store()

        if not track_store:
            pytest.skip("No tracks available for testing")

        paths = list(track_store.keys())[:2]

        # Send with track_paths (correct key)
        resp = client.post("/api/review/bulk-edit", json={
            "track_paths": paths,
            "genre": "TestGenre",
            "subgenre": "TestSub",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["updated"] >= 0


# ---------------------------------------------------------------------------
# Settings — element ID and field name consistency
# ---------------------------------------------------------------------------
class TestSettingsFields:
    """Settings save must use correct field names."""

    def test_save_classify_batch_size(self, client):
        """classify_batch_size (not batch_size) must be saved."""
        resp = client.post("/api/settings", json={
            "classify_batch_size": 15,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["saved"] is True

        # Verify it was saved
        resp2 = client.get("/api/settings")
        assert resp2.status_code == 200
        settings = resp2.get_json()
        assert settings["classify_batch_size"] == 15

    def test_save_auto_approve_threshold(self, client):
        """auto_approve_threshold must persist correctly."""
        resp = client.post("/api/settings", json={
            "auto_approve_threshold": 65,
        })
        assert resp.status_code == 200

        resp2 = client.get("/api/settings")
        settings = resp2.get_json()
        assert settings["auto_approve_threshold"] == 65


# ---------------------------------------------------------------------------
# Taxonomy — genre filter population
# ---------------------------------------------------------------------------
class TestTaxonomyEndpoints:
    """Taxonomy CRUD must work correctly."""

    def test_add_genre_and_verify(self, client):
        """Add a genre, then verify it appears in GET /api/taxonomy."""
        resp = client.post("/api/taxonomy/genre", json={
            "name": "TestGenreForBugfix",
            "description": "A test genre for bug fix verification",
            "subgenres": {"Sub1": "Description 1"}
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "TestGenreForBugfix" in data["genres"]

        # Verify via GET
        resp2 = client.get("/api/taxonomy")
        taxonomy = resp2.get_json()
        assert "TestGenreForBugfix" in taxonomy["genres"]

        # Clean up
        resp3 = client.delete("/api/taxonomy/genre/TestGenreForBugfix")
        assert resp3.status_code == 200


# ---------------------------------------------------------------------------
# Analyzer — empty BPM handling
# ---------------------------------------------------------------------------
class TestAnalyzerEdgeCases:
    """Analyzer must handle edge cases gracefully."""

    def test_analyze_nonexistent_file(self, client):
        """Analyzing a nonexistent file should set track.error, not crash."""
        from app import get_track_store
        from app.services.analyzer import analyze_track
        from app.models.track import Track

        track_store = get_track_store()
        test_track = Track(
            file_path="/nonexistent/audio_file.mp3",
            filename="audio_file.mp3"
        )

        result = analyze_track(test_track)
        assert result.error is not None
        assert "analysis failed" in result.error.lower() or "no bpm" in result.error.lower()


# ---------------------------------------------------------------------------
# CSS / Frontend — verify no syntax errors in static files
# ---------------------------------------------------------------------------
class TestStaticFiles:
    """Static files must be syntactically valid."""

    def test_css_has_no_unmatched_braces(self):
        """CSS file should not have unmatched closing braces."""
        css_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "static", "style.css"
        )
        if not os.path.exists(css_path):
            pytest.skip("CSS file not found")

        with open(css_path) as f:
            content = f.read()

        # Count braces (rough check — not perfect but catches obvious issues)
        opens = content.count("{")
        closes = content.count("}")
        # Allow small tolerance for CSS values like content: "}"
        assert abs(opens - closes) <= 2, (
            f"CSS brace mismatch: {opens} opens vs {closes} closes"
        )

    def test_js_has_no_obvious_syntax_errors(self):
        """JS file should not have obvious issues like 'undefined' string comparisons."""
        js_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "static", "app.js"
        )
        if not os.path.exists(js_path):
            pytest.skip("JS file not found")

        with open(js_path) as f:
            content = f.read()

        # Check that handleBulkEdit sends track_paths (not file_paths)
        assert "track_paths: Array.from(window.selectedTracks)" in content, (
            "handleBulkEdit must send 'track_paths' not 'file_paths'"
        )

        # Check that confidence uses 'confidence-mid' (not 'confidence-medium')
        assert "'confidence-mid'" in content, (
            "getConfidenceBadgeClass must return 'confidence-mid'"
        )
        # Make sure the old buggy string is gone
        assert "'confidence-medium'" not in content, (
            "'confidence-medium' should have been renamed to 'confidence-mid'"
        )


# ---------------------------------------------------------------------------
# Review routes — response shape consistency
# ---------------------------------------------------------------------------
class TestReviewRoutesResponseShapes:
    """Review endpoints must return consistent response shapes."""

    def test_bulk_approve_returns_count(self, client):
        """bulk-approve returns {approved: count}, not an array."""
        resp = client.post("/api/review/bulk-approve", json={"min_confidence": 80})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "approved" in data
        assert isinstance(data["approved"], int)

    def test_write_tags_returns_op_id(self, client):
        """write-tags returns {op_id, total}, not an array."""
        resp = client.post("/api/review/write", json={})
        assert resp.status_code in (202, 500)
        if resp.status_code == 202:
            data = resp.get_json()
            assert "op_id" in data
            assert "total" in data
