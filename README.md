# IDJLM Pro

IDJLM Pro is a Tauri desktop app with a local Flask service and SQLite library. The current working tree makes the Latin music workspace the primary interface for importing folders, listening, applying personal tags, reviewing audio-model suggestions, writing metadata, and preparing copies for another library.

## Latin music workspace

The workspace has Library, Review, Categories, Export, Activity, and Settings pages. Folder scans keep source files in place. The library separates original metadata, model proposals, and human decisions. Personal tags are stored as exact literal values, including commas; they are not split into genre axes. Review choices remain human decisions, and the UI reports unsupported or unanalyzed tracks without inventing model evidence.

The prior metadata classifier remains available through Advanced tools. It analyzes track text and file metadata; it does not identify Latin music by listening. The redesigned audio path uses a local pretrained audio model when the runtime and model are installed. It is experimental: no accuracy promise, calibrated Latin subgenre performance, or 15,000-track completion time is claimed. Manual import, tagging, review, and metadata operations do not require a cloud API key. Optional audio analysis needs the local runtime and model; legacy AI features may use their configured provider.

The personal comment palette and the music taxonomy are separate. The taxonomy can represent music family, style, dance use, version, vocal language, and other supported axes without flattening them into one internal genre string. A profile can map approved labels to standard Genre or Comment fields on staged copies. A staged copy is not proof that a file reached an iPad or is searchable in djay.

See the [implementation status](docs/implementation-status-2026-11-10.md) for verified behavior and limits, the [competitor refresh](docs/competitor-refresh-2026-11-10.md) for current product references, and the [redesign brief](docs/jb-latin-redesign-2026-10-18/README.md), [engineering specification](docs/jb-latin-redesign-2026-10-18/engineering-spec.md), and [UX/UI specification](docs/jb-latin-redesign-2026-10-18/ux-ui-spec.md) for implementation detail. The [18 October audit](docs/latin-classifier-redesign-2026-10-18.md) records the original requirements and verified defects.

## Source development

With Python 3 and Node.js installed, build the frontend bundle and start the app:

```bash
npm install
npm run build
./start.sh
```

`start.sh` creates the Python virtual environment if needed, installs the base requirements, and starts the Flask sidecar. It listens on port 5050 by default; `FLASK_PORT` can select another port. No `.env` or cloud provider key is needed for local import, playback, review, tagging, safe writes, or export preparation. Legacy cloud-enrichment features can use optional values from `.env`.

For isolated repository work in Codex Cloud, see [the Cloud pilot guide](docs/CODEX_CLOUD.md). Cloud does not use `.env` files or validate native desktop installers.

For live Vite development, start `npm run dev` in one terminal and run `IDJLM_VITE_DEV=1 .venv/bin/python run_app.py` in another. Keep any provider credentials in the platform's private user configuration, not in source control. Audio analysis is optional: the supported Apple Silicon source environment installs its extra runtime with `.venv/bin/pip install -r requirements-audio.txt`, then downloads the pinned model from Settings. The base environment intentionally omits the audio runtime; no model weights are silently bundled or downloaded.

The isolated browser harness creates synthetic MP3 fixtures and sets `IDJLM_USER_DATA_DIR` to a temporary directory before importing the app. It does not scan a personal music library or download a model:

```bash
/home/ubuntu/.local/share/uv/tools/playwright/bin/python scripts/verify_latin_ui.py
```

Its current result and screenshots are recorded in the [implementation status](docs/implementation-status-2026-11-10.md). The command path is specific to the current development host.

## Source map

- `app/routes/` contains Flask routes, including the local `/api/v2` workspace API.
- `app/services/` contains the library store, durable jobs, audio model adapter, tag writer, restore, and staged-copy export.
- `app/static/modules/latin-redesign.js` implements the primary workspace interactions.
- `templates/partials/redesign-shell.html` contains its page shell.
- `frontend/main.js` coordinates primary and Advanced workspace startup.
- `src-tauri/` contains the desktop wrapper.
- `tests/` contains route, store, job, model-runtime, writer, and export tests.

See [CHANGELOG.md](CHANGELOG.md) for recorded release history. Linux source tests do not certify a native macOS release, a representative Latin-music accuracy result, or transfer and discovery on an iPad.
