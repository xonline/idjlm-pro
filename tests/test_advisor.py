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

    def test_suggest_next_tracks_key_weight_zero_excludes_key(self):
        """When key_weight=0, key compatibility should not affect ranking."""
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
                override_genre="house",
            ),
            "/track2.mp3": Track(
                file_path="/track2.mp3",
                filename="track2.mp3",
                existing_title="Same Key Different BPM",
                existing_artist="Artist B",
                analyzed_bpm=140.0,  # Different BPM
                analyzed_key="8A",   # Same key
                analyzed_energy=7,
                override_genre="house",
            ),
            "/track3.mp3": Track(
                file_path="/track3.mp3",
                filename="track3.mp3",
                existing_title="Different Key Same BPM",
                existing_artist="Artist C",
                analyzed_bpm=121.0,  # Close BPM
                analyzed_key="1A",   # Incompatible key
                analyzed_energy=7,
                override_genre="house",
            ),
        }
        # With key_weight=0, track3 (close BPM) should rank higher than track2 (far BPM)
        result = suggest_next_tracks(store, "/track1.mp3", limit=2, key_weight=0.0, bpm_weight=1.0, energy_weight=0.0, genre_weight=0.0)
        assert len(result) == 2
        assert result[0]["file_path"] == "/track3.mp3"  # Close BPM wins when key doesn't matter

    def test_suggest_next_tracks_bpm_weight_zero_excludes_bpm(self):
        """When bpm_weight=0, BPM compatibility should not affect ranking."""
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
                override_genre="house",
            ),
            "/track2.mp3": Track(
                file_path="/track2.mp3",
                filename="track2.mp3",
                existing_title="Same Key Different BPM",
                existing_artist="Artist B",
                analyzed_bpm=140.0,  # Different BPM
                analyzed_key="8A",   # Same key
                analyzed_energy=7,
                override_genre="house",
            ),
            "/track3.mp3": Track(
                file_path="/track3.mp3",
                filename="track3.mp3",
                existing_title="Different Key Same BPM",
                existing_artist="Artist C",
                analyzed_bpm=121.0,  # Close BPM
                analyzed_key="1A",   # Incompatible key
                analyzed_energy=7,
                override_genre="house",
            ),
        }
        # With bpm_weight=0, track2 (same key) should rank higher than track3 (close BPM)
        result = suggest_next_tracks(store, "/track1.mp3", limit=2, key_weight=1.0, bpm_weight=0.0, energy_weight=0.0, genre_weight=0.0)
        assert len(result) == 2
        assert result[0]["file_path"] == "/track2.mp3"  # Same key wins when BPM doesn't matter

    def test_suggest_next_tracks_energy_weight_affects_ranking(self):
        """When energy_weight > 0, energy differences should affect ranking."""
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
                override_genre="house",
            ),
            "/track2.mp3": Track(
                file_path="/track2.mp3",
                filename="track2.mp3",
                existing_title="Same Energy",
                existing_artist="Artist B",
                analyzed_bpm=121.0,
                analyzed_key="8A",
                analyzed_energy=7,   # Same energy
                override_genre="house",
            ),
            "/track3.mp3": Track(
                file_path="/track3.mp3",
                filename="track3.mp3",
                existing_title="Different Energy",
                existing_artist="Artist C",
                analyzed_bpm=121.0,
                analyzed_key="8A",
                analyzed_energy=3,   # Different energy
                override_genre="house",
            ),
        }
        # With energy_weight=1.0, track2 (same energy) should rank higher
        result = suggest_next_tracks(store, "/track1.mp3", limit=2, key_weight=0.0, bpm_weight=0.0, energy_weight=1.0, genre_weight=0.0)
        assert len(result) == 2
        assert result[0]["file_path"] == "/track2.mp3"

    def test_suggest_next_tracks_genre_weight_affects_ranking(self):
        """When genre_weight > 0, genre matching should affect ranking."""
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
                override_genre="house",
            ),
            "/track2.mp3": Track(
                file_path="/track2.mp3",
                filename="track2.mp3",
                existing_title="Same Genre",
                existing_artist="Artist B",
                analyzed_bpm=121.0,
                analyzed_key="8A",
                analyzed_energy=7,
                override_genre="house",  # Same genre
            ),
            "/track3.mp3": Track(
                file_path="/track3.mp3",
                filename="track3.mp3",
                existing_title="Different Genre",
                existing_artist="Artist C",
                analyzed_bpm=121.0,
                analyzed_key="8A",
                analyzed_energy=7,
                override_genre="techno",  # Different genre
            ),
        }
        # With genre_weight=1.0, track2 (same genre) should rank higher
        result = suggest_next_tracks(store, "/track1.mp3", limit=2, key_weight=0.0, bpm_weight=0.0, energy_weight=0.0, genre_weight=1.0)
        assert len(result) == 2
        assert result[0]["file_path"] == "/track2.mp3"

    def test_suggest_next_tracks_all_weights_one(self):
        """Test that all weights=1.0 produces expected scoring."""
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
                override_genre="house",
            ),
            "/track2.mp3": Track(
                file_path="/track2.mp3",
                filename="track2.mp3",
                existing_title="Highly Compatible",
                existing_artist="Artist B",
                analyzed_bpm=120.0,  # Same BPM
                analyzed_key="8A",   # Same key
                analyzed_energy=7,   # Same energy
                override_genre="house",  # Same genre
            ),
        }
        result = suggest_next_tracks(store, "/track1.mp3", limit=5, key_weight=1.0, bpm_weight=1.0, energy_weight=1.0, genre_weight=1.0)
        assert len(result) == 1
        assert result[0]["file_path"] == "/track2.mp3"
        assert result[0]["score"] == 100

    def test_e4_weighted_params_regression(self):
        """Regression: E.4 weighted advisor params must affect ranking (issue #209)."""
        from app.services.advisor import suggest_next_tracks
        from app.models.track import Track
        store = {
            "/s.mp3": Track(file_path="/s.mp3", filename="s.mp3",
                existing_title="S", existing_artist="A",
                analyzed_bpm=120.0, analyzed_key="8A",
                analyzed_energy=5, override_genre="house"),
            "/a.mp3": Track(file_path="/a.mp3", filename="a.mp3",
                existing_title="A", existing_artist="B",
                analyzed_bpm=120.0, analyzed_key="8A",
                analyzed_energy=5, override_genre="house"),
        }
        # All weights 1.0 → perfect score for fully compatible track
        r = suggest_next_tracks(store, "/s.mp3", limit=1,
            key_weight=1.0, bpm_weight=1.0, energy_weight=1.0, genre_weight=1.0)
        assert len(r) == 1 and r[0]["file_path"] == "/a.mp3" and r[0]["score"] == 100
        # key_weight=0 + same BPM/energy/genre should still match (BPM/energy/genre unchanged)
        r0 = suggest_next_tracks(store, "/s.mp3", limit=1,
            key_weight=0.0, bpm_weight=1.0, energy_weight=1.0, genre_weight=1.0)
        assert r0[0]["file_path"] == "/a.mp3"

    def test_advisor_weighted_params_regression_e4(self):
        """Regression test: /api/suggest_next and /api/setlist/suggest accept bpm/key/energy/genre weights (issue #209 E.4)."""
        from app.services.advisor import suggest_next_tracks
        from app.models.track import Track
        store = {
            "/a.mp3": Track(file_path="/a.mp3", filename="a.mp3", existing_title="A", existing_artist="Art",
                          analyzed_bpm=120, analyzed_key="8A", analyzed_energy=5, override_genre="house"),
            "/b.mp3": Track(file_path="/b.mp3", filename="b.mp3", existing_title="B", existing_artist="Art2",
                          analyzed_bpm=121, analyzed_key="8B", analyzed_energy=7, override_genre="techno"),
        }
        # All weights=0 -> score should be 0 (no max_score contribution)
        result = suggest_next_tracks(store, "/a.mp3", limit=1, key_weight=0.0, bpm_weight=0.0, energy_weight=0.0, genre_weight=0.0)
        assert result == []  # With zero weights there is no scoring basis
        # Default weights=1 should return results with positive scores
        result_full = suggest_next_tracks(store, "/a.mp3", limit=1)
        assert len(result_full) == 1
        assert result_full[0]["score"] > 0

    def test_weighted_params_on_suggest_next(self):
        """Regression: /api/suggest_next uses bpm_weight/key_weight/energy_weight/genre_weight."""
        from app.services.advisor import suggest_next_tracks
        from app.models.track import Track
        store = {
            "/s.mp3": Track(file_path="/s.mp3", filename="s.mp3", existing_title="S", existing_artist="A",
                          analyzed_bpm=120, analyzed_key="8A", analyzed_energy=7, override_genre="house"),
            "/c.mp3": Track(file_path="/c.mp3", filename="c.mp3", existing_title="C", existing_artist="B",
                          analyzed_bpm=121, analyzed_key="8A", analyzed_energy=7, override_genre="house"),
        }
        # All weights 1 should give high score to same-key/same-bpm/same-energy/same-genre
        r_all = suggest_next_tracks(store, "/s.mp3", limit=1, key_weight=1, bpm_weight=1, energy_weight=1, genre_weight=1)
        assert len(r_all) == 1
        assert r_all[0]["file_path"] == "/c.mp3"
        assert r_all[0]["score"] == 100
        # Zero key weight should reduce score for same-key track (but still high due to bpm/energy/genre)
        r_zero_key = suggest_next_tracks(store, "/s.mp3", limit=1, key_weight=0, bpm_weight=1, energy_weight=1, genre_weight=1)
        # With key_weight=0, max_score drops but BPM/energy/genre perfect matches still yield 100
        assert r_zero_key[0]["score"] == 100

    def test_advisor_weighted_params_regression_e4(self):
        """E.4 regression: /api/suggest_next uses bpm_weight/key_weight/energy_weight/genre_weight."""
        from app.services.advisor import suggest_next_tracks
        from app.models.track import Track
        store = {
            "/s.mp3": Track(file_path="/s.mp3", filename="s.mp3", existing_title="S", existing_artist="A",
                           analyzed_bpm=120, analyzed_key="8A", analyzed_energy=7, override_genre="house"),
            "/c.mp3": Track(file_path="/c.mp3", filename="c.mp3", existing_title="C", existing_artist="B",
                           analyzed_bpm=121, analyzed_key="8A", analyzed_energy=7, override_genre="house"),
        }
        r = suggest_next_tracks(store, "/s.mp3", limit=1, key_weight=1.0, bpm_weight=1.0, energy_weight=1.0, genre_weight=1.0)
        assert r[0]["file_path"] == "/c.mp3"
