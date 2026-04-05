# Changelog

All notable changes to IDJLM Pro are documented here.

---

## [2.4.10] — 2026-04-05

### Bug Fixes
- **"Let's go" button unreadable on Pure Black theme** — `btn-primary` uses accent (`#e0e0e0`) as background with white text, making it invisible. Added `body.pure-black .btn-primary { color: #000000 }` so text is black on the near-white button.
- **Settings save not working** — `initSettingsTab()` was defined but never called from `DOMContentLoaded`; the Save button had no event listener attached. Fixed.
- **Settings threshold ID mismatch** — `saveSettings()` read from `settings-threshold` (non-existent) and referenced undefined `appState`; fixed to read from `settings-auto-approve` with safe fallback.
- **Track edit save → 404** — `saveTrackEdits()` used `encodeURIComponent(path)` in the URL path, but Flask's `<path:>` converter doesn't decode `%2F` as expected, causing lookup misses. Changed to `PUT /api/tracks/by-path?path=...` (query param). Same fix applied to the approve-button in the track table.
- **Bulk select bar never appeared** — JS referenced `id="bulk-actions-bar"` but HTML had `id="bulk-action-bar"` (no 's'). Fixed HTML id to match.
- **Audio playback failing** — `audio.play()` was called immediately after setting `audio.src` before the browser loaded the data. Added `audio.load()` before `audio.play()` in both `playTrack()` and `toggleAudioPlay()`. Also fixed `audio.src` absolute vs. relative comparison in `toggleAudioPlay()`.

### Improvements
- **One save button for Settings** — "Save All Settings" button now saves both API keys and taxonomy in one click. Separate "Save Taxonomy" button removed from UI.

---

## [2.4.9] — 2026-04-05

### Bug Fixes
- **Tab switching broken** — Organise / Set Planner / Settings tabs were unclickable; `initNavigation()` was called in `DOMContentLoaded` but never defined. Added the function to wire `.nav-btn` click events to `switchTab()`.
- **Edit modal close/save/cancel broken** — `initEditModal()` was defined but never called on page load; all modal button listeners were never attached.
- **Audio player controls broken** — `initAudioPlayer()` was defined but never called; prev/next/seek/play-pause in the bottom bar didn't respond.
- **View details panel not opening** — `openTrackDetail()` toggled a CSS `.open` class but no CSS rule for that class existed; panel had inline `style="display:none"` that was never cleared. Fixed to use `style.display` directly. Also wired up the × close button and overlay-click to close.
- **Column preferences not loading** — `initColumnToggle()` was defined but never called; saved column visibility from localStorage was ignored on load.
- **Bulk select not wiring** — `initBulkSelectFeature()` and `initSearchFeature()` were defined but never called.

### Improvements
- **Default theme** — changed from `dark` to `pure-black`; new users no longer need to manually switch theme.
- **"Sub-Genre" renamed to "Comments"** — all UI labels (table column, edit modal, bulk edit, organise options, taxonomy editor, set planner filter) now read "Comments" to match industry terminology.

---

## [2.4.8] — 2026-04-05

### Bug Fixes
- **Logo layout** — "IDJLM Pro" and version were stacking vertically (wrong CSS class `logo-container` → `logo`); now inline on one row with correct alignment

### Improvements
- **Native folder picker** — clicking "Change" or "Choose Folder" now opens a native OS folder dialog instead of a text input; no more typing file paths manually. Falls back to text input in dev/browser mode.

---

## [2.4.7] — 2026-04-05

### Improvements
- **Version in sidebar** — app version now shown next to "IDJLM Pro" in top-left (e.g. `IDJLM Pro v2.4.7`); reads from bundled VERSION file at runtime
- **PyInstaller bundle** — VERSION file now included in macOS DMG and Windows ZIP builds so version displays correctly in the packaged app

---

## [2.4.6] — 2026-04-05

### Improvements
- **Spotify dev link** — "Get credentials ↗" link to developer.spotify.com/dashboard added inline next to the Spotify Enrichment section label in Settings
- **Save Settings confirmation** — clicking Save now always shows a "Settings saved" toast; previously showed nothing when API key fields were empty (keys already saved appear masked in placeholders, so inputs look empty)

---

## [2.4.5] — 2026-04-05

### Features
- **4-theme system** — sidebar now shows 4 colour swatches; click to switch theme instantly
  - **Purple Dark** — original design (unchanged)
  - **Pro Booth** — amber/orange on deep charcoal; Pioneer CDJ/rekordbox aesthetic
  - **Studio Dark** — cyan on navy; Ableton/DAW aesthetic
  - **Pure Black** — true black with white typography; Spotify/Apple Music aesthetic
- Theme selection persists across sessions via `localStorage`

---

## [2.4.4] — 2026-04-05

### Native App (run_app.py)
- **Random port** — Flask now binds to a free ephemeral port instead of hardcoded 5050; overridable via `FLASK_PORT` env var
- **Close confirmation dialog** — pywebview window now prompts "Are you sure you want to close?" before quitting (prevents accidental data loss mid-session)

---

## [2.4.3] — 2026-04-05

### Bug Fixes
- **Sort failure on null fields** — sorting by confidence/BPM/year no longer silently falls back to wrong order when values are None
- **Edited status never reverted** — clearing all overrides now correctly reverts track status from `edited` back to `pending`
- **Bulk-edit validation bypass** — `/api/review/bulk-edit` now validates BPM/key/year identically to the single-track endpoint

### Features
- **Harmonic mix suggestions** — `/api/mixes/compatible/<path>` endpoint now exists; returns top 10 compatible tracks by Camelot key (±1) + BPM (±8%)
- **Rekordbox INITIALKEY** — tag writer now writes `TXXX:INITIALKEY` alongside `TKEY` for full Rekordbox/Serato compatibility
- **Latin metadata in ID3** — clave pattern, energy score, vocal flag, tempo category now written as `COMM` frames (portable to all DJ tools)
- **Classifier clave + comment hints** — detected clave pattern and existing COMMENT tag now included in AI classification prompt; style hints added for Bachata/Salsa subgenre disambiguation
- **API retry with backoff** — Claude/Gemini rate limit errors (429) now retry 3× with 30s/60s/120s delays before falling back
- **Skip already-classified tracks** — "Classify All" skips tracks already classified; add `"force": true` to request body to reclassify all
- **Onboarding modal** — first-time users see a 6-step quick-start guide (dismissed via localStorage)
- **Setlist persistence** — setlist survives page refresh via localStorage; "Clear Setlist" button added

---

## [2.4.2] — 2026-04-05

### Bug Fixes
- **M3U export** — was broken; now uses native `fetch()` instead of `apiFetch()` so blob download works
- **Bulk selection** — never activated due to wrong DOM id (`track-table-body` → `tracks-tbody`)
- **Apple Music sync** — was sending full library instead of selection; fixed `Set.length` → `Set.size`
- **Review keyboard shortcuts (a/s)** — were no-ops; added missing `data-approve-btn`/`data-skip-btn` attributes
- **Stale folder path on session resume** — old sessions without `folder_path` metadata no longer corrupt auto-save path
- **Stack traces** — no longer leaked to frontend; all routes now log server-side and return generic error messages
- **Bulk approve parameter** — frontend/backend mismatch fixed (`threshold` → `min_confidence`; backend now accepts both)
- **Approval log race condition** — concurrent write-tag threads now use a lock to prevent log corruption

### Improvements
- **Search debounce** — 300ms debounce on library search; no more UI freeze while typing
- **Track table pagination** — 100 tracks per page with prev/next controls; eliminates browser slowdown on large libraries
- **Input validation** — BPM (40–300), Key (≤10 chars), Year (1900–2030) validated before saving; returns 400 on invalid input

---

## [2.4.1] — 2026-04-05

### Improvements
- **Gemini 2.0-flash** — classifier upgraded from `gemini-1.5-flash` to `gemini-2.0-flash` for better genre accuracy
- **Auto-save after classify & write-tags** — session persisted automatically so progress is never lost between steps
- **Keyboard navigation** — ↑/↓ arrows to move between tracks, Space to approve selected row
- **Threshold input** — confidence threshold is now an inline editable number field (was static text); value persists via `localStorage`
- **New app icon** — Nano Banana-generated vinyl record icon with purple-to-cyan gradient and neon waveform

### Bug Fixes (Codex-reviewed)
- **NaN threshold guard** — `parseInt("")` on cleared threshold input now falls back to `80` instead of `NaN`
- **Stale folder path on session resume** — `_current_folder_path` now restored from session metadata on load so auto-save works correctly in resumed sessions

---

## [2.4.0] — 2026-04-05

![v2.4.0 screenshot](docs/screenshot-v2.4.0.png)

### UI Redesign — Single Library View
- **Sidebar trimmed to 4 items** — Library, Organise, Set Planner, Settings
- **Library toolbar** — folder picker + Analyze All + Classify All + Approve ≥N% + Write Tags on one row
- **Inline stats bar** — total/analyzed/classified/approved always visible; progress bar appears during pipeline runs
- **Inline approve column** — approve/unapprove per row, no Review tab needed
- **SSE progress** — analyze/classify/write-tags progress shown inline in stats bar
- **Removed standalone tabs** — Import, Review, Stats, Taxonomy, Setlist, Wheel, Duplicates; content folded into Library / Settings / Set Planner / Organise
- **No backend changes** — all API routes unchanged

---

## [2.3.2] — 2026-04-05

### Bug Fixes
- **Track data missing in UI** — `Track.to_dict()` used `dataclasses.asdict()` which excludes `@property` methods; all computed fields (`final_genre`, `final_bpm`, `final_key`, `display_title`, `display_artist`, `final_subgenre`, `final_year`, `final_comment`) now explicitly included in the serialised dict
- **Audio playback broken** — audio route changed from `/api/audio/<path:file_path>` to `/api/audio?path=...` (query param); `encodeURIComponent` was encoding `/` → `%2F` making Flask `os.path.abspath()` resolve to wrong path
- **Edit modal couldn't be closed** — JS errors from undefined track properties prevented event handlers; root cause fixed; Escape key handler added as belt-and-braces
- **Session lost on browser refresh** — session now auto-saved immediately after every import
- **No UX guidance after import** — toast now says "click Analyze All to extract BPM & key"; app auto-switches to Tracks tab after import so user can see what was loaded

### Track Model
- Added `override_comment` field and `final_comment` property (falls back to `proposed_subgenre` then `existing_comment`)

---

## [2.3.1] — 2026-04-05

### Launch UX
- **Splash screen on startup** — animated loading screen appears immediately when the app launches; no more blank bounce in the Dock for 5+ minutes on first run
- **Smart Flask wait** — app polls for Flask readiness instead of a fixed sleep; swaps splash → main UI the moment the server is up
- **Reduced bundle size** — excludes matplotlib, IPython, jupyter, notebook, test/unittest from PyInstaller build; cuts cold-start Gatekeeper scan time on macOS

### App Icon
- **Custom vinyl record icon** — dark rounded-square background, purple→teal gradient label, subtle groove rings, three-dot AI motif; generated from `assets/make_icon.py`
- macOS `.icns` and Windows `.ico` both auto-generated during CI build via `assets/make_icon.py` (Pillow); `iconutil` used on macOS runner for full multi-resolution `.icns`

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
- Rebranded to IDJLM Pro (Intelligent DJ Library Manager)

---

## [1.8.0] — 2026-04-03

### Stats Tab
- **Library Stats tab** — summary cards: Total Tracks, Classified, Approved, Written to Files
- **Genre Distribution chart** — horizontal bar chart (Chart.js) showing track count per genre
- **BPM Distribution chart** — bar chart bucketed into ranges: 60–79, 80–89, 90–99, 100–109, 110–119, 120+
- **Release Year Distribution chart** — decade breakdown: Pre-2000, 2000s, 2010s, 2020s
- **Top Sub-Genres list** — top 10 sub-genres with count badges; all charts update live when tab activated

### Camelot Wheel in Review Modal
- **SVG Camelot wheel** — 12 positions × 2 rings (inner = minor A keys, outer = major B keys)
- Active track key highlighted in purple; compatible adjacent keys highlighted in green
- Renders automatically when opening any track's edit/review modal

---

## [1.7.0] — 2026-04-03

### Audio Preview
- **Inline audio player in Review tab** — play/pause button per track, progress bar with seek-by-click
- Single shared audio element (one track plays at a time); active track shows pause icon in green
- Audio streamed via `GET /api/audio/<path:file_path>`

### M3U Export UI in Review Tab
- **Export Playlist dropdown** in Review footer — "Export All Approved" or "Export by Genre…"
- Genre selector modal dynamically lists unique genres from approved tracks
- Triggers file download via `/api/export/m3u?genre=X&status=approved`

---

## [1.6.0] — 2026-04-03

### Session Save / Resume
- **Resume Session banner** on Import tab — shows on page load when a previous session exists; displays track count, folder path, last saved timestamp
- **Save Session button** — `POST /api/session/save`; persists all track data to disk
- **Resume button** — `POST /api/session/load`; restores full library state without re-scanning

### Folder Watcher
- **Watch Folder toggle** in Import controls — `POST /api/watch/start` / `POST /api/watch/stop`
- Polls `GET /api/watch/poll` every 5 seconds; newly detected MP3s added automatically to the track table
- Status line shows watched path while active

---

## [1.5.0] — 2026-04-02

### Export Formats
- **Rekordbox XML export** — `GET /api/export/rekordbox` — valid Rekordbox 6.0 DJ_PLAYLISTS XML with COLLECTION + PLAYLISTS nodes; URL-encoded file Location paths
- **CSV export** — `GET /api/export/csv` — columns: title, artist, album, year, genre, subgenre, bpm, key, energy, confidence, file_path
- **JSON export** — `GET /api/export/json` — array of track objects with all metadata fields
- All export endpoints support query filters: genre, subgenre, status, bpm_min/max, energy_min/max, key

---

## [1.4.0] — 2026-04-02

### Bulk Operations
- **Bulk approve by threshold** — approve all tracks with confidence ≥ N% in one click
- **Bulk tag write** — write all approved tracks' ID3 tags in a single batch operation with SSE progress stream
- **Bulk select with checkboxes** — floating action bar for batch approve / skip / delete on selected tracks
- **Text search** — client-side track filtering with 333 ms debounce

---

## [1.3.0] — 2026-04-01

### Spotify Enrichment
- **Spotify metadata enrichment** — searches Spotify by artist + title; fills missing year, album art URL, and genre data
- Gap-fill only — never overwrites existing tags
- Skips gracefully when `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` not configured
- Album art URL stored on track; embedded into ID3 `APIC` frame via mutagen

---

## [1.2.0] — 2026-04-01

### Review Workflow + Tag Writing
- **Review tab** — side-by-side current vs proposed tags per track; approve / skip / edit individually
- **Confidence threshold slider** — bulk approve all tracks above chosen threshold
- **Tag writer service** — writes approved changes to ID3 via mutagen: GENRE→TCON, sub-genre→COMM, BPM→TBPM, KEY→TKEY, YEAR→TDRC
- Only writes fields that changed and were approved; backs up nothing (git is the safety net)

---

## [1.1.0] — 2026-03-31

### AI Classification
- **Claude AI classifier** — sends audio features + metadata + taxonomy to Claude API; returns genre, sub-genre, confidence (0–100), and reasoning text
- Batches up to 10 tracks per API call to reduce cost
- Taxonomy-aware — sub-genre definitions from `taxonomy.json` included in every prompt
- **Taxonomy tab** — add, rename, or remove genres and sub-genres; AI adapts immediately to changes

---

## [1.0.0] — 2026-03-30

### Initial Release
- **MP3 scanner** — walks a folder recursively, finds all MP3 files, reads existing ID3 tags (title, artist, album, year, genre, comment, BPM, key) via mutagen
- **Audio analysis** — librosa pipeline per track: BPM detection, musical key → Camelot notation (1A–12B), energy score (1–10 scale), waveform amplitude array (60 points)
- **Dark-themed single-page app** — Flask + vanilla JS; tabs: Import, Tracks, Review, Taxonomy, Settings
- **In-memory track store** — session-scoped dict keyed by file path; all state lives server-side
- **Settings tab** — Anthropic API key, Spotify credentials, batch size, auto-approve threshold
- **Import workflow** — enter folder path → scan → analyze → classify → review → write tags
