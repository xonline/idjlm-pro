"""Phase D regression tests — Chromaprint dedup + AcoustID identification.

Guards the two failure modes that would silently break dedup:
  1. Renamed copies of identical audio must share a fingerprint and group.
  2. The fingerprint must survive a SQLite round-trip (dedup runs post-restart).

AcoustID lookups are always mocked — tests must never hit the live web service.
"""
import os
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from app.models.track import Track
from app.services.duplicate_detector import find_duplicates
from app.services.fingerprint import (
    _parse_lookup_response,
    compute_fingerprint,
    identify_track,
    is_acoustid_enabled,
)
from app.services.track_store import TrackStore


# Chromaprint is chroma-based: it keys on pitch class, so a tone and its octave
# fingerprint identically. The two melodies below use disjoint pitch classes so
# that "different audio" is actually different to the fingerprinter.
MELODY_A = [261.63, 329.63, 392.00, 523.25, 440.00, 349.23]  # C  E  G  C  A  F
MELODY_B = [233.08, 277.18, 311.13, 369.99, 207.65, 246.94]  # Bb C# D# F# G# B


def _write_melody(path, notes, seconds=12, sr=44100):
    """fpcalc needs a real, varied signal of adequate length — not a pure tone."""
    per_note = seconds / len(notes)
    parts = []
    for freq in notes:
        t = np.linspace(0, per_note, int(sr * per_note), endpoint=False)
        tone = 0.4 * np.sin(2 * np.pi * freq * t) + 0.15 * np.sin(2 * np.pi * freq * 3 * t)
        envelope = np.minimum(1, np.linspace(0, 8, len(t))) * np.minimum(
            1, np.linspace(8, 0, len(t))
        )
        parts.append(tone * envelope)
    sf.write(path, np.concatenate(parts).astype(np.float32), sr)
    return path


@pytest.fixture(scope="module")
def audio_files(tmp_path_factory):
    d = tmp_path_factory.mktemp("fp_audio")
    original = _write_melody(str(d / "track_a.wav"), MELODY_A)
    renamed = str(d / "totally_different_name.wav")
    with open(original, "rb") as src, open(renamed, "wb") as dst:
        dst.write(src.read())
    other = _write_melody(str(d / "track_b.wav"), MELODY_B)
    return {"original": original, "renamed": renamed, "other": other}


def _track(path, **kw):
    return Track(file_path=path, filename=os.path.basename(path), **kw)


class TestFingerprintComputation:
    def test_renamed_copy_has_identical_fingerprint(self, audio_files):
        fp_original = compute_fingerprint(audio_files["original"])
        fp_renamed = compute_fingerprint(audio_files["renamed"])

        assert fp_original, "fpcalc produced no fingerprint for the original"
        assert fp_original == fp_renamed

    def test_different_audio_has_different_fingerprint(self, audio_files):
        assert compute_fingerprint(audio_files["original"]) != compute_fingerprint(
            audio_files["other"]
        )

    def test_unsupported_extension_returns_none(self, tmp_path):
        txt = tmp_path / "notes.txt"
        txt.write_text("not audio")
        assert compute_fingerprint(str(txt)) is None


class TestFingerprintDedup:
    def test_renamed_copies_group_as_same_audio_content(self, audio_files):
        """The D.1 deliverable: dedup by audio content, not by name or tags."""
        fp = compute_fingerprint(audio_files["original"])
        store = {
            audio_files["original"]: _track(audio_files["original"], audio_fingerprint=fp),
            audio_files["renamed"]: _track(audio_files["renamed"], audio_fingerprint=fp),
            audio_files["other"]: _track(
                audio_files["other"],
                audio_fingerprint=compute_fingerprint(audio_files["other"]),
            ),
        }

        result = find_duplicates(store)
        fp_groups = [g for g in result["groups"] if g["reason"] == "same_audio_content"]

        assert len(fp_groups) == 1
        assert set(fp_groups[0]["tracks"]) == {
            audio_files["original"],
            audio_files["renamed"],
        }
        assert audio_files["other"] not in fp_groups[0]["tracks"]

    def test_tracks_without_fingerprints_are_not_grouped_together(self):
        """A None fingerprint must not collide with another None fingerprint."""
        store = {
            "/a/one.mp3": _track("/a/one.mp3", audio_fingerprint=None),
            "/a/two.mp3": _track("/a/two.mp3", audio_fingerprint=None),
        }
        result = find_duplicates(store)
        assert [g for g in result["groups"] if g["reason"] == "same_audio_content"] == []


class TestFingerprintPersistence:
    def test_fingerprint_survives_sqlite_round_trip(self, tmp_path, audio_files):
        """Dedup runs after restart — a dropped fingerprint breaks it silently."""
        store = TrackStore(db_path=str(tmp_path / "tracks.db"))
        fp = compute_fingerprint(audio_files["original"])
        assert fp

        path = audio_files["original"]
        store[path] = _track(path, audio_fingerprint=fp)

        reloaded = TrackStore(db_path=str(tmp_path / "tracks.db"))
        assert reloaded[path].audio_fingerprint == fp


class TestAcoustIDIdentification:
    LOOKUP_OK = {
        "status": "ok",
        "results": [
            {
                "id": "acoustid-high",
                "score": 0.97,
                "recordings": [
                    {
                        "id": "mb-recording-1",
                        "title": "Strobe",
                        "artists": [{"name": "deadmau5"}],
                    }
                ],
            },
            {
                "id": "acoustid-low",
                "score": 0.61,
                "recordings": [
                    {"id": "mb-recording-2", "title": "Strobe (Radio Edit)", "artists": []}
                ],
            },
        ],
    }

    def test_parses_best_scoring_match(self):
        match = _parse_lookup_response(self.LOOKUP_OK)

        assert match["musicbrainz_id"] == "mb-recording-1"
        assert match["title"] == "Strobe"
        assert match["artist"] == "deadmau5"
        assert match["score"] == 0.97

    def test_low_scoring_results_are_rejected(self):
        noisy = {
            "status": "ok",
            "results": [
                {
                    "id": "acoustid-noise",
                    "score": 0.12,
                    "recordings": [{"id": "mb-x", "title": "Wrong Track"}],
                }
            ],
        }
        assert _parse_lookup_response(noisy) is None

    def test_error_and_empty_responses_return_none(self):
        assert _parse_lookup_response({"status": "error"}) is None
        assert _parse_lookup_response({"status": "ok", "results": []}) is None

    def test_identify_track_returns_match(self, audio_files):
        with patch.dict(os.environ, {"ACOUSTID_API_KEY": "test-key"}):
            with patch("acoustid.lookup", return_value=self.LOOKUP_OK) as mock_lookup:
                match = identify_track(audio_files["original"])

        assert match["title"] == "Strobe"
        assert match["musicbrainz_id"] == "mb-recording-1"
        mock_lookup.assert_called_once()

    def test_identify_track_without_api_key_is_disabled(self, audio_files):
        env = {k: v for k, v in os.environ.items() if k != "ACOUSTID_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            assert is_acoustid_enabled() is False
            with patch("acoustid.lookup") as mock_lookup:
                assert identify_track(audio_files["original"]) is None
            mock_lookup.assert_not_called()

    def test_identify_track_swallows_lookup_errors(self, audio_files):
        """A network failure must degrade to None, never raise into the import path."""
        with patch.dict(os.environ, {"ACOUSTID_API_KEY": "test-key"}):
            with patch("acoustid.lookup", side_effect=Exception("network down")):
                assert identify_track(audio_files["original"]) is None

    def test_meta_argument_matches_pyacoustid_contract(self, audio_files):
        """Guard the mock against drifting from the real library.

        Every other AcoustID test here feeds _parse_lookup_response a dict we
        wrote ourselves. If pyacoustid's expected `meta` shape changed, those
        would all still pass while the live lookup silently returned nothing.
        Pin it to the library's own default instead of our assumption.
        """
        import acoustid

        with patch.dict(os.environ, {"ACOUSTID_API_KEY": "test-key"}):
            with patch("acoustid.lookup", return_value=self.LOOKUP_OK) as mock_lookup:
                identify_track(audio_files["original"])

        meta = mock_lookup.call_args.kwargs["meta"]
        assert meta == acoustid.DEFAULT_META == ["recordings"]

    def test_parser_matches_real_pyacoustid_navigation(self):
        """Our parser must read the same keys pyacoustid's own parser reads.

        Score/id/title are compared directly. The artist *separator* is
        deliberately ours (", " vs pyacoustid's "; "), so compare the names
        rather than the joined string — see the multi-artist test below.
        """
        import acoustid

        ours = _parse_lookup_response(self.LOOKUP_OK)
        theirs = list(acoustid.parse_lookup_result(self.LOOKUP_OK))
        best_score, mb_id, title, artist = max(theirs, key=lambda r: r[0])

        assert ours["musicbrainz_id"] == mb_id
        assert ours["title"] == title
        assert ours["score"] == best_score
        assert set(ours["artist"].split(", ")) == set(artist.split("; "))

    def test_multiple_artists_are_comma_joined(self):
        """Collabs are the common case in a DJ library — pin the joined format."""
        payload = {
            "status": "ok",
            "results": [
                {
                    "id": "acoustid-collab",
                    "score": 0.9,
                    "recordings": [
                        {
                            "id": "mb-collab",
                            "title": "Ghosts 'n' Stuff",
                            "artists": [{"name": "deadmau5"}, {"name": "Rob Swire"}],
                        }
                    ],
                }
            ],
        }
        assert _parse_lookup_response(payload)["artist"] == "deadmau5, Rob Swire"
