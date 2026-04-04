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


def _detect_key_from_chroma(chroma: np.ndarray) -> str:
    """
    Detect key from chroma features and estimate major/minor.
    chroma shape: (12, time_frames)
    Returns Camelot notation string.
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

    # Map to Camelot
    camelot_dict = CAMELOT_MINOR if is_minor else CAMELOT_MAJOR
    camelot_key = camelot_dict.get(dominant_pitch, "Unknown")

    return camelot_key


def _normalize_energy(rms: np.ndarray, sr: int, hop_length: int) -> int:
    """
    Normalize RMS energy to 1-10 scale.
    rms shape: (1, time_frames)
    """
    # Flatten and compute mean RMS
    rms_mean = np.mean(rms)

    # Normalize to 0-1 range (empirical: typical audio RMS ranges 0.01-0.5)
    normalized = min(1.0, rms_mean / 0.2)

    # Scale to 1-10
    energy_score = max(1, int(normalized * 10))
    energy_score = min(10, energy_score)

    return energy_score


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
        track.analyzed_bpm = float(bpm)

        # BPM half/double correction for Latin dance tempos
        if track.analyzed_bpm > 160:
            track.analyzed_bpm = track.analyzed_bpm / 2
            track.bpm_corrected = True
        elif track.analyzed_bpm < 70:
            track.analyzed_bpm = track.analyzed_bpm * 2
            track.bpm_corrected = True

        # Key detection via chroma features
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        track.analyzed_key = _detect_key_from_chroma(chroma)

        # Energy score
        S = librosa.feature.melspectrogram(y=y, sr=sr)
        rms = librosa.feature.rms(S=S)
        track.analyzed_energy = _normalize_energy(rms, sr, hop_length=512)

        track.analysis_done = True

    except Exception as e:
        track.error = f"Audio analysis failed: {str(e)}"

    return track
