# XDJ Library Manager

<p align="center">
  <img src="app/static/icon.png" width="120" alt="XDJ Library Manager" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.8.0-blue" alt="Version" />
  <img src="https://img.shields.io/badge/platform-Mac%20%7C%20Windows-lightgrey" alt="Platform" />
  <img src="https://img.shields.io/badge/AI-Gemini%202.5%20Flash-orange" alt="AI" />
  <img src="https://img.shields.io/badge/music-Latin%20Dance-red" alt="Genre" />
</p>

**Bulk genre & sub-genre tagging for your DJ music library — powered by Gemini AI.**

Built for DJs with large Latin dance collections (Salsa, Bachata, Kizomba, and more). Import a folder of MP3s, let AI suggest genre + sub-genre for every track, review, and write the tags — in minutes, not hours.

---

## Download

→ **[Go to Releases](https://github.com/xonline/dj-library-manager/releases/latest)** and download for your platform:

| Platform | File |
|----------|------|
| 🍎 **Mac** | `XDJ-Library-Manager-mac.zip` |
| 🪟 **Windows** | `XDJ-Library-Manager-windows.zip` |

**Mac:** Unzip → double-click `XDJ Library Manager.app`
> **First launch:** macOS may block the app. Go to **System Settings → Privacy & Security → Open Anyway**.
> Or in Terminal: `xattr -cr "/path/to/XDJ Library Manager.app"`

**Windows:** Unzip → double-click `XDJ Library Manager.exe`

No Python. No Terminal. No installation.

---

## Setup (first time only)

You need a free **Gemini API key** for AI classification.

1. Go to [aistudio.google.com](https://aistudio.google.com/) — sign in with Google
2. Click **Get API key → Create API key**
3. Open XDJ Library Manager → **Settings** tab → paste key → **Save**

Done.

---

## How to use

### 1 — Import
Click **Import Folder** → select your MP3 folder (subfolders included).
All tracks appear with their existing ID3 tags.

### 2 — Analyse
Click **Analyse All** — detects BPM, musical key (Camelot notation), and energy level 1–10.
Real-time progress bar with ETA.

### 3 — Classify with AI
Click **Classify All** — Gemini reads each track's metadata + audio features and suggests genre + sub-genre with a confidence score.
Auto-rotates models on rate limits (2.5 Flash → 2.5 Flash Lite → 2.0 Flash).

### 4 — Review
Go to the **Review** tab. Each track shows current tags vs. AI suggestion side by side.
- **A** — approve · **S** — skip · **E** — edit · **← →** — navigate
- Confidence colours: 🟢 ≥85% · 🟡 60–84% · 🔴 <60%
- **Bulk approve** — accept everything above your threshold in one click

### 5 — Write tags
Click **Write Tags** — approved changes saved to MP3 ID3 tags.
Original tags are backed up first to `~/.xdj_library_manager/backups/`.

---

## Features

| Feature | Details |
|---------|--------|
| **AI Classification** | Gemini 2.5 Flash (default) with auto model rotation on rate limits |
| **Model selection** | Choose from 2.5 Pro / 2.5 Flash / 2.5 Flash Lite / 2.0 Flash in Settings |
| **Audio analysis** | BPM, Camelot key, energy level via librosa |
| **Bulk review** | Keyboard shortcuts, sort/filter, confidence colouring |
| **Audio preview** | Inline playback in the review queue |
| **Tag backup** | Auto-saves originals before any write |
| **Auto-save** | Session saved every 30 tracks during processing |
| **CSV export** | Full library export with all metadata |
| **Folder watcher** | Auto-import new MP3s dropped into a watched folder |
| **Taxonomy editor** | Add/remove genres and sub-genres — changes apply immediately |
| **Spotify enrichment** | Optional — pulls year and popularity to fill gaps |
| **Version badge** | App shows current version in the UI header |
| **App icon** | Vinyl record with neon glow (AI generated) |

---

## Genre taxonomy

| Genre | Sub-genres |
|-------|------------|
| Salsa | Salsa Romantica, Salsa Dura, Timba, Salsa Choke, Salsa Sensual, Guaracha, Son Cubano |
| Bachata | Bachata Tradicional, Bachata Sensual, Bachata Moderna, Bachata Urbana |
| Kizomba | Kizomba Tradicional, Urban Kiz, Semba, Ghetto Zouk, Tarraxinha |
| Cha Cha | — |
| Merengue | — |
| Reggaeton | — |
| Zouk | — |

Customise via the **Taxonomy** tab — changes apply immediately to the next classification run.

---

## Changelog

### v1.8.0 — 2026-04-04
- **New:** App icon — vinyl record with neon cyan/purple glow (generated with Imagen 4.0)
- **New:** Version badge visible in the app header (always know which build you're on)
- **Fix:** Releases page — removed orphaned `latest` and `v` releases, single clean release going forward
- **Fix:** Workflow now deletes + recreates the release tag on each push (no more duplicates)
- **Fix:** Mac instructions updated — System Settings → Privacy & Security → Open Anyway (Tahoe 26.4 compatible)
- **Fix:** Removed `install-mac.command` helper (was itself blocked by Gatekeeper)

### v1.7.0 — 2026-04-04
- **New:** Standalone Mac `.app` and Windows `.exe` via GitHub Actions — no Python, no install
- **New:** GitHub Releases page with download links
- **New:** Ad-hoc code signing for macOS (`codesign --force --deep --sign -`) to reduce Gatekeeper friction
- **New:** Release notes published immediately; Mac + Windows builds upload in parallel

### v1.6.0 — 2026-04-04
- **New:** CSV export — full library with all metadata
- **New:** M3U playlist export
- **New:** Session save/load — resume exactly where you left off
- **New:** Confidence threshold setting — re-classify only low-confidence tracks

### v1.5.0 — 2026-04-04
- **New:** Tag backup — original ID3 tags saved to `~/.xdj_library_manager/backups/` before every write
- **New:** Auto-save every 30 tracks during analysis and classification
- **New:** Persistent settings across sessions (`~/.xdj_library_manager/settings.json`)

### v1.4.0 — 2026-04-04
- **New:** Audio preview player — sticky mini player at the bottom of the review queue
- **New:** ▶ button per track to play directly from the review list

### v1.3.0 — 2026-04-04
- **New:** Keyboard shortcuts in review — A (approve), S (skip), E (edit), ← → (navigate)
- **New:** Sort + filter toolbar — sort by title, artist, BPM, confidence, genre, status
- **New:** Stats bar — track count, genre breakdown, average confidence (updates live)
- **New:** Confidence colour coding — 🟢 ≥85% · 🟡 60–84% · 🔴 <60%
- **New:** Side-by-side tag comparison in review (current → proposed)
- **New:** Dynamic page title shows progress ("XDJ — Analysing 45/234...")
- **New:** Empty state onboarding shown when no tracks loaded

### v1.2.0 — 2026-04-04
- **New:** Real-time SSE progress streaming during analysis and classification
- **New:** ETA display — "Processing X / Y · 2.3 tracks/sec · ETA: 2m 30s"
- **New:** Cancel button to stop processing mid-run
- **New:** Progress bar with sticky positioning

### v1.1.0 — 2026-04-04
- **New:** Gemini model selector in Settings — choose 2.5 Pro, 2.5 Flash, 2.5 Flash Lite, 2.0 Flash
- **New:** Auto model rotation on rate limits (429 errors) — falls back to next model automatically
- **Fix:** Removed "Claude AI" branding from About section
- **Fix:** Corrected Gemini model IDs to stable names (removed deprecated preview suffixes)

### v1.0.1 — 2026-04-04
- **Fix:** Critical — only 1 track appeared when importing large folders
  Root cause: `innerHTML +=` in a loop caused O(n²) DOM re-parsing; browser timed out after the first row.
  Fix: replaced with `DocumentFragment` — all rows built in memory, single DOM insert.

### v1.0.0 — 2026-04-04
- Initial release
- Import MP3 folders (recursive), reads all existing ID3 tags
- Audio analysis: BPM, Camelot key, energy level via librosa
- AI classification: genre + sub-genre + confidence via Gemini
- Review queue with per-track approve/skip/edit
- Bulk approve above confidence threshold
- ID3 tag writer (TCON, COMM, TBPM, TKEY, TDRC)
- Folder watcher, taxonomy editor, Spotify enrichment

---

## For developers

```bash
git clone https://github.com/xonline/dj-library-manager.git
cd dj-library-manager
cp config.example.env .env
# Add GEMINI_API_KEY to .env
./start.sh
# Open http://localhost:5050
```

**Build standalone app (Mac):**
```bash
./build-mac.sh
# Requires Python 3.10+ (brew install python@3.12)
# Output: dist/XDJ Library Manager.app
```
