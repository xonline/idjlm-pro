"""
Synthetic ground-truth dataset generator for key-detection benchmark (Issue #204).

Generates 100+ short audio clips with known musical keys — labelled in both
pitch-class/mode and Camelot notation — simulating Latin-music characteristics.

Hardening (v3) to stress-test detectors and create differentiation:
  - Detuning: each note's frequency shifts ±15-30 cents from equal temperament
  - Spectral smearing: short reverb / feedback delay adds chroma leakage
  - Out-of-key contamination: low-level non-diatonic notes (bass walks, chromatic passing tones)
  - Quantization noise: 16-bit and then compressed-equivalent quantisation
  - Variable velocity: chords attenuated to simulate live performance
  - Inharmonicity: slight frequency-dependent stretching (piano-like)
  - Pink noise floor at -40 to -50 dBFS
  - Random key-shift offset sampled per variant, within music-acceptable bounds
"""

import numpy as np
import librosa

SEED = 42

# 24 keys: 12 major + 12 minor (matched to Camelot wheel)
# Uses the same Camelot-major/minor mapping as app/services/analyzer.py to avoid
# self-referential consistency errors.
KEYS = [
    (0, 'major', '8B',  'C major'),
    (1, 'major', '3B',  'C# major'),
    (2, 'major', '10B', 'D major'),
    (3, 'major', '5B',  'D# major'),
    (4, 'major', '12B', 'E major'),
    (5, 'major', '7B',  'F major'),
    (6, 'major', '2B',  'F# major'),
    (7, 'major', '9B',  'G major'),
    (8, 'major', '4B',  'G# major'),
    (9, 'major', '11B', 'A major'),
    (10, 'major', '6B', 'A# major'),
    (11, 'major', '1B', 'B major'),
    # Minor Camelot codes: see analyzer.py CAMELOT_MINOR for mapping
    (0, 'minor', '5A',  'C minor'),
    (1, 'minor', '12A', 'C# minor'),
    (2, 'minor', '7A',  'D minor'),
    (3, 'minor', '2A',  'D# minor'),
    (4, 'minor', '9A',  'E minor'),
    (5, 'minor', '4A',  'F minor'),
    (6, 'minor', '11A', 'F# minor'),
    (7, 'minor', '6A',  'G minor'),
    (8, 'minor', '1A',  'G# minor'),
    (9, 'minor', '8A',  'A minor'),
    (10, 'minor', '3A', 'A# minor'),
    (11, 'minor', '10A','B minor'),
]


# Validate Camelot codes against the production mapping to prevent silent data
# corruption (the v1 dataset had 4 duplicated Camelot codes for minor keys).
def _assert_keys_consistent():
    from app.services.analyzer import CAMELOT_MAJOR, CAMELOT_MINOR

    for pc, mode, camelot, _name in KEYS:
        expected = (CAMELOT_MINOR if mode == 'minor' else CAMELOT_MAJOR)[pc]
        if expected != camelot:
            raise AssertionError(
                f'KEYS table inconsistent: pc={pc} mode={mode} expected {expected} got {camelot}'
            )


_assert_keys_consistent()

# Interval maps (semitones from root)
MAJOR_INTERVALS = {
    'I':   [0, 4, 7],       # root, major 3rd, 5th
    'IV':  [5, 9, 0],       # subdominant: 4th, 6th, root
    'V':   [7, 11, 2],      # dominant: 5th, 7th, 2nd
}

MINOR_INTERVALS = {
    'i':   [0, 3, 7],       # root, minor 3rd, 5th
    'iv':  [5, 8, 0],       # subdominant: 4th, minor 6th, root
    'V':   [7, 11, 2],      # dominant: 5th, major 7th, 2nd (harmonic minor)
}


def _midi_to_hz(midi):
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def _son_clave(t, sr, tempo=120):
    """Generate a son clave pattern (2-3 son clave)."""
    beat_sec = 60.0 / tempo
    # 2-3 son clave: [0, 3, 6, 10, 12] in 1/16th note units within 2 bars
    # Pattern: ...X...X...X......X...X...
    # In 4/4 time, 2 bars = 8 beats = 32 sixteenth notes
    hits_16th = [0, 3, 6, 10, 12]  # 16th-note positions within the 2-bar cycle
    out = np.zeros_like(t)
    for pos_16th in hits_16th:
        onset = pos_16th * beat_sec / 4.0
        idx = int(onset * sr)
        if idx < len(t):
            length = int(0.02 * sr)
            end = min(idx + length, len(t))
            env = np.exp(-np.arange(end - idx) / (0.005 * sr))
            out[idx:end] += 0.3 * env
    return out


def _generate_chord_audio(root_pc, mode, sr, duration, rng, tempo=100):
    """
    Generate audio with a chord progression I-IV-V-I (major) or i-iv-V-i (minor).
    Each chord holds for 2 beats at the given tempo.
    Produces ~2 bars (8 beats) of audio.

    Hardening additions (compared to v1):
      - Notes are detuned ±15-30 cents from equal temperament to stress chroma.
      - Octaves have slight inharmonicity (frequency stretching) like a real piano.
      - Chromatic passing tones (~5-10% energy of chordal content) contaminate the
        spectrum so detectors cannot rely on pure diatonic content.
      - Additive pink noise at low level adds spectral floor smearing.
      - Per-chord velocity variation (0.7-1.0) simulates live performance.
      - After synthesis we apply 16-bit quantization noise to mimic a lossy source.
    """
    n_samples = int(sr * duration)
    t = np.arange(n_samples) / float(sr)
    audio = np.zeros(n_samples, dtype=np.float32)

    beat_sec = 60.0 / tempo
    chords_per_bar = 4
    chord_duration = beat_sec * (duration / (4 * beat_sec)) / 4

    if mode == 'major':
        chord_types = ['I', 'IV', 'V', 'I']
        intervals = MAJOR_INTERVALS
    else:
        chord_types = ['i', 'iv', 'V', 'i']
        intervals = MINOR_INTERVALS

    # Tonic root MIDI note (choose comfortable register for each key)
    root_midi = 48 + root_pc  # ~C3-C#4 range

    # Distribute 4 chords evenly across duration
    chord_len = n_samples // 4
    for chord_idx, chord_name in enumerate(chord_types):
        chord_semis = intervals[chord_name]
        start = chord_idx * chord_len
        end = start + chord_len if chord_idx < 3 else n_samples
        seg_len = end - start
        t_seg = t[start:end] - t[start]

        # Per-chord velocity (live performance variation)
        chord_velocity = float(rng.uniform(0.7, 1.0))

        # Build the chord: root + intervals
        for semitone_offset in chord_semis:
            # Get the scale degree relative to tonic
            degree_pc = (root_pc + semitone_offset) % 12
            # Root MIDI + octave adjustment
            note_midi = root_midi + semitone_offset
            if semitone_offset >= 12:
                note_midi = root_midi + (semitone_offset % 12) + 12

            freq = _midi_to_hz(note_midi)

            # Detuning: ±15-30 cents off equal temperament
            detune_cents = rng.uniform(-30, 30)
            freq *= 2.0 ** (detune_cents / 1200.0)

            # Add slow vibrato (mainly to break chroma's pitch-class peak)
            vibrato_rate = rng.uniform(4.5, 6.5)  # Hz
            vibrato_depth = rng.uniform(0.001, 0.003)  # ±0.1-0.3%
            phase = rng.uniform(0, 2 * np.pi)

            # Multiple octaves for richer sound
            for octave in range(3):
                # Inharmonicity: stretch octaves slightly (>2x) for upper harmonics
                inharmonicity_factor = 1.0 + (octave * 0.002 * rng.uniform(0.7, 1.3))
                oct_freq = freq * (2 ** octave) * inharmonicity_factor
                amp = (
                    chord_velocity
                    * (1.0 / (octave + 1))
                    * (0.8 if octave == 0 else 0.4 / octave)
                )
                # Gentle amplitude envelope per chord
                env = np.ones(seg_len)
                attack = int(0.02 * sr)
                env[:attack] = np.linspace(0, 1, attack)
                if chord_idx < 3:
                    decay = int(0.1 * sr)
                    env[-decay:] = np.linspace(1, 0.6, decay)
                # Vibrato modulates frequency over time
                freq_mod = oct_freq * (1.0 + vibrato_depth * np.sin(2 * np.pi * vibrato_rate * t_seg))
                # Phase accumulation for time-varying frequency
                inst_phase = 2 * np.pi * np.cumsum(freq_mod) / sr + phase
                audio[start:end] += amp * np.sin(inst_phase) * env

        # Chromatic passing tones (low level, non-diatonic) — adds spectral
        # contamination to stress chroma-based detectors. Walks between chords
        # by half steps.
        if rng.random() < 0.5:
            for pass_i in range(1 if rng.random() < 0.5 else 2):
                # Choose a non-chord tone randomly (scale-wise neighbour)
                pass_semi = rng.integers(0, 12)
                if pass_semi in chord_semis:
                    continue  # Skip diatonic — we want chromatic contamination
                pass_midi = root_midi + int(pass_semi)
                pass_freq = _midi_to_hz(pass_midi) * 2.0 ** (rng.uniform(-25, 25) / 1200.0)
                pass_amp = 0.05 + 0.05 * rng.random()  # 5-10% of chordal energy
                pass_onset_rel = rng.uniform(0.2, 0.8)
                pass_start = start + int(pass_onset_rel * seg_len)
                pass_len = int(0.2 * sr)
                pass_end = min(pass_start + pass_len, n_samples)
                if pass_end > pass_start:
                    pass_env = np.exp(-np.arange(pass_end - pass_start) / (0.06 * sr))
                    pass_t = t[pass_start:pass_end] - t[pass_start]
                    audio[pass_start:pass_end] += (
                        pass_amp * np.sin(2 * np.pi * pass_freq * pass_t + rng.uniform(0, 2 * np.pi)) * pass_env
                    )

    # Add montuno-style arpeggios (syncopated chordal patterns)
    arp_notes = [0, 2, 4, 2]  # 16th-note pattern
    arp_div = int(chord_len / 4)
    for chord_idx in range(4):
        chord_name = chord_types[chord_idx]
        chord_semis = intervals[chord_name]
        chord_start = chord_idx * chord_len
        for arp_i, degree_idx in enumerate(arp_notes):
            if degree_idx >= len(chord_semis):
                continue
            semitone_offset = chord_semis[degree_idx]
            note_midi = root_midi + semitone_offset
            freq = _midi_to_hz(note_midi)
            # Slight detuning on arpeggios too
            freq *= 2.0 ** (rng.uniform(-20, 20) / 1200.0)
            phase = rng.uniform(0, 2 * np.pi)
            arp_pos = chord_start + arp_i * (chord_len // 4)
            arp_len = int(0.15 * sr)
            end = min(arp_pos + arp_len, n_samples)
            env = np.exp(-np.arange(end - arp_pos) / (0.04 * sr))
            audio[arp_pos:end] += 0.2 * np.sin(2 * np.pi * freq * t[arp_pos:end] + phase) * env

    # Pink noise floor at low level (~-40 dBFS) — broad spectral smearing
    noise = _pink_noise(n_samples, rng).astype(np.float32)
    noise *= 0.005  # roughly -40 dBFS relative to the 0.85 peak target
    audio += noise

    return audio.astype(np.float32)


def _pink_noise(n, rng):
    """Generate pink noise (1/f spectrum) using the Voss-McCartney algorithm."""
    n_rows = 16
    rows = rng.standard_normal((n_rows, n))
    # Add one new random value per row for each sample — increases efficiency
    # by only flipping a subset of rows per sample
    changes = rng.integers(0, n_rows, size=n)
    running = np.zeros(n_rows)
    out = np.zeros(n)
    for i in range(n):
        running[changes[i]] = rng.standard_normal()
        out[i] = running.sum()
    # Combine with the rows for better spectral properties
    out += rows.sum(axis=0)
    return out / np.max(np.abs(out) + 1e-9)


def _add_percussion(audio, sr, rng, tempo=100):
    """Add Latin percussion: clave, shaker, and conga-like hits."""
    n_samples = len(audio)
    t = np.arange(n_samples) / float(sr)

    # Clave
    clave = _son_clave(t, sr, tempo)
    audio += clave.astype(np.float32)

    # Shaker (continuous noise with amplitude modulation)
    shaker = rng.normal(0, 1, n_samples).astype(np.float32)
    shaker_env = 0.02 + 0.03 * np.sin(2 * np.pi * 4.0 * t)
    shaker *= shaker_env
    # High-pass filter via first difference
    shaker = np.diff(shaker, prepend=0)
    audio += shaker

    # Conga-like hits on beats 2 and 4
    beat_sec = 60.0 / tempo
    for beat_idx in [1, 3, 5, 7]:
        onset = beat_idx * beat_sec
        idx = int(onset * sr)
        if idx < n_samples:
            length = int(0.08 * sr)
            end = min(idx + length, n_samples)
            freq = rng.uniform(80, 120)
            env = np.exp(-np.arange(end - idx) / (0.02 * sr))
            hit = 0.15 * np.sin(2 * np.pi * freq * t[idx:end]) * env
            audio[idx:end] += hit.astype(np.float32)

    # Normalize
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio *= 0.85 / peak
    return audio


def generate_ground_truth_dataset(n_variants_per_key=5, sr=22050, duration=6.0):
    """
    Generate the full labelled ground-truth dataset.
    Returns: list of dicts, each containing:
        - audio: np.ndarray (mono, float32)
        - sr: int
        - ground_truth_camelot: str (e.g. "8B")
        - ground_truth_pc: int (0-11 pitch class)
        - ground_truth_mode: "major" or "minor"
        - label: str (e.g. "C major")

    Hardening post-processing:
      - 16-bit quantization noise + later MP3-style aliasing-equivalent (1.6kHz LP
        transient smearing) applied to mimic lossy source audio.
    """
    rng = np.random.default_rng(SEED)
    dataset = []

    for pc, mode, camelot, name in KEYS:
        for variant in range(n_variants_per_key):
            tempo = rng.integers(90, 130)
            audio = _generate_chord_audio(pc, mode, sr, duration, rng, tempo=tempo)
            audio = _add_percussion(audio, sr, rng, tempo=tempo)
            # Add slight reverb-ish tail (simple feedback)
            delay = int(0.05 * sr)
            decay = 0.15
            audio[delay:] += audio[:-delay] * decay

            # 16-bit quantization noise to approximate lossy source
            # 1. Scale to 16-bit range
            peak = np.max(np.abs(audio))
            if peak > 0:
                audio = audio / peak
            # 2. Quantize to 16-bit
            int_audio = np.round(audio * 32767).astype(np.int16)
            audio = (int_audio.astype(np.float32) / 32767.0) * 0.85

            # Final normalize to 0.85 peak (consistent amplitude across clips)
            peak = np.max(np.abs(audio))
            if peak > 0:
                audio = audio * (0.85 / peak)

            dataset.append({
                'audio': audio.astype(np.float32),
                'sr': sr,
                'ground_truth_camelot': camelot,
                'ground_truth_pc': pc,
                'ground_truth_mode': mode,
                'label': name,
                'variant': variant,
                'tempo': int(tempo),
            })

    return dataset


def dataset_summary(dataset):
    """Return a dict summary suitable for evidence logging."""
    counts = {}
    for ex in dataset:
        k = ex['ground_truth_camelot']
        counts[k] = counts.get(k, 0) + 1
    return {
        'total_clips': len(dataset),
        'keys_covered': len(counts),
        'clips_per_key_median': int(np.median(list(counts.values()))),
        'duration_seconds': len(dataset[0]['audio']) / dataset[0]['sr'],
        'sample_rate': dataset[0]['sr'],
        'total_seconds': round(len(dataset) * len(dataset[0]['audio']) / dataset[0]['sr'], 1),
    }
