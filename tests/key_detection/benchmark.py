"""
Key-detection benchmark harness (Issue #204).

Compares detector strategies on the labelled ground-truth set:

 1. current           — Production _detect_key_from_chroma (binary templates on chroma_cqt)
 2. krumhansl_cqt     — Krumhansl-Schmuckler profiles on chroma_cqt
 3. krumhansl_hpss    — HPSS audio → chroma_cqt → Krumhansl-Schmuckler
 4. krumhansl_cens    — chroma_cens → Krumhansl-Schmuckler (CENS is more robust)
 5. krumhansl_tuned   — tuning-corrected chroma_cqt → Krumhansl-Schmuckler
 6. hpss_cens_krum    — HPSS audio → chroma_cens → Krumhansl-Schmuckler (best combo)

Evaluation:
  - exact_camelot: primary metric (Camelot code match)
  - tonic_only: same tonic, mode wrong
  - relative_match: relative major/minor swap (DJ-acceptable)
  - confusion matrix per key

Output: JSON evidence file for regression tests.
"""

import os
import json
import sys
import time
import numpy as np
import librosa

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.services.analyzer import (
    _detect_key_from_chroma as current_detector,
    CAMELOT_MAJOR, CAMELOT_MINOR,
)

# ---------------------------------------------------------------------------
# Krumhansl-Schmuckler key profile vectors (Krumhansl 1990 / Noland 2002)
# Empirically-derived perceptual key profiles.
# ---------------------------------------------------------------------------

MAJOR_PROFILE = np.array([
    6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
    2.52, 5.19, 2.39, 3.66, 2.29, 2.88,
])

MINOR_PROFILE = np.array([
    6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
    2.54, 4.75, 3.98, 2.69, 3.34, 3.17,
])


def _camelot_from_pc_mode(pc, is_minor):
    return (CAMELOT_MINOR if is_minor else CAMELOT_MAJOR).get(int(pc) % 12, "Unknown")


# ---------------------------------------------------------------------------
# Core Krumhansl-Schmuckler key finder
# ---------------------------------------------------------------------------

def _detect_krumhansl(chroma, sr=None):
    """
    Krumhansl-Schmuckler key-finding via cosine similarity against all 24
    rotated key profiles. Returns (camelot, confidence 0-100).
    """
    chroma_mean = np.mean(chroma, axis=1).astype(np.float64)
    norm = np.linalg.norm(chroma_mean)
    if norm < 1e-9:
        return "Unknown", 0
    chroma_norm = chroma_mean / norm

    best_score = -np.inf
    best_pc = 0
    best_minor = False

    for is_minor in (False, True):
        tmpl = MINOR_PROFILE if is_minor else MAJOR_PROFILE
        tmpl_norm = tmpl / (np.linalg.norm(tmpl) or 1.0)
        for shift in range(12):
            rotated = np.roll(tmpl_norm, shift)
            score = float(np.dot(chroma_norm, rotated))
            if score > best_score:
                best_score = score
                best_pc = shift
                best_minor = is_minor

    confidence = int(np.clip((best_score - 0.5) * 200, 0, 100))
    return _camelot_from_pc_mode(best_pc, best_minor), confidence


# ---------------------------------------------------------------------------
# Detector implementations
# ---------------------------------------------------------------------------

def detector_current(audio, sr):
    """Production detector: chroma_cqt → binary template matching."""
    chroma = librosa.feature.chroma_cqt(y=audio, sr=sr)
    return current_detector(chroma)


def detector_krumhansl_cqt(audio, sr):
    """chroma_cqt → Krumhansl-Schmuckler cosine correlation."""
    chroma = librosa.feature.chroma_cqt(y=audio, sr=sr)
    return _detect_krumhansl(chroma, sr)


def detector_krumhansl_hpss(audio, sr):
    """HPSS harmonic separation → chroma_cqt → Krumhansl."""
    y_harmonic, _ = librosa.effects.hpss(audio)
    chroma = librosa.feature.chroma_cqt(y=y_harmonic, sr=sr)
    return _detect_krumhansl(chroma, sr)


def detector_krumhansl_cens(audio, sr):
    """chroma_cens → Krumhansl (CENS is temporally smoothed/normalized)."""
    chroma = librosa.feature.chroma_cens(y=audio, sr=sr)
    return _detect_krumhansl(chroma, sr)


def detector_krumhansl_tuned(audio, sr):
    """Tuning-corrected chroma_cqt → Krumhansl."""
    # Estimate tuning offset from A4=440
    tuning = librosa.estimate_tuning(y=audio, sr=sr)
    chroma = librosa.feature.chroma_cqt(y=audio, sr=sr, tuning=tuning)
    return _detect_krumhansl(chroma, sr)


def detector_hpss_cens_krum(audio, sr):
    """HPSS → chroma_cens → Krumhansl — best-practice pipeline."""
    y_harmonic, _ = librosa.effects.hpss(audio)
    chroma = librosa.feature.chroma_cens(y=y_harmonic, sr=sr)
    return _detect_krumhansl(chroma, sr)


# ---------------------------------------------------------------------------
# Essentia KeyDetector (optional — heavy ARM dep)
# ---------------------------------------------------------------------------

_ESSENTIA_AVAILABLE = None


def _essentia_ready():
    global _ESSENTIA_AVAILABLE
    if _ESSENTIA_AVAILABLE is not None:
        return _ESSENTIA_AVAILABLE
    try:
        from essentia.standard import KeyDetector  # noqa: F401
        _ESSENTIA_AVAILABLE = True
    except Exception:
        _ESSENTIA_AVAILABLE = False
    return _ESSENTIA_AVAILABLE


_CAMELOT_FROM_PC_MODE = {}


def _camelot_from_pc_mode(pc, is_minor):
    if not _CAMELOT_FROM_PC_MODE:
        for p, v in CAMELOT_MAJOR.items():
            _CAMELOT_FROM_PC_MODE[(p, False)] = v
        for p, v in CAMELOT_MINOR.items():
            _CAMELOT_FROM_PC_MODE[(p, True)] = v
    return _CAMELOT_FROM_PC_MODE.get((int(pc) % 12, bool(is_minor)), "Unknown")


def detector_essentia(audio, sr):
    """Essentia KeyDetector → Camelot mapping."""
    from essentia.standard import (
        KeyDetector as EssentiaKeyDetector,
        FrameGenerator,
    )

    # Essentia expects mono float32
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    detector = EssentiaKeyDetector()
    keys_pcs = []
    keys_scales = []
    strengths = []
    for frame in FrameGenerator(audio, frameSize=4096, hopSize=2048):
        key_pc, scale, strength = detector(frame.astype(np.float32))
        keys_pcs.append(key_pc)
        keys_scales.append(scale)
        strengths.append(strength)

    # Aggregate per-frame votes
    from collections import Counter
    mode_votes = Counter()
    for pc, sc in zip(keys_pcs, keys_scales):
        is_minor = (int(sc) == 1)
        mode_votes[(int(pc) % 12, is_minor)] += 1

    if not mode_votes:
        return "Unknown", 0

    (best_pc, best_minor), _ = mode_votes.most_common(1)[0]
    # Confidence: fraction of frames voting top-1
    confidence = int(100.0 * mode_votes.most_common(1)[0][1] / sum(mode_votes.values()))
    return _camelot_from_pc_mode(best_pc, best_minor), confidence


# ---------------------------------------------------------------------------
# Detector registry
# ---------------------------------------------------------------------------

DETECTORS = [
    ('current',          detector_current,        'chroma_cqt → binary template [production]'),
    ('krumhansl_cqt',    detector_krumhansl_cqt,  'chroma_cqt → Krumhansl-Schmuckler'),
    ('krumhansl_hpss',   detector_krumhansl_hpss, 'HPSS → chroma_cqt → Krumhansl'),
    ('krumhansl_cens',   detector_krumhansl_cens,  'chroma_cens → Krumhansl'),
    ('krumhansl_tuned',  detector_krumhansl_tuned,'tuning-corrected chroma_cqt → Krumhansl'),
    ('hpss_cens_krum',   detector_hpss_cens_krum, 'HPSS → chroma_cens → Krumhansl [best pipeline]'),
]


def _register_essentia():
    """Attempt to register essentia detector if available; record reason if not."""
    global DETECTORS
    if _essentia_ready():
        DETECTORS.append(
            ('essentia', detector_essentia, 'essentia KeyDetector → Camelot')
        )
        return True, None
    return False, 'essentia unavailable on this platform (does not build on ARM)'


_ESSSENTIA_REGISTERED, _ESSENTIA_REASON = _register_essentia()


# ---------------------------------------------------------------------------
# Camelot helpers
# ---------------------------------------------------------------------------

CAMELOT_TO_PC_MODE = {}
for pc, val in CAMELOT_MAJOR.items():
    CAMELOT_TO_PC_MODE[val] = (pc, False)
for pc, val in CAMELOT_MINOR.items():
    CAMELOT_TO_PC_MODE[val] = (pc, True)


def _tonic_of(camelot_code):
    info = CAMELOT_TO_PC_MODE.get(camelot_code)
    return info[0] if info else None


def _is_relative_signature_match(guessed, truth):
    if guessed == "Unknown" or truth == "Unknown":
        return False
    g_pc, g_minor = CAMELOT_TO_PC_MODE[guessed]
    t_pc, t_minor = CAMELOT_TO_PC_MODE[truth]
    if g_minor == t_minor:
        return False
    if t_minor and not g_minor and (t_pc + 3) % 12 == g_pc:
        return True
    if not t_minor and g_minor and (g_pc + 3) % 12 == t_pc:
        return True
    return False


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

EVIDENCE_DIR = os.path.join(os.path.dirname(__file__), 'data')


def run_benchmark(dataset):
    """
    Run all detectors on the dataset.
    Returns {name: {accuracy_percent, exact_match_count, tonic_only_count,
                    relative_only_count, total, confidence_mean,
                    per_key_accuracy, per_key_predictions, time_seconds}}
    """
    results = {}
    n = len(dataset)
    for name, detector_fn, _desc in DETECTORS:
        exact = 0
        tonic_only = 0
        relative_only = 0
        total = 0
        confidence_sum = 0.0
        per_key_correct = {}
        per_key_predictions = {}
        confidences = []
        times = []

        for i, ex in enumerate(dataset):
            audio, sr = ex['audio'], ex['sr']
            truth = ex['ground_truth_camelot']
            t0 = time.perf_counter()
            try:
                pred, conf = detector_fn(audio, sr)
            except Exception as e:
                pred, conf = "Unknown", 0
                sys.stderr.write(f'[{name}] clip {i} ({truth}) failed: {e}\n')
            elapsed = time.perf_counter() - t0
            times.append(elapsed)

            total += 1
            confidence_sum += conf
            confidences.append(conf)

            per_key_correct.setdefault(truth, [0, 0])
            per_key_correct[truth][1] += 1
            per_key_predictions.setdefault(truth, {})
            per_key_predictions[truth][pred] = per_key_predictions[truth].get(pred, 0) + 1

            if pred == truth:
                exact += 1
                per_key_correct[truth][0] += 1
            elif _tonic_of(pred) == _tonic_of(truth):
                tonic_only += 1
            elif _is_relative_signature_match(pred, truth):
                relative_only += 1

        accuracy = (exact / total) * 100.0 if total else 0.0
        results[name] = {
            'accuracy_percent': round(accuracy, 2),
            'exact_match_count': exact,
            'tonic_only_count': tonic_only,
            'relative_only_count': relative_only,
            'total': total,
            'confidence_mean': round(confidence_sum / max(total, 1), 1),
            'time_mean_ms': round(np.mean(times) * 1000, 1),
            'per_key_accuracy': {
                k: round((v[0] / v[1]) * 100, 1) if v[1] else 0.0
                for k, v in per_key_correct.items()
            },
            'per_key_predictions': per_key_predictions,
        }

    return results


def save_evidence(results, summary, evidence_path=None):
    """Write results + dataset summary to JSON."""
    if evidence_path is None:
        os.makedirs(EVIDENCE_DIR, exist_ok=True)
        evidence_path = os.path.join(EVIDENCE_DIR, 'benchmark_results.json')

    blob = {
        'issue': '#204 IDJLM C.1 key-detection benchmark',
        'detectors': [n for n, _, _ in DETECTORS],
        'dataset': summary,
        'results': results,
        'essentia_registered': _ESSSENTIA_REGISTERED,
        'essentia_reason': _ESSENTIA_REASON if not _ESSSENTIA_REGISTERED else None,
    }
    with open(evidence_path, 'w') as fp:
        json.dump(blob, fp, indent=2)
    return evidence_path


def main():
    """Run benchmark end-to-end."""
    from tests.key_detection.ground_truth_dataset import (
        generate_ground_truth_dataset, dataset_summary,
    )

    print('Generating ground-truth dataset...', flush=True)
    dataset = generate_ground_truth_dataset(n_variants_per_key=5, duration=6.0)
    summary = dataset_summary(dataset)
    print(f'  {summary}', flush=True)

    if len(dataset) < 100:
        print(f'FAIL: dataset has only {len(dataset)} clips (<100 threshold)', flush=True)
        return 1
    print(f'OK: {len(dataset)} clips across {summary["keys_covered"]} keys, '
          f'{summary["total_seconds"]}s total audio', flush=True)

    print('Running benchmark on {} detectors...'.format(len(DETECTORS)), flush=True)
    results = run_benchmark(dataset)

    print()
    print(f'{"Detector":22s} {"Acc%":>7s} {"Exact":>6s} {"Tonic":>6s} {"Rel":>5s} '
          f'{"Conf":>5s} {"Time(ms)":>8s}', flush=True)
    print('-' * 65, flush=True)
    for name, _fn, _desc in DETECTORS:
        r = results[name]
        print(f'{name:22s} {r["accuracy_percent"]:6.1f}% '
              f'{r["exact_match_count"]:4d}/{r["total"]:<d} '
              f'{r["tonic_only_count"]:4d}   {r["relative_only_count"]:3d}   '
              f'{r["confidence_mean"]:4.1f}  {r["time_mean_ms"]:7.1f}',
              flush=True)

    evidence_path = save_evidence(results, summary)
    print(f'\nEvidence: {evidence_path}', flush=True)

    current_acc = results['current']['accuracy_percent']
    best_other = max(
        (n, results[n]['accuracy_percent']) for n, _, _ in DETECTORS if n != 'current'
    )

    print(f'\nCurrent accuracy:  {current_acc:.1f}%', flush=True)
    print(f'Best alternative:  {best_other[0]} = {best_other[1]:.1f}%', flush=True)
    print(f'Target: >=80% (MIK parity)', flush=True)

    # Check if best alternative beats current by >=10 points
    if best_other[1] >= current_acc + 10:
        print(f'\n>> WINNER: {best_other[0]} beats current by {best_other[1] - current_acc:.1f} pts', flush=True)
    else:
        print(f'\n>> No detector beats current by >=10pts. Keep current production detector.', flush=True)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
