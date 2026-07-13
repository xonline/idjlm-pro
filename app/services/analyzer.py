import re as _re
import numpy as np
import librosa

from app.models.track import Track


# Camelot wheel mapping: pitch class (0-11) to major/minor keys
# Index corresponds to chromatic scale: C=0, C#=1, D=2, D#=3, E=4, F=5, F#=6, G=7, G#=8, A=9, A#=10, B=11

def compute_waveform_peaks(file_path: str, num_samples: int = 600) -> list:
    """Compute peak amplitude per segment for waveform visualization.
    Returns num_samples normalised floats (0.0-1.0) using librosa.
    Skips loading if audio is already available via analyze_track integration.
    """
    try:
        y, sr = librosa.load(file_path, sr=22050, mono=True)
        mono = np.abs(y)
        chunk_size = max(1, len(mono) // num_samples)
        peaks = []
        for i in range(num_samples):
            start = i * chunk_size
            end = start + chunk_size
            chunk = mono[start:end]
            peaks.append(float(chunk.max()) if len(chunk) > 0 else 0.0)
        max_val = max(peaks) if peaks else 1.0
        if max_val > 0:
            peaks = [p / max_val for p in peaks]
        return peaks
    except Exception:
        return []


CAMELOT_MAJOR = {
    0: "8B",    # C major
    1: "3B",    # C#/Db major
    2: "10B",   # D major
    3: "5B",    # D#/Eb major
    4: "12B",   # E major
    5: "7B",    # F major
    6: "2B",    # F#/Gb major
    7: "9B",    # G major
    8: "4B",    # G#/Ab major
    9: "11B",   # A major
    10: "6B",   # A#/Bb major
    11: "1B",   # B major
}

CAMELOT_MINOR = {
    0: "5A",    # A minor (relative to C major)
    1: "12A",   # A#/Bbm minor
    2: "7A",    # B minor
    3: "2A",    # C minor
    4: "9A",    # C#/Dbm minor
    5: "4A",    # D minor
    6: "11A",   # D#/Ebm minor
    7: "6A",    # E minor
    8: "1A",    # F minor
    9: "8A",    # F#/Gbm minor
    10: "3A",   # G minor
    11: "10A",  # G#/Abm minor
}


def _detect_key_from_chroma(chroma: np.ndarray) -> tuple:
    """
    Detect key from chroma features and estimate major/minor.
    chroma shape: (12, time_frames)
    Returns (Camelot notation string, confidence 0-100).
    """
    # Average chroma across time
    chroma_mean = np.mean(chroma, axis=1)

    # Find dominant pitch class (0-11)
    dominant_pitch = np.argmax(chroma_mean)

    # Detect major vs minor using chroma relative energy
    # Simple heuristic: compute energy in major and minor templates
    major_template = np.array([1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1], dtype=float)
    minor_template = np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 0, 1], dtype=float)

    # Rotate templates to dominant pitch
    major_template_rotated = np.roll(major_template, dominant_pitch)
    minor_template_rotated = np.roll(minor_template, dominant_pitch)

    major_score = np.sum(chroma_mean * major_template_rotated)
    minor_score = np.sum(chroma_mean * minor_template_rotated)

    # Determine mode: if minor score is notably higher, it's minor
    is_minor = minor_score > major_score * 1.1

    # Compute confidence from template score difference
    max_score = max(major_score, minor_score, 1e-6)
    min_score = min(major_score, minor_score)
    confidence = min(100, int((1 - min_score / max_score) * 100))

    # Map to Camelot
    camelot_dict = CAMELOT_MINOR if is_minor else CAMELOT_MAJOR
    camelot_key = camelot_dict.get(dominant_pitch, "Unknown")

    return camelot_key, confidence


def _normalize_energy(rms: np.ndarray) -> int:
    """
    Per-track fallback normalization. Only invoked when the library has fewer
    than two analyzed RMS samples (so library-relative percentile cannot be
    computed yet). Uses the natural log of the RMS mean compressed into the
    1-10 scale — independent of any hardcoded ceiling.
    """
    rms_mean = max(1e-6, float(np.mean(rms)))

    # log10(rms) typically spans -3.5 to -0.2 (-70 dBFS to -2 dBFS).
    # Map [-3.5, -0.2] -> [1, 10]. Values outside clamp to the bounds.
    log_rms = np.log10(rms_mean)
    score = 1 + (log_rms + 3.5) * 9 / 3.3  # -3.5 -> 1, -0.2 -> 10
    score = max(1, min(10, int(round(score))))

    return score


def apply_library_percentile_normalization(tracks: list) -> int:
    """
    Reassign ``analyzed_energy`` for every analyzed track using the library's own
    RMS distribution. Track RMS means are mapped to percentile rank inside *this*
    collection, then percentile -> 1-10 scale.

    Returns the number of tracks rescaled.
    Tracks without ``raw_rms`` (or with non-positive RMS) are left untouched.
    """
    rms_by_track = [(t, float(t.raw_rms)) for t in tracks if t.raw_rms is not None and t.raw_rms > 0]
    if not rms_by_track:
        return 0

    sorted_rms = sorted(rms for _, rms in rms_by_track)
    n = len(sorted_rms)

    if n < 2:
        # Single track — force-score to 5 so the UI has something usable.
        for track, _ in rms_by_track:
            track.analyzed_energy = 5
        return n

    for track, raw in rms_by_track:
        # Count values strictly below, plus half the ties.
        below = 0
        equal = 0
        for v in sorted_rms:
            if v < raw:
                below += 1
            elif v == raw:
                equal += 1
            else:
                break
        # Average of the tied ranks keeps the mapping monotonic.
        percentile = (below + (equal - 1) / 2.0) / (n - 1)
        percentile = max(0.0, min(1.0, percentile))

        score = int(round(1 + percentile * 9))
        track.analyzed_energy = max(1, min(10, score))

    return n


def _compute_energy_timeline(y: np.ndarray, sr: int, target_points: int = 300) -> list:
    """
    Compute per-frame RMS energy over time, returning a downsampled list of
    [timestamp_seconds, rms_value] pairs suitable for loudness envelope rendering.
    """
    rms_frames = librosa.feature.rms(y=y)
    rms_values = rms_frames.flatten()
    times = librosa.frames_to_time(np.arange(len(rms_values)), sr=sr, hop_length=512).tolist()

    if len(rms_values) <= target_points:
        return [[round(float(t), 2), round(float(v), 6)] for t, v in zip(times, rms_values)]

    indices = np.linspace(0, len(rms_values) - 1, target_points, dtype=int)
    timeline = []
    for i in indices:
        timeline.append([round(float(times[i]), 2), round(float(rms_values[i]), 6)])
    return timeline


def _detect_phrase_boundaries(y: np.ndarray, sr: int, min_segment_sec: float = 6.0) -> list:
    rms = librosa.feature.rms(y=y)
    rms_env = rms.flatten()
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)

    if len(rms_env) != len(onset_env):
        target_len = len(onset_env)
        rms_env = np.interp(
            np.linspace(0, len(rms_env) - 1, target_len),
            np.arange(len(rms_env)),
            rms_env,
        )

    onset_norm = onset_env / (np.max(onset_env) + 1e-6)
    rms_norm = rms_env / (np.max(rms_env) + 1e-6)

    onset_diff = np.abs(np.diff(onset_norm, prepend=onset_norm[0]))
    rms_diff = np.abs(np.diff(rms_norm, prepend=rms_norm[0]))
    novelty = onset_diff * 0.65 + rms_diff * 0.35

    from scipy.signal import savgol_filter, find_peaks

    win = max(3, int(sr * 1.5 / 512))
    if win % 2 == 0:
        win += 1
    smooth = savgol_filter(novelty, win, 2) if len(novelty) > win else novelty

    min_dist = max(3, int(min_segment_sec * sr / 512))
    peaks, props = find_peaks(smooth, distance=min_dist, prominence=np.std(smooth) * 0.4)

    hop_length = 512
    boundaries = []
    for idx in peaks:
        t = round(float(librosa.frames_to_time(idx, sr=sr, hop_length=hop_length)), 2)
        conf = min(100, int((props["prominences"][np.where(peaks == idx)[0][0]] / (np.max(props["prominences"]) + 1e-6)) * 100))
        boundaries.append([t, conf])

    return boundaries


def detect_vocal_flag(y: np.ndarray, sr: int) -> tuple:
    """
    Detect whether track contains vocals, instrumentals, or mostly instrumentals.
    Returns: (vocal_flag: str, confidence: int)
    vocal_flag one of: "vocal", "instrumental", "mostly_instrumental"
    confidence: 0-100

    Bias: default to "vocal" when uncertain. Latin dance music (salsa, bachata,
    merengue, cumbia) has heavy percussion which suppresses harmonic_ratio even
    when vocals are clearly present — so thresholds are intentionally permissive.
    Only classify "instrumental" when there is strong evidence of no vocals.
    """
    # 1. Harmonic/percussive separation
    y_harmonic, y_percussive = librosa.effects.hpss(y)
    harmonic_rms = float(np.sqrt(np.mean(y_harmonic**2)))
    percussive_rms = float(np.sqrt(np.mean(y_percussive**2)))
    harmonic_ratio = harmonic_rms / (harmonic_rms + percussive_rms + 1e-6)

    # 2. Spectral flatness (higher = more noise-like / less tonal)
    flatness = float(np.mean(librosa.feature.spectral_flatness(y=y)))

    # 3. MFCC variance (vocals produce high variance in MFCCs 1-5)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_var = float(np.mean(np.var(mfcc[1:6], axis=1)))

    # 4. Zero crossing rate (vocals have moderate ZCR)
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))

    # Scoring heuristic — biased toward "vocal":
    # Vocals tend to: moderate-high harmonic ratio, low flatness, high mfcc_var
    # Thresholds are loosened vs. pure-instrument detection to avoid false negatives
    # on Latin dance tracks where percussion competes with harmonic content.
    vocal_score = 0
    if harmonic_ratio > 0.45:   # was 0.55 — Latin percussion lowers this significantly
        vocal_score += 35
    elif harmonic_ratio > 0.35:
        vocal_score += 20
    if flatness < 0.025:        # was 0.015 — loosen to catch vocal tracks with rich instrumentation
        vocal_score += 25
    elif flatness < 0.04:
        vocal_score += 12
    if mfcc_var > 200:          # was 300 — salsa vocals generate ~200-350 range
        vocal_score += 25
    elif mfcc_var > 100:        # was 150
        vocal_score += 10
    if 0.04 < zcr < 0.20:      # was 0.05-0.15 — slightly wider range
        vocal_score += 15

    # Decision thresholds — biased toward "vocal":
    # ≥55 → vocal (was 70), 30-54 → mostly_instrumental (was 45-69), <30 → instrumental (was <45)
    # This means: only call "instrumental" when multiple features strongly suggest no vocals.
    if vocal_score >= 55:
        return "vocal", min(100, vocal_score)
    elif vocal_score >= 30:
        return "mostly_instrumental", min(100, 100 - vocal_score + 30)
    else:
        return "instrumental", min(100, 100 - vocal_score)


_PYLOUDNORM_AVAILABLE = None


def _pyloudnorm_ready() -> bool:
    """Lazy import of pyloudnorm; returns False if not installed/usable."""
    global _PYLOUDNORM_AVAILABLE
    if _PYLOUDNORM_AVAILABLE is not None:
        return _PYLOUDNORM_AVAILABLE
    try:
        import pyloudnorm as pyln  # noqa: F401
        _PYLOUDNORM_AVAILABLE = True
    except Exception:
        _PYLOUDNORM_AVAILABLE = False
    return _PYLOUDNORM_AVAILABLE


def _compute_lufs(y: np.ndarray, sr: int) -> tuple:
    """
    Compute Integrated LUFS (ITU-R BS.1770), LUFS Range (LRA), and True Peak (dBTP).

    Primary path: ``pyloudnorm`` which implements BS.1770-4 gating + K-weighting.
    Fallback: legacy RMS/percentile approximation (kept for environments where
    pyloudnorm is unavailable or the signal is too short for BS.1770 gating).

    Returns: (integrated_lufs, lra, true_peak) or (None, None, None) on total failure.
    """
    if y.ndim > 1:
        y_mono = np.mean(y, axis=1)
    else:
        y_mono = y

    # Try pyloudnorm (BS.1770) first.
    if _pyloudnorm_ready():
        try:
            import pyloudnorm as pyln

            # pyloudnorm expects float in [-1, 1]; librosa.load produces that.
            meter = pyln.Meter(sr)
            integrated = float(meter.integrated_loudness(y_mono))
            if np.isnan(integrated) or np.isinf(integrated):
                raise ValueError("pyloudnorm returned non-finite integrated LUFS")

            # True peak via pyloudnorm's own helper (4x oversample).
            try:
                true_peak = float(pyln.metrics.true_peak(sr, y_mono))
            except Exception:
                # Approximate from raw sample peak if true_peak helper unavailable
                peak = float(np.max(np.abs(y_mono)))
                true_peak = 20.0 * np.log10(peak) if peak > 0 else -70.0

            # LRA — pyloudnorm expects a BS.1770 momentary loudness array. Cheapest
            # correct path: compute integrated on each 3-second window.
            try:
                window_size = int(sr * 3.0)
                if len(y_mono) >= window_size:
                    short_term = []
                    for start in range(0, len(y_mono) - window_size + 1, window_size):
                        s_val = float(meter.integrated_loudness(y_mono[start:start + window_size]))
                        if not (np.isnan(s_val) or np.isinf(s_val)):
                            short_term.append(s_val)
                    if len(short_term) >= 2:
                        short_term = np.array(short_term)
                        p10 = float(np.percentile(short_term, 10))
                        p95 = float(np.percentile(short_term, 95))
                        lra = round(p95 - p10, 1)
                    else:
                        lra = None
                else:
                    lra = None
            except Exception:
                lra = None

            return round(integrated, 1), lra, round(true_peak, 1)

        except Exception:
            # Fall through to legacy path.
            pass

    return _compute_lufs_legacy(y_mono, sr)


def _compute_lufs_legacy(y: np.ndarray, sr: int) -> tuple:
    """
    Legacy LUFS approximation using only numpy/librosa. Provided as a fallback
    when pyloudnorm is unavailable or rejects the signal.
    """
    try:
        # Ensure mono
        if y.ndim > 1:
            y = np.mean(y, axis=1)

        # 1. K-weighted pre-filtering: high-pass below 100Hz, boost 1.5kHz-4kHz
        # Simple FIR high-pass at 100 Hz
        nyquist = sr / 2.0
        100.0 / nyquist
        # Use a simple difference-based high-pass approximation
        # y_filtered = y - low_pass(y); approximate low-pass with rolling mean
        hp_taps = max(3, int(sr / 100))  # ~100 Hz window
        if hp_taps > len(y):
            hp_taps = len(y)
        kernel = np.ones(hp_taps) / hp_taps
        low_freq = np.convolve(y, kernel, mode='same')
        y_hp = y - low_freq

        # Boost 1.5kHz-4kHz region with a simple band-pass energy boost
        # Approximate: compute energy in mid-high freq band and amplify
        1500.0 / nyquist
        4000.0 / nyquist
        bp_taps_low = max(3, int(sr / 1500))
        bp_taps_high = max(3, int(sr / 4000))
        if bp_taps_low > len(y_hp):
            bp_taps_low = len(y_hp)
        if bp_taps_high > len(y_hp):
            bp_taps_high = len(y_hp)
        bp_kernel_low = np.ones(bp_taps_low) / bp_taps_low
        bp_kernel_high = np.ones(bp_taps_high) / bp_taps_high
        band_low = np.convolve(y_hp, bp_kernel_low, mode='same')
        band_high = np.convolve(y_hp, bp_kernel_high, mode='same')
        band_mid = band_low - band_high
        # Add 3dB boost to mid band
        y_kweighted = y_hp + 0.4 * band_mid

        # 2. Compute RMS in 400ms windows with 100ms hop
        window_size = int(sr * 0.4)
        hop_size = int(sr * 0.1)
        if window_size > len(y_kweighted):
            window_size = len(y_kweighted)
            hop_size = max(1, window_size // 4)

        rms_values = []
        for start in range(0, len(y_kweighted) - window_size + 1, hop_size):
            segment = y_kweighted[start:start + window_size]
            rms = np.sqrt(np.mean(segment ** 2))
            rms_values.append(rms)

        if not rms_values:
            return None, None, None

        rms_values = np.array(rms_values)

        # 3. Convert to dBFS: 20 * log10(rms / 1.0), clamped to -70 LUFS floor
        with np.errstate(divide='ignore', invalid='ignore'):
            dbfs = np.where(rms_values > 0, 20 * np.log10(rms_values), -70.0)
        dbfs = np.maximum(dbfs, -70.0)

        # 4. Relative threshold gating: exclude windows below -10 LUFS of mean
        mean_dbfs = float(np.mean(dbfs))
        threshold = mean_dbfs - 10.0
        gated = dbfs[dbfs >= threshold]

        if len(gated) == 0:
            # Fallback: use all windows
            gated = dbfs

        # 5. Integrated LUFS = mean of gated windows
        integrated_lufs = round(float(np.mean(gated)), 1)

        # 6. LUFS Range (LRA) — difference between 10th and 90th percentile
        p10 = float(np.percentile(gated, 10))
        p90 = float(np.percentile(gated, 90))
        lra = round(p90 - p10, 1)

        # 7. True Peak — max absolute sample value converted to dBFS
        true_peak_linear = float(np.max(np.abs(y_kweighted)))
        if true_peak_linear > 0:
            true_peak = round(20 * np.log10(true_peak_linear), 1)
            true_peak = max(true_peak, -70.0)
        else:
            true_peak = -70.0

        return integrated_lufs, lra, true_peak

    except Exception:
        return None, None, None



# Standard music key → Camelot wheel mapping for _normalize_key_to_camelot
_KEY_NAME_TO_CAMELOT = {
    # Major keys
    ('C', False): '8B',  ('D', False): '10B', ('E', False): '12B',
    ('F', False): '7B',  ('G', False): '9B',  ('A', False): '11B',
    ('B', False): '1B',  ('Db', False): '3B', ('Eb', False): '5B',
    ('Gb', False): '2B', ('Ab', False): '4B', ('Bb', False): '6B',
    ('C#', False): '3B', ('D#', False): '5B', ('F#', False): '2B',
    ('G#', False): '4B', ('A#', False): '6B',
    # Minor keys
    ('A', True): '8A',  ('B', True): '2A',  ('C', True): '5A',
    ('D', True): '7A',  ('E', True): '9A',  ('F', True): '4A',
    ('G', True): '11A', ('Ab', True): '1A', ('Bb', True): '3A',
    ('Db', True): '12A', ('Eb', True): '6A',
    ('Gb', True): '10A', ('A#', True): '3A', ('D#', True): '6A',
    ('C#', True): '12A', ('F#', True): '11A', ('G#', True): '1A',
}


def _normalize_key_to_camelot(raw_key: str):
    """
    Convert various key notations to Camelot format (e.g. "8A", "11B").
    Handles:
    - Already Camelot: "8A", "11B" — returned as-is
    - OpenKey: "6m" / "6d" — "6A" / "6B"
    - Standard: "C major", "Am", "F# minor", "Ebm" etc.
    Returns None if unrecognizable.
    """
    if not raw_key:
        return None
    s = raw_key.strip()

    # Already Camelot notation (1-12 + A/B)
    if _re.match(r'^\d{1,2}[ABab]$', s):
        return s[:-1] + s[-1].upper()

    # OpenKey: "6m" (minor=A) / "6d" (major=B)
    m = _re.match(r'^(\d{1,2})([mMdD])$', s)
    if m:
        num, mode = m.group(1), m.group(2).lower()
        return f"{num}A" if mode == 'm' else f"{num}B"

    # Try "C# minor", "Bb Major" with full mode word
    m = _re.match(r'^([A-Ga-g][#b]?)\s+(major|minor|maj|min)\s*$', s, _re.IGNORECASE)
    if m:
        root_raw, mode_word = m.group(1), m.group(2).lower()
        is_minor = mode_word in ('minor', 'min')
        root = root_raw[0].upper() + root_raw[1:] if len(root_raw) > 1 else root_raw.upper()
        return _KEY_NAME_TO_CAMELOT.get((root, is_minor))

    # Try compact: "C", "Am", "C#m", "Ebm", "F#"
    m = _re.match(r'^([A-Ga-g])([#b]?)(m|M)?$', s)
    if m:
        note, acc, mode_char = m.group(1).upper(), m.group(2), m.group(3) or ''
        root = note + acc
        is_minor = mode_char.lower() == 'm'
        return _KEY_NAME_TO_CAMELOT.get((root, is_minor))

    return None


def _read_tags_bpm_key(file_path: str):
    """
    Read BPM and key from existing audio tags via mutagen.
    Returns (bpm_float, camelot_key_str) or (None, None).
    """
    try:
        import mutagen
        audio = mutagen.File(file_path, easy=True)
        if audio is None:
            return None, None

        bpm = None
        key = None

        bpm_tag = audio.get('bpm') or audio.get('tempo')
        key_tag = audio.get('initialkey') or audio.get('key')

        if bpm_tag:
            try:
                bpm = round(float(str(bpm_tag[0]).strip()), 1)
                if bpm < 40 or bpm > 300:  # sanity check
                    bpm = None
            except (ValueError, IndexError):
                bpm = None

        if key_tag:
            raw_key = str(key_tag[0]).strip()
            if raw_key:
                key = _normalize_key_to_camelot(raw_key)

        return bpm, key
    except Exception:
        return None, None


def _compute_tempo_category(bpm, genre):
    if not bpm:
        return None
    genre_lower = (genre or "").lower()
    if "bachata" in genre_lower:
        if bpm < 110: return "slow"
        elif bpm < 128: return "medium"
        else: return "fast"
    elif "kizomba" in genre_lower or "zouk" in genre_lower:
        if bpm < 80: return "slow"
        elif bpm < 100: return "medium"
        else: return "fast"
    elif "reggaeton" in genre_lower:
        if bpm < 90: return "slow"
        elif bpm < 105: return "medium"
        else: return "fast"
    else:
        if bpm < 90: return "slow"
        elif bpm < 115: return "medium"
        else: return "fast"


def _apply_bpm_correction(bpm_raw, genre):
    if not bpm_raw:
        return bpm_raw, False
    genre_lower = (genre or "").lower()
    if "bachata" in genre_lower:
        dance_min, dance_max = 110, 145
    elif "kizomba" in genre_lower or "zouk" in genre_lower:
        dance_min, dance_max = 80, 110
    elif "cha cha" in genre_lower or "chacha" in genre_lower:
        dance_min, dance_max = 108, 132
    elif "reggaeton" in genre_lower:
        dance_min, dance_max = 90, 110
    elif "merengue" in genre_lower:
        dance_min, dance_max = 150, 170
    else:
        dance_min, dance_max = 75, 110

    corrected = False
    result = bpm_raw

    if bpm_raw > dance_max * 1.5:
        result = bpm_raw / 2
        corrected = True
    elif bpm_raw < dance_min * 0.7:
        result = bpm_raw * 2
        corrected = True

    if not corrected and bpm_raw > dance_max:
        candidate_4_3 = bpm_raw * 0.75
        if dance_min * 0.9 <= candidate_4_3 <= dance_max * 1.1:
            result = round(candidate_4_3, 1)
            corrected = True

    if not corrected:
        if result > 200:
            result = result / 2
            corrected = True
        elif result < 50:
            result = result * 2
            corrected = True

    if result != round(result, 1):
        result = round(result, 1)
    return result, corrected


def _analyze_track_core(file_path, genre=""):
    """Extract audio features from a file. Returns a dict of results.
    Standalone — no Track object, no cache, no library-relative
    normalization. Designed to be picklable and safe for multiprocessing
    worker processes (only uses module-level imports, no Flask/app state).
    """
    result = {
        "file_path": file_path,
        "analyzed_bpm": None,
        "bpm_from_tags": False,
        "bpm_confidence": None,
        "bpm_corrected": False,
        "analyzed_key": None,
        "key_confidence": None,
        "raw_rms": None,
        "duration": None,
        "energy_timeline": None,
        "phrase_boundaries": None,
        "vocal_flag": None,
        "vocal_confidence": None,
        "tempo_category": None,
        "analyzed_lufs": None,
        "analyzed_lufs_range": None,
        "analyzed_true_peak": None,
        "waveform_data": None,
        "waveform_peaks": None,
        "error": None,
    }

    try:
        existing_bpm, existing_key = _read_tags_bpm_key(file_path)
        skip_bpm = existing_bpm is not None
        skip_key = existing_key is not None
        skip_librosa_load = skip_bpm and skip_key

        y = None
        sr = None
        if not skip_librosa_load:
            y, sr = librosa.load(file_path, sr=22050, mono=True)

        if skip_bpm:
            result["analyzed_bpm"] = existing_bpm
            result["bpm_from_tags"] = True
            result["bpm_confidence"] = 100
        else:
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            bpm_raw, _ = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env)
            bpm_arr = np.asarray(bpm_raw)
            if bpm_arr.size == 0:
                raise ValueError("No BPM detected — audio may be silent or corrupt")
            raw_val = round(float(bpm_arr.item() if bpm_arr.ndim > 0 else bpm_arr), 1)
            onset_ratio = np.max(onset_env) / (np.mean(onset_env) + 1e-6)
            result["bpm_confidence"] = min(100, int(onset_ratio * 15))
            corrected_val, was_corrected = _apply_bpm_correction(raw_val, genre)
            result["analyzed_bpm"] = round(corrected_val, 1) if corrected_val else raw_val
            result["bpm_corrected"] = was_corrected

        result["tempo_category"] = _compute_tempo_category(result["analyzed_bpm"], genre)

        if skip_key:
            result["analyzed_key"] = existing_key
            result["key_confidence"] = 100
        else:
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            result["analyzed_key"], result["key_confidence"] = _detect_key_from_chroma(chroma)

        if y is None:
            y, sr = librosa.load(file_path, sr=22050, mono=True)

        rms = librosa.feature.rms(y=y)
        result["raw_rms"] = round(float(np.mean(rms)), 6)
        result["duration"] = round(float(len(y)) / float(sr), 2)
        result["energy_timeline"] = _compute_energy_timeline(y, sr)
        result["phrase_boundaries"] = _detect_phrase_boundaries(y, sr)

        result["vocal_flag"], result["vocal_confidence"] = detect_vocal_flag(y, sr)

        try:
            lufs, lra, true_peak = _compute_lufs(y, sr)
            result["analyzed_lufs"] = lufs
            result["analyzed_lufs_range"] = lra
            result["analyzed_true_peak"] = true_peak
        except Exception:
            pass

        num_points = 60
        chunk = max(1, len(y) // num_points)
        points = []
        for i in range(num_points):
            segment = y[i * chunk:(i + 1) * chunk]
            points.append(float(np.max(np.abs(segment))) if len(segment) else 0.0)
        max_amp = max(points) if max(points) > 0 else 1.0
        result["waveform_data"] = [round(p / max_amp, 3) for p in points]

        num_peaks = 600
        mono_abs = np.abs(y)
        peak_chunk = max(1, len(mono_abs) // num_peaks)
        raw_peaks = []
        for i in range(num_peaks):
            seg = mono_abs[i * peak_chunk:(i + 1) * peak_chunk]
            raw_peaks.append(float(seg.max()) if len(seg) > 0 else 0.0)
        peak_max = max(raw_peaks) if raw_peaks else 1.0
        if peak_max > 0:
            result["waveform_peaks"] = [round(p / peak_max, 4) for p in raw_peaks]
        else:
            result["waveform_peaks"] = raw_peaks

    except Exception as e:
        result["error"] = f"Audio analysis failed: {str(e)}"

    return result


_ANALYSIS_FIELD_MAP = [
    ("analyzed_bpm", "analyzed_bpm"),
    ("bpm_from_tags", "bpm_from_tags"),
    ("bpm_confidence", "bpm_confidence"),
    ("bpm_corrected", "bpm_corrected"),
    ("analyzed_key", "analyzed_key"),
    ("key_confidence", "key_confidence"),
    ("raw_rms", "raw_rms"),
    ("duration", "duration"),
    ("energy_timeline", "energy_timeline"),
    ("phrase_boundaries", "phrase_boundaries"),
    ("vocal_flag", "vocal_flag"),
    ("vocal_confidence", "vocal_confidence"),
    ("tempo_category", "tempo_category"),
    ("analyzed_lufs", "analyzed_lufs"),
    ("analyzed_lufs_range", "analyzed_lufs_range"),
    ("analyzed_true_peak", "analyzed_true_peak"),
    ("waveform_data", "waveform_data"),
    ("waveform_peaks", "waveform_peaks"),
]


def _apply_result_to_track(track, result):
    for src_key, dst_key in _ANALYSIS_FIELD_MAP:
        val = result.get(src_key)
        if val is not None:
            setattr(track, dst_key, val)
    track.analysis_done = True


def _postprocess_analysis(track):
    from app.services.analysis_cache import put as cache_put
    cache_put(track)


def analyze_track(track: Track) -> Track:
    """
    Analyze audio features: BPM, key (Camelot), energy (1-10), LUFS loudness,
    energy timeline, and phrase/section boundaries.
    """
    if track.error:
        return track
    if track.analysis_done:
        return track

    genre = (track.proposed_genre or track.existing_genre or "").lower()
    result = _analyze_track_core(track.file_path, genre)

    if result.get("error"):
        track.error = result["error"]
        return track

    _apply_result_to_track(track, result)

    try:
        from app import get_track_store
        track_store = get_track_store()
        all_tracks = list(track_store.values()) if isinstance(track_store, dict) else list(track_store)
    except Exception:
        all_tracks = [track]

    rescaled = apply_library_percentile_normalization(all_tracks)
    if rescaled == 0:
        track.analyzed_energy = _normalize_energy(np.array([track.raw_rms or 0.0]))

    if track.duration is None and result.get("duration"):
        track.duration = result["duration"]

    _postprocess_analysis(track)
    return track


def analyze_tracks_batch(file_paths, track_store, progress_queue=None, num_workers=None):
    """Analyze multiple tracks in parallel using a multiprocessing worker pool.

    Each worker process runs :func:`_analyze_track_core` on a single file.
    The parent process applies results back to Track objects, normalizes
    energy across the library, writes the analysis cache, and can push
    progress events into *progress_queue* (a ``queue.Queue`` compatible
    object, matching the SSE progress-reporting semantics).

    Returns:
        (analyzed_count, errors_list)
    """
    import multiprocessing
    import os as _os

    if num_workers is None:
        num_workers = min(_os.cpu_count() or 4, len(file_paths))
    num_workers = max(1, num_workers)

    work_items = []
    skipped = 0
    for fp in file_paths:
        track = track_store.get(fp) if hasattr(track_store, "get") else track_store[fp] if fp in track_store else None
        if track is None:
            continue
        if track.error:
            skipped += 1
            continue
        if track.analysis_done:
            skipped += 1
            continue
        genre = (track.proposed_genre or track.existing_genre or "").lower()
        work_items.append((fp, genre))

    if not work_items:
        if progress_queue is not None:
            progress_queue.put({"done": True, "analyzed": 0, "errors": [], "refetch": True})
        return 0, []

    analyzed = 0
    errors = []
    completed = 0
    total = len(file_paths)
    processed_for_progress = 0

    with multiprocessing.Pool(processes=num_workers) as pool:
        for result in pool.imap_unordered(_analyze_track_worker, work_items):
            completed += 1
            fp = result["file_path"]
            track = track_store.get(fp) if hasattr(track_store, "get") else track_store.get(fp)

            if track is None:
                continue

            if result.get("error"):
                errors.append({"path": fp, "error": result["error"]})
                track.error = result["error"]
                if progress_queue is not None:
                    progress_queue.put({
                        "current": completed,
                        "total": total,
                        "error": result["error"],
                    })
            else:
                _apply_result_to_track(track, result)
                # Fill in duration from analysis if not already set
                if track.duration is None and result.get("duration"):
                    track.duration = result["duration"]
                analyzed += 1
                processed_for_progress += 1
                if progress_queue is not None:
                    progress_queue.put({
                        "current": completed,
                        "total": total,
                        "track": track.display_title,
                        "analyzed": analyzed,
                    })

    # Percentile energy normalization across the whole library
    try:
        all_tracks = list(track_store.values()) if hasattr(track_store, "values") else list(track_store)
        apply_library_percentile_normalization(all_tracks)
    except Exception:
        pass

    # Cache each successfully analyzed track
    for fp, _genre in work_items:
        track = track_store.get(fp) if hasattr(track_store, "get") else track_store.get(fp)
        if track and track.analysis_done and not track.error:
            _postprocess_analysis(track)

    if progress_queue is not None:
        progress_queue.put({"done": True, "analyzed": analyzed, "errors": errors, "refetch": True})

    return analyzed, errors


def _analyze_track_worker(args):
    """Entry point for multiprocessing pool — unpacks args for imap_unordered."""
    file_path, genre = args
    return _analyze_track_core(file_path, genre)
