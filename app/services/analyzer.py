"""Audio analysis: BPM, key, energy."""
import librosa
import numpy as np

# Camelot wheel mapping
CAMALOT_MAPPING = {
    0: "8B", 1: "3B", 2: "10B", 3: "5B", 4: "12B", 5: "7B", 6: "2B",
    7: "9B", 8: "4B", 9: "11B", 10: "6B", 11: "1B",
}

CAMALOT_MAJOR = {v: k for k, v in CAMALOT_MAPPING.items()}
CAMALOT_MINOR = {f"{k}A": v for k, v in CAMALOT_MAJOR.items()}


def analyze_track(track):
    """Extract BPM, key, energy from MP3."""
    try:
        y, sr = librosa.load(track.file_path)

        # BPM via onset detection
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        bpm = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0]
        track.bpm = round(bpm, 1)

        # Key via chroma features
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = chroma.mean(axis=1)
        key_idx = np.argmax(chroma_mean)
        track.key = CAMALOT_MAPPING.get(key_idx, "0A")

        # Energy (RMS normalized to 1-10)
        energy = np.sqrt(np.mean(librosa.feature.melspectrogram(y=y, sr=sr) ** 2))
        track.energy = max(1, min(10, int(energy * 10)))
    except Exception:
        pass
