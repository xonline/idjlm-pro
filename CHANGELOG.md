# Changelog

All notable changes to IDLM Pro are documented here.

---

## [2.3.0] — 2026-04-05

### Organise Tab
- **Library Health Dashboard** — live stats: total, analyzed, classified, approved, tags written, duplicates; coverage bars for BPM/Key/Energy/Artwork; genre breakdown
- **Filename → Tag Parser** — scans tracks named "Artist - Title.mp3" with missing tags, previews parsed values vs existing tags, apply individually or all at once
- **Folder Auto-Organiser** — move approved tracks into `Genre/Sub-Genre/` (or `Genre/` or `Genre/Sub-Genre/Year/`) folder structure; dry-run preview before committing moves
- **Key Accuracy Validator** — compares stored Camelot keys against librosa-detected keys; flags mismatches of ≥2 Camelot steps; one-click fix individual or all

### Set Planner Tab
- **Energy Arc Set Planner** — auto-builds a DJ set shaped to Warm-Up, Peak Hour, Cool-Down, or Full Night arc; configurable duration, genre filter, BPM range
- **Arc visualiser** — canvas preview of the selected energy curve
- **Export as M3U** — download the generated set directly as an M3U playlist

### Audio Intelligence (computed during Analysis)
- **Vocal / Instrumental detector** — classifies each track as "vocal", "instrumental", or "mostly_instrumental" using harmonic separation + spectral flatness + MFCC variance; confidence 0–100
- **Tempo category** — genre-aware slow/medium/fast label (Bachata, Kizomba, Salsa, etc. each have calibrated BPM thresholds)

### Track Table
- Added Clave column (was in JS but missing from HTML header — fixed)
- Added Vocal column (badge: blue=Vocal, green=Instr., orange=Mostly Instr.)
- Added Tempo column (badge: red=Fast, orange=Medium, blue=Slow)

### Automation
- GitHub Actions workflow — auto-builds macOS DMG + Windows ZIP and creates GitHub release on every `v*.*.*` tag push
- `CHANGELOG.md` extracted from README into its own file; release notes populated automatically per version

---

## [2.2.0] — 2026-04-04

### Latin DJ Features (djay Pro add-on)
- **Clave pattern detector** — auto-detects 2-3 vs 3-2 clave in Salsa/Son/Mambo tracks using onset correlation templates; confidence score 0–100
- **Montuno detector** — locates rhythmic breakdown entry point via spectral flux peaks
- **Smart cue points** — 4 auto-detected positions per track: Beat 1 (first downbeat), Montuno/Drop entry, Main hook (highest onset density), Outro (energy drop below 40% of peak)
- **Mix compatibility score** — 0–100 score across BPM proximity (25 pts, double/half BPM aware), Camelot wheel distance (35 pts), energy match (20 pts), genre match (20 pts)
- **Tag validator** — flags tracks with missing BPM, missing key, low-confidence genre, and non-standard Camelot notation
- **Cue sheet export** — JSON export of suggested cue points per track, filterable by genre
- **M3U playlist splitter** — configurable chunk size (100 / 500 / 1000 tracks per file, default 500); exports as ZIP of multiple M3U files

---

## [2.1.1] — 2026-04-04

### Track Waveform Thumbnails
- Mini waveform thumbnail in every track row (80×24 px canvas, mirrored teal bar graph)
- 60-point amplitude array computed during librosa analysis — no extra audio load
- Renders immediately after analysis; updates live as tracks are analyzed

---

## [2.1.0] — 2026-04-04

### Frontend Round 2
- SSE progress bars for long-running operations (Analysis, Classification, Tagging)
- Track detail slide-in panel: full metadata, AI classification with confidence, album art
- Setlist Builder tab: harmonic mixing suggestions (Camelot wheel compatibility), duration tracking
- Text search bar with client-side filtering and debounce (333 ms)
- Bulk select with checkboxes and floating action bar for batch operations
- Apple Music sync button with tooltip
- Enhanced Settings: AI model selector (Claude / Gemini / Ollama), API key management, batch size, auto-approve threshold
- Export to CSV, JSON, Rekordbox XML with genre filtering
- Mobile-responsive UI with dark theme consistency

---

## [2.0.0] — 2026-04-04

### Core Library Tools
- Duplicate track detector (content-hash scan + remove)
- Album art auto-fetch from Spotify + embed in ID3
- BPM half/double auto-correction for Latin dance tempos
- Smart playlist builder with BPM range, energy, and key filters

---

## [1.9.0] — 2026-04-04

### Rebrand
- Rebranded to IDLM Pro (Intelligent DJ Library Manager)
