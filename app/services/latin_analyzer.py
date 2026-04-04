import numpy as np
import librosa

from app.models.track import Track


def detect_clave_pattern(y: np.ndarray, sr: int, bpm: float) -> tuple[str, int]:
    """
    Detect 2-3 vs 3-2 clave pattern using onset strength patterns.

    Returns: (clave_pattern: "2-3"|"3-2"|None, confidence: 0-100)

    Divides track into 2-bar windows (8 beats at semiquaver resolution = 16 steps).
    Correlates against clave templates and uses majority vote.
    """
    try:
        # Compute onset strength
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)

        # Calculate frames per beat
        # BPM = beats per minute, sr = samples per second
        # beat_frame = (60 / bpm) * sr / hop_length
        # librosa.onset.onset_strength uses hop_length=2048 by default
        hop_length = 2048
        frames_per_beat = (60.0 / bpm) * sr / hop_length
        frames_per_2bars = frames_per_beat * 8  # 2 bars = 8 beats

        # Clave templates (16-step semiquaver patterns)
        # 1 = strong onset, 0 = weak
        template_2_3 = np.array([1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0])
        template_3_2 = np.array([1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0])

        # Divide onset_env into 2-bar windows
        num_windows = max(1, len(onset_env) // int(frames_per_2bars))

        if num_windows == 0:
            return None, 0

        votes_2_3 = 0
        votes_3_2 = 0
        valid_windows = 0

        for win_idx in range(num_windows):
            start_frame = int(win_idx * frames_per_2bars)
            end_frame = int((win_idx + 1) * frames_per_2bars)

            if end_frame > len(onset_env):
                break

            window = onset_env[start_frame:end_frame]

            if len(window) < 16:
                continue

            # Resample window to 16 points if necessary
            if len(window) != 16:
                indices = np.linspace(0, len(window) - 1, 16)
                window = np.interp(indices, np.arange(len(window)), window)

            # Normalize window
            window_max = np.max(window)
            if window_max > 0:
                window = window / window_max
            else:
                continue

            # Correlate against templates
            corr_2_3 = np.sum(window * template_2_3)
            corr_3_2 = np.sum(window * template_3_2)

            if corr_2_3 > corr_3_2:
                votes_2_3 += 1
            else:
                votes_3_2 += 1

            valid_windows += 1

        if valid_windows == 0:
            return None, 0

        # Majority vote
        total_votes = votes_2_3 + votes_3_2
        if votes_2_3 > votes_3_2:
            confidence = int((votes_2_3 / total_votes) * 100)
            return "2-3", confidence
        elif votes_3_2 > votes_2_3:
            confidence = int((votes_3_2 / total_votes) * 100)
            return "3-2", confidence
        else:
            # Tie
            return None, 50

    except Exception:
        return None, 0


def detect_montuno_entry(y: np.ndarray, sr: int) -> float:
    """
    Detect montuno (rhythmic breakdown) section by finding where
    rhythmic density increases significantly and sustains.

    Returns: timestamp (seconds) of montuno entry, or 0.0 if not detected.
    """
    try:
        # Compute onset strength (rhythmic density)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)

        # Smooth with moving average to find sustained increases
        window_size = max(1, len(onset_env) // 20)  # ~5% of track length
        if window_size < 2:
            window_size = 2

        smoothed = np.convolve(onset_env, np.ones(window_size) / window_size, mode='valid')

        # Find peak of smoothed onset envelope (highest sustained density)
        if len(smoothed) == 0:
            return 0.0

        peak_idx = np.argmax(smoothed)

        # Convert frame index to time
        hop_length = 2048
        montuno_time = peak_idx * hop_length / sr

        return float(montuno_time)

    except Exception:
        return 0.0


def detect_cue_points(y: np.ndarray, sr: int, bpm: float) -> list:
    """
    Suggest 4 cue points for DJ use.

    Returns: list of {label, position_sec, type} dicts
    """
    cues = []

    try:
        # 1. Beat 1: first strong downbeat (skip intro silence)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        hop_length = 2048

        # Find first significant onset (after 1% of track to skip silence)
        threshold_frame = len(onset_env) // 100
        significant_onsets = np.where(onset_env[threshold_frame:] > np.max(onset_env) * 0.3)[0]

        if len(significant_onsets) > 0:
            beat1_frame = significant_onsets[0] + threshold_frame
            beat1_sec = beat1_frame * hop_length / sr
            cues.append({
                "label": "Beat 1",
                "position_sec": float(beat1_sec),
                "type": "hot_cue"
            })

        # 2. Montuno/Drop: entry point with highest sustained density
        montuno_sec = detect_montuno_entry(y, sr)
        if montuno_sec > 0:
            cues.append({
                "label": "Montuno/Drop",
                "position_sec": montuno_sec,
                "type": "hot_cue"
            })

        # 3. Main hook: section with highest onset strength over 8-bar window
        frames_per_beat = (60.0 / bpm) * sr / hop_length
        window_frames = int(frames_per_beat * 8)  # 8 beats

        if len(onset_env) >= window_frames:
            max_energy = -1
            best_pos = 0
            for i in range(len(onset_env) - window_frames):
                window_energy = np.mean(onset_env[i:i + window_frames])
                if window_energy > max_energy:
                    max_energy = window_energy
                    best_pos = i

            hook_sec = best_pos * hop_length / sr
            cues.append({
                "label": "Main Hook",
                "position_sec": float(hook_sec),
                "type": "hot_cue"
            })

        # 4. Outro: last 20% where energy drops below 40% of peak
        peak_energy = np.max(onset_env)
        threshold = peak_energy * 0.4

        # Find the last 20% of track
        track_len = len(y)
        start_outro = int(track_len * 0.8)

        if start_outro < len(y):
            outro_onsets = onset_env[int(start_outro * hop_length / sr * sr / hop_length):]
            low_energy_indices = np.where(outro_onsets < threshold)[0]

            if len(low_energy_indices) > 0:
                outro_frame = int(start_outro * hop_length / sr * sr / hop_length) + low_energy_indices[0]
                outro_sec = outro_frame * hop_length / sr
                cues.append({
                    "label": "Outro",
                    "position_sec": float(outro_sec),
                    "type": "hot_cue"
                })

    except Exception:
        pass

    return cues


def analyze_latin(track: Track) -> Track:
    """
    Analyze Latin music features: clave pattern, montuno detection, cue points.
    Sets: clave_pattern, clave_confidence, suggested_cues, latin_analysis_done=True
    Returns: track
    """
    if track.error or not track.analyzed_bpm:
        return track

    try:
        # Load audio
        y, sr = librosa.load(track.file_path, sr=22050, mono=True)

        # Detect clave pattern
        clave_pattern, confidence = detect_clave_pattern(y, sr, track.analyzed_bpm)
        track.clave_pattern = clave_pattern
        track.clave_confidence = confidence

        # Detect cue points
        cues = detect_cue_points(y, sr, track.analyzed_bpm)
        track.suggested_cues = cues

        track.latin_analysis_done = True

    except Exception as e:
        track.error = f"Latin analysis failed: {str(e)}"

    return track
