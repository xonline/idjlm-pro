# IDJLM Pro

IDJLM Pro is a desktop app for managing a Latin music library with local import, listening, human review, tagging, and export tools.

## Try the current review build on a Mac

The latest stable release remains [v4.1.0](https://github.com/xonline/idjlm-pro/releases/tag/v4.1.0). The current [4.2.3 Apple Silicon review build](https://github.com/xonline/idjlm-pro/releases/tag/review-4.2.3) fixes the reported desktop startup freeze and includes the local Latin-library workflow merged through [PR #44](https://github.com/xonline/idjlm-pro/pull/44).

This is an **ad-hoc signed, unnotarized test prerelease**—not a stable release. macOS will quarantine a browser download and show its expected unidentified-developer warning on first launch. It needs one manual [Privacy & Security approval](https://support.apple.com/en-au/102445), and cannot receive normal Gatekeeper acceptance until a Developer ID certificate and notarization are configured.

1. Download the Apple Silicon DMG and its `.sha256` checksum from the 4.2.3 review release; verify the checksum before opening it.
2. Open the DMG, copy **IDJLM Pro** to Applications, then eject the DMG.
3. If macOS shows the expected unidentified-developer warning, open **System Settings → Privacy & Security** and choose **Open Anyway**. Use that override only after verifying the release and checksum. If macOS instead says the app is **damaged**, stop and download it again; do not override that alert.
4. Test a copied sample folder: import, review, preview a write, restore it, then preview an export. Do not begin with an irreplaceable library.

The review build proves neither Latin-music accuracy, M3 16 GB performance at 15,000 tracks, nor iPad/djay transfer discovery. The optional audio model weights are not bundled and remain experimental.

The primary workflow has six pages, not six or seven required steps: **Library, Review, Categories, Export, Activity, and Settings**. You can import and organise a folder without a cloud API key. The optional local audio model is configured from Settings and remains experimental.

## What the review build does

![Current Library workspace with generated review tracks](https://raw.githubusercontent.com/xonline/idjlm-pro/4f01346/docs/screenshots/latin-library-workspace.png)

The primary workspace has six pages: Library, Review, Categories, Export, Activity, and Settings. It imports folders without moving the source files, keeps existing metadata, model suggestions, and human decisions distinct, and stores personal tags as literal values. Previewed tag writes keep backups and support guarded restore. Export profiles create staged copies and verify metadata on those copies.

Audio classification runs through an optional local pretrained model. It is experimental. There is no measured Latin-family or fine-style accuracy, no calibrated acceptance threshold, and no 15,000-track performance result. Manual import, review, tagging, and export do not require a cloud API. The earlier metadata-based classifier and other tools remain under Advanced.

A staged copy does not confirm transfer to an iPad or discovery in djay. Physical transfer and destination-app checks remain open.

See the [reliability check](https://github.com/xonline/idjlm-pro/blob/8817c5f/docs/reliability-status-2026-11-19.md), the [implementation status](https://github.com/xonline/idjlm-pro/blob/4f01346/docs/implementation-status-2026-11-10.md) for prior verification evidence and limits, the [redesign brief](https://github.com/xonline/idjlm-pro/blob/4f01346/docs/jb-latin-redesign-2026-10-18/README.md) and its engineering and UX specifications for workflow detail, and the [changelog](CHANGELOG.md) for release history.

## Run from source (developers)

To run the review branch without an installer, install Git, Node.js 20 with npm, and Python 3.11 or 3.12, then use the same Python version explicitly when creating the environment:

```bash
git clone --branch review-4.2.3 https://github.com/xonline/idjlm-pro.git
cd idjlm-pro
npm ci
npm run build
python3.12 -m venv .venv  # use python3.11 if 3.12 is unavailable
./start.sh
```

Open `http://localhost:5050` after the service starts. `start.sh` uses the existing `.venv`, installs the base Python requirements, and starts the local service.

## Optional local audio model

The base Python environment does not install the audio runtime or model weights. On supported Apple Silicon, install the optional runtime and then download the pinned model from Settings:

```bash
.venv/bin/pip install -r requirements-audio.txt
```

Model download requires an internet connection. Local import, review, metadata writes, and export continue to work without it.

## Development checks

For isolated browser checks with synthetic audio, use a separate verification
environment rather than assuming the application environment includes Playwright:

```bash
python3 -m venv /tmp/idjlm-ui-check
/tmp/idjlm-ui-check/bin/pip install playwright
/tmp/idjlm-ui-check/bin/playwright install chromium
PYTHONDONTWRITEBYTECODE=1 /tmp/idjlm-ui-check/bin/python scripts/verify_latin_ui.py
```

The harness uses a temporary data directory. It does not scan a personal library or download a model. See the [implementation status](https://github.com/xonline/idjlm-pro/blob/4f01346/docs/implementation-status-2026-11-10.md) for the recorded test results.

The [Codex Cloud pilot guide](docs/CODEX_CLOUD.md) covers isolated repository work in Codex Cloud. Cloud checks do not validate native desktop installers.

## Source map

- `app/routes/` contains Flask routes, including the local `/api/v2` workspace API.
- `app/services/` contains the library store, audio model adapter, tag writer, restore, and staged-copy export.
- `app/static/modules/latin-redesign.js` implements the primary workspace interactions.
- `templates/partials/redesign-shell.html` contains the workspace shell.
- `frontend/main.js` coordinates primary and Advanced workspace startup.
- `src-tauri/` contains the desktop wrapper.
- `tests/` contains route, store, job, model-runtime, writer, and export tests.

Linux source tests do not establish model accuracy on Latin music, performance on an M3 Mac with 16 GB memory, or successful transfer and discovery on an iPad.
