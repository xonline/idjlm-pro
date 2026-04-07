# IDJLM Pro — Claude Learnings

## PyInstaller / macOS Bundle

- All runtime data files (config, session state, user data) must write to `~/Library/Application Support/IDJLM Pro/` — the PyInstaller `.app` bundle is codesigned and read-only at runtime. On Linux, use `~/.idjlm-pro/` instead.
- On startup, load user-overridable files by checking the user-writable path first, falling back to the bundle copy: `user_path if os.path.exists(user_path) else bundle_path`

## JavaScript Initialisation

- After splitting UI setup into dedicated `initX()` functions, verify every function is actually called from `DOMContentLoaded`. Use a registry array (e.g. `[initEditModal, initAudioPlayer, ...]`) to make omissions obvious at a glance.
