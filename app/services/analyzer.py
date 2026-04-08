import numpy as np
import librosa

from app.models.track import Track


# Camelot wheel mapping: pitch class (0-11) to major/minor keys
# Index corresponds to chromatic scale: C=0, C#=1, D=2, D#=3, E=4, F=5, F#=6, G=7, G#=8, A=9, A#=10, B=11
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
    normalized = min(1.0, rms_mean / 0.2)

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

    # Scoring heuristic:
    # Vocals tend to: high harmonic ratio, low-moderate flatness, high mfcc_var
    vocal_score = 0
    if harmonic_ratio > 0.55:
        vocal_score += 35
    if flatness < 0.015:
        vocal_score += 25
    if mfcc_var > 300:
        vocal_score += 25
    elif mfcc_var > 150:
        vocal_score += 10
    if 0.05 < zcr < 0.15:
        vocal_score += 15

    if vocal_score >= 70:
        return "vocal", min(100, vocal_score)
    elif vocal_score >= 45:
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
        cutoff = 100.0 / nyquist
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
        bp_low = 1500.0 / nyquist
        bp_high = 4000.0 / nyquist
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


def analyze_track(track: Track) -> Track:
    """
    Analyze audio features: BPM, key (Camelot), energy (1-10), LUFS loudness.
    Populates: analyzed_bpm, analyzed_key, analyzed_energy, analyzed_lufs,
               analyzed_lufs_range, analyzed_true_peak, analysis_done=True
    Applies BPM correction: if > 160, halve it; if < 70, double it.
    Sets bpm_corrected=True if a correction was applied.
    Sets track.error on exception.
    """
    if track.error:
        return track

    try:
        # Load audio
        y, sr = librosa.load(track.file_path, sr=22050, mono=True)

        # BPM detection
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        bpm, _ = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env)
        # librosa returns ndarray; handle empty, single, and multi-element arrays
        bpm_arr = np.asarray(bpm)
        if bpm_arr.size == 0:
            raise ValueError("No BPM detected — audio may be silent or corrupt")
        track.analyzed_bpm = float(bpm_arr.item() if bpm_arr.ndim > 0 else bpm_arr)

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
        elif "reggaeton" in genre:
            dance_min, dance_max = 90, 110
        elif "merengue" in genre:
            dance_min, dance_max = 150, 170
        else:  # Salsa, Cha Cha, default — librosa detects double for salsa
            dance_min, dance_max = 75, 110

        # If raw BPM is roughly double the dance range, halve it
        if bpm_raw > dance_max * 1.5:
            track.analyzed_bpm = bpm_raw / 2
            track.bpm_corrected = True
        # If raw BPM is roughly half the dance range, double it
        elif bpm_raw < dance_min * 0.7:
            track.analyzed_bpm = bpm_raw * 2
            track.bpm_corrected = True

        # Fallback: absolute correction for edge cases
        if not track.bpm_corrected:
            if track.analyzed_bpm > 200:
                track.analyzed_bpm = track.analyzed_bpm / 2
                track.bpm_corrected = True
            elif track.analyzed_bpm < 50:
                track.analyzed_bpm = track.analyzed_bpm * 2
                track.bpm_corrected = True

        # Tempo category based on genre + BPM
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

        # Key detection via chroma features
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        track.analyzed_key, track.key_confidence = _detect_key_from_chroma(chroma)

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

        track.analysis_done = True

    except Exception as e:
        track.error = f"Audio analysis failed: {str(e)}"

    return track
