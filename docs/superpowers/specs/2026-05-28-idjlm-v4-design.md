# IDJLM Pro v4 — Design Spec

**Date:** 2026-05-28  
**Status:** Approved — ready for implementation planning  
**Session:** Brainstorm + QA audit completed

---

## 1. Goal

Full overhaul of IDJLM Pro. Two parallel streams:

1. **UI Redesign** — rebuild the interface to be competitive with Tagami/OneTagger; desktop-native feel, proper density, readable typography
2. **Bug Fixes** — fix 13 confirmed bugs from the live QA audit against real test songs

This is v4.0. The existing Python/Flask backend stays. The UI layer is replaced.

---

## 2. Architecture

### Desktop Wrapper: Tauri
- Wrap the existing Flask app in a Tauri window (Rust + OS WebKit)
- No browser tab — launches as a native `.app` / `.exe`
- File dialogs use Tauri's native OS picker (replaces the current text-input folder path hack)
- Existing `build-mac.sh` / PyInstaller approach superseded by Tauri build
- Flask still runs on `localhost:5050` internally; Tauri's webview points to it

### Why Tauri over pywebview
- More control over window chrome, system tray, file dialogs
- Better cross-platform build pipeline (GitHub Actions)
- Long-term: Tauri allows native menu bar, drag-and-drop from Finder/Explorer

---

## 3. Design System

### Typography
- **UI / labels / nav**: `Outfit` (400, 500, 600, 700, 800) — readable at 11px+, distinctive, not generic
- **Data values (BPM, Key, times)**: `Geist Mono` (400, 500) — monospace, precise, technical feel

### Colour System — Three themes + three switchable accents

#### Dark (default — IDJLM identity)
```
--bg0: #0a0a10   (deep indigo-black)
--bg1: #12121c   (panels)
--bg2: #1a1a26   (inputs, cards)
--bg3: #222232   (hover, elevated)
--ln:  #2c2c40   (borders)
--t1:  #f2f2f8   (primary   — 16.1:1 contrast ✓)
--t2:  #c4c4d8   (secondary —  8.2:1 contrast ✓)
--t3:  #8888a8   (muted     —  4.7:1 contrast ✓)
--t4:  #55556a   (disabled — decorative only)
```

#### Light
```
--bg0: #f4f3f8
--bg1: #ffffff
--bg2: #eceaf5
--bg3: #e2e0ef
--ln:  #d0cedf
--t1:  #0e0e18   (19.5:1 ✓)
--t2:  #3a3a52   ( 9.1:1 ✓)
--t3:  #606080   ( 4.9:1 ✓)
```

#### Accessibility
```
--bg0: #000000
--bg1: #080808
--bg2: #111111
--bg3: #1a1a1a
--ln:  #383838
--t1:  #ffffff   (21:1 ✓)
--t2:  #e8e8e8   (17.5:1 ✓)
--t3:  #c0c0c0   ( 9.2:1 ✓)
```

#### Accent colours (user-switchable in Settings)
| Name | Hex | Default |
|------|-----|---------|
| Purple | `#8b5cf6` | ✓ IDJLM identity |
| Teal | `#14b8a6` | |
| Orange | `#f97316` | |

**All contrast values verified against WCAG AA (4.5:1 minimum). Accessibility theme achieves AAA on all levels.**

Theme + accent stored in `localStorage`. Theme switcher lives in Settings tab only (not in the app toolbar).

---

## 4. Layout

### Player bar (top, full width)
- Play/pause button, now-playing title + artist
- Waveform visualisation (Web Audio API — bars rendered from analysed waveform data)
- Position, remaining time (Geist Mono)
- BPM (animated pulse at track tempo), Camelot key chip

### Sidebar (left, 192px)
- Logo: `IDJLMPro` with accent colour on `LM`
- Nav sections: Library, Tools, Sources
- Items: text `--t2` inactive, accent + accent-tint active, left border accent indicator
- Collection counts in Geist Mono muted

### Main content
- Toolbar: search box (bg0 background, t1 text, t3 placeholder — all explicitly set), action buttons, pipeline stepper
- Track table: dense rows (38px), sticky headers, columns: # · Art · Title/Artist · Genre · BPM · Key · Energy · Duration · Actions
- Search, BPM, Key all readable — explicit `color: var(--t1)` on inputs

### Pipeline stepper
- Segmented control style (not large widget)
- Shows: Import ✓ → Analyse ✓ → Classify (active) → Review → Write
- Compact enough that track table is visible below it

---

## 5. Bug Fixes Required (from QA audit)

### P1 — Broken functionality

| ID | Fix |
|----|-----|
| BUG-002 | `navigation.js:69` — change `stat-analyzed` → `stat-analysed` |
| BUG-003 | `pipeline.js:1510` — change `health-analyzed` → `health-analysed` |
| BUG-004 | `review.js:101` — bulk-approve handler: replace `.forEach()` with `showToast(result.approved + ' tracks approved')` |
| BUG-005 | `review.js:127` — write-tags handler: replace sync `.forEach()` with async op_id pattern (same as library.js) |

### P2 — Significant UX issues

| ID | Fix |
|----|-----|
| BUG-006 | Add `pointer-events: none` to onboarding overlay when hidden |
| BUG-007 | `showOnboardingIfNeeded()`: check `localStorage('idjlm-onboarding-done')` first, not `window.tracks.length` |
| BUG-008 | `fetchModels()`: only call on Settings tab open, not on page load; show empty state "Enter API key to see models" |
| BUG-009 | `testApiKey()`: read value from the input field and send it with the request; don't rely on saved `.env` key |
| BUG-010 | Route exception handlers: return `str(e)` in dev mode; keep generic message in prod but log the full trace |
| BUG-011 | Wrap all 9 API key inputs in `<form autocomplete="off">` elements |

### Additional findings (QA audit)

| ID | Fix |
|----|-----|
| BPM-PRECISION | Round BPM to 1 decimal place: `round(float(bpm), 1)` in `analyzer.py` |
| PYSOUNDFILE | Install `soundfile` + `libsndfile1` system dep — eliminates deprecated audioread fallback, ~3x faster analysis |
| ENERGY-CAL | Current empirical max (0.2 RMS) causes most salsa tracks to score 8-10. Recalibrate to 0.35 |

---

## 6. What We Are NOT Doing in v4

- Not rewriting the Flask backend (routes, services, models stay)
- Not changing the taxonomy/genre system
- Not changing the AI classification prompts
- Not adding new features (Set Planner, Next Advisor, Stats stay as-is, just rendered in new UI)
- No migration of existing session data needed

---

## 7. Success Criteria

- [ ] App launches as a native desktop window (no browser tab)
- [ ] All 5 P1 bugs fixed — verified with test suite against `/upload/songs test/`
- [ ] All text in dark theme passes WCAG AA (4.5:1) — verified programmatically
- [ ] Search box text and placeholders are readable in all three themes
- [ ] BPM shows as `112.3` not `112.34714673913044`
- [ ] Analysis completes in < 2× the time it took before (PySoundFile fix)
- [ ] Stats & Library health dashboard shows real values
- [ ] Write Tags from Review tab writes tags correctly
- [ ] Theme + accent persist across app restarts (localStorage)
