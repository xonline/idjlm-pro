# IDJLM Pro — Claude Learnings

## Tauri Sidecar / Runtime Data

- All runtime data files (config, session state, user data) must write to `~/Library/Application Support/IDJLM Pro/`. On Linux, use `~/.idjlm-pro/` instead.
- Tauri packages the Python Flask sidecar with PyInstaller. Keep provider settings in the user-writable path; do not bundle `.env` files or desktop release secrets.

## JavaScript Initialisation

- After splitting UI setup into dedicated `initX()` functions, verify every function is actually called from `DOMContentLoaded`. Use a registry array (e.g. `[initEditModal, initAudioPlayer, ...]`) to make omissions obvious at a glance.
