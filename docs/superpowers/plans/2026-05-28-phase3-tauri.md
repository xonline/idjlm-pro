# IDJLM v4 Phase 3 — Tauri Desktop Wrapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the existing Flask/Python backend in a Tauri v2 webview shell so IDJLM Pro launches as a native .app/.exe with no browser tab or URL bar visible to the user.

**Architecture:** Tauri v2 acts as the native window host; the existing `run_app.py` Flask server starts as a Tauri sidecar process before the webview loads. The webview polls `localhost:5050` and navigates to it once Flask responds 200 OK. The existing pywebview integration in `library.js` is extended to also handle the Tauri path via `window.__TAURI__` detection.

**Tech Stack:** Tauri v2, Rust, existing Python/Flask backend (Python 3.12, Flask 3.x)

---

## Context: What Exists Today

- **Backend:** `run_app.py` — Flask app, binds to a free port (default 5050 via `FLASK_PORT` env var). Already has a splash screen, readiness poll loop, and pywebview API.
- **Current native wrapper:** `pywebview` (listed in `requirements.txt`) inside `run_app.py`. The `build-mac.sh` bundles the whole thing via PyInstaller.
- **Folder picker:** `app/static/modules/library.js` `openFolderPicker()` already checks `window.pywebview && window.pywebview.api` — we extend this check to also catch `window.__TAURI__`.
- **Icons:** `assets/icon_256.png`, `assets/icon_1024.png`, `assets/icon.icns`, `assets/icon.ico` — all already present.
- **Version:** 3.5.0 (from `VERSION` file).
- **Existing CI:** `.github/workflows/ci.yml` — Python tests on ubuntu-latest. We add a parallel Tauri build workflow.

## Why Tauri over PyInstaller+pywebview

| Factor | PyInstaller + pywebview | Tauri v2 |
|---|---|---|
| Bundle size | ~200-400 MB (Python runtime bundled) | ~8-15 MB (Rust + system webview) |
| Native look | pywebview renders OS WebKit | Tauri uses OS WebKit/WebView2 — same |
| Update mechanism | Manual zip replacement | Tauri built-in updater plugin |
| Code signing | Manual | Tauri handles per-platform |
| CI build matrix | Single platform per runner | Multi-platform via tauri-action |
| Future IPC | pywebview JS API | `tauri::command` + invoke() — more capable |

---

## Prerequisites (Developer Machine)

- macOS 14+ with Xcode Command Line Tools (`xcode-select --install`)
- Rust toolchain via rustup (`curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`)
- Node.js 18+ (for Tauri CLI — `npm install -g @tauri-apps/cli@next`)
- Python 3.12 (existing — used as Flask sidecar process, not bundled into Rust)
- For Windows cross-build: use GitHub Actions runner (do not attempt locally unless on Windows)

---

## Step 1 — Install Tauri CLI and Rust Prerequisites

- [ ] **1.1** Verify Rust is installed and up to date:
  ```bash
  rustup --version          # must exist
  rustup update stable
  rustup target list --installed
  # macOS needs: aarch64-apple-darwin (M-series) and/or x86_64-apple-darwin
  # Add if missing:
  rustup target add aarch64-apple-darwin
  rustup target add x86_64-apple-darwin
  ```

- [ ] **1.2** Install Tauri CLI v2 globally via npm (version-pinned):
  ```bash
  npm install -g @tauri-apps/cli@^2.5.0
  tauri --version   # should print: tauri-cli 2.5.x
  ```

- [ ] **1.3** Verify macOS system dependencies (WebKit is bundled in macOS — no extra install):
  ```bash
  xcode-select -p   # must return a path, e.g. /Library/Developer/CommandLineTools
  # If not: xcode-select --install
  ```

- [ ] **1.4** Commit nothing yet. This step is environment-only.

---

## Step 2 — `tauri init` and Configure `tauri.conf.json`

- [ ] **2.1** Run `tauri init` from the project root. When prompted, answer:
  ```
  What is your app name?                     IDJLM Pro
  What should the window title be?           IDJLM Pro
  Where are your web assets located?         ../app/static   (not used — we load from URL)
  What is the URL of your dev server?        http://localhost:5050
  What is your frontend dev command?         (leave blank — Python starts separately)
  What is your frontend build command?       (leave blank)
  ```

  This creates `src-tauri/` with:
  - `src-tauri/Cargo.toml`
  - `src-tauri/src/main.rs`
  - `src-tauri/tauri.conf.json`
  - `src-tauri/build.rs`
  - `src-tauri/icons/` (placeholder icons)

- [ ] **2.2** Replace `src-tauri/tauri.conf.json` with the following exact content:
  ```json
  {
    "$schema": "https://schema.tauri.app/config/2",
    "productName": "IDJLM Pro",
    "version": "3.5.0",
    "identifier": "au.idjlm.pro",
    "build": {
      "frontendDist": "http://localhost:5050",
      "devUrl": "http://localhost:5050",
      "beforeDevCommand": "",
      "beforeBuildCommand": ""
    },
    "app": {
      "withGlobalTauri": true,
      "windows": [
        {
          "title": "IDJLM Pro",
          "width": 1280,
          "height": 800,
          "minWidth": 960,
          "minHeight": 640,
          "resizable": true,
          "fullscreen": false,
          "decorations": true,
          "center": true,
          "url": "about:blank"
        }
      ],
      "security": {
        "csp": null
      }
    },
    "bundle": {
      "active": true,
      "targets": "all",
      "icon": [
        "icons/32x32.png",
        "icons/128x128.png",
        "icons/128x128@2x.png",
        "icons/icon.icns",
        "icons/icon.ico"
      ],
      "resources": {
        "run_app.py": "run_app.py",
        "app/**/*": "app/",
        "templates/**/*": "templates/",
        "taxonomy.json": "taxonomy.json",
        ".env": ".env"
      },
      "macOS": {
        "dmg": {
          "background": null,
          "windowSize": { "width": 660, "height": 400 }
        },
        "minimumSystemVersion": "11.0",
        "signingIdentity": null,
        "entitlements": null
      },
      "windows": {
        "certificateThumbprint": null,
        "digestAlgorithm": "sha256",
        "timestampUrl": ""
      }
    },
    "plugins": {
      "shell": {
        "open": false,
        "sidecar": true
      },
      "dialog": {
        "open": true,
        "save": false
      }
    }
  }
  ```

  Key decisions explained:
  - `"url": "about:blank"` — window starts blank; Rust `setup()` hook navigates to Flask once ready
  - `"csp": null` — disables CSP enforcement (Flask serves its own headers; Tauri's CSP would block inline scripts)
  - `"withGlobalTauri": true` — injects `window.__TAURI__` into all webview pages (required for dialog.open in JS)
  - `"signingIdentity": null` — set to your Apple Developer ID string when preparing a notarised release
  - `"sidecar": true` under `plugins.shell` — required to use `tauri-plugin-shell` sidecar API
  - `bundle.resources` — copies Flask source tree into `Contents/Resources/` in the bundle

- [ ] **2.3** Update `src-tauri/Cargo.toml` — add required dependencies:
  ```toml
  [package]
  name = "idjlm-pro"
  version = "3.5.0"
  description = "IDJLM Pro — Intelligent DJ Library Manager"
  authors = ["xonline"]
  license = "MIT"
  repository = ""
  default-run = "idjlm-pro"
  edition = "2021"
  rust-version = "1.77.2"

  [lib]
  name = "idjlm_pro_lib"
  crate-type = ["staticlib", "cdylib", "rlib"]

  [[bin]]
  name = "idjlm-pro"
  path = "src/main.rs"

  [build-dependencies]
  tauri-build = { version = "2", features = [] }

  [dependencies]
  tauri = { version = "2", features = ["macos-private-api"] }
  tauri-plugin-shell = "2"
  tauri-plugin-dialog = "2"
  serde = { version = "1", features = ["derive"] }
  serde_json = "1"
  ```

- [ ] **2.4** Commit:
  ```bash
  git add src-tauri/ tauri.conf.json
  git commit -m "feat: add Tauri v2 scaffold — conf, Cargo.toml, init structure"
  ```

---

## Step 3 — Flask Sidecar Setup (Rust `main.rs`)

The goal: Tauri's `setup()` hook spawns `python3 run_app.py` as a child process, polls `localhost:5050` until the port accepts TCP connections, then navigates the webview to `http://localhost:5050`.

- [ ] **3.1** Replace `src-tauri/src/main.rs` with the following exact content:

  ```rust
  // Prevents additional console window on Windows in release. DO NOT REMOVE.
  #![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

  use std::net::TcpStream;
  use std::path::PathBuf;
  use std::process::{Child, Command};
  use std::sync::{Arc, Mutex};
  use std::thread;
  use std::time::{Duration, Instant};

  use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};
  use tauri_plugin_dialog::DialogExt;

  /// Port Flask listens on. Must match FLASK_PORT env var (or run_app.py default).
  const FLASK_PORT: u16 = 5050;
  /// Seconds to wait for Flask before giving up and showing an error.
  const FLASK_TIMEOUT_SECS: u64 = 60;

  /// Shared handle to the Flask child process so we can kill it on app exit.
  struct FlaskProcess(Arc<Mutex<Option<Child>>>);

  /// Poll TCP connect to 127.0.0.1:FLASK_PORT until successful or timeout.
  fn wait_for_flask(timeout: Duration) -> bool {
      let deadline = Instant::now() + timeout;
      while Instant::now() < deadline {
          if TcpStream::connect(format!("127.0.0.1:{}", FLASK_PORT)).is_ok() {
              // Add a small grace delay — Flask accepts TCP before all routes register
              thread::sleep(Duration::from_millis(300));
              return true;
          }
          thread::sleep(Duration::from_millis(200));
      }
      false
  }

  /// Resolve the path to `run_app.py` relative to the Tauri resource dir.
  /// In dev mode this is the project root; in production it is inside the bundle.
  fn find_run_app(app: &AppHandle) -> PathBuf {
      let resource_dir = app.path().resource_dir().expect("resource dir not found");
      let candidate = resource_dir.join("run_app.py");
      if candidate.exists() {
          return candidate;
      }
      // Fallback: relative to binary location
      std::env::current_exe()
          .ok()
          .and_then(|p| p.parent().map(|d| d.join("run_app.py")))
          .unwrap_or_else(|| PathBuf::from("run_app.py"))
  }

  /// Tauri command exposed to JS: opens a native folder picker and returns the path.
  /// Called via: window.__TAURI__.core.invoke('pick_folder')
  #[tauri::command]
  async fn pick_folder(app: AppHandle) -> Option<String> {
      app.dialog()
          .file()
          .set_title("Select Music Folder")
          .pick_folder()
          .await
          .map(|p| p.to_string_lossy().into_owned())
  }

  /// Navigate the named webview window to a URL using JS location assignment.
  /// Uses window.navigate() which is the Tauri v2 WebviewWindow navigate method.
  fn navigate_to_flask(window: &tauri::WebviewWindow) {
      let url = format!("http://localhost:{}", FLASK_PORT);
      // Tauri v2: navigate via the WebviewWindow navigate method (not JS injection)
      let _ = window.navigate(url.parse().expect("valid url"));
  }

  /// Show an error message in the splash window by setting the status text.
  fn show_splash_error(window: &tauri::WebviewWindow, msg: &str) {
      // Use Tauri's built-in JS execution (not user data) — this is safe internal navigation
      let script = format!(
          "var el = document.querySelector('.status'); if(el) el.textContent = '{}';",
          msg.replace('\'', "\\'")
      );
      let _ = window.run_javascript(&script);
  }

  fn main() {
      tauri::Builder::default()
          .plugin(tauri_plugin_shell::init())
          .plugin(tauri_plugin_dialog::init())
          .manage(FlaskProcess(Arc::new(Mutex::new(None))))
          .setup(|app| {
              let app_handle = app.handle().clone();
              let flask_arc = app.state::<FlaskProcess>().0.clone();

              // Splash HTML — shown immediately while Flask starts.
              // Matches the existing splash in run_app.py for visual consistency.
              let splash_html = concat!(
                  "<!DOCTYPE html><html><head><meta charset='utf-8'><style>",
                  "* { margin:0; padding:0; box-sizing:border-box; }",
                  "body { background:#0f0f13; display:flex; flex-direction:column;",
                  "align-items:center; justify-content:center; height:100vh;",
                  "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;",
                  "color:#e0e0e0; user-select:none; }",
                  ".icon { width:96px; height:96px;",
                  "background:linear-gradient(135deg,#8b5cf6 0%,#06b6d4 100%);",
                  "border-radius:22px; display:flex; align-items:center;",
                  "justify-content:center; font-size:48px; margin-bottom:28px;",
                  "box-shadow:0 0 40px rgba(139,92,246,0.35);",
                  "animation:breathe 2.4s ease-in-out infinite; }",
                  "@keyframes breathe {",
                  "0%,100%{box-shadow:0 0 40px rgba(139,92,246,0.35);transform:scale(1);}",
                  "50%{box-shadow:0 0 60px rgba(139,92,246,0.55);transform:scale(1.03);}}",
                  "h1 { font-size:26px; font-weight:700; letter-spacing:-0.5px; margin-bottom:6px;",
                  "background:linear-gradient(135deg,#c4b5fd,#67e8f9);",
                  "-webkit-background-clip:text; -webkit-text-fill-color:transparent; }",
                  ".subtitle{font-size:13px;color:#555;margin-bottom:40px;letter-spacing:0.3px;}",
                  ".bar-track{width:220px;height:3px;background:#1e1e2e;border-radius:2px;overflow:hidden;}",
                  ".bar-fill{ height:100%;width:40%;",
                  "background:linear-gradient(90deg,#8b5cf6,#06b6d4);",
                  "border-radius:2px;animation:slide 1.8s ease-in-out infinite;}",
                  "@keyframes slide{0%{margin-left:-40%;}100%{margin-left:100%;}}",
                  ".status{margin-top:18px;font-size:11px;color:#3a3a4a;letter-spacing:0.5px;text-transform:uppercase;}",
                  "</style></head><body>",
                  "<div class='icon'>&#127925;</div>",
                  "<h1>IDJLM Pro</h1>",
                  "<p class='subtitle'>Intelligent DJ Library Manager</p>",
                  "<div class='bar-track'><div class='bar-fill'></div></div>",
                  "<p class='status'>Starting up&hellip;</p>",
                  "</body></html>"
              );

              // Create the main window showing splash immediately
              let window = WebviewWindowBuilder::new(
                  &app_handle,
                  "main",
                  WebviewUrl::Html(splash_html.to_string()),
              )
              .title("IDJLM Pro")
              .inner_size(1280.0, 800.0)
              .min_inner_size(960.0, 640.0)
              .resizable(true)
              .center()
              .build()?;

              // Spawn Flask in a background thread; navigate window once ready
              thread::spawn(move || {
                  let run_app_path = find_run_app(&app_handle);

                  // python3 on macOS/Linux, python on Windows
                  let python_bin = if cfg!(target_os = "windows") { "python" } else { "python3" };

                  let child = Command::new(python_bin)
                      .arg(&run_app_path)
                      .env("FLASK_PORT", FLASK_PORT.to_string())
                      .env("FLASK_ENV", "production")
                      .env("PYTHONDONTWRITEBYTECODE", "1")
                      // Disable pywebview inside run_app.py — Tauri is the window host
                      .env("IDJLM_HEADLESS", "1")
                      .current_dir(
                          run_app_path
                              .parent()
                              .unwrap_or_else(|| std::path::Path::new(".")),
                      )
                      .spawn();

                  match child {
                      Ok(c) => {
                          *flask_arc.lock().unwrap() = Some(c);
                      }
                      Err(e) => {
                          eprintln!("[idjlm] Failed to start Flask: {e}");
                          show_splash_error(&window, &format!("Error starting Flask: {e}"));
                          return;
                      }
                  }

                  // Poll until Flask port is open
                  if wait_for_flask(Duration::from_secs(FLASK_TIMEOUT_SECS)) {
                      navigate_to_flask(&window);
                  } else {
                      show_splash_error(&window, "Flask failed to start — check logs");
                  }
              });

              Ok(())
          })
          .on_window_event(|window, event| {
              // Kill Flask when the main window closes
              if let tauri::WindowEvent::CloseRequested { .. } = event {
                  if let Some(state) = window.try_state::<FlaskProcess>() {
                      if let Ok(mut guard) = state.0.lock() {
                          if let Some(mut child) = guard.take() {
                              let _ = child.kill();
                          }
                      }
                  }
              }
          })
          .invoke_handler(tauri::generate_handler![pick_folder])
          .run(tauri::generate_context!())
          .expect("error while running tauri application");
  }
  ```

  Implementation notes:
  - `IDJLM_HEADLESS=1` env var is passed to `run_app.py` so we can guard the pywebview block: `if not os.getenv("IDJLM_HEADLESS"):` — prevents double window creation
  - `navigate_to_flask` uses Tauri's native `WebviewWindow::navigate()` method, not JS injection, for clean URL transitions
  - `show_splash_error` uses `run_javascript` only for trusted internal UI text (no user data flows through it)
  - Flask child process is stored in `FlaskProcess` managed state and killed on window close

- [ ] **3.2** Patch `run_app.py` to respect `IDJLM_HEADLESS`:

  In `run_app.py`, wrap the `if __name__ == "__main__":` block so pywebview is skipped when Tauri is the host:

  ```python
  if __name__ == "__main__":
      flask_app = create_app()

      flask_thread = threading.Thread(target=_run_flask, args=(flask_app,), daemon=True)
      flask_thread.start()

      # When launched by Tauri (IDJLM_HEADLESS=1), skip pywebview entirely.
      # Tauri handles the window; we just run Flask and block.
      if os.getenv("IDJLM_HEADLESS"):
          try:
              while True:
                  time.sleep(1)
          except KeyboardInterrupt:
              pass
          raise SystemExit(0)

      # --- existing pywebview block unchanged below this line ---
      try:
          import webview
          ...
  ```

- [ ] **3.3** Commit:
  ```bash
  git add src-tauri/src/main.rs run_app.py
  git commit -m "feat(tauri): Rust main.rs — Flask sidecar spawn + readiness poll + splash window"
  ```

---

## Step 4 — Native File Dialog Integration in `library.js`

The current `openFolderPicker()` checks `window.pywebview`. We extend it to also handle Tauri.

- [ ] **4.1** Edit `app/static/modules/library.js`. Replace the `openFolderPicker` function (lines 16-27) with:

  ```js
  async function openFolderPicker() {
    // Tauri v2 — invoke the pick_folder Rust command directly (most reliable path)
    if (window.__TAURI__ && window.__TAURI__.core) {
      try {
        const selected = await window.__TAURI__.core.invoke('pick_folder');
        if (selected) doImport(selected);
      } catch (e) {
        console.warn('[idjlm] Tauri pick_folder invoke failed, trying dialog plugin:', e);
        // Fallback: dialog plugin JS API
        try {
          const selected2 = await window.__TAURI__.dialog.open({
            directory: true,
            multiple: false,
            title: 'Select Music Folder'
          });
          if (selected2) doImport(selected2);
        } catch (e2) {
          console.warn('[idjlm] Tauri dialog.open also failed, using text input:', e2);
          _showTextInput();
        }
      }
      return;
    }

    // pywebview native dialog (legacy PyInstaller build — kept for rollback)
    if (window.pywebview && window.pywebview.api) {
      const path = await window.pywebview.api.choose_folder();
      if (path) doImport(path);
      return;
    }

    // Dev-mode / plain browser fallback: show text input
    _showTextInput();
  }

  function _showTextInput() {
    if (folderInput)  folderInput.style.display  = 'inline-block';
    if (btnImport)    btnImport.style.display    = 'inline-block';
    if (folderInput)  folderInput.focus();
  }
  ```

  Detection priority:
  1. `window.__TAURI__.core.invoke('pick_folder')` — calls the Rust `#[tauri::command]` directly; most reliable
  2. `window.__TAURI__.dialog.open()` — dialog plugin JS API; fallback if invoke fails
  3. `window.pywebview` — legacy PyInstaller build (preserved for rollback)
  4. Text input — dev mode / plain browser

- [ ] **4.2** The `"withGlobalTauri": true` setting in `tauri.conf.json` (added in Step 2.2) ensures `window.__TAURI__` is injected into all webview pages served from Flask. No additional changes needed.

- [ ] **4.3** Commit:
  ```bash
  git add app/static/modules/library.js
  git commit -m "feat(library.js): Tauri native folder dialog via invoke + dialog plugin fallback"
  ```

---

## Step 5 — App Icons

The `assets/` directory already contains `icon_256.png`, `icon_1024.png`, `icon.icns`, and `icon.ico`. Tauri requires a specific set of PNG sizes plus `.icns` and `.ico` in `src-tauri/icons/`.

- [ ] **5.1** Use Tauri's built-in icon generator (preferred — handles all format conversions):
  ```bash
  cd /path/to/idjlm
  tauri icon assets/icon_1024.png
  # Automatically outputs all required sizes to src-tauri/icons/
  ```

  Expected output in `src-tauri/icons/`:
  ```
  32x32.png
  128x128.png
  128x128@2x.png
  256x256.png
  512x512.png
  icon.icns
  icon.ico
  ```

- [ ] **5.2** If `tauri icon` is unavailable (older CLI), generate manually with ImageMagick:
  ```bash
  mkdir -p src-tauri/icons

  convert assets/icon_1024.png -resize 32x32     src-tauri/icons/32x32.png
  convert assets/icon_1024.png -resize 128x128   src-tauri/icons/128x128.png
  convert assets/icon_1024.png -resize 256x256   src-tauri/icons/128x128@2x.png
  convert assets/icon_1024.png -resize 256x256   src-tauri/icons/256x256.png
  convert assets/icon_1024.png -resize 512x512   src-tauri/icons/512x512.png
  cp assets/icon.icns  src-tauri/icons/icon.icns
  cp assets/icon.ico   src-tauri/icons/icon.ico
  ```

- [ ] **5.3** Verify `tauri.conf.json` `bundle.icon` array matches the generated filenames (already correct per Step 2.2).

- [ ] **5.4** Commit:
  ```bash
  git add src-tauri/icons/
  git commit -m "chore: add Tauri icon set generated from assets/icon_1024.png"
  ```

---

## Step 6 — Build Test (macOS)

- [ ] **6.1** Run dev mode first to verify the wiring without a full production build:
  ```bash
  cd /path/to/idjlm

  # Kill any stray Flask processes first
  pkill -f "run_app.py" || true

  # Tauri dev mode — Rust compiles, window opens, sidecar starts Flask
  tauri dev
  ```
  Expected: Tauri window opens with splash, Flask starts automatically, UI loads within ~5 seconds.

- [ ] **6.2** Verify folder picker works:
  - Click "Choose Folder" (or the get-started button)
  - Native macOS folder picker dialog should open — no text input visible
  - Select a folder — import should proceed normally

- [ ] **6.3** Verify clean shutdown:
  - Close the Tauri window
  - Run `ps aux | grep run_app.py` — the process should be gone

- [ ] **6.4** Production build:
  ```bash
  cargo tauri build
  # Output: src-tauri/target/release/bundle/macos/IDJLM Pro.app
  #         src-tauri/target/release/bundle/dmg/IDJLM Pro_3.5.0_aarch64.dmg
  ```

- [ ] **6.5** Verify the .app bundle:
  ```bash
  open "src-tauri/target/release/bundle/macos/IDJLM Pro.app"
  ```
  Checklist:
  - [ ] App launches without a browser tab or URL bar
  - [ ] Splash screen appears immediately
  - [ ] Flask starts and UI loads
  - [ ] Click "Choose Folder" — native OS folder picker opens (not text input)
  - [ ] Selecting a folder triggers the import flow
  - [ ] Closing the window kills the Flask process (`ps aux | grep run_app` returns nothing)

- [ ] **6.6** If `run_app.py` is not found at runtime in the bundle, debug with:
  ```bash
  ls "src-tauri/target/release/bundle/macos/IDJLM Pro.app/Contents/Resources/"
  ```
  Adjust `bundle.resources` paths in `tauri.conf.json` accordingly. The key (source) is a glob relative to `src-tauri/` parent; the value (destination) is the name inside `Resources/`.

- [ ] **6.7** Verify `.gitignore` excludes the build target:
  ```
  src-tauri/target/
  ```
  Add if missing, then commit:
  ```bash
  git add .gitignore
  git commit -m "chore: exclude src-tauri/target/ from git tracking"
  ```

---

## Step 7 — GitHub Actions CI for macOS + Windows

- [ ] **7.1** Create `.github/workflows/tauri-build.yml`:

  ```yaml
  name: Tauri Build

  on:
    push:
      branches: [main]
      tags:
        - 'v*'
    pull_request:
      branches: [main]

  jobs:
    build-tauri:
      strategy:
        fail-fast: false
        matrix:
          include:
            - platform: macos-latest      # Apple Silicon
              args: '--target aarch64-apple-darwin'
            - platform: macos-13          # Intel
              args: '--target x86_64-apple-darwin'
            - platform: windows-latest
              args: ''

      runs-on: ${{ matrix.platform }}

      steps:
        - name: Checkout
          uses: actions/checkout@v4

        - name: Install Rust stable
          uses: dtolnay/rust-toolchain@stable
          with:
            targets: >-
              ${{
                matrix.platform == 'macos-latest' && 'aarch64-apple-darwin' ||
                matrix.platform == 'macos-13' && 'x86_64-apple-darwin' ||
                ''
              }}

        - name: Rust cache
          uses: swatinem/rust-cache@v2
          with:
            workspaces: './src-tauri -> target'

        - name: Install Python 3.12
          uses: actions/setup-python@v5
          with:
            python-version: '3.12'

        - name: Install Python dependencies
          run: pip install -r requirements.txt

        - name: Install Node.js (for Tauri CLI)
          uses: actions/setup-node@v4
          with:
            node-version: '20'

        - name: Install Tauri CLI
          run: npm install -g @tauri-apps/cli@^2.5.0

        - name: Prepare .env for bundle
          shell: bash
          run: |
            if [ ! -f .env ]; then cp config.example.env .env; fi

        - name: Build Tauri app
          run: tauri build ${{ matrix.args }}

        - name: Upload macOS .dmg
          if: runner.os == 'macOS'
          uses: actions/upload-artifact@v4
          with:
            name: idjlm-pro-dmg-${{ matrix.platform }}
            path: src-tauri/target/*/release/bundle/dmg/*.dmg
            retention-days: 7

        - name: Upload Windows .msi
          if: runner.os == 'Windows'
          uses: actions/upload-artifact@v4
          with:
            name: idjlm-pro-msi
            path: src-tauri/target/release/bundle/msi/*.msi
            retention-days: 7

        - name: Upload Windows .exe (NSIS installer)
          if: runner.os == 'Windows'
          uses: actions/upload-artifact@v4
          with:
            name: idjlm-pro-nsis
            path: src-tauri/target/release/bundle/nsis/*.exe
            retention-days: 7
  ```

- [ ] **7.2** The existing `ci.yml` (Python unit tests) runs unchanged in parallel.

  > **Windows note:** Windows runner uses `python` (not `python3`) — this is already handled in `main.rs` with the `cfg!(target_os = "windows")` branch.

- [ ] **7.3** For release builds with code signing, replace the "Build Tauri app" step with `tauri-apps/tauri-action@v0`:
  ```yaml
  - name: Build and release
    uses: tauri-apps/tauri-action@v0
    env:
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      # macOS notarisation — set these in repo secrets when ready
      APPLE_CERTIFICATE: ${{ secrets.APPLE_CERTIFICATE }}
      APPLE_CERTIFICATE_PASSWORD: ${{ secrets.APPLE_CERTIFICATE_PASSWORD }}
      APPLE_SIGNING_IDENTITY: ${{ secrets.APPLE_SIGNING_IDENTITY }}
      APPLE_ID: ${{ secrets.APPLE_ID }}
      APPLE_ID_PASSWORD: ${{ secrets.APPLE_ID_PASSWORD }}
      APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
    with:
      tagName: ${{ github.ref_name }}
      releaseName: 'IDJLM Pro ${{ github.ref_name }}'
      releaseBody: 'See CHANGELOG.md for release notes.'
      releaseDraft: true
      args: ${{ matrix.args }}
  ```
  Add secrets to the GitHub repo under Settings > Secrets when an Apple Developer account is available.

- [ ] **7.4** Commit:
  ```bash
  git add .github/workflows/tauri-build.yml
  git commit -m "ci: add Tauri build workflow — macOS arm64 + x86_64, Windows"
  ```

---

## Docs Update

- [ ] Update `README.md` — add a "Building the Desktop App" section:
  ```
  ## Building the Desktop App (Tauri — v3.5.0+)

  Requirements: Rust (via rustup), Node.js 18+, Python 3.12

      npm install -g @tauri-apps/cli@^2.5.0  # install Tauri CLI once

      tauri dev                               # dev mode — hot reload
      cargo tauri build                       # production build
      # Output: src-tauri/target/release/bundle/

  The older PyInstaller approach (build-mac.sh) is retained for rollback
  but is no longer the primary build path for releases v3.5.0+.
  ```

- [ ] Add deprecation header to `build-mac.sh` line 1:
  ```bash
  # DEPRECATED as of v3.5.0 — superseded by Tauri (src-tauri/).
  # Retained for emergency rollback only. Do not use for new releases.
  ```

- [ ] Commit:
  ```bash
  git add README.md build-mac.sh
  git commit -m "docs: Tauri build instructions in README; deprecate build-mac.sh"
  ```

---

## Known Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Python 3.12 not found on end-user machine | Medium (macOS has Python 3 via Xcode, but 3.12 not guaranteed) | See Sidecar Binary appendix — bundle a PyInstaller binary as a Tauri sidecar; no Python dependency |
| `window.__TAURI__` not injected | Low | Confirmed by `"withGlobalTauri": true` in conf; double-check after any Tauri version bump |
| Flask port 5050 collision | Low (another process using 5050) | Pass different `FLASK_PORT` env var before launching; or port `_find_free_port()` logic into Rust and set via env |
| CSP blocks Flask inline scripts | Low (`"csp": null` disables Tauri CSP) | If re-enabled later, add `unsafe-inline` exception or move to external script files |
| macOS Gatekeeper rejects unsigned app | High for end-user distribution | Set `signingIdentity` in conf; use `tauri-action` with Apple Developer ID secrets in CI |
| Windows Defender / SmartScreen warning | Medium | Sign with EV certificate or accepted publisher cert; `tauri-action` handles this |
| Flask TCP port open before routes registered | Low | 300ms grace delay after TCP connect in `wait_for_flask()` handles this |
| pywebview window opens alongside Tauri | Low | `IDJLM_HEADLESS=1` env var guards the pywebview block in `run_app.py` |

---

## Appendix: Sidecar Binary Option (Zero Python Dependency)

If you want the app to work on machines with no Python installed (non-technical end users):

**1.** Create a PyInstaller single-file binary of `run_app.py`:
```bash
pip install pyinstaller
pyinstaller --onefile --name idjlm-flask-server \
  --add-data "templates:templates" \
  --add-data "app/static:app/static" \
  --add-data "taxonomy.json:." \
  --hidden-import "engineio.async_drivers.threading" \
  --collect-all librosa \
  --collect-all flask \
  run_app.py
# Output: dist/idjlm-flask-server
```

**2.** Rename with the Tauri platform triple suffix (required by Tauri sidecar conventions):
```bash
# macOS Apple Silicon:
cp dist/idjlm-flask-server binaries/idjlm-flask-server-aarch64-apple-darwin
# macOS Intel:
cp dist/idjlm-flask-server binaries/idjlm-flask-server-x86_64-apple-darwin
# Windows:
copy dist\idjlm-flask-server.exe binaries\idjlm-flask-server-x86_64-pc-windows-msvc.exe
```

**3.** Register the sidecar in `tauri.conf.json`:
```json
"bundle": {
  "externalBin": ["binaries/idjlm-flask-server"]
}
```

**4.** In `main.rs`, replace the `Command::new("python3")` block with:
```rust
use tauri_plugin_shell::ShellExt;

let sidecar_cmd = app_handle.shell().sidecar("idjlm-flask-server")
    .expect("sidecar not found")
    .env("FLASK_PORT", FLASK_PORT.to_string())
    .env("IDJLM_HEADLESS", "1");

let (mut _rx, child) = sidecar_cmd.spawn().expect("failed to spawn sidecar");
*flask_arc.lock().unwrap() = Some(child);
```

Bundle size impact: adds ~80-120 MB to the .app. Recommended once the app is ready for broad distribution.

---

## File Inventory

| File | Action | Step |
|---|---|---|
| `src-tauri/tauri.conf.json` | Create with exact content | 2.2 |
| `src-tauri/Cargo.toml` | Create with exact content | 2.3 |
| `src-tauri/src/main.rs` | Create with exact content | 3.1 |
| `run_app.py` | Patch — add `IDJLM_HEADLESS` guard | 3.2 |
| `src-tauri/icons/` | Populate via `tauri icon` | 5.1 |
| `app/static/modules/library.js` | Edit `openFolderPicker()` | 4.1 |
| `.github/workflows/tauri-build.yml` | Create | 7.1 |
| `README.md` | Add Tauri build instructions | docs |
| `build-mac.sh` | Add deprecation header | docs |
| `.gitignore` | Add `src-tauri/target/` | 6.7 |

---

*Plan version: 1.0 — 2026-05-28*
*IDJLM Pro v3.5.0 — Phase 3: Tauri Desktop Wrapper*
