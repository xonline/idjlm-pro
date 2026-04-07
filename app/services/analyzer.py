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


def analyze_track(track: Track) -> Track:
    """
    Analyze audio features: BPM, key (Camelot), energy (1-10).
    Populates: analyzed_bpm, analyzed_key, analyzed_energy, analysis_done=True
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

        # BPM half/double correction for Latin dance tempos
        if track.analyzed_bpm > 160:
            track.analyzed_bpm = track.analyzed_bpm / 2
            track.bpm_corrected = True
        elif track.analyzed_bpm < 70:
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
