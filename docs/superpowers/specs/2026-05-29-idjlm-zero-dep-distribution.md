# IDJLM Pro — Zero-Dependency Distribution

**Date:** 2026-05-29  
**Status:** Approved  
**Goal:** Users download the app, open it, and it works. No Python, no pip, no terminal.

---

## Problem

The current Tauri wrapper calls `python3 run_app.py` at launch. This requires Python 3.12 and all pip dependencies (`flask`, `librosa`, `numpy`, `soundfile`, `mutagen`, `scikit-learn`, etc.) to be pre-installed by the user. That's a dealbreaker for non-technical users.

---

## Solution: PyInstaller Sidecar

Bundle the entire Python backend into a platform-native binary using PyInstaller. Tauri ships this binary as an `externalBin` sidecar. `main.rs` launches the sidecar instead of calling `python3`.

**Result:** `.dmg` / `.exe` installer. Install. Open. Works.

---

## Architecture

```
idjlm-pro.app/
  Contents/
    MacOS/
      idjlm-pro          ← Tauri frontend binary
    Resources/
      idjlm-server-aarch64-apple-darwin   ← PyInstaller bundle (Flask + all deps)
```

The Tauri binary spawns `idjlm-server` as a child process, polls `localhost:5050` until Flask is ready, then loads the webview. Identical to the current setup — only the launcher changes from `python3 run_app.py` to `./idjlm-server`.

---

## Components

### 1. `idjlm.spec` — PyInstaller spec file

- Entrypoint: `run_app.py`
- `--onefile` mode: single binary output
- `add_data`: bundles `app/static/`, `templates/`, `app/` (Python source)
- Hidden imports: `librosa`, `soundfile`, `mutagen`, `flask`, `sklearn`, `numpy`, `scipy`
- Output: `dist/idjlm-server` (renamed with platform suffix for Tauri)

### 2. `src-tauri/tauri.conf.json` — sidecar config

```json
"bundle": {
  "externalBin": ["binaries/idjlm-server"]
}
```

Platform suffixes handled by Tauri automatically (`-aarch64-apple-darwin`, `-x86_64-apple-darwin`, `-x86_64-pc-windows-msvc`).

### 3. `src-tauri/src/main.rs` — sidecar launcher

Replace `std::process::Command::new("python3")` with `tauri::process::Command::new_sidecar("idjlm-server")`. Same readiness polling loop, same cleanup on window close.

### 4. `.github/workflows/tauri-build.yml` — CI pipeline

Each platform runner:
1. `pip install pyinstaller` + `pip install -r requirements.txt`
2. `pyinstaller idjlm.spec --distpath src-tauri/binaries/`
3. Rename binary with platform suffix
4. `tauri build` (bundles the binary automatically)

---

## Path Handling

PyInstaller sets `sys._MEIPASS` when running from a bundle. `run_app.py` must use this to resolve asset paths:

```python
import sys, os
BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
```

Flask's `template_folder` and `static_folder` must use `BASE`-relative paths.

---

## File Size

Expected installer sizes:
- macOS arm64: ~350–450MB (numpy + scipy + librosa are large)
- Windows x86_64: ~400–500MB

Acceptable for a desktop DJ tool. Can be reduced later with `--exclude-module` pruning.

---

## Out of Scope

- Auto-update mechanism (future)
- Code signing / notarization (future — needed for macOS Gatekeeper)
- Size optimisation via UPX or module pruning (future)
