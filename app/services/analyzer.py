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
    Normalize RMS energy to 1-10 scale.
    rms shape: (1, time_frames)
    """
    rms_mean = np.mean(rms)

    # Normalize to 0-1 range (empirical: typical audio RMS ranges 0.01-0.5)
    normalized = min(1.0, rms_mean / 0.35)  # raised from 0.2 — salsa tracks clustered at 9-10 in calibration testing

    # Scale to 1-10
    energy_score = max(1, int(normalized * 10))
    energy_score = min(10, energy_score)

    return energy_score


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


def _compute_lufs(y: np.ndarray, sr: int) -> tuple:
    """
    Compute Integrated LUFS, LUFS Range (LRA), and True Peak approximation.
    Uses only numpy/librosa — no pyloudnorm.

    Returns: (integrated_lufs, lra, true_peak) or (None, None, None) on failure.
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


def analyze_track(track: Track) -> Track:
    """
    Analyze audio features: BPM, key (Camelot), energy (1-10), LUFS loudness.
    Populates: analyzed_bpm, analyzed_key, analyzed_energy, analyzed_lufs,
               analyzed_lufs_range, analyzed_true_peak, analysis_done=True
    Applies BPM correction: if > 160, halve it; if < 70, double it.
    Sets bpm_corrected=True if a correction was applied.
    Sets bpm_from_tags=True when BPM was read from existing file tags.
    Sets track.error on exception.

    Optimization: reads existing BPM/key tags first (mutagen). If both are
    present and valid, skips librosa BPM+key detection entirely. LUFS/energy
    analysis always runs regardless.
    """
    if track.error:
        return track

    try:
        # ------------------------------------------------------------------ #
        # Step 1: Try to read existing BPM / key from file tags               #
        # ------------------------------------------------------------------ #
        existing_bpm, existing_key = _read_tags_bpm_key(track.file_path)

        skip_bpm = existing_bpm is not None
        skip_key = existing_key is not None
        skip_librosa_load = skip_bpm and skip_key

        # ------------------------------------------------------------------ #
        # Step 2: Load audio (required for energy/LUFS/waveform, and for any #
        #         BPM or key that couldn't be read from tags)                 #
        # ------------------------------------------------------------------ #
        y = None
        sr = None
        if not skip_librosa_load:
            y, sr = librosa.load(track.file_path, sr=22050, mono=True)

        # ------------------------------------------------------------------ #
        # Step 3: BPM — use tag value if available, else run librosa          #
        # ------------------------------------------------------------------ #
        if skip_bpm:
            track.analyzed_bpm = existing_bpm
            track.bpm_from_tags = True
            track.bpm_confidence = 100  # tag-sourced is authoritative
        else:
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            bpm, _ = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env)
            # librosa returns ndarray; handle empty, single, and multi-element arrays
            bpm_arr = np.asarray(bpm)
            if bpm_arr.size == 0:
                raise ValueError("No BPM detected — audio may be silent or corrupt")
            track.analyzed_bpm = round(float(bpm_arr.item() if bpm_arr.ndim > 0 else bpm_arr), 1)

            # BPM confidence — based on onset strength peak clarity
            onset_ratio = np.max(onset_env) / (np.mean(onset_env) + 1e-6)
            track.bpm_confidence = min(100, int(onset_ratio * 15))

            # Genre-aware BPM half/double correction for Latin dance tempos
            # librosa detects the raw beat frequency, which for salsa is typically
            # double what DJs think of as the BPM (e.g. 189 detected → 95 dance BPM)
            bpm_raw = track.analyzed_bpm
            genre = (track.proposed_genre or track.existing_genre or "").lower()

            # Expected DJ dance BPM ranges (what the final result should be)
            if "bachata" in genre:
                dance_min, dance_max = 110, 145
            elif "kizomba" in genre or "zouk" in genre:
                dance_min, dance_max = 80, 110
            elif "cha cha" in genre or "chacha" in genre:
                dance_min, dance_max = 108, 132  # natural range — no 4/3 correction
            elif "reggaeton" in genre:
                dance_min, dance_max = 90, 110
            elif "merengue" in genre:
                dance_min, dance_max = 150, 170
            else:  # Salsa, son, timba — clave causes 4/3 over-detection
                dance_min, dance_max = 75, 110

            # If raw BPM is roughly double the dance range, halve it
            if bpm_raw > dance_max * 1.5:
                track.analyzed_bpm = bpm_raw / 2
                track.bpm_corrected = True
            # If raw BPM is roughly half the dance range, double it
            elif bpm_raw < dance_min * 0.7:
                track.analyzed_bpm = bpm_raw * 2
                track.bpm_corrected = True

            # Check 4/3 correction (librosa sometimes detects at 4/3 speed for syncopated Latin rhythms)
            # e.g. salsa 112 * 0.75 = 84 BPM (expected ~85)
            if not track.bpm_corrected and bpm_raw > dance_max:
                candidate_4_3 = bpm_raw * 0.75
                if dance_min * 0.9 <= candidate_4_3 <= dance_max * 1.1:
                    track.analyzed_bpm = round(candidate_4_3, 1)
                    track.bpm_corrected = True

            # Fallback: absolute correction for edge cases
            if not track.bpm_corrected:
                if track.analyzed_bpm > 200:
                    track.analyzed_bpm = track.analyzed_bpm / 2
                    track.bpm_corrected = True
                elif track.analyzed_bpm < 50:
                    track.analyzed_bpm = track.analyzed_bpm * 2
                    track.bpm_corrected = True

        # Tempo category based on genre + BPM (always derived from final BPM)
        bpm = track.analyzed_bpm
        genre = (track.proposed_genre or track.existing_genre or "").lower()

        if bpm:
            # Genre-aware BPM ranges for Latin dance styles
            if "bachata" in genre:
                if bpm < 110: tempo_cat = "slow"
                elif bpm < 128: tempo_cat = "medium"
                else: tempo_cat = "fast"
            elif "kizomba" in genre or "zouk" in genre:
                if bpm < 80: tempo_cat = "slow"
                elif bpm < 100: tempo_cat = "medium"
                else: tempo_cat = "fast"
            elif "reggaeton" in genre:
                if bpm < 90: tempo_cat = "slow"
                elif bpm < 105: tempo_cat = "medium"
                else: tempo_cat = "fast"
            else:  # Salsa, Merengue, Cha Cha, default
                if bpm < 90: tempo_cat = "slow"
                elif bpm < 115: tempo_cat = "medium"
                else: tempo_cat = "fast"
            track.tempo_category = tempo_cat

        # ------------------------------------------------------------------ #
        # Step 4: Key — use tag value if available, else run librosa chroma   #
        # ------------------------------------------------------------------ #
        if skip_key:
            track.analyzed_key = existing_key
            track.key_confidence = 100  # tag-sourced is authoritative
        else:
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            track.analyzed_key, track.key_confidence = _detect_key_from_chroma(chroma)

        # ------------------------------------------------------------------ #
        # Step 5: Energy, vocals, LUFS — always run (these are our value-add  #
        #         and not stored in standard tags)                             #
        # ------------------------------------------------------------------ #
        # If we skipped librosa.load above, load now for energy/vocal/LUFS
        if y is None:
            y, sr = librosa.load(track.file_path, sr=22050, mono=True)

        # Energy score
        # Compute RMS directly from waveform (compatible with all librosa versions)
        rms = librosa.feature.rms(y=y)
        track.analyzed_energy = _normalize_energy(rms)

        # Vocal detection
        vocal_flag, vocal_confidence = detect_vocal_flag(y, sr)
        track.vocal_flag = vocal_flag
        track.vocal_confidence = vocal_confidence

        # LUFS loudness analysis (non-blocking — sets to None on failure)
        try:
            lufs, lra, true_peak = _compute_lufs(y, sr)
            track.analyzed_lufs = lufs
            track.analyzed_lufs_range = lra
            track.analyzed_true_peak = true_peak
        except Exception:
            track.analyzed_lufs = None
            track.analyzed_lufs_range = None
            track.analyzed_true_peak = None

        # Waveform thumbnail: 60 amplitude points across full track
        num_points = 60
        chunk = max(1, len(y) // num_points)
        points = []
        for i in range(num_points):
            segment = y[i * chunk:(i + 1) * chunk]
            points.append(float(np.max(np.abs(segment))) if len(segment) else 0.0)
        max_amp = max(points) if max(points) > 0 else 1.0
        track.waveform_data = [round(p / max_amp, 3) for p in points]

        # High-resolution waveform peaks: 600 amplitude points for detail panel
        if not track.waveform_peaks:
            num_peaks = 600
            mono_abs = np.abs(y)
            peak_chunk = max(1, len(mono_abs) // num_peaks)
            raw_peaks = []
            for i in range(num_peaks):
                seg = mono_abs[i * peak_chunk:(i + 1) * peak_chunk]
                raw_peaks.append(float(seg.max()) if len(seg) > 0 else 0.0)
            peak_max = max(raw_peaks) if raw_peaks else 1.0
            if peak_max > 0:
                track.waveform_peaks = [round(p / peak_max, 4) for p in raw_peaks]
            else:
                track.waveform_peaks = raw_peaks

        track.analysis_done = True

    except Exception as e:
        track.error = f"Audio analysis failed: {str(e)}"

    return track
