"""Tests for the Next Track Advisor service."""
import pytest


class TestAdvisor:
    """Test the Next Track Advisor service."""

    def test_camelot_compatibility_map(self):
        from app.services.advisor import CAMELOT_COMPATIBLE
        # Every key should have exactly 4 compatible keys (itself, relative, +1, -1)
        for key, compatible in CAMELOT_COMPATIBLE.items():
            assert len(compatible) == 4
            assert key in compatible  # A key is compatible with itself

    def test_suggest_next_tracks_empty_store(self):
        from app.services.advisor import suggest_next_tracks
        result = suggest_next_tracks({}, "/nonexistent")
        assert result == []

    def test_suggest_next_tracks_single_track(self):
        from app.services.advisor import suggest_next_tracks
        from app.models.track import Track

        store = {
            "/track1.mp3": Track(
                file_path="/track1.mp3",
                filename="track1.mp3",
                existing_title="Track One",
                existing_artist="Artist A",
                analyzed_bpm=120.0,
                analyzed_key="8A",
                analyzed_energy=7,
            )
        }
        result = suggest_next_tracks(store, "/track1.mp3", limit=5)
        assert result == []  # No other tracks to suggest

    def test_suggest_next_tracks_with_candidates(self):
        from app.services.advisor import suggest_next_tracks
        from app.models.track import Track

        store = {
            "/track1.mp3": Track(
                file_path="/track1.mp3",
                filename="track1.mp3",
                existing_title="Source",
                existing_artist="Artist",
                analyzed_bpm=120.0,
                analyzed_key="8A",
                analyzed_energy=7,
            ),
            "/track2.mp3": Track(
                file_path="/track2.mp3",
                filename="track2.mp3",
                existing_title="Compatible",
                existing_artist="Artist B",
                analyzed_bpm=121.0,  # Very close BPM
                analyzed_key="8A",   # Same key
                analyzed_energy=7,   # Same energy
            ),
            "/track3.mp3": Track(
                file_path="/track3.mp3",
                filename="track3.mp3",
                existing_title="Different",
                existing_artist="Artist C",
                analyzed_bpm=140.0,  # Far BPM
                analyzed_key="1A",   # Incompatible key
                analyzed_energy=3,   # Different energy
            ),
        }
        result = suggest_next_tracks(store, "/track1.mp3", limit=2)
        assert len(result) == 2
        # track2 should score higher than track3
        assert result[0]["file_path"] == "/track2.mp3"
        assert result[0]["score"] > result[1]["score"]
