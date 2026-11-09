# Implementation status · 10 November 2026

This note distinguishes implementation from measured behavior for the `feat/latin-library-redesign-implementation` review branch.

## What is implemented

The primary interface contains Library, Review, Categories, Export, Activity, and Settings. It has additive folder import, a local SQLite store, resumable job records, literal personal tags, human correction and decision history, review previews, verified MP3 metadata writes with backup and guarded restore, and staged-copy export profiles. Advanced keeps the earlier planner, analysis, DJ-library, and organization tools available.

The old text classifier remains a separate legacy path. A local pretrained audio-classification adapter and model-management API are present. The current Linux/aarch64 frozen sidecar passes `--verify-audio-runtime` and imports the optional audio runtime with torch `2.15.0+cu132`; the verifier also confirms the pinned CLAP model registry and its required-file list. It does not prove that model weights are present in the bundle or prove frozen-model inference. Earlier source-runtime inference used a generated audio fixture, not a representative Latin-music test set. The base source virtualenv intentionally reports `runtime_unavailable`; the supported Apple Silicon source setup installs `.venv/bin/pip install -r requirements-audio.txt`, then the user installs the pinned model from Settings while online.

## Verification evidence

The full Python suite passed with `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider`: **371 passed, 14 skipped, 5 warnings** in 250.12 seconds. The captured output is `/tmp/idjlm-full-pytest.log`. It did not print individual skip reasons, so this note does not assign exact causes to each skip. A later focused run passed **29 tests across audio classification, export, format writing, source writing, and reconciliation**. Subsequent route/export changes passed `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_v2_routes.py::test_additive_import_preserves_decision_across_folders_and_rescan tests/test_v2_routes.py::test_api_verified_write_restore_and_export_readback tests/test_safe_export.py` (**7 passed in 0.90s**). Python compilation and `npm run build` passed. Ruff passed with `PYTHONDONTWRITEBYTECODE=1 ruff check app/ --select E,F,W --ignore E501,E701`. The final browser test and compiled-bundle smoke are described below.

The isolated browser harness `scripts/verify_latin_ui.py` sets `IDJLM_USER_DATA_DIR` to a new temporary directory before importing Flask, generates short synthetic MP3s, and uses the real local routes for import, tagging, review, writes, restore, and export. Only the OS folder chooser is represented by a test route. Its final fresh run completed **16 checks** with `ok: true`, no page errors, and no failed requests in `/tmp/idjlm-latin-ui-2zpog3jc`. It verified:

- First-run local workflow and import of 125 synthetic files, manual Salsa and Salsa Romántica correction, additive folder A → B → A rescan, and retained human decisions.
- Exact literal catalogue-tag updates for all filtered and explicitly selected tracks, including comma-containing values, plus drawer Save & next.
- Search, cursor paging, saved-view persistence, six-page navigation, and the slash-to-search shortcut.
- MP3 tag-write preview cancellation, literal managed-tag write/readback while preserving raw Comment frames, canceled remove/restore previews, and exact guarded restore.
- Staged-copy Genre readback, unchanged source audio checksum, changed-output preview, explicit replacement confirmation, and retained prior staged copy.
- Empty review state without invented model evidence, inspector playback, Advanced round-trip, visible rows at 1024×768, persisted light theme/text scale/reduced-motion settings, Escape dismissal, and focus return.

A second browser smoke opened the compiled `/static/dist/main.js` bundle with Vite unset, imported a real synthetic MP3, and opened its inspector successfully: `/tmp/idjlm-compiled-smoke-rh3wvwtj`. Neither browser run downloads or installs an audio model.

The final run's screenshots are under [`~/docs/screenshots/`](../../../docs/screenshots/): `idjlm-latin-onboarding-empty.png`, `idjlm-latin-library-desktop.png`, `idjlm-latin-library-1024x768.png`, and `idjlm-latin-library-compact.png`. The populated 1024×768 screenshot shows track rows in the working viewport. All screenshots show generated test tracks.

## Limits and safety notes

- Generated sine-wave fixtures verify app integration only. No representative Latin evaluation establishes family or fine-style accuracy for Salsa Romántica, Salsa Dura, Timba, Bachata, Kizomba, or other labels. No calibrated acceptance threshold is demonstrated.
- The M3 MacBook Air with 16 GB memory has not been benchmarked. The Linux frozen sidecar verification did not run model inference. No 15,000-track time or memory target is claimed.
- No physical iPad, Finder cable copy, wireless SMB transfer, Music sync, OneLibrary, or djay My Collection search was exercised. A prepared local copy is not a transfer acknowledgement or proof that djay can find detailed Genre values.
- The current browser harness uses a temporary data directory and synthetic audio. A pre-fix pytest conftest run targeted real Linux settings locations such as `~/.idjlm-pro/taxonomy.json` and `setlist.json`; there is no exact pre-run backup, so no restoration is assumed. Music-library media was not targeted by the current isolated browser harness.
- The 1024×768 browser screenshot is a responsive-layout check, not native macOS accessibility certification or a 200% zoom test.

## Reproduction

From the repository root, the isolated browser harness is run with the managed Playwright interpreter:

```bash
/home/ubuntu/.local/share/uv/tools/playwright/bin/python scripts/verify_latin_ui.py
```

It starts a local Flask and Vite process, makes a temporary user-data and synthetic-media tree, and stops those processes on exit. The reported `/tmp/idjlm-latin-ui-*` directory is diagnostic test data, not user-library data.

For source checks, the evidence commands used for the current suite/build are:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 ruff check app/ --select E,F,W --ignore E501,E701
npm run build
```

Keep the remaining Mac, accuracy, scale, transfer, and destination-app checks open until separately measured.
