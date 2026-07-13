"""Regression tests for CODEX_REVIEW_2026-04-05.txt P2 findings (issue #198, A.3).

Source:
    ~/projects/idjlm/CODEX_REVIEW_2026-04-05.txt
    ~/.claude/plans/2026-07-04-idjlm-backend-plan.md (Phase A.3)

P2 finding summary:
    BUG-014   Silent sort failure on mixed types — GET /api/tracks?sort_by=bpm
              (or year) mixes int(0) placeholders with the string-typed
              final_bpm/final_year properties. Comparing str and int raises
              TypeError mid-sort, which was silently swallowed and fell back
              to filename order with no indication to the caller.
    BUG-015   Stale 'edited' review_status — clearing the last override on a
              track must revert review_status from "edited" back to "pending".
    BUG-016   /api/review/bulk-edit validation bypass — bulk edits must reject
              the same invalid bpm/key/year values that the single-track
              PUT /api/tracks/<path> endpoint already rejects (e.g. bpm="fast").

These tests assert the *currently correct* state and will fail loudly if any
of the three bugs regresses. The historical Codex review text is kept as-is
in CODEX_REVIEW_2026-04-05.txt.
"""
import pytest


def _make_track(file_path, filename, **kwargs):
    from app.models.track import Track
    return Track(file_path=file_path, filename=filename, **kwargs)


@pytest.fixture
def seeded_tracks(client):
    """Insert deterministic tracks directly into the track store and clean up after."""
    from app import get_track_store

    store = get_track_store()
    tracks = {
        "/tmp/a3-track-1.mp3": _make_track(
            "/tmp/a3-track-1.mp3", "a3-track-1.mp3", existing_bpm="128", existing_year="2020"
        ),
        "/tmp/a3-track-2.mp3": _make_track(
            "/tmp/a3-track-2.mp3", "a3-track-2.mp3"  # no bpm/year at all -> None
        ),
        "/tmp/a3-track-3.mp3": _make_track(
            "/tmp/a3-track-3.mp3", "a3-track-3.mp3", existing_bpm="90", existing_year="1999"
        ),
    }
    store.update(tracks)
    yield tracks
    for path in tracks:
        store.pop(path, None)


# ---------------------------------------------------------------------------
# BUG-014  Sorting by a numeric column must never silently fall back to
#          filename order when some tracks have that field unset.
# ---------------------------------------------------------------------------
class TestSortMixedTypes:
    def test_sort_key_normalizes_mixed_none_and_string(self):
        """final_bpm/final_year are string-typed properties; None must not be
        compared against them as an int (which raises TypeError)."""
        t1 = _make_track("/a.mp3", "a.mp3", existing_bpm="128")
        t2 = _make_track("/b.mp3", "b.mp3")  # final_bpm is None
        t3 = _make_track("/c.mp3", "c.mp3", existing_bpm="90")

        assert isinstance(t1.final_bpm, str)
        assert t2.final_bpm is None

        # This is the exact key function used in app/routes/track_routes.py.
        def sort_key(t, sort_attr="final_bpm", is_numeric=True):
            value = getattr(t, sort_attr, None)
            if is_numeric:
                try:
                    return float(value) if value not in (None, "") else 0.0
                except (TypeError, ValueError):
                    return 0.0
            return value if isinstance(value, str) else ("" if value is None else str(value))

        tracks = [t1, t2, t3]
        tracks.sort(key=sort_key)  # must not raise TypeError
        assert [t.filename for t in tracks] == ["b.mp3", "c.mp3", "a.mp3"]

    def test_api_tracks_sort_by_bpm_ascending_with_missing_values(self, client, seeded_tracks):
        """GET /api/tracks?sort_by=bpm must order by numeric bpm value, not
        fall back to filename order, even when a track has no bpm set."""
        resp = client.get("/api/tracks?sort_by=bpm&sort_dir=asc")
        assert resp.status_code == 200
        data = resp.get_json()

        filenames = [t["filename"] for t in data["tracks"] if t["filename"].startswith("a3-track-")]
        # None/unset (track-2) sorts first (treated as 0), then 90, then 128.
        assert filenames == ["a3-track-2.mp3", "a3-track-3.mp3", "a3-track-1.mp3"], (
            f"Expected bpm-ascending order with missing values first, got {filenames}. "
            "If this is filename order (a3-track-1, -2, -3) the sort silently fell back."
        )

    def test_api_tracks_sort_by_year_descending_with_missing_values(self, client, seeded_tracks):
        """Same mixed-type hazard applies to final_year."""
        resp = client.get("/api/tracks?sort_by=year&sort_dir=desc")
        assert resp.status_code == 200
        data = resp.get_json()

        filenames = [t["filename"] for t in data["tracks"] if t["filename"].startswith("a3-track-")]
        assert filenames == ["a3-track-1.mp3", "a3-track-3.mp3", "a3-track-2.mp3"], (
            f"Expected year-descending order with missing values last, got {filenames}."
        )


# ---------------------------------------------------------------------------
# BUG-015  Clearing the last override must revert review_status from
#          "edited" back to "pending" (single-track and bulk-edit paths).
# ---------------------------------------------------------------------------
class TestEditedStatusClearsWhenOverridesRemoved:
    def test_single_track_put_reverts_to_pending(self, client, seeded_tracks):
        path = "/tmp/a3-track-1.mp3"

        # Set an override -> status becomes "edited"
        resp = client.put(f"/api/tracks/by-path?path={path}", json={"override_genre": "Techno"})
        assert resp.status_code == 200
        assert resp.get_json()["review_status"] == "edited"

        # Clear the only override -> status must revert to "pending"
        resp = client.put(f"/api/tracks/by-path?path={path}", json={"override_genre": ""})
        assert resp.status_code == 200
        assert resp.get_json()["review_status"] == "pending", (
            "Track stayed 'edited' after its last override was cleared — "
            "status filtering by 'edited' will never empty out."
        )

    def test_bulk_edit_reverts_to_pending(self, client, seeded_tracks):
        from app import get_track_store

        paths = ["/tmp/a3-track-1.mp3"]

        resp = client.post("/api/review/bulk-edit", json={"track_paths": paths, "bpm": "120"})
        assert resp.status_code == 200
        assert get_track_store()[paths[0]].review_status == "edited"

        resp = client.post("/api/review/bulk-edit", json={"track_paths": paths, "bpm": ""})
        assert resp.status_code == 200
        assert get_track_store()[paths[0]].review_status == "pending", (
            "Bulk-edit left the track in 'edited' status after clearing its "
            "only override via bulk-edit."
        )


# ---------------------------------------------------------------------------
# BUG-016  /api/review/bulk-edit must validate bpm/key/year the same way the
#          single-track PUT /api/tracks/<path> endpoint does.
# ---------------------------------------------------------------------------
class TestBulkEditValidation:
    def test_bulk_edit_rejects_non_numeric_bpm(self, client, seeded_tracks):
        resp = client.post("/api/review/bulk-edit", json={
            "track_paths": list(seeded_tracks.keys()),
            "bpm": "fast",
        })
        assert resp.status_code == 400, (
            f"bulk-edit accepted bpm='fast' (status {resp.status_code}) — "
            "validation bypass lets invalid data ship in bulk."
        )
        assert "numeric" in resp.get_json().get("error", "").lower()

    def test_bulk_edit_rejects_out_of_range_bpm(self, client, seeded_tracks):
        resp = client.post("/api/review/bulk-edit", json={
            "track_paths": list(seeded_tracks.keys()),
            "bpm": "999",
        })
        assert resp.status_code == 400

    def test_bulk_edit_rejects_out_of_range_year(self, client, seeded_tracks):
        resp = client.post("/api/review/bulk-edit", json={
            "track_paths": list(seeded_tracks.keys()),
            "year": "1500",
        })
        assert resp.status_code == 400

    def test_bulk_edit_rejects_oversized_key(self, client, seeded_tracks):
        resp = client.post("/api/review/bulk-edit", json={
            "track_paths": list(seeded_tracks.keys()),
            "key": "way-too-long-key-value",
        })
        assert resp.status_code == 400

    def test_bulk_edit_accepts_valid_values(self, client, seeded_tracks):
        resp = client.post("/api/review/bulk-edit", json={
            "track_paths": list(seeded_tracks.keys()),
            "bpm": "128",
            "key": "8A",
            "year": "2020",
        })
        assert resp.status_code == 200
        assert resp.get_json()["updated"] == len(seeded_tracks)
