# XDJ Library Manager

<p align="center">
  <img src="app/static/icon.png" width="120" alt="XDJ Library Manager" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="Version" />
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
**Windows:** Unzip → double-click `XDJ Library Manager.exe`

> **Mac (first launch):** macOS may block the app. Go to **System Settings → Privacy & Security → Open Anyway**.
> Or in Terminal: `xattr -cr "/path/to/XDJ Library Manager.app"`

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

### v1.0.0 — 2026-04-04
- **New:** Mac + Windows standalone app — no Python, no installation
- **New:** AI genre + sub-genre classification via Gemini 2.5 Flash
- **New:** Gemini model selector — 2.5 Pro / 2.5 Flash / 2.5 Flash Lite / 2.0 Flash
- **New:** Auto model rotation on rate limits / quota errors
- **New:** BPM, Camelot key, energy analysis via librosa
- **New:** Real-time SSE progress bar with ETA and cancel button
- **New:** Keyboard shortcuts in review (A/S/E/←/→)
- **New:** Sort + filter toolbar (by title, artist, BPM, confidence, genre, status)
- **New:** Stats bar — track count, genre breakdown, average confidence
- **New:** Confidence colour coding (green / orange / red)
- **New:** Audio preview player — inline playback in review queue
- **New:** Tag backup before every write (`~/.xdj_library_manager/backups/`)
- **New:** Auto-save every 30 tracks during processing
- **New:** Session save/load — resume where you left off
- **New:** CSV export of full library
- **New:** Folder watcher — auto-import new files
- **New:** Taxonomy editor — add/remove genres live
- **New:** Confidence threshold — bulk approve above your score
- **New:** Spotify enrichment (optional — year, popularity)
- **New:** Version badge in app header
- **New:** App icon (vinyl record with neon glow)
- **Fix:** Import bug — only 1 track appeared from hundreds (DOM rendering bug)

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
