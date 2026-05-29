# Zero-Dependency Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bundle IDJLM Pro's Python backend + all dependencies into a platform binary so users only need to install the app — no Python, no pip, no terminal.

**Architecture:** PyInstaller wraps `run_app.py` and all deps (Flask, librosa, numpy, soundfile, mutagen, etc.) into a single executable called `idjlm-server`. Tauri's `externalBin` bundles it. `main.rs` launches this binary instead of calling `python3`. GitHub Actions builds the PyInstaller binary on each platform before Tauri packages the app.

**Tech Stack:** PyInstaller 6.x, Tauri 2.x, Rust, GitHub Actions matrix (macOS arm64, macOS x86_64, Windows x86_64)

---

### Task 1: Create `idjlm.spec` — PyInstaller spec file

**Files:**
- Create: `idjlm.spec`

- [ ] **Create `idjlm.spec` at the project root**

```python
# idjlm.spec
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

librosa_datas, librosa_binaries, librosa_hiddenimports = collect_all('librosa')
soundfile_datas, soundfile_binaries, soundfile_hiddenimports = collect_all('soundfile')
sklearn_datas, sklearn_binaries, sklearn_hiddenimports = collect_all('sklearn')
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')

a = Analysis(
    ['run_app.py'],
    pathex=['.'],
    binaries=soundfile_binaries + librosa_binaries + sklearn_binaries + numpy_binaries,
    datas=[
        ('app', 'app'),
        ('templates', 'templates'),
        ('taxonomy.json', '.'),
        *librosa_datas,
        *soundfile_datas,
        *sklearn_datas,
        *numpy_datas,
        *collect_data_files('scipy'),
    ],
    hiddenimports=[
        *librosa_hiddenimports,
        *soundfile_hiddenimports,
        *sklearn_hiddenimports,
        *numpy_hiddenimports,
        *collect_submodules('scipy'),
        *collect_submodules('flask'),
        *collect_submodules('flask_cors'),
        *collect_submodules('mutagen'),
        *collect_submodules('google.generativeai'),
        *collect_submodules('anthropic'),
        *collect_submodules('spotipy'),
        *collect_submodules('watchdog'),
        *collect_submodules('pylast'),
        *collect_submodules('deezer'),
        'resampy', 'soxr', 'audioread', 'pooch', 'lazy_loader',
        'numba', 'llvmlite', 'certifi', 'charset_normalizer', 'urllib3',
        'PIL', 'PIL.Image',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'IPython', 'jupyter', 'matplotlib', 'tkinter', 'PyQt5', 'PyQt6',
        'wx', 'gi', 'cv2', 'tensorflow', 'torch', 'torchvision', 'pywebview',
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='idjlm-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
)
```

- [ ] **Commit**

```bash
cd /home/ubuntu/projects/idjlm
git add idjlm.spec
git commit -m "build: add PyInstaller spec for zero-dep sidecar binary"
```

---

### Task 2: Install PyInstaller and do a local test build

**Files:**
- No file changes — install only

- [ ] **Install PyInstaller into the venv**

```bash
cd /home/ubuntu/projects/idjlm
.venv/bin/pip install pyinstaller
```

Expected: `Successfully installed pyinstaller-X.X.X`

- [ ] **Run test build (takes 3–10 minutes)**

```bash
cd /home/ubuntu/projects/idjlm
.venv/bin/pyinstaller idjlm.spec --clean 2>&1 | tail -30
```

Expected last line: `Building EXE from EXE-00.toc completed successfully.`

If any `ModuleNotFoundError` warnings appear, add those module names to `hiddenimports` in `idjlm.spec` and rebuild.

- [ ] **Verify binary exists**

```bash
ls -lh /home/ubuntu/projects/idjlm/dist/idjlm-server
file /home/ubuntu/projects/idjlm/dist/idjlm-server
```

Expected: binary file ~300–500MB.

- [ ] **Smoke-test the binary**

```bash
cd /home/ubuntu/projects/idjlm
IDJLM_HEADLESS=1 FLASK_PORT=5051 ./dist/idjlm-server &
SIDECAR_PID=$!
# Allow up to 30s for first-run extraction + Flask boot
for i in $(seq 1 30); do
  curl -s http://localhost:5051/ > /dev/null 2>&1 && echo "Flask up after ${i}s" && break
  sleep 1
done
curl -s http://localhost:5051/ | grep -c "IDJLM" && echo "HTML OK"
kill $SIDECAR_PID
```

Expected: `Flask up after Xs`, `HTML OK`.

---

### Task 3: Place binary where Tauri expects it + update .gitignore

**Files:**
- Create: `src-tauri/binaries/` directory
- Modify: `.gitignore`

- [ ] **Create binaries directory and copy with triple suffix**

```bash
mkdir -p /home/ubuntu/projects/idjlm/src-tauri/binaries
TRIPLE=$(rustc -Vv | grep host | awk '{print $2}')
echo "Triple: $TRIPLE"
cp /home/ubuntu/projects/idjlm/dist/idjlm-server \
   /home/ubuntu/projects/idjlm/src-tauri/binaries/idjlm-server-${TRIPLE}
ls -lh /home/ubuntu/projects/idjlm/src-tauri/binaries/
```

Expected: one file named `idjlm-server-aarch64-unknown-linux-gnu` (or current platform triple).

- [ ] **Update .gitignore**

```bash
cd /home/ubuntu/projects/idjlm
grep -q "src-tauri/binaries/" .gitignore || echo "src-tauri/binaries/" >> .gitignore
grep -q "^dist/" .gitignore || echo "dist/" >> .gitignore
grep -q "^build/" .gitignore || echo "build/" >> .gitignore
```

- [ ] **Commit**

```bash
cd /home/ubuntu/projects/idjlm
git add .gitignore
git commit -m "build: ignore PyInstaller output dirs and sidecar binaries"
```

---

### Task 4: Update `tauri.conf.json` — externalBin, remove raw Python resources

**Files:**
- Modify: `src-tauri/tauri.conf.json`

- [ ] **Replace the `bundle` section**

Open `src-tauri/tauri.conf.json`. Find the `"bundle"` object and replace it with:

```json
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
  "externalBin": [
    "binaries/idjlm-server"
  ],
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
}
```

The `"resources"` key is removed — the sidecar binary contains everything.

- [ ] **Commit**

```bash
cd /home/ubuntu/projects/idjlm
git add src-tauri/tauri.conf.json
git commit -m "feat: configure Tauri externalBin sidecar, remove raw Python resource bundling"
```

---

### Task 5: Update `src-tauri/src/main.rs` — launch sidecar binary

**Files:**
- Modify: `src-tauri/src/main.rs`

- [ ] **Replace `find_run_app` with `find_sidecar`**

Find the `fn find_run_app(app: &AppHandle) -> PathBuf` function and replace it entirely with:

```rust
/// Resolve path to the `idjlm-server` sidecar binary.
/// Production: Tauri places it in resource_dir (triple suffix stripped).
/// Dev: src-tauri/binaries/idjlm-server-{triple} (built locally via PyInstaller).
fn find_sidecar(app: &AppHandle) -> PathBuf {
    if let Ok(resource_dir) = app.path().resource_dir() {
        let candidate = resource_dir.join("idjlm-server");
        if candidate.exists() {
            return candidate;
        }
    }

    let triple = if cfg!(all(target_os = "macos", target_arch = "aarch64")) {
        "aarch64-apple-darwin"
    } else if cfg!(all(target_os = "macos", target_arch = "x86_64")) {
        "x86_64-apple-darwin"
    } else if cfg!(all(target_os = "windows", target_arch = "x86_64")) {
        "x86_64-pc-windows-msvc"
    } else if cfg!(target_arch = "aarch64") {
        "aarch64-unknown-linux-gnu"
    } else {
        "x86_64-unknown-linux-gnu"
    };

    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().and_then(|d| d.parent()).and_then(|d| d.parent())
            .map(|root| root.join("src-tauri").join("binaries")
                .join(format!("idjlm-server-{}", triple))))
        .unwrap_or_else(|| PathBuf::from(format!("idjlm-server-{}", triple)))
}
```

- [ ] **Replace the Flask spawn block**

Inside `thread::spawn(move || {`, find the section that starts with:
```rust
let run_app_path = find_run_app(&app_handle);
let python_bin = if cfg!(target_os = "windows") { "python" } else { "python3" };
let child = Command::new(python_bin)
    .arg(&run_app_path)
```

Replace it with:

```rust
let sidecar_path = find_sidecar(&app_handle);

let child = Command::new(&sidecar_path)
    .env("FLASK_PORT", FLASK_PORT.to_string())
    .env("FLASK_ENV", "production")
    .env("PYTHONDONTWRITEBYTECODE", "1")
    .env("IDJLM_HEADLESS", "1")
    .spawn();

match child {
    Ok(c) => {
        *flask_arc.lock().unwrap() = Some(c);
    }
    Err(e) => {
        eprintln!("[idjlm] Failed to start sidecar at {:?}: {e}", sidecar_path);
        show_splash_error(&window, &format!("Error starting app: {e}"));
        return;
    }
}
```

Note: remove the old `match child { Ok(c) => ...` block that followed the old spawn — the new spawn above already includes it.

- [ ] **Increase timeout constant**

Find `const FLASK_TIMEOUT_SECS: u64 = 60;` and change to:

```rust
const FLASK_TIMEOUT_SECS: u64 = 90;
```

PyInstaller `--onefile` adds 5–20s on first launch for temp-dir extraction.

- [ ] **Verify it compiles**

```bash
cd /home/ubuntu/projects/idjlm/src-tauri
cargo build 2>&1 | tail -10
```

Expected: `Finished dev [unoptimized + debuginfo] target(s)`.

- [ ] **Commit**

```bash
cd /home/ubuntu/projects/idjlm
git add src-tauri/src/main.rs
git commit -m "feat: launch idjlm-server sidecar instead of python3 run_app.py"
```

---

### Task 6: Update GitHub Actions CI — build PyInstaller before Tauri

**Files:**
- Modify: `.github/workflows/tauri-build.yml`

- [ ] **Replace the entire file contents**

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
          - platform: macos-latest
            target: aarch64-apple-darwin
            py_arch: arm64
          - platform: macos-13
            target: x86_64-apple-darwin
            py_arch: x64
          - platform: windows-latest
            target: x86_64-pc-windows-msvc
            py_arch: x64

    runs-on: ${{ matrix.platform }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install Rust stable
        uses: dtolnay/rust-toolchain@stable
        with:
          targets: ${{ matrix.target }}

      - name: Rust cache
        uses: swatinem/rust-cache@v2
        with:
          workspaces: './src-tauri -> target'

      - name: Install Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          architecture: ${{ matrix.py_arch }}

      - name: Install Python dependencies + PyInstaller
        run: |
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Build PyInstaller sidecar
        run: pyinstaller idjlm.spec --clean --distpath src-tauri/binaries/tmp
        shell: bash

      - name: Stage sidecar binary (macOS / Linux)
        if: runner.os != 'Windows'
        run: |
          mkdir -p src-tauri/binaries
          mv src-tauri/binaries/tmp/idjlm-server \
             src-tauri/binaries/idjlm-server-${{ matrix.target }}
        shell: bash

      - name: Stage sidecar binary (Windows)
        if: runner.os == 'Windows'
        run: |
          New-Item -ItemType Directory -Force -Path src-tauri/binaries
          Move-Item src-tauri/binaries/tmp/idjlm-server.exe `
            src-tauri/binaries/idjlm-server-${{ matrix.target }}.exe
        shell: pwsh

      - name: Install Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install Tauri CLI
        run: npm install -g @tauri-apps/cli@^2.5.0

      - name: Build Tauri app
        run: tauri build --target ${{ matrix.target }}

      - name: Upload macOS .dmg
        if: runner.os == 'macOS'
        uses: actions/upload-artifact@v4
        with:
          name: idjlm-pro-dmg-${{ matrix.target }}
          path: src-tauri/target/${{ matrix.target }}/release/bundle/dmg/*.dmg
          retention-days: 30

      - name: Upload Windows .msi
        if: runner.os == 'Windows'
        uses: actions/upload-artifact@v4
        with:
          name: idjlm-pro-msi
          path: src-tauri/target/release/bundle/msi/*.msi
          retention-days: 30

      - name: Upload Windows NSIS installer
        if: runner.os == 'Windows'
        uses: actions/upload-artifact@v4
        with:
          name: idjlm-pro-nsis
          path: src-tauri/target/release/bundle/nsis/*.exe
          retention-days: 30
```

- [ ] **Commit**

```bash
cd /home/ubuntu/projects/idjlm
git add .github/workflows/tauri-build.yml
git commit -m "ci: build PyInstaller sidecar before Tauri — zero-dep distribution"
```

---

### Task 7: End-to-end local test

- [ ] **Kill any leftover processes**

```bash
pkill -f "idjlm-server" 2>/dev/null; pkill -f "run_app.py" 2>/dev/null; sleep 1
```

- [ ] **Test the sidecar serves the full app**

```bash
cd /home/ubuntu/projects/idjlm
IDJLM_HEADLESS=1 FLASK_PORT=5052 ./dist/idjlm-server &
SIDECAR_PID=$!

for i in $(seq 1 60); do
  curl -s http://localhost:5052/ > /dev/null 2>&1 && echo "Flask up after ${i}s" && break
  sleep 1
done

curl -s http://localhost:5052/ | grep -c "IDJLM" && echo "HTML OK"
curl -s http://localhost:5052/api/tracks | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('API OK — total:', d.get('total', d.get('count', 'unknown')))
"
kill $SIDECAR_PID
```

Expected:
```
Flask up after Xs
1
HTML OK
API OK — total: 0
```

- [ ] **Tag and push to trigger CI builds**

```bash
cd /home/ubuntu/projects/idjlm
git tag v4.0.0
git push origin main --tags
```

CI builds `.dmg` (macOS) and `.msi`/`.exe` (Windows) artifacts. Check GitHub Actions tab — jobs take ~15–25 minutes. Artifacts appear under each completed run.

---

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ImportError: No module named X` at sidecar runtime | Add `'X'` to `hiddenimports` in `idjlm.spec`, rebuild |
| `FileNotFoundError: templates/index.html` | Confirm `('templates', 'templates')` is in `idjlm.spec` datas |
| Sidecar takes 20–30s to start (first run only) | Normal — PyInstaller extracts to tmpdir once; subsequent runs reuse it |
| CI: "sidecar binary not found" during tauri build | Check the rename/move step output; verify file exists before `tauri build` |
| Windows DLL missing | Add DLL via `collect_all()` or explicit `binaries` entry in spec |
