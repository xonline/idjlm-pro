# IDJLM Pro — Desktop App Modernization Analysis

**Date:** 2026-04-05  
**Summary:** Research into turning IDJLM Pro from a PyInstaller + pywebview bundle into a proper native desktop app.

---

## Current Architecture

IDJLM Pro is currently:
- **Backend:** Flask web framework (Python 3.12)
- **Frontend:** Vanilla JavaScript + HTML/CSS (static assets + server-rendered templates)
- **Packaging:** PyInstaller bundles with pywebview for embedded WebKit display
- **Distribution:** macOS .dmg + Windows .zip via GitHub Actions

### Critical finding: Build is currently broken

**Codex identified a P1 bug:** The GitHub Actions release workflow installs `requirements.txt` and `pyinstaller` but never installs `pywebview`. Because `run_app.py` imports `webview` and the PyInstaller spec references `--collect-all webview`, both macOS and Windows builds fail with `ModuleNotFoundError: No module named 'webview'`.

**Fix:** Add `pyinstaller` to install step or add `pywebview` to `requirements.txt` before PyInstaller runs.

---

## Current pywebview Implementation

### What's working
- **run_app.py** properly implements:
  - Daemon Flask thread that starts the local server on port 5050
  - Connection polling via `_wait_for_flask()` to detect when Flask is ready
  - Splash screen with nice CSS animation shown while Flask boots
  - Clean window swap: initially shows splash, then loads `http://localhost:5050`
  - Fallback: if pywebview unavailable, opens system browser instead
  - Proper metadata: title, size, min_size set

### What's missing for "proper native app" feel
1. **No custom titlebar**  
   Currently uses default OS chrome, which is fine but not distinctive

2. **Window is bare**  
   No app menu, no right-click context menus, no keyboard shortcuts, no tray integration

3. **pywebview NOT in requirements.txt**  
   This means:
   - Local dev/testing may not have it installed
   - Release builds fail
   - Unclear to users what's needed

4. **No JS↔Python bridge**  
   All interactions are over HTTP (Flask routes), missing opportunities for:
   - Native file dialogs
   - Open folder requests
   - Drag/drop integrations
   - Native notifications

5. **Port is hardcoded (5050)**  
   Risk of conflicts if user runs multiple instances or has local services on that port

---

## Option Analysis (per Codex)

### Option 1: Polish Existing pywebview (RECOMMENDED)

**Effort:** Low (1–5 days for quick wins, 1–2 weeks for high polish)  
**Language change:** No  
**Best for:** Fast path to a decent native-looking desktop app

#### Specific improvements for IDJLM Pro

1. **Add `pywebview` to requirements.txt**  
   - Ensures it's installed locally and in CI/CD builds

2. **Fix GitHub Actions**  
   - Ensure `pywebview` is available before PyInstaller runs

3. **Update run_app.py:**
   ```python
   # Use random free port to avoid conflicts
   PORT = int(os.getenv("FLASK_PORT", 0))  # 0 = OS picks free port
   
   # Hide window until fully loaded
   window = webview.create_window(
       title="IDJLM Pro",
       html=SPLASH_HTML,
       width=1280,
       height=820,
       min_size=(960, 640),
       background_color="#0f0f13",
       # Add these:
       confirm_close=True,  # Ask before closing
       resizable=True,
       fullscreen=False,
   )
   window.hide()  # Hide until Flask ready
   # In _load_app():
   window.show()  # Show after load_url() succeeds
   ```

4. **Add JS↔Python bridge for desktop actions:**
   ```python
   # In flask app or new routes
   @app.route("/api/native/open-dialog")
   def open_file_dialog():
       # Expose to webview bridge for native file pickers
       pass
   ```

5. **Create custom titlebar (optional, medium effort):**
   - Set `frameless=True` in pywebview
   - Add HTML drag region at top of app
   - Add custom close/min/max buttons
   - Requires CSS `user-select: none` and JavaScript for window controls

6. **Improve splash timing:**
   - Current splash is good
   - Could add progress indicator or subtle animation

#### Pros
- Ship it fast
- Almost zero rewrite
- Familiar stack (Flask + vanilla JS)
- Users get a real app, not "browser tab"
- Already proven in release workflow

#### Cons
- Still fundamentally a webview
- Platform-specific CSS quirks will show (WKWebView on macOS vs WebView2 on Windows vs GTK on Linux)
- Custom titlebar is fiddly across OSes
- Desktop integrations (file associations, menu bar, Cmd+Q handling) are basic

#### Realistic outcome
A polished, native-looking desktop app that feels professional. Not indistinguishable from "real" desktop apps, but perfectly serviceable. Comparable to apps like Discord (which is also Electron, for comparison).

---

### Option 2: Electron Wrapper

**Effort:** Medium (2–6 weeks)  
**Language change:** Add JavaScript/Node (Flask stays)  
**Best for:** If you want robust native menus, auto-updates, tray icons

#### What this looks like for IDJLM Pro
1. Create Electron main process that spawns Flask as child process
2. Electron window loads `http://localhost:RANDOM_PORT`
3. Gradually move desktop-only logic from Flask routes to Electron/Node

#### Pros
- Very polished native shell
- Easy native menus, tray, notifications, file associations
- Auto-update framework (electron-updater)
- Better debugging tools
- Larger community

#### Cons
- Heavy footprint (app size ~200+ MB)
- Two runtimes (Python + Node)
- More complex packaging/signing on macOS
- Release builds are slower
- IPC complexity if Flask and Electron main diverge

#### Realistic outcome for IDJLM Pro
A very polished app with feature parity to Logic Pro or Final Cut Pro UI. More than you probably need right now. Overkill for a DJ library tool unless you plan heavy app-ification (tray widgets, complex menus, system integrations).

---

### Option 3: Tauri Wrapper

**Effort:** Medium-High (2–6 weeks for wrapper, 1–3 months for clean migration)  
**Language change:** Add Rust (Flask can stay initially, but awkward)  
**Best for:** If you want lighter packaging than Electron and are willing to invest in cleaner architecture

#### What this looks like for IDJLM Pro
1. Rewrite app shell in Rust/Tauri
2. Run Flask locally or refactor backend into Tauri commands
3. Frontend stays vanilla JS

#### Architectural tension
Tauri assumes a static SPA frontend + lightweight Rust backend. Flask's server-side rendering model doesn't fit cleanly. You'd either:
- **Keep Flask:** Run it locally, Tauri is just a shell. Still have Python + Rust + JS. Packaging is weird.
- **Refactor to SPA + Tauri commands:** Rewrite backend logic as Rust functions exposed to JS. Big rewrite, but clean long-term.

#### Pros
- Smaller bundle size than Electron (~50–100 MB vs 200+)
- Modern architecture
- Strong native integrations
- Good security model

#### Cons
- Learning curve (Rust for you = learning a new language)
- Smaller ecosystem than Electron
- More architectural work if you keep Flask
- If you refactor to full Tauri, major rewrite of backend logic

#### Realistic outcome
Only worthwhile if you're committed to a cleaner long-term architecture and have time to learn Rust. Otherwise, Electron or pywebview is better ROI.

---

### Option 4: PySide6/Qt Rewrite

**Effort:** High (1–6+ months)  
**Language change:** No Python change, but complete UI framework rewrite  
**Best for:** Only if desktop becomes your primary focus and webview limitations are blocking you

#### What this looks like
Complete UI redesign in Qt/PySide6. Flask could stay as local API, or refactor business logic directly into PyQt app.

#### Pros
- True native desktop app
- Strong system integration
- Better performance
- Mature ecosystem
- Still Python

#### Cons
- Biggest rewrite cost
- Vanilla JS UI code not reusable
- Different mental model (event-driven desktop vs web)
- Learning curve even for Python devs

#### Realistic outcome
Professional, true native desktop app. Only justified if you're building a complex desktop product and webview is hitting real limitations.

---

## Recommendation

### Immediate (next 1–2 weeks)

**Go with Option 1: Polish existing pywebview**

1. **Fix the build:**
   - Add `pywebview>=5.0` to requirements.txt
   - Update GitHub Actions to confirm pywebview is installed

2. **Quick wins (2–3 days):**
   - Use random free port instead of 5050
   - Hide window until Flask ready, then show
   - Add `confirm_close=True` for safety
   - Ensure icons are correct in PyInstaller

3. **Nice-to-haves (1 week):**
   - JS↔Python bridge for file dialogs and folder opens
   - Keyboard shortcut handling (Cmd+Q on macOS, etc.)
   - Proper app metadata (icon, version, name)

4. **Result:** A polished, native-looking desktop app with no visible browser UI. Users download IDJLM-Pro-*.dmg, double-click, app opens. Feels like a real app.

### Later (if needed)

- **Option 2 (Electron):** Only if you need rich menus, tray icons, or OS-level integrations beyond what pywebview offers
- **Option 3 (Tauri):** Only if you want lighter packaging and have time to invest in cleaner architecture
- **Option 4 (PySide6):** Only if desktop becomes primary product and webview hits real UX limits

---

## Summary Table

| Aspect | pywebview | Electron | Tauri | PySide6 |
|--------|-----------|----------|-------|------|
| Time to ship | 1–5 days | 2–6 weeks | 2–6 weeks | 1–6 months |
| App size | ~100 MB | ~250 MB | ~80 MB | ~80 MB |
| Native feel | Good | Excellent | Excellent | True native |
| Packaging | PyInstaller | electron-builder | tauri-bundler | PyInstaller |
| Language change | No | Add Node/JS | Add Rust | Rewrite UI |
| Code reuse | 95% | 80% | 80% | ~30% |
| Best for | Your current situation | High-polish desktop | Modern, lightweight | True desktop product |

---

## Critical Next Steps

1. **Fix requirements.txt:** Add `pywebview>=5.0`
2. **Fix GitHub Actions:** Ensure pywebview is installed before PyInstaller
3. **Test release build locally:** Verify DMG/EXE can be built and run
4. **Run the app:** Confirm no browser UI is visible to user

Then assess: Is the pywebview experience good enough? If yes, done. If no, revisit in 3–6 months.

