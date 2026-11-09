#!/usr/bin/env python3
"""Fail build setup early when the bundled local-audio runtime is incomplete.

This does not download model weights or contact an inference provider.  The
PyInstaller spec collects the same imports because the production runner loads
them lazily only after the user installs the pinned local checkpoint.
"""
import sys
from pathlib import Path


# GitHub Actions invokes this by filename, so only ``scripts/`` would normally
# be on sys.path. Keep its discovery identical to the PyInstaller build root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.audio_classification import ModelRegistry


def main() -> int:
    import torch
    from huggingface_hub import HfApi, snapshot_download  # noqa: F401
    from transformers import AutoProcessor, ClapModel  # noqa: F401

    spec = ModelRegistry().get()
    assert spec.adapter == "transformers_clap"
    assert spec.required_files
    assert torch.__version__
    print(f"audio runtime ready: {spec.id}@{spec.revision} torch={torch.__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
