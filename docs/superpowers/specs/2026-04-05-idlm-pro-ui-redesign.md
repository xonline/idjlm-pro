# IDLM Pro — UI Redesign Spec

**Date:** 2026-04-05  
**Status:** Approved  
**Version target:** 2.4.0

---

## Problem

The current UI has 11 tabs. The core workflow (Import → Analyze → Classify → Review → Write Tags) is split across multiple tabs, forcing the user to navigate back and forth just to do one thing. A first-time user has no idea where to start.

---

## Solution

**Option A — Single Library View.** Import controls and pipeline buttons move into a toolbar above the track table. Everything happens on one screen. The sidebar shrinks to 4 items.

---

## Navigation Structure

### Sidebar (4 items)

| Item | Contents |
|------|----------|
| **Library** | Main screen — folder import, pipeline, track table |
| **Organise** | Health dashboard, filename→tag parser, folder auto-organiser, key validator |
| **Set Planner** | Energy arc builder, M3U export |
| **Settings** | API keys, taxonomy editor, preferences, batch size, auto-approve threshold |

**Removed tabs:** Import, Review, Stats, Taxonomy (all collapsed into Library or Settings).

---

## Library Screen Layout

```
┌────────────────────────────────────────────────────────────────┐
│ TOOLBAR                                                         │
│  📁 /Music/Latin  [Change]   [▶ Analyze All] [✦ Classify All] [✎ Write Tags] │
├────────────────────────────────────────────────────────────────┤
│ STATS BAR (inline, always visible)                              │
│  847 tracks  •  509 analyzed  •  312 classified  •  48 approved │
│  [▓▓▓▓▓▓░░░░] 60%  (progress bar, visible only during active run) │
├────────────────────────────────────────────────────────────────┤
│ FILTERS                                                         │
│  Search...           Genre ▾    Status ▾    Sort ▾             │
├────────────────────────────────────────────────────────────────┤
│ TRACK TABLE                                                     │
│  ▶  La Vida Es Un Carnaval  │ Celia Cruz  │ Salsa   │ 8B 128bpm │ ✓ │ … │
│  ▶  Obsesión                │ Aventura    │ Bachata  │ 2A 126bpm │ ✓ │ … │
│     Bemba Colorá            │ Celia Cruz  │ pending  │  —        │   │ … │
└────────────────────────────────────────────────────────────────┘
```

### Toolbar

- Folder path display + **Change** button (opens folder input)
- On first load with no session: prompt "Pick a folder to get started"
- **Analyze All** — runs audio analysis (BPM, key, energy, waveform) on unanalyzed tracks
- **Classify All** — runs AI classification on unclassified tracks  
- **Write Tags** — writes approved tags to ID3 for all approved tracks
- Buttons are disabled/greyed when pipeline step isn't applicable (e.g. Classify All disabled if nothing is analyzed yet)

### Stats Bar

Always visible. Shows: total tracks, analyzed count, classified count, approved count.  
During an active pipeline run: shows a progress bar inline (slim, 4px) + "509 / 847 analyzing…" text. Disappears when idle.

### Track Table

Columns: Play | Title | Artist | Genre (badge) | BPM/Key | Approve | Actions (…)

- **Play button** (▶) — inline audio preview, one track at a time
- **Genre badge** — shows `proposed_genre` if classified, "pending" if not
- **Approve checkbox** — tick to approve AI classification; this is the inline review (no separate Review tab)
- **Actions (…)** — opens edit modal for full metadata editing, Camelot wheel, cue points

### Approve Flow (inline)

No separate Review tab. Each row has a checkmark column:
- Unclassified: empty, greyed out
- Classified, unapproved: pulsing dot (needs attention)
- Approved: green tick
- Skipped: grey dash

Bulk approve: "Approve all ≥ 80% confidence" button in the toolbar (appears after classification runs).

---

## Import Flow

1. User clicks **Change** (or sees the "Pick a folder" prompt on first load)
2. Folder path input appears in-place in the toolbar
3. User enters path → clicks **Import** (or hits Enter)
4. Tracks populate in the table immediately as they're scanned
5. Toast: "847 tracks imported — click Analyze All to extract BPM & key"
6. Session auto-saved

No separate Import tab. No page navigation required.

---

## Organise Screen

Unchanged functionally. Just moves from a tab to a sidebar item. Contains:
- Library health dashboard (coverage bars)
- Filename → tag parser
- Folder auto-organiser
- Key accuracy validator

---

## Settings Screen

Merges the old Settings + Taxonomy tabs:
- **API Keys** section — Anthropic, Spotify
- **Taxonomy** section — genre/sub-genre editor (was its own tab)
- **Processing** section — batch size, auto-approve threshold, AI model selector

---

## Files to Change

| File | Change |
|------|--------|
| `templates/index.html` | Restructure: remove Import/Review/Stats/Taxonomy tabs; add toolbar + stats bar to Library; sidebar to 4 items |
| `app/static/app.js` | Merge import logic into toolbar; inline approve logic in track rows; remove tab-switch code for removed tabs; fold taxonomy editor into Settings section |
| `app/static/style.css` | Toolbar styles; stats bar; progress bar; inline approve column; sidebar 4-item layout |

No backend changes required — all routes remain the same.

---

## Success Criteria

1. User opens app → sees track table (or "pick a folder" prompt) immediately, no tab navigation needed
2. Full workflow (import → analyze → classify → approve → write) completable without leaving the Library screen
3. Sidebar has exactly 4 items
4. Audio preview still works inline
5. Edit modal still accessible via Actions (…) per row
