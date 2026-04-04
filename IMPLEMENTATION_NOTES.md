# Implementation Notes — IDLM Pro Features

## Quick Reference for Developers

### Files Modified
1. **templates/index.html** — Added 6 new sections and Chart.js CDN
2. **app/static/app.js** — Added 1500+ lines of feature code
3. **app/static/style.css** — Added 250+ lines of CSS styling

### Key Global Variables Added
```javascript
let currentAudioPlayer = null;        // Audio player element reference
let isWatching = false;               // Folder watch state
let watchPollInterval = null;         // Watch polling timer
let chartInstances = {                // Chart.js instances (destroyed/recreated)
  genres: null,
  bpm: null,
  years: null,
};
```

### Critical Dependencies
- **Chart.js** (via CDN) — Required for stats charts to render
- All features use existing dark theme colors
- No external libraries added (pure vanilla JS except Chart.js)

---

## Feature Details & Implementation

### 1. Stats Tab
**Files:** HTML tab section + JS rendering functions + CSS grid/cards

**Key Functions:**
- `initStatsTab()` — Attaches click listener to stats nav button
- `renderStats()` — Entry point, called when tab activated
- `renderGenreChart()` — Horizontal bar chart
- `renderBpmChart()` — BPM range distribution
- `renderYearChart()` — Decade breakdown
- `renderSubgenreList()` — Top 10 subgenres

**Important:** Charts are DESTROYED before recreation on each tab switch to prevent memory leaks.

---

### 2. Camelot Wheel
**Files:** SVG container in modal + JS wheel generator

**Key Functions:**
- `createCamelotWheel(keyStr)` — SVG generator using Math for positioning
- `isCompatibleKey(key1, key2)` — Calculates harmonic compatibility

**Color Logic:**
- Current key: Purple (#8b5cf6)
- Compatible keys (adjacent): Green (#34d399)  
- Other keys: Dim gray (#888)

**Camelot Mapping:** Full 24-position map (1A–12B) included in `CAMELOT_MAP` constant.

---

### 3. Audio Player
**Files:** Hidden audio element + inline UI in review cards + play control logic

**Key Functions:**
- `toggleAudioPlay(btn, filePath)` — Handles play/pause/seek logic
- Single audio player reused across all tracks
- Progress bar click for seeking

**Audio Source:** `/api/audio/<path:file_path>` (URL-encoded file path)

**State:** Button shows ▶ (paused) or ⏸ (playing)

---

### 4. Session Save/Resume
**Files:** Resume banner + session buttons + helper functions

**Key Functions:**
- `checkPreviousSession()` — Called on page load
- `initImportTab()` — Enhanced with session listeners

**API Calls:**
- `GET /api/session/exists` — Check on load
- `POST /api/session/save` — User clicks "Save Session"
- `POST /api/session/load` — User clicks "Resume"

**Banner Display:** Auto-shows if session exists, can be dismissed

---

### 5. Folder Watcher
**Files:** Toggle button + status text + polling logic

**Key Functions:**
- Enhanced `initImportTab()` — Sets up watcher button listeners
- `pollFolderWatch()` — Runs every 5 seconds via `setInterval`

**API Calls:**
- `POST /api/watch/start` — Enable watching
- `POST /api/watch/stop` — Disable watching
- `GET /api/watch/poll` — Check for new tracks

**State:** `isWatching` boolean + `watchPollInterval` timer ID

**UI Updates:** Status text shows folder path when active, empty when off

---

### 6. M3U Export
**Files:** Dropdown menu in review footer + genre selector modal

**Key Functions:**
- Enhanced `initReviewTab()` — Sets up dropdown listeners
- `showGenreSelector()` — Creates modal dynamically (not in HTML)

**Dropdown:**
- Toggle shows/hides menu on button click
- Closes on outside click
- Two options: "Export All" and "Export by Genre"

**Genre Selector Modal:**
- Dynamically created (not pre-loaded in HTML)
- Gets genres from approved tracks only
- Modal created with `createElement` and `appendChild`

**API Calls:**
- `GET /api/export/m3u?status=approved` — All tracks
- `GET /api/export/m3u?genre=X&status=approved` — By genre
- File download via `window.location` assignment

---

## Styling Consistency

All new components use existing dark theme:
- Background: `#0f0f13`, `#1a1a24`
- Borders: `#2a2a3a`
- Text: `#e0e0e0` (light), `#888` (dim)
- Purple accent: `#8b5cf6`
- Green success: `#34d399`
- Amber warning: `#fbbf24`
- Red error: `#f87171`

No inline styles used (all in CSS classes) except minimal positioning for modals.

---

## Testing Recommendations

### Stats Tab
```javascript
// In browser console:
window.tracks = [{final_genre: 'House', final_bpm: 125, final_year: 2020, final_subgenre: 'Tech House', review_status: 'approved'}, ...];
switchTab('stats');
renderStats();
```

### Camelot Wheel
- Open any track in edit modal
- Check SVG renders correctly
- Verify key highlighting in purple
- Confirm adjacent keys show in green

### Audio Player
- Click play button on review item
- Verify audio loads from `/api/audio/...`
- Test progress bar click to seek
- Check play/pause icon updates

### Session/Watcher
- Mock API responses with network dev tools
- Test banner display logic
- Verify polling interval starts/stops
- Check toast notifications on new tracks

### Export
- Verify dropdown opens/closes
- Test both export options
- Check genre selector modal creation
- Confirm file download triggers

---

## Common Pitfalls & Solutions

### Charts Not Rendering
**Issue:** Chart.js CDN not loaded
**Solution:** Ensure `<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>` is before app.js

### Audio Player Issues
**Issue:** Audio won't play (CORS error)
**Solution:** Backend must set proper CORS headers for `/api/audio/` endpoint

### Memory Leaks in Stats
**Issue:** Charts accumulate and crash
**Solution:** Ensured `chartInstances[key].destroy()` before creating new instance

### Watch Polling Never Stops
**Issue:** `watchPollInterval` not cleared on stop
**Solution:** Verified `clearInterval(watchPollInterval)` and set to `null`

### Export Modal Not Closing
**Issue:** Modal stays visible after export
**Solution:** Added `modal.remove()` after file download

---

## Future Enhancements

1. **Keyboard shortcuts** — Add hotkeys for play/pause, export, approve
2. **Playlist preview** — Show selected M3U contents before download
3. **Chart animations** — Add transitions on chart update
4. **Watcher notifications** — Visual badge with count of new tracks
5. **Session versioning** — Save multiple session snapshots
6. **Camelot recommendations** — Suggest next track based on key compatibility

---

## API Response Shapes (Reference)

All backend endpoints must return exact JSON structures:

```javascript
// Session exists
{ exists: true, track_count: 45, saved_at: "2026-04-04T10:30:00", folder_path: "/path/to/folder" }

// Session save
{ saved: true, path: "/path/to/folder", track_count: 45 }

// Session load
{ loaded: true, count: 45, tracks: [{...}, {...}] }

// Watch start
{ watching: true, folder: "/path/to/folder" }

// Watch stop
{ watching: false }

// Watch poll
{ tracks: [{...}, {...}] }  // Empty array if no new tracks
```

---

## Code Quality Notes

- All functions are modular and single-purpose
- No function does more than ~50 lines (except chart configs)
- Event listeners use arrow functions where appropriate
- DOM queries cached in function scope
- Error handling via existing `showToast()` and `showSpinner()`
- Follows existing code style (2-space indent, camelCase, descriptive names)
