# Changelog

All notable changes to IDJLM Pro are documented here.

---

## [2.7.0] — 2026-04-08

### High Impact Features
- **Tag backup & restore** — Before writing tags, current ID3 values are backed up. Restore from any backup point via the Organise tab. Auto-cleanup removes backups older than 7 days (max 20 kept).
- **Re-classify workflow** — Select tracks, pick an AI provider (Claude/Gemini/OpenRouter/Ollama), force re-classify with a specific model. New modal in the bulk actions bar.
- **Parallel analysis** — ThreadPoolExecutor (4 workers) for audio analysis. ~4x speedup on large libraries. SSE progress shows "(parallel)" indicator.
- **Import filters** — Filter by file type (checkboxes), date range (modified after/before), and exclude subfolders (comma-separated strings). Collapsible filter panel below folder picker.

### Medium Impact Features
- **Drag-and-drop setlist reordering** — Native HTML5 DnD on setlist items. Visual drop indicator, saves order immediately on drop.
- **Smart Playlist builder** — New "Playlists" tab with saved filter queries. Filter by genre, sub-genre, BPM range, energy, key, status. Run anytime against current library.
- **Latin features UI integration** — "Analyze Latin" button in pipeline. Cue points shown in track detail panel. Mix score badges in setlist. "Mix Well With" suggestions in track detail.
- **Duplicate merge workflow** — Radio buttons to select which duplicate to keep, merge best fields from others. Shows summary of merged fields.
- **Library-wide search** — Server-side search across 17 fields (title, artist, genre, key, album, comments, reasoning, file path, clave...). Debounced at 300ms. Existing genre/status filters still work on top.
- **Export filtering UI** — Modal with genre, sub-genre, status, BPM, key, energy filters before export. "Export All" bypasses filters. Works for M3U, CSV, JSON, Rekordbox XML.

### Nice to Have
- **Keyboard shortcut reference** — Press `?` or `Cmd+/` to open shortcut cheat sheet. `1-4` for tabs, `/` for search, `Ctrl+S` save session, `Enter`/`Delete` for approve/skip.
- **Progress bar visualization** — Colored progress bar in stats bar (blue=analyze, green=classify, amber=write). Shows percentage during all SSE operations.
- **Post-write change summary** — After writing tags, toast shows "X written, Y changed" with expandable detail of actual field changes.
- **Mobile-responsive CSS** — 3 breakpoints (1024/768/480px). Sidebar collapses to icons, table scrolls horizontally, modals go full-width, touch-friendly 44px tap targets.

### Tests
- **80 tests passing** (1 pre-existing numpy skip in system Python)

---

## [2.6.0] — 2026-04-08

### New Features
- **Cascading provider → model selector in Settings** — Provider dropdown (Anthropic / OpenRouter / Gemini / Ollama) drives which API key section is shown and populates the model dropdown live from the provider's API.
- **Dynamic model listing endpoint (`POST /api/list_models`)** — Queries each provider's API for available models. OpenRouter models show free/paid badges based on pricing.
- **Model refresh button** — Re-fetch the model list at any time without saving first.

### Improvements
- **Gemini API compatibility (2026+)** — Supports both new `google.genai` and legacy `google.generativeai` APIs with automatic fallback from gemini-2.5-flash to gemini-2.0-flash.
- **Analysis logging** — Added detailed logger output for track analysis including per-track success/failure and summary counts.
- **Settings save reloads env** — `load_dotenv(override=True)` called after writing `.env` so changes take effect immediately without restart.
- **OpenRouter default model updated** — Default changed from `google/gemini-2.0-flash-exp:free` to `google/gemini-2.5-flash:free`.

### Tests
- **7 new tests** for `/api/list_models` endpoint (missing provider, unknown provider, claude/gemini without keys, ollama, openrouter).
- **82 total tests** passing.

---

## [2.5.9] — 2026-04-07

### Bug Fixes
- **Analysis results not showing in table** — SSE `onComplete` callbacks now refetch `GET /api/tracks` after every pipeline operation (analyze, classify, write tags).
- **JS runtime errors breaking page** — `getFilteredTracks()` now guards against missing DOM elements. `renderStatsDashboard()` only calls Chart.js methods if `typeof Chart !== 'undefined'`.
- **Stats dashboard crashing on empty library** — `renderStatsDashboard()` now exits early if `window.tracks` is empty.

---

## [2.5.8] — 2026-04-07

### Critical Fixes
- **Analysis complete but nothing shows** — SSE `onComplete` callbacks expected `data.tracks` but backend only sent summary counts. Now refetches `GET /api/tracks` after every pipeline operation (analyze, classify, write tags). Table updates correctly.
- **AppleScript routes not wired** — `applescript_bp` existed but was never registered in `create_app()`. Now registered. djay Pro integration is live.
- **Folder watcher only watched MP3** — Now watches all supported formats: MP3, FLAC, WAV, M4A, AAC, OGG, AIFF, AIF.
- **AIFF files unsupported** — Added `.aiff` and `.aif` to `SUPPORTED_EXTENSIONS`.

### New Features
- **OpenRouter AI model** — Access 100+ models (Gemini, Claude, Llama, Mistral, etc.) via single API key. Free models available. Configurable model via `OPENROUTER_MODEL` env var (default: `google/gemini-2.0-flash-exp:free`).
- **BPM confidence score** — `bpm_confidence` (0-100) computed from onset strength peak clarity. Shows which analyses are reliable.
- **Key confidence score** — `key_confidence` (0-100) computed from chroma template correlation strength.
- **Camelot Wheel visualization** — Stats tab now shows an SVG Camelot wheel with key distribution (darker = more tracks in that key).
- **Stats dashboard upgrade** — Collection summary card (total, % analyzed, % classified, % approved), key distribution chart, energy distribution chart.
- **Genre normalization** — Auto-maps common genre variants ("Salsa Romántica" → "Salsa", "Reggaetón" → "Reggaeton") on import. Reduces AI classification errors.
- **Multi-source metadata enrichment** — MusicBrainz (free, no key) and Discogs (optional token) added as fallbacks when Spotify enrichment fails.
- **Bulk Edit button** — "Bulk Edit" button in bulk actions bar opens the bulk edit modal for selected tracks.

### Improved
- **Energy recalibration** — Perceptual model combining RMS + spectral centroid + onset density instead of naive RMS-only mapping.
- **SSE `refetch` flag** — All `done` events now include `refetch: true` so frontend knows to refresh track data.
- **Config template** — `config.example.env` expanded with all options, AI model choices, and documentation links.

---

## [2.5.7] — 2026-04-07

### Critical Bug Fixes
- **Session resume broken — `load_session()` always failed** — `Track.to_dict()` serialised 8 computed properties (`display_title`, `final_genre`, `final_bpm`, etc.) that are not dataclass fields. `Track(**track_dict)` in `load_session()` raised `TypeError` for every track, causing a silent total data loss on resume. Now filters `track_dict` to only dataclass fields before reconstruction.
- **Classification 10× slower than necessary** — `/api/classify` looped through tracks calling `classify_service([track])` individually, defeating the built-in batch optimisation. Now collects all tracks and passes them at once; the service batches them per `CLASSIFY_BATCH_SIZE` (default 10). 1 API call per 10 tracks instead of 1 per track.

### Frontend Bug Fixes
- **Bulk edit saved 0 tracks** — `handleBulkEdit()` sent `file_paths` but backend expected `track_paths`. Fixed to send `track_paths`.
- **Double search listener** — `initTracksTab()` and `initSearchFeature()` both attached `input` listeners to `#search-tracks`, causing double-filtering and stale `_searchMatch` state. Removed the duplicate from `initTracksTab()`.
- **Confidence badges unstyled** — JS returned `confidence-medium` but CSS defined `.confidence-mid`. Renamed JS to use `confidence-mid`.
- **Settings threshold not loading** — `loadSettings()` read from `#settings-auto-approve-threshold` (non-existent); HTML has `#settings-auto-approve` (range slider). Fixed both `loadSettings()` and `saveSettingsRound2()` to use the correct ID. Also updates the displayed value text on load.
- **Settings saved wrong key name** — `saveSettingsRound2()` sent `batch_size` but backend expects `classify_batch_size`. Fixed.
- **Genre filter duplicated options** — `populateGenreFilters()` appended options without clearing, causing duplicates on every taxonomy reload. Now resets to `<option value="">All Genres</option>` first.
- **Organise tab crash on first run** — `runOrganise()` accessed `_previewData` property without checking if preview was run first. Now shows a warning toast if no preview data exists.
- **Genre select listener leak** — `openEditModal()` added a new `change` listener to the genre select on every open, accumulating handlers. Now clones and replaces the element to clear stale listeners.

### CSS Fixes
- **Stray closing brace** removed after `.sync-button-tooltip` rule
- **Added missing classes**: `.data-table`, `.btn-accent`, `.btn-sm`, `.nav-badge`
- **Added missing setlist/suggestion classes**: `.setlist-track-number`, `.setlist-track-duration`, `.suggestion-title`, `.suggestion-meta`
- **Added missing track detail classes**: `.track-detail-title-header`, `.track-detail-artist`, `.track-detail-album`, `.track-detail-classification`, `.classification-item`

### Backend Fixes
- **Analyzer crash on silent/corrupt audio** — `librosa.beat.beat_track` can return an empty array; `.item()` raised `IndexError`. Now checks array size and raises a descriptive error.
- **Album art content-type not validated** — Spotify URL could return HTML (redirect/error) and write it as image data to ID3. Now validates `Content-Type` starts with `image/` and derives correct MIME type.
- **`_normalize_energy` unused parameters** removed (`sr`, `hop_length`).

### Testing
- **New test suite** (`tests/test_bugfixes.py`) — 11 new tests covering session round-trip, bulk edit payload, settings fields, taxonomy CRUD, analyzer edge cases, static file validation, and review response shapes.
- **All 70 tests pass** (69 passed, 1 skipped).

---

## [2.5.6] — 2026-04-06

### Bug Fixes
- **"Analysis stream error: undefined"** — SSE progress endpoint was sending plain `data:` messages (browser `message` events), but the frontend listened for named events (`progress`, `complete`). No handlers ever fired; the connection silently closed and triggered the error toast with `undefined`. Fixed by emitting `event: progress` / `event: complete` named events. Keep-alive pings now use SSE comment syntax (`: ping`) to avoid being mistaken for data.
- **Error toast showed "undefined"** — `connectToProgress` passed a raw DOM `Event` to `onError`, which has no `.message`. Now wraps it in `new Error('Connection lost')` so the message is always readable.

### Improvements
- **API key confirmation** — Saved keys now display first 4 + last 4 characters in the input placeholder (e.g. `sk-a...xyz1  —  saved ✓`) so users can confirm which key is stored without exposing the full value.
- **Save button feedback** — Save button flashes green with "✓ Saved" for 2 seconds after a successful settings save.
- **Settings reload** — `loadSettings()` now also populates the Anthropic key placeholder and syncs AI model, Ollama model, batch size, and auto-approve threshold fields on every load.

---

## [2.5.5] — 2026-04-05

### Bug Fixes
- **`/api/analyze` and `/api/classify` still crashing (500)** — `get_json()` without `silent=True` was present in both `analyze_tracks` (line 100) and `classify_tracks` (line 163) in `import_routes.py`. Both now use `get_json(silent=True) or {}`. Applied the same fix to all remaining routes app-wide (latin, watch, organise, track, review, setplan, key, settings, bulk, setlist).
- **`session.json` read-only error** — `session_service.py` wrote `session.json` to the bundle root (read-only inside `.app`). Now writes to `~/Library/Application Support/IDJLM Pro/session.json` (macOS) / `~/.idjlm-pro/session.json` (other). Session persists across launches and survives app updates.

---

## [2.5.4] — 2026-04-05

### Bug Fixes
- **Taxonomy edits failing (settings save → 500)** — `PUT /api/taxonomy` tried to write `taxonomy.json` to the read-only `.app` bundle path. Now writes to `~/Library/Application Support/IDJLM Pro/taxonomy.json` (macOS). All three write sites fixed (full replace, add genre, delete genre). Taxonomy is also loaded from the user-writable copy on startup so edits persist across launches.
- **`/api/analyze` and `/api/session/save` crash with empty body (500)** — `request.get_json()` without `silent=True` raised `BadRequest` when the body was empty or Content-Type missing. Fixed in `import_routes.py` and `session_routes.py`.

### Feature
- **Bulk Analyse selected tracks** — When tracks are selected via checkboxes, an "Analyse" button now appears in the bulk-actions bar. Only the selected tracks are sent to `/api/analyze`, with progress shown in the stats bar. Previously, only "Analyse All" was available.

---

## [2.5.3] — 2026-04-05

### Bug Fixes
- **Audio preview "Could not load audio"** — Two fixes: (1) `play()` was called before the audio buffer was ready; now waits for `canplay` event. (2) Audio route only allowed `.mp3` — now supports FLAC, WAV, M4A, AAC, OGG too. An `error` event handler shows a specific message if the file can't load at all.
- **Set Planner / Organise dropdowns too small** — Those tabs use `class="input"` but CSS only defined `.input-text` / `.input-select`. Added `.input` to the shared selector so font, height, padding and border match the rest of the app.
- **Settings loaded from wrong path on startup** — `run_app.py` loaded `.env` from the bundle path at startup, ignoring the user-directory settings file we fixed in v2.5.1. Now loads from `~/Library/Application Support/IDJLM Pro/.env` first.
- **No log file** — Errors from the bundled app were invisible. Now writes to `~/Library/Logs/IDJLM Pro/idjlm.log` (macOS) / `~/.idjlm-pro/logs/idjlm.log` (other). Rotating, max 2 MB × 3 backups.

---

## [2.5.2] — 2026-04-05

### Bug Fixes
- **Genre not shown before AI classification** — `final_genre` now falls back to the file's existing genre tag (`existing_genre`). Tracks with genres already tagged in their files now show them immediately after import, before AI runs.
- **Wave column removed** — The "Wave" column showed waveform thumbnails only after audio analysis (librosa). Before analysis it always showed `—`. Removed entirely — it added visual noise without value at the typical workflow stage.

### Improvements
- **Set Planner arc button font** — Arc type buttons (Warm-Up, Peak Hour, etc.) now use the same 14px font as other form controls instead of the slightly-smaller 0.82rem.

---

## [2.5.1] — 2026-04-05

### Bug Fixes
- **Settings lost on every launch (DMG)** — Settings were saved to `.env` at a path relative to the app bundle. When launched directly from a mounted DMG (read-only filesystem), writes failed silently and all settings were gone on next open. Settings now stored in `~/Library/Application Support/IDJLM Pro/.env` (macOS) or `~/.idjlm-pro/.env` (other platforms) — a user-writable location that persists across DMG launches, app updates, and reinstalls. Existing settings are migrated automatically on first launch.

---

## [2.5.0] — 2026-04-05

### Bug Fixes
- **Organise tab crash** — `initOrganiseTab()` was called from `switchTab()` but never defined, causing `ReferenceError` every time the Organise tab was clicked. Now defined; wires all buttons (health refresh, parse filenames, organise preview/run, key validator, duplicate scan) and triggers a health load on first visit.
- **Set Planner tab crash** — Same issue: `initSetPlanTab()` was called but never defined. Now defined; loads arc options, populates genre filter from taxonomy, and wires the Generate Set button.
- **Bulk edit modal buttons dead** — Save / Cancel / × buttons on the bulk-edit modal had no event listeners. Wired in `initBulkSelectFeature()`.
- **Bulk edit ID mismatch** — `handleBulkEdit()` read from `bulk-edit-genre/subgenre/bpm/year` but the HTML modal uses `bulk-genre/subgenre/bpm/year`. Fixed all four IDs.
- **Bulk edit genre select empty** — `showBulkEditModal()` now populates the genre `<select>` from `window.taxonomy` before opening.
- **Setlist never rendered** — `renderSetlist()` used wrong container IDs (`setlist-current-tracks` → `setlist-tracks`; `setlist-suggestions` → `setlist-suggestions-container`). Fixed. Empty-state / main-panel show/hide now works correctly using the static HTML elements.
- **Setlist footer overwritten** — `renderSetlist()` was dynamically replacing footer innerHTML, destroying the static Export M3U button. Now updates only `setlist-count` and `setlist-duration` span text.
- **`initSetlistTab()` silently bailed** — Was checking for the wrong container IDs (same mismatch), always returned early. Fixed and now called from `DOMContentLoaded`.
- **Export modal never wired** — `btn-export-csv/json/rekordbox` had no event listeners. Wired in `initBulkSelectFeature()` alongside the close button. Export modal can now be opened via the new "Export" button in the bulk-action bar.

### Improvements
- **Export button in bulk-action bar** — Selecting tracks and clicking "Export" now opens the Export Library modal (CSV / JSON / Rekordbox XML).
- **M3U export in setlist panel** — "Export M3U" button in the Set Planner setlist section now POSTs selected paths and triggers a download.

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
