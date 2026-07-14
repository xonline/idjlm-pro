import os
import logging
import shutil

import numpy as np
import soundfile as sf

from app.utils import paths

logger = logging.getLogger(__name__)

STEM_NAMES = ["vocals", "drums", "bass", "other"]

_model_cache = None


def _get_separator(device="cpu"):
    global _model_cache
    if _model_cache is None:
        from openunmix import utils

        _model_cache = utils.load_separator(
            model_str_or_path="umxhq",
            niter=1,
            residual=False,
            device=device,
            pretrained=True,
            filterbank="torch",
        )
        _model_cache.freeze()
    return _model_cache


def separate_stems(track, output_dir, progress_callback=None):
    stems_dir = os.path.join(output_dir, "stems")

    existing = _existing_stems(stems_dir)
    if len(existing) == len(STEM_NAMES):
        logger.info("Stems already exist for %s, skipping", track.display_title)
        return existing

    os.makedirs(stems_dir, exist_ok=True)

    try:
        import torch
        audio, rate = sf.read(track.file_path, always_2d=True)
    except Exception as e:
        raise RuntimeError(f"Failed to read audio file: {e}") from e

    if rate != 44100:
        import librosa
        if audio.ndim == 2:
            audio = librosa.resample(audio.T, orig_sr=rate, target_sr=44100).T
        else:
            audio = librosa.resample(audio, orig_sr=rate, target_sr=44100)
        rate = 44100

    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)
    elif audio.shape[1] < 2:
        audio = np.column_stack([audio[:, 0], audio[:, 0]])
    elif audio.shape[1] > 2:
        audio = audio[:, :2]

    audio_tensor = torch.tensor(audio.T, dtype=torch.float32)

    if progress_callback:
        progress_callback("Loading model...", 0, len(STEM_NAMES))

    separator = _get_separator()

    if progress_callback:
        progress_callback("Separating stems...", 0, len(STEM_NAMES))

    with torch.no_grad():
        estimates = separator(audio_tensor[None, ...])
        estimates = separator.to_dict(estimates)

    saved = {}
    max_val = 0.0
    for name in STEM_NAMES:
        if name in estimates:
            v = float(estimates[name].abs().max())
            if v > max_val:
                max_val = v

    for i, name in enumerate(STEM_NAMES):
        if name not in estimates:
            logger.warning("Stem '%s' not produced by model", name)
            continue

        if progress_callback:
            progress_callback(f"Writing {name}...", i + 1, len(STEM_NAMES))

        stem_audio = estimates[name].detach().cpu().numpy()
        stem_audio = stem_audio[0]
        if stem_audio.ndim == 2:
            stem_audio = stem_audio.T

        if max_val > 0 and max_val > 1.0:
            stem_audio = stem_audio / max_val
        stem_audio = stem_audio * 0.95

        stem_path = os.path.join(stems_dir, f"{name}.wav")
        sf.write(stem_path, stem_audio, rate, subtype="PCM_16")
        saved[name] = stem_path

    logger.info("Stem separation complete for %s: %d stems written to %s",
                track.display_title, len(saved), stems_dir)
    return saved


def _existing_stems(stems_dir):
    result = {}
    for name in STEM_NAMES:
        path = os.path.join(stems_dir, f"{name}.wav")
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            result[name] = path
    return result


def get_stems_dir(content_hash):
    return os.path.join(paths.app_user_dir(), "stems", str(content_hash).lstrip("/"))


def get_stems_for_track(track):
    stems_dir = os.path.join(get_stems_dir(track.content_hash or track.file_path), "stems")
    return _existing_stems(stems_dir)


def delete_stems(track):
    stem_dir = get_stems_dir(track.content_hash or track.file_path)
    if os.path.isdir(stem_dir):
        shutil.rmtree(stem_dir)
        logger.info("Deleted stems for %s", track.display_title)
        return True
    return False
