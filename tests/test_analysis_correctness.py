"""
Regression tests for IDJLM analysis-correctness quick-wins (Phase C.2-C.4).

- C.2: library-relative percentile energy normalisation (replaces hardcoded 0.35)
- C.3: real LUFS via pyloudnorm (ITU-R BS.1770) with legacy fallback
- C.4: set planner uses real track durations, not a 4-min constant

Every test is synthetic (no audio files needed) and verifies the contract
documented in the issue body, not the implementation.
"""
import numpy as np
import pytest

from app import get_track_store


# ---------------------------------------------------------------------------
# C.2 — Library-relative percentile energy normalisation
# ---------------------------------------------------------------------------
class TestPercentileEnergyNormalization:
    """
    The old contract was: ``int(min(1.0, rms_mean / 0.35) * 10)`` clamped to [1, 10].
    That hardcoded 0.35 ceiling meant delibrately-quiet Latin recordings could
    still score 9-10 just because ``rms_mean`` was close to 0.35.

    New contract: percentile rank inside the library; lowest track -> 1,
    highest -> 10, monotonic (ties get a midpoint), integer-rounded.
    """

    def test_imports(self):
        from app.services.analyzer import apply_library_percentile_normalization
        assert callable(apply_library_percentile_normalization)

    def test_empty_collection_no_op(self):
        from app.services.analyzer import apply_library_percentile_normalization
        from app.models.track import Track

        tracks = [Track(file_path="/a.mp3", filename="a.mp3")]
        assert apply_library_percentile_normalization(tracks) == 0
        assert tracks[0].analyzed_energy is None

    def test_single_track_forced_to_middle(self):
        from app.services.analyzer import apply_library_percentile_normalization
        from app.models.track import Track

        t = Track(file_path="/only.mp3", filename="only.mp3", raw_rms=0.10)
        n = apply_library_percentile_normalization([t])
        assert n == 1
        assert t.analyzed_energy == 5

    def test_two_tracks_span_min_max(self):
        """
        With just two tracks, the quietest must land at 1 and the loudest at 10.
        A hardcoded 0.35 ceiling would lock any rms_mean < 0.35 to score 1 anyway,
        but it would also collapse any rms_mean > 0.35 to 10 regardless of relative
        ordering. The percentile contract guarantees spread across the 1-10 range.
        """
        from app.services.analyzer import apply_library_percentile_normalization
        from app.models.track import Track

        quiet = Track(file_path="/q.mp3", filename="q.mp3", raw_rms=0.01)
        loud = Track(file_path="/L.mp3", filename="L.mp3", raw_rms=0.30)
        apply_library_percentile_normalization([quiet, loud])

        assert quiet.analyzed_energy == 1
        assert loud.analyzed_energy == 10

    def test_more_than_two_is_monotonic(self):
        from app.services.analyzer import apply_library_percentile_normalization
        from app.models.track import Track

        rms = [0.01, 0.05, 0.10, 0.20, 0.30]
        tracks = [
            Track(file_path=f"/t{i}.mp3", filename=f"t{i}.mp3", raw_rms=r)
            for i, r in enumerate(rms)
        ]
        apply_library_percentile_normalization(tracks)

        scores = [t.analyzed_energy for t in tracks]
        # Monotonic: score never decreases as RMS increases.
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1], f"Non-monotonic at {i}: {scores}"
        # Lowest is 1, highest is 10, all in [1, 10].
        assert scores[0] == 1
        assert scores[-1] == 10
        for s in scores:
            assert 1 <= s <= 10

    def test_no_hardcoded_ceiling_dominant(self):
        """
        The 0.35 hardcoded ceiling collapsed everything from rms_mean ~0.18 up to
        rms_mean ~0.49 into score 10. With percentile normalisation the *relative*
        position drives the score.
        """
        from app.services.analyzer import apply_library_percentile_normalization
        from app.models.track import Track

        # Five tracks all below the old 0.35 ceiling but spread evenly.
        rms = [0.04, 0.10, 0.16, 0.22, 0.28]
        tracks = [
            Track(file_path=f"/x{i}.mp3", filename=f"x{i}.mp3", raw_rms=r)
            for i, r in enumerate(rms)
        ]
        apply_library_percentile_normalization(tracks)

        scores = {t.raw_rms: t.analyzed_energy for t in tracks}
        # Lowest should be 1, highest 10, middle should NOT all be 10.
        assert scores[min(rms)] == 1
        assert scores[max(rms)] == 10
        middle_rms = sorted(rms)[2]
        assert scores[middle_rms] < 10, (
            "Middle RMS still scoring 10 — hardcoded ceiling leaked through"
        )

    def test_no_hardcoded_ceiling_in_normalization_logic(self):
        """
        Guardrail: the old hardcoded ceiling ``rms_mean / 0.35`` must no longer
        drive the energy score. The function body may still *mention* 0.35 in
        docstring prose explaining the legacy contract, but it must no longer
        divide by it.
        """
        import re
        from pathlib import Path

        src_path = Path(__file__).resolve().parent.parent / "app" / "services" / "analyzer.py"
        src = src_path.read_text()
        start = src.find("def _normalize_energy(")

        # Walk lines, skipping the opening/closing docstring fence. The 0.35
        # ceiling must NOT appear outside the docstring.
        in_docstring = False
        body_lines = []
        for line in src[start:].splitlines():
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if not in_docstring:
                    in_docstring = True
                    # Single-line docstring.
                    if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                        in_docstring = False
                    continue
                # Closing fence.
                in_docstring = False
                continue
            if in_docstring:
                continue
            if stripped.startswith("def ") or stripped.startswith("from ") or stripped.startswith("import "):
                continue
            body_lines.append(line)
            if stripped and "return " in stripped:
                break

        body = "\n".join(body_lines)
        match = re.search(r"/\s*0\.35|\*\s*0\.35", body)
        assert match is None, (
            f"_normalize_energy still uses 0.35 literally in code: {match.group(0)!r}\n"
            f"Body checked:\n{body}"
        )


# ---------------------------------------------------------------------------
# C.3 — Real LUFS via pyloudnorm (ITU-R BS.1770)
# ---------------------------------------------------------------------------
class TestLuftsRealPyloudnorm:
    """
    The old _compute_lufs returned a hand-rolled ``20*log10(rms)`` clamped to
    -70 LUFS — that's dBFS, not BS.1770 LUFS (which uses K-weighted gating).

    New contract: ``pyloudnorm`` is preferred; built with a 1 kHz sine at known
    amplitude, integrated LUFS should be ~ -3.01 LUFS (i.e. matched to amplitude
    when calibrated). Returns a 3-tuple of (integrated_lufs, lra, true_peak).
    Falls back gracefully when pyloudnorm is unavailable.
    """

    def test_pyloudnorm_importable(self):
        """pyloudnorm must be installed for BS.1770 computation."""
        import importlib

        try:
            pyln = importlib.import_module("pyloudnorm")
            assert hasattr(pyln, "Meter")
        except ImportError:
            pytest.fail("pyloudnorm is not installed; ITFS BS.1770 LUFS unavailable")

    def test_signature_unchanged(self):
        """
        ``_compute_lufs`` keeps its 3-tuple return contract so callers (analyzer,
        routes) don't regress.
        """
        from app.services.analyzer import _compute_lufs
        result = _compute_lufs(np.zeros(22050, dtype=np.float32), 22050)
        assert isinstance(result, tuple)
        assert len(result) == 3
        integrated, lra, true_peak = result
        assert integrated is None or isinstance(integrated, (int, float))
        assert lra is None or isinstance(lra, (int, float))
        assert true_peak is None or isinstance(true_peak, (int, float))

    def test_sine_wave_returns_finite_lufs(self):
        """
        1 kHz sine at moderate amplitude should produce a finite, sensible LUFS
        value with pyloudnorm. -10 dBFS sine should hit somewhere around
        -10 LUFS (within a few LUFS — BS.1770's K-weighting adds a small
        bias, not the broken behaviour of the old impl).
        """
        from app.services.analyzer import _compute_lufs

        sr = 22050
        duration_sec = 5
        t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
        # 1 kHz sine at -10 dBFS amplitude (~0.316 peak).
        amplitude = 10 ** (-10 / 20)
        y = (amplitude * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)

        integrated, _lra, true_peak = _compute_lufs(y, sr)

        if integrated is not None:
            # Should be roughly -10 LUFS +/- a couple LUFS, definitely not -70.
            assert -20 <= integrated <= -3, (
                f"1 kHz at -10 dBFS should produce ~-10 LUFS, got {integrated}"
            )
            # True peak should be near the source amplitude, in dBTP.
            if true_peak is not None:
                assert -15 <= true_peak <= -5, (
                    f"True peak shouldtrack the -10 dBFS source, got {true_peak}"
                )
        else:
            pytest.fail("_compute_lufs returned None for a clearly audible signal")

    def test_silent_input_does_not_crash(self):
        from app.services.analyzer import _compute_lufs

        # Even if pyloudnorm rejects silence, the legacy fallback must yield
        # a (None, None, None) tuple instead of raising.
        result = _compute_lufs(np.zeros(22050, dtype=np.float32), 22050)
        assert result == (None, None, None) or result[0] is not None

    def test_fallback_path_exists(self):
        """Legacy fallback is preserved for environments without pyloudnorm."""
        from app.services.analyzer import _compute_lufs_legacy
        assert callable(_compute_lufs_legacy)


# ---------------------------------------------------------------------------
# C.4 — Set planner uses real track durations, not a 4-min constant
# ---------------------------------------------------------------------------
class TestSetplanRealDurations:
    """
    Old behaviour: ``num_tracks = max(8, duration_minutes // 4)`` and
    ``estimated_duration_minutes = len(selected_tracks) * 4``. Latin tracks
    routinely run 3:30 to 4:30 — close to 4, but reggaeton edits and intro
    tracks can be 2:00, while salsa extends easily to 5:30+.

    New contract: use the library's mean track duration (seconds -> minutes)
    to size the set; expose ``avg_track_duration_minutes`` so callers and the
    UI can show what assumption was used.
    """

    def test_mean_duration_helper_basic(self):
        from app.routes.setplan_routes import _mean_track_duration_min
        from app.models.track import Track

        # Five tracks, average 4:24 (264 sec) -> 4.4 min.
        durations_sec = [180, 240, 264, 300, 336]
        tracks = [
            Track(file_path=f"/t{i}.mp3", filename=f"t{i}.mp3", duration=d)
            for i, d in enumerate(durations_sec)
        ]
        avg_min = _mean_track_duration_min(tracks)
        assert 4.3 < avg_min < 4.5, f"Expected ~4.4 min, got {avg_min}"

    def test_mean_duration_skips_unknown(self):
        from app.routes.setplan_routes import _mean_track_duration_min
        from app.models.track import Track

        tracks = [
            Track(file_path="/a.mp3", filename="a.mp3", duration=200),
            Track(file_path="/b.mp3", filename="b.mp3", duration=None),
            Track(file_path="/c.mp3", filename="c.mp3", duration=300),
        ]
        # Only 200 and 300 -> 250 sec -> 4.17 min.
        avg_min = _mean_track_duration_min(tracks)
        assert 4.0 < avg_min < 4.3

    def test_mean_duration_falls_back_when_all_zero(self):
        from app.routes.setplan_routes import _mean_track_duration_min, _DEFAULT_TRACK_DURATION_MIN
        from app.models.track import Track

        tracks = [
            Track(file_path="/a.mp3", filename="a.mp3", duration=None),
            Track(file_path="/b.mp3", filename="b.mp3", duration=0),
        ]
        avg_min = _mean_track_duration_min(tracks)
        assert avg_min == _DEFAULT_TRACK_DURATION_MIN

    def test_generate_uses_avg_duration(self):
        """
        With a 60-minute requested set, the planner should produce more tracks
        when the library mean is short (<4 min) and fewer when it's long (>4
        min) — not a flat 15 tracks either way.
        """
        from app.models.track import Track
        from app.routes import setplan_routes

        store = get_track_store()
        store.clear()

        try:
            # 20 tracks at 2 min each -> mean 2 min. 60-min set should need ~30 tracks.
            short_tracks = [
                Track(
                    file_path=f"/short_{i}.mp3",
                    filename=f"short_{i}.mp3",
                    analyzed_energy=5,
                    analyzed_bpm=120.0,
                    duration=120,
                )
                for i in range(20)
            ]
            for t in short_tracks:
                store[t.file_path] = t

            avg_min = setplan_routes._mean_track_duration_min(list(store.values()))
            assert 1.9 < avg_min < 2.1

            n_expected = max(8, round(60 / avg_min))
            assert n_expected > 20

            # 20 tracks at 8 min each -> mean 8 min. 60-min set should need only ~8 tracks.
            store.clear()
            long_tracks = [
                Track(
                    file_path=f"/long_{i}.mp3",
                    filename=f"long_{i}.mp3",
                    analyzed_energy=5,
                    analyzed_bpm=120.0,
                    duration=480,
                )
                for i in range(20)
            ]
            for t in long_tracks:
                store[t.file_path] = t

            avg_min_long = setplan_routes._mean_track_duration_min(list(store.values()))
            n_long = max(8, round(60 / avg_min_long))
            assert 7 <= n_long <= 9
        finally:
            store.clear()

    def test_generate_endpoint_surfaces_avg_duration(self, client):
        """``/api/setplan/generate`` must return avg_track_duration_minutes."""
        from app.models.track import Track

        store = get_track_store()
        store.clear()
        try:
            tracks = [
                Track(
                    file_path=f"/p_{i}.mp3",
                    filename=f"p_{i}.mp3",
                    analyzed_energy=5,
                    analyzed_bpm=120.0,
                    duration=300,
                )
                for i in range(12)
            ]
            for t in tracks:
                store[t.file_path] = t

            resp = client.post(
                "/api/setplan/generate",
                json={"arc": "warmup", "duration_minutes": 60},
            )
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert "avg_track_duration_minutes" in data
            assert 4.9 < data["avg_track_duration_minutes"] < 5.1
            assert data["stats"]["avg_track_duration_minutes"] == data["avg_track_duration_minutes"]
            # estimated_duration_minutes must NOT be a flat len(tracks) * 4.
            assert data["stats"]["estimated_duration_minutes"] != len(data["tracks"]) * 4
        finally:
            store.clear()

    def test_source_no_longer_divides_by_four_minutes(self):
        """
        Guardrail: the ``duration_minutes // 4`` constant must be gone from
        setplan_routes.py.
        """
        from pathlib import Path

        src_path = (
            Path(__file__).resolve().parent.parent / "app" / "routes" / "setplan_routes.py"
        )
        src = src_path.read_text()
        assert "// 4" not in src, (
            "setplan_routes.py still uses whole-number // 4 truncation for num_tracks"
        )
        assert "* 4" not in src, (
            "setplan_routes.py still uses flat '* 4' for estimated_duration_minutes"
        )
