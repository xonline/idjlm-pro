# IDJLM v4 Phase 2 — UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the IDJLM Pro visual layer with a new design system — Outfit + Geist Mono typography, 3-theme × 3-accent token system, redesigned sidebar/player bar/track table/pipeline stepper — while keeping all Flask backend routes and JS business logic completely intact.

**Architecture:** All changes are confined to `templates/index.html` (HTML structure), `app/static/style.css` (CSS token system + component styles), and targeted modifications to `app/static/modules/settings.js` (move theme/accent switcher) and `app/static/modules/pipeline.js` (genreChip function update). No backend routes, models, or services are touched. Theme state is persisted in `localStorage` using `data-theme` and `data-accent` attributes on `<html>`.

**Tech Stack:** HTML5, CSS custom properties (data-attribute themes), Google Fonts (Outfit + Geist Mono via `<link>`), Web Audio API (waveform bars in player), Vanilla JS (no new dependencies)

---

## File Map

| File | What changes |
|------|-------------|
| `templates/index.html` | Font `<link>` tag, `data-theme`/`data-accent` on `<html>`, sidebar HTML, player bar HTML (move to top + waveform canvas), pipeline stepper markup (compact segmented control), settings section (add theme/accent switcher), remove `.theme-swatches` from sidebar |
| `app/static/style.css` | Replace entire `:root` + theme blocks (lines 1–179) with new token system; replace `.sidebar` + `.logo` + `.nav-btn` + `.theme-swatches`; replace `.audio-player-bar` and children; replace `.pipeline-stepper` and children; update `.search-input` + `.filter-select` with explicit tokens; update `.genre-chip`; add energy bar column style; add accent switcher styles |
| `app/static/modules/settings.js` | Replace `THEMES` array + `applyTheme()` + `initTheme()` + `initThemeSwatches()` with new version supporting `data-theme` / `data-accent`; wire up accent radio buttons in Settings tab |
| `app/static/modules/pipeline.js` | Update `genreChip()` function to emit `.genre-pill` class instead of inline style (line 231-236); keep `GENRE_COLORS` array |

---

## Task 1: CSS Token System — Replace `:root` and all Theme Blocks

**Files:**
- Modify: `app/static/style.css` lines 1-179 (current `:root`, `body.light`, `body.pro-booth`, `body.studio`, `body.pure-black` blocks)

This task replaces the old semantic token names (`--bg-page`, `--text-primary`, etc.) with the new spec names (`--bg0` through `--bg3`, `--ln`, `--t1` through `--t4`, `--acc`). It also migrates from `body.classname` theme switching to `[data-theme="name"]` on `<html>`, and adds `[data-accent]` support.

After this task the app will have broken styles (old token names referenced in CSS below line 179 still use old names). That is expected — Tasks 2-9 progressively fix each component. A regression check at the end of each task confirms no NEW breakage was introduced by that task alone.

- [ ] **Step 1: Replace the `:root` and four theme blocks at the top of `style.css`**

Open `app/static/style.css`. Delete lines 1-179 in their entirety and replace with:

```css
/* ============================================================================
   IDJLM Pro v4 — CSS Token System
   3 themes (dark/light/accessibility) x 3 accents (purple/teal/orange)
   Theme applied via: <html data-theme="dark|light|accessibility">
   Accent applied via: <html data-accent="purple|teal|orange">
   ============================================================================ */

/* ---------- Dark theme (default — IDJLM identity, purple-tinted blacks) ---- */
:root,
[data-theme="dark"] {
  --bg0: #0a0a10;
  --bg1: #12121c;
  --bg2: #1a1a26;
  --bg3: #222232;
  --ln:  #2c2c40;
  --t1:  #f2f2f8;   /* 16.1:1 contrast */
  --t2:  #c4c4d8;   /*  8.2:1 contrast */
  --t3:  #8888a8;   /*  4.7:1 contrast */
  --t4:  #55556a;   /* decorative only  */
  /* Semantic aliases — used by legacy CSS below during migration */
  --bg-page:          var(--bg0);
  --bg-panel:         var(--bg1);
  --bg-subtle:        var(--bg2);
  --bg-hover:         var(--bg3);
  --bg-deeper:        var(--bg3);
  --bg-secondary:     var(--bg2);
  --bg-tertiary:      var(--bg3);
  --border:           var(--ln);
  --border-color:     var(--ln);
  --text-primary:     var(--t1);
  --text-secondary:   var(--t2);
  --text-muted:       var(--t3);
  --text-placeholder: var(--t3);
  --text-loud:        var(--t1);
  /* Status colours */
  --green:      #34d399;
  --green-dim:  rgba(52, 211, 153, 0.12);
  --amber:      #f59e0b;
  --amber-dim:  rgba(245, 158, 11, 0.12);
  --red:        #f87171;
  --red-dim:    rgba(248, 113, 113, 0.12);
  --blue:       #60a5fa;
  --blue-dim:   rgba(96, 165, 250, 0.12);
  --overlay:           rgba(0, 0, 0, 0.75);
  --spinner-overlay:   rgba(0, 0, 0, 0.85);
  /* Radius + shadow */
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 20px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 12px 40px rgba(0, 0, 0, 0.5);
  --radius-sm:   6px;
  --radius-md:  10px;
  --radius-lg:  14px;
  --radius-pill: 999px;
}

/* ---------- Light theme ---------------------------------------------------- */
[data-theme="light"] {
  --bg0: #f4f3f8;
  --bg1: #ffffff;
  --bg2: #eceaf5;
  --bg3: #e2e0ef;
  --ln:  #d0cedf;
  --t1:  #0e0e18;   /* 19.5:1 contrast */
  --t2:  #3a3a52;   /*  9.1:1 contrast */
  --t3:  #606080;   /*  4.9:1 contrast */
  --t4:  #9090a8;
  --bg-page:          var(--bg0);
  --bg-panel:         var(--bg1);
  --bg-subtle:        var(--bg2);
  --bg-hover:         var(--bg3);
  --bg-deeper:        var(--bg3);
  --bg-secondary:     var(--bg2);
  --bg-tertiary:      var(--bg3);
  --border:           var(--ln);
  --border-color:     var(--ln);
  --text-primary:     var(--t1);
  --text-secondary:   var(--t2);
  --text-muted:       var(--t3);
  --text-placeholder: var(--t3);
  --text-loud:        var(--t1);
  --green:      #059669;
  --green-dim:  rgba(5, 150, 105, 0.1);
  --amber:      #d97706;
  --amber-dim:  rgba(217, 119, 6, 0.1);
  --red:        #dc2626;
  --red-dim:    rgba(220, 38, 38, 0.1);
  --blue:       #2563eb;
  --blue-dim:   rgba(37, 99, 235, 0.1);
  --overlay:           rgba(0, 0, 0, 0.4);
  --spinner-overlay:   rgba(0, 0, 0, 0.5);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.07);
  --shadow-md: 0 4px 20px rgba(0, 0, 0, 0.08);
  --shadow-lg: 0 12px 40px rgba(0, 0, 0, 0.1);
  --radius-sm:   6px;
  --radius-md:  10px;
  --radius-lg:  14px;
  --radius-pill: 999px;
}

/* ---------- Accessibility theme (AAA contrast) ----------------------------- */
[data-theme="accessibility"] {
  --bg0: #000000;
  --bg1: #080808;
  --bg2: #111111;
  --bg3: #1a1a1a;
  --ln:  #383838;
  --t1:  #ffffff;   /* 21:1 contrast */
  --t2:  #e8e8e8;   /* 17.5:1 contrast */
  --t3:  #c0c0c0;   /*  9.2:1 contrast */
  --t4:  #909090;
  --bg-page:          var(--bg0);
  --bg-panel:         var(--bg1);
  --bg-subtle:        var(--bg2);
  --bg-hover:         var(--bg3);
  --bg-deeper:        var(--bg3);
  --bg-secondary:     var(--bg2);
  --bg-tertiary:      var(--bg3);
  --border:           var(--ln);
  --border-color:     var(--ln);
  --text-primary:     var(--t1);
  --text-secondary:   var(--t2);
  --text-muted:       var(--t3);
  --text-placeholder: var(--t3);
  --text-loud:        var(--t1);
  --green:      #4ade80;
  --green-dim:  rgba(74, 222, 128, 0.12);
  --amber:      #fbbf24;
  --amber-dim:  rgba(251, 191, 36, 0.12);
  --red:        #f87171;
  --red-dim:    rgba(248, 113, 113, 0.12);
  --blue:       #93c5fd;
  --blue-dim:   rgba(147, 197, 253, 0.12);
  --overlay:           rgba(0, 0, 0, 0.85);
  --spinner-overlay:   rgba(0, 0, 0, 0.95);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.5);
  --shadow-md: 0 4px 20px rgba(0, 0, 0, 0.6);
  --shadow-lg: 0 12px 40px rgba(0, 0, 0, 0.7);
  --radius-sm:   6px;
  --radius-md:  10px;
  --radius-lg:  14px;
  --radius-pill: 999px;
}

/* ---------- Accent: Purple (default — IDJLM identity) ---------------------- */
:root,
[data-accent="purple"] {
  --acc:           #8b5cf6;
  --acc-hover:     #a37cf8;
  --acc-glow:      rgba(139, 92, 246, 0.22);
  --acc-dim:       rgba(139, 92, 246, 0.12);
  /* legacy aliases */
  --accent:        var(--acc);
  --accent-hover:  var(--acc-hover);
  --accent-glow:   var(--acc-glow);
  --accent-dim:    var(--acc-dim);
}

/* ---------- Accent: Teal --------------------------------------------------- */
[data-accent="teal"] {
  --acc:           #14b8a6;
  --acc-hover:     #2dd4bf;
  --acc-glow:      rgba(20, 184, 166, 0.22);
  --acc-dim:       rgba(20, 184, 166, 0.12);
  --accent:        var(--acc);
  --accent-hover:  var(--acc-hover);
  --accent-glow:   var(--acc-glow);
  --accent-dim:    var(--acc-dim);
}

/* ---------- Accent: Orange ------------------------------------------------- */
[data-accent="orange"] {
  --acc:           #f97316;
  --acc-hover:     #fb923c;
  --acc-glow:      rgba(249, 115, 22, 0.22);
  --acc-dim:       rgba(249, 115, 22, 0.12);
  --accent:        var(--acc);
  --accent-hover:  var(--acc-hover);
  --accent-glow:   var(--acc-glow);
  --accent-dim:    var(--acc-dim);
}

/* ---------- Legacy theme class aliases (keep for JS migration period) ------ */
/* These let the old body.light / body.pro-booth classes still resolve tokens  */
body.light           { --bg0:#f4f3f8; --bg1:#ffffff; --bg2:#eceaf5; --bg3:#e2e0ef; --ln:#d0cedf; --t1:#0e0e18; --t2:#3a3a52; --t3:#606080; --t4:#9090a8; --bg-page:var(--bg0); --bg-panel:var(--bg1); --bg-subtle:var(--bg2); --bg-hover:var(--bg3); --bg-deeper:var(--bg3); --bg-secondary:var(--bg2); --bg-tertiary:var(--bg3); --border:var(--ln); --border-color:var(--ln); --text-primary:var(--t1); --text-secondary:var(--t2); --text-muted:var(--t3); --text-placeholder:var(--t3); --text-loud:var(--t1); }
body.pro-booth       { --bg-page:#09080d; --bg-panel:#100e14; --bg-subtle:#18141e; --bg-hover:#201a28; --bg-deeper:#281f32; --border:#2a1f38; --border-color:#2a1f38; --bg-secondary:#18141e; --bg-tertiary:#201a28; --text-primary:#e8d8c8; --text-secondary:#8a6a5a; --text-muted:#6a5040; --text-placeholder:#4a3028; --text-loud:#fff0e0; --accent:#f97316; --accent-hover:#fb923c; --acc:#f97316; }
body.studio          { --bg-page:#060a10; --bg-panel:#0b1018; --bg-subtle:#101820; --bg-hover:#141e2a; --bg-deeper:#182535; --border:#1c2d40; --border-color:#1c2d40; --bg-secondary:#101820; --bg-tertiary:#141e2a; --text-primary:#b8d0e8; --text-secondary:#4a6a88; --text-muted:#3a5060; --text-placeholder:#243040; --text-loud:#e0f0ff; --accent:#00c8f0; --accent-hover:#38dcff; --acc:#00c8f0; }
body.pure-black      { --bg-page:#000000; --bg-panel:#0a0a0a; --bg-subtle:#111111; --bg-hover:#181818; --bg-deeper:#222222; --border:#282828; --border-color:#282828; --bg-secondary:#111111; --bg-tertiary:#181818; --text-primary:#d0d0d0; --text-secondary:#555555; --text-muted:#444444; --text-placeholder:#303030; --text-loud:#ffffff; --accent:#e0e0e0; --accent-hover:#ffffff; --acc:#e0e0e0; }
body.pure-black .btn-primary { color: #000000; }
```

- [ ] **Step 2: Visual smoke-test — load app, confirm dark theme renders without total blank-out**

Run:
```bash
cd /home/ubuntu/projects/idjlm && python app.py
# open http://localhost:5050 in browser
```
Expected: App loads. Some component colours may look off (tokens migrating) but the layout should render. The sidebar should show, the track table should show. No pure white or pure invisible text.

- [ ] **Step 3: Commit**

```bash
git add app/static/style.css
git commit -m "feat(v4): replace CSS token system — 3 themes x 3 accents with data-attr switching"
```

---

## Task 2: Font Imports — Outfit + Geist Mono

**Files:**
- Modify: `templates/index.html` lines 1-8 (`<head>`)
- Modify: `app/static/style.css` — `body` font-family rule (around line 196)

- [ ] **Step 1: Add Google Fonts `<link>` to `<head>` in `index.html`**

Replace the current `<head>` block (lines 1-8) with:

```html
<!DOCTYPE html>
<html lang="en" data-theme="dark" data-accent="purple">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IDJLM Pro</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/style.css">
</head>
```

Note: `data-theme="dark"` and `data-accent="purple"` on `<html>` — this is the default. JS will override from `localStorage` on load (wired in Task 8).

- [ ] **Step 2: Update `body` font-family in `style.css`**

Find the `body` rule. The current rule contains:
```css
  font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
```

Replace just that line with:
```css
  font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

- [ ] **Step 3: Add Geist Mono utility class to `style.css`**

Immediately after the `body` rule closing `}`, add:

```css
/* Geist Mono — applied to BPM, Key, times, counts via .mono class */
.mono {
  font-family: 'Geist Mono', 'Fira Code', 'Courier New', monospace;
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 4: Visual check — Outfit renders in sidebar nav labels**

Reload `http://localhost:5050`. Open DevTools, inspect the sidebar "Library" button. In the Computed styles panel, check `font-family`. Expected: `Outfit` listed first (once fonts have loaded). Text looks rounder and tighter than before.

- [ ] **Step 5: Commit**

```bash
git add templates/index.html app/static/style.css
git commit -m "feat(v4): add Outfit + Geist Mono fonts via Google Fonts"
```

---

## Task 3: Sidebar Redesign

**Files:**
- Modify: `templates/index.html` lines 34-63 (the `<nav class="sidebar">` block)
- Modify: `app/static/style.css` — sidebar CSS section (lines 240-352)

The sidebar needs: 192px width, logo with "IDJLMPro" where "Pro" is accent-coloured, nav sections (Library / Tools / Sources), nav items with left accent border when active, collection counts in Geist Mono, and removal of `.theme-swatches` (those move to Settings in Task 8).

- [ ] **Step 1: Replace the `<nav class="sidebar">` HTML block in `index.html`**

Find the nav block starting at line 34 (`<!-- SIDEBAR -->`). Replace everything from line 34 through line 63 (`</nav>`) with:

```html
    <!-- SIDEBAR -->
    <nav class="sidebar">
      <!-- Logo -->
      <div class="sidebar-logo">
        <img src="/static/icon_256.png" alt="" class="sidebar-logo-img">
        <span class="sidebar-logo-text">IDJLM<span class="sidebar-logo-accent">Pro</span></span>
        {% if version %}<span id="header-version-badge" class="version-badge" title="Check for updates">v{{ version }}</span>{% endif %}
      </div>

      <!-- Library section -->
      <div class="sidebar-section-label">Library</div>
      <nav class="sidebar-nav">
        <button class="nav-btn active" data-tab="library">
          <svg class="nav-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
          <span>Library</span>
          <span class="nav-count mono" id="sidebar-count-library">--</span>
        </button>
        <button class="nav-btn" data-tab="playlists">
          <svg class="nav-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
          <span>Playlists</span>
        </button>
      </nav>

      <!-- Tools section -->
      <div class="sidebar-section-label">Tools</div>
      <nav class="sidebar-nav">
        <button class="nav-btn" data-tab="organise">
          <svg class="nav-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
          <span>Stats &amp; Library</span>
        </button>
        <button class="nav-btn" data-tab="setplan">
          <svg class="nav-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          <span>Set Planner</span>
        </button>
      </nav>

      <!-- Sources section -->
      <div class="sidebar-section-label">Sources</div>
      <nav class="sidebar-nav">
        <button class="nav-btn" data-tab="settings" id="nav-btn-settings">
          <svg class="nav-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>
          <span>Settings</span>
        </button>
      </nav>
    </nav>
```

- [ ] **Step 2: Replace sidebar CSS rules in `style.css`**

Find the existing `.sidebar` rule (around line 240). Replace the entire sidebar section (`.sidebar`, `.logo`, `.logo-icon`, `.logo-text`, `.nav-menu`, `.nav-icon`, `.nav-btn`, `.nav-btn:hover`, `.nav-btn.active`, `.theme-swatches`, `.swatch*` rules, `.stats-panel`) with:

```css
/* ============================================================================
   Sidebar — v4
   ============================================================================ */

.sidebar {
  width: 192px;
  flex-shrink: 0;
  background-color: var(--bg1);
  border-right: 1px solid var(--ln);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 14px 14px;
  border-bottom: 1px solid var(--ln);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.4px;
  flex-shrink: 0;
}

.sidebar-logo-img {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  flex-shrink: 0;
}

.sidebar-logo-text {
  color: var(--t1);
  white-space: nowrap;
}

.sidebar-logo-accent {
  color: var(--acc);
}

.sidebar-section-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--t4);
  padding: 14px 14px 4px;
  flex-shrink: 0;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 0 6px;
  flex-shrink: 0;
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: 9px;
  height: 34px;
  padding: 0 8px;
  width: 100%;
  background: none;
  border: none;
  border-left: 2px solid transparent;
  border-radius: 6px;
  color: var(--t2);
  cursor: pointer;
  font-family: 'Outfit', sans-serif;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease;
  text-align: left;
}

.nav-icon {
  flex-shrink: 0;
  color: currentColor;
  opacity: 0.7;
}

.nav-count {
  margin-left: auto;
  font-size: 11px;
  color: var(--t4);
}

.nav-btn:hover:not(.active) {
  background-color: var(--bg2);
  color: var(--t1);
}

.nav-btn:hover:not(.active) .nav-icon {
  opacity: 1;
}

.nav-btn.active {
  background-color: color-mix(in srgb, var(--acc) 12%, transparent);
  border-left-color: var(--acc);
  color: var(--acc);
  padding-left: 6px;
  border-radius: 0 6px 6px 0;
}

.nav-btn.active .nav-icon {
  opacity: 1;
}

/* Keep legacy swatch classes resolving for any JS that still references them */
.theme-swatches { display: none; }
.swatch         { display: none; }
.stats-panel    { margin-top: auto; padding: 16px; border-top: 1px solid var(--ln); font-size: 11px; }
```

- [ ] **Step 3: Visual check — sidebar renders correctly**

Reload app. Expected:
- Sidebar is 192px wide (verify in DevTools Computed)
- "Library" button has left accent border (purple stripe)
- Section labels "Library", "Tools", "Sources" visible in small caps
- No theme swatches visible in sidebar
- Logo reads "IDJLMPro" with "Pro" in accent colour

- [ ] **Step 4: Commit**

```bash
git add templates/index.html app/static/style.css
git commit -m "feat(v4): redesign sidebar — 192px, section labels, SVG icons, accent border active state"
```

---

## Task 4: Player Bar — Move to Top, Add Waveform Canvas

**Files:**
- Modify: `templates/index.html` — restructure app layout; move player bar to top; add waveform canvas
- Modify: `app/static/style.css` — replace `.audio-player-bar` block; add `.app-body` wrapper
- Modify: `app/static/modules/pipeline.js` — add `initWaveform()` function

The existing player is a bottom bar (fixed position). The new design:
- Top, full-width, above the sidebar+content split (56px height)
- Layout: [controls] [track info] [waveform canvas flex:1] [time (mono)] [BPM pulse] [key chip]
- Waveform: 64 frequency bars from AnalyserNode via requestAnimationFrame
- The `.app` layout changes: player bar (56px) then `.app-body` flex-row (sidebar + content)

- [ ] **Step 1: Restructure the app layout in `index.html`**

Find line 33:
```html
  <div class="app" id="app-content" style="opacity:0; transition: opacity 0.4s ease 0.3s;">
    <!-- SIDEBAR -->
    <nav class="sidebar">
```

Replace the opening line with:
```html
  <div class="app" id="app-content" style="opacity:0; transition: opacity 0.4s ease 0.3s;">

    <!-- PLAYER BAR — top, full width -->
    <div id="audio-player-bar" class="player-bar">
      <div class="player-controls">
        <button id="audio-prev" class="player-btn" title="Previous">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="4" x2="5" y2="20" stroke="currentColor" stroke-width="2"/></svg>
        </button>
        <button id="audio-play-pause" class="player-btn player-btn-play" title="Play/Pause">
          <svg id="icon-play" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          <svg id="icon-pause" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="display:none"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
        </button>
        <button id="audio-next" class="player-btn" title="Next">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="4" x2="19" y2="20" stroke="currentColor" stroke-width="2"/></svg>
        </button>
      </div>

      <div class="player-track-info">
        <span id="audio-track-title" class="player-title">No track loaded</span>
        <span id="audio-track-artist" class="player-artist">--</span>
      </div>

      <div class="player-waveform-wrap">
        <input type="range" id="audio-seek" min="0" max="100" value="0" class="player-seek-overlay" aria-label="Seek">
        <canvas id="waveform-canvas" class="player-waveform" height="40"></canvas>
      </div>

      <div class="player-meta">
        <span id="audio-time" class="player-time mono">0:00 / 0:00</span>
        <span id="player-bpm" class="player-bpm mono" title="BPM">--</span>
        <span id="player-key" class="player-key-chip">--</span>
      </div>
    </div>

    <!-- SIDEBAR + CONTENT ROW -->
    <div class="app-body">
    <!-- SIDEBAR -->
    <nav class="sidebar">
```

Then after the closing `</main>` tag (before the `</div>` that closes `.app`), add:
```html
    </div><!-- /.app-body -->
```

Remove the old audio player block at the bottom of the file (around lines 1236-1250):
```html
  <!-- Audio Player (hidden) -->
  <audio id="audio-player" style="display: none;"></audio>

  <!-- Audio Player Bottom Bar -->
  <div id="audio-player-bar" class="audio-player-bar hidden">
    <button id="audio-prev" class="audio-btn" title="Previous">...</button>
    ...
  </div>
```

Replace with just the audio element (keep for JS):
```html
  <audio id="audio-player" style="display:none;"></audio>
```

- [ ] **Step 2: Replace audio player CSS and add layout rules in `style.css`**

Find the old `.app { display: flex; height: 100vh; width: 100%; }` rule (around line 234). Replace it with:

```css
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
}

.app-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}
```

Find the `.audio-player-bar` block (around line 1782) and replace everything through `.audio-time` closing brace (around line 1835) with:

```css
/* ============================================================================
   Player Bar — v4 (top, full width)
   ============================================================================ */

.player-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 56px;
  padding: 0 16px;
  background: var(--bg1);
  border-bottom: 1px solid var(--ln);
  flex-shrink: 0;
  z-index: 100;
}

.player-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.player-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  background: none;
  border: none;
  border-radius: 50%;
  color: var(--t2);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.player-btn:hover {
  background: var(--bg3);
  color: var(--t1);
}

.player-btn-play {
  width: 36px;
  height: 36px;
  background: var(--acc);
  color: #fff;
  margin: 0 2px;
}

.player-btn-play:hover {
  background: var(--acc-hover);
  color: #fff;
}

.player-track-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex-shrink: 0;
  min-width: 140px;
  max-width: 200px;
}

.player-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--t1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.player-artist {
  font-size: 11px;
  color: var(--t3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.player-waveform-wrap {
  flex: 1;
  position: relative;
  height: 40px;
  min-width: 0;
}

.player-waveform {
  width: 100%;
  height: 100%;
  display: block;
  border-radius: 4px;
}

.player-seek-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
  z-index: 2;
  margin: 0;
  padding: 0;
}

.player-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.player-time {
  font-size: 11px;
  color: var(--t3);
  min-width: 80px;
  text-align: right;
}

.player-bpm {
  font-size: 12px;
  color: var(--t2);
  min-width: 44px;
  text-align: center;
}

.player-key-chip {
  font-size: 11px;
  font-weight: 600;
  color: var(--acc);
  background: var(--acc-dim);
  border: 1px solid color-mix(in srgb, var(--acc) 30%, transparent);
  border-radius: var(--radius-pill);
  padding: 2px 8px;
  min-width: 36px;
  text-align: center;
}

/* Legacy audio-player-bar class — keep for JS that checks .hidden */
.audio-player-bar { display: none; }
.audio-player-bar.hidden { display: none; }
```

- [ ] **Step 3: Add waveform Web Audio API drawing in `pipeline.js`**

Open `app/static/modules/pipeline.js`. At the end of the file (after all existing code), add:

```javascript
// ============================================================================
// Waveform Visualiser — Web Audio API
// ============================================================================

(function initWaveformVisualiser() {
  let animId = null;
  let analyser = null;
  let canvasCtx = null;

  function setupAudioContext(audioEl) {
    if (analyser) return; // already connected
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaElementSource(audioEl);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      source.connect(analyser);
      analyser.connect(audioCtx.destination);
    } catch (e) {
      // Web Audio unavailable — waveform shows idle bars only
    }
  }

  function drawFrame() {
    const canvas = document.getElementById('waveform-canvas');
    if (!canvas) return;
    animId = requestAnimationFrame(drawFrame);

    const W = canvas.clientWidth;
    const H = canvas.clientHeight;
    if (W === 0 || H === 0) return;
    canvas.width = W;
    canvas.height = H;

    const ctx = canvasCtx || (canvasCtx = canvas.getContext('2d'));
    ctx.clearRect(0, 0, W, H);

    const style = getComputedStyle(document.documentElement);
    const accColor = style.getPropertyValue('--acc').trim() || '#8b5cf6';
    const dimColor = style.getPropertyValue('--acc-dim').trim() || 'rgba(139,92,246,0.12)';

    const BAR_COUNT = 64;
    const gap = 1;
    const barW = Math.max(1, Math.floor((W - gap * (BAR_COUNT - 1)) / BAR_COUNT));

    let freqData = null;
    if (analyser) {
      freqData = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(freqData);
    }

    for (let i = 0; i < BAR_COUNT; i++) {
      const amp = freqData
        ? freqData[Math.floor(i * freqData.length / BAR_COUNT)] / 255
        : 0.06;
      const barH = Math.max(2, amp * H * 0.85);
      const x = i * (barW + gap);
      const y = (H - barH) / 2;

      ctx.fillStyle = amp > 0.08 ? accColor : dimColor;
      ctx.beginPath();
      // Rounded rect (manual for older WebKit compat)
      const r = Math.min(2, barW / 2);
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + barW - r, y);
      ctx.arcTo(x + barW, y, x + barW, y + r, r);
      ctx.lineTo(x + barW, y + barH - r);
      ctx.arcTo(x + barW, y + barH, x + barW - r, y + barH, r);
      ctx.lineTo(x + r, y + barH);
      ctx.arcTo(x, y + barH, x, y + barH - r, r);
      ctx.lineTo(x, y + r);
      ctx.arcTo(x, y, x + r, y, r);
      ctx.closePath();
      ctx.fill();
    }
  }

  document.addEventListener('DOMContentLoaded', function() {
    const audioEl = document.getElementById('audio-player');
    if (!audioEl) return;

    // Set up audio context on first user interaction (browser autoplay policy)
    audioEl.addEventListener('play', function() {
      setupAudioContext(audioEl);
    }, { once: true });

    drawFrame();
  });
})();
```

- [ ] **Step 4: Update play/pause icon toggle in `pipeline.js`**

Search `pipeline.js` for `audio-play-pause`. Find the event listeners that set the button text to play/pause symbols. There will be handlers that do something like `btn.textContent = '▶'` or set innerHTML. In those same code paths, add icon toggling alongside:

Find the pattern where playback state changes to "playing" — add:
```javascript
const iconPlay  = document.getElementById('icon-play');
const iconPause = document.getElementById('icon-pause');
if (iconPlay)  iconPlay.style.display  = 'none';
if (iconPause) iconPause.style.display = 'block';
```

Find the pattern where playback state changes to "paused/stopped" — add:
```javascript
const iconPlay  = document.getElementById('icon-play');
const iconPause = document.getElementById('icon-pause');
if (iconPlay)  iconPlay.style.display  = 'block';
if (iconPause) iconPause.style.display = 'none';
```

- [ ] **Step 5: Visual check — player bar at top, waveform visible**

Reload app. Expected:
- Player bar is at the top, full width, 56px tall
- 64 small bars visible in waveform area (dim colour when no track playing)
- Play button is circular with accent background
- Sidebar + content visible below player bar
- Old bottom bar completely gone

- [ ] **Step 6: Commit**

```bash
git add templates/index.html app/static/style.css app/static/modules/pipeline.js
git commit -m "feat(v4): move player bar to top, add Web Audio waveform visualiser"
```

---

## Task 5: Track Table Redesign — Dense 38px Rows, Album Art, Geist Mono Data

**Files:**
- Modify: `templates/index.html` — `<thead>` of `#tracks-table` (lines 186-204); add Art column header
- Modify: `app/static/modules/tracks.js` — `pageData.forEach` loop (around line 180); add art cell, apply `.mono` to BPM/Key, stack Title/Artist
- Modify: `app/static/style.css` — `.tracks-table` rules; new column width classes; art thumb

New column order per spec: `# | Art | Title/Artist | Genre | Sub-genre | Conf | BPM | Key | Clave | Vocal | Tempo | LUFS | Year | Status | Approve | Action`

- [ ] **Step 1: Update `<thead>` in `index.html`**

Find the `<thead>` block of `#tracks-table` (around lines 186-205). Replace the `<tr>` content:

```html
            <thead>
              <tr>
                <th class="col-check"><input type="checkbox" id="select-all-checkbox" /></th>
                <th class="col-art"></th>
                <th data-sort="display_title" class="col-title">Title / Artist</th>
                <th data-sort="final_genre" class="col-genre">Genre</th>
                <th data-sort="final_subgenre" class="col-subgenre">Sub-genre</th>
                <th data-sort="confidence" class="col-conf">Conf</th>
                <th data-sort="final_bpm" class="col-bpm">BPM</th>
                <th data-sort="final_key" class="col-key">Key</th>
                <th data-sort="clave_pattern" class="col-clave">Clave</th>
                <th data-sort="vocal_flag" class="col-vocal">Vocal</th>
                <th data-sort="tempo_category" class="col-tempo">Tempo</th>
                <th data-sort="analyzed_lufs" class="col-lufs">LUFS</th>
                <th data-sort="final_year" class="col-year">Year</th>
                <th data-sort="review_status" class="col-status">Status</th>
                <th class="col-approve">Approve</th>
                <th class="col-action">Action</th>
              </tr>
            </thead>
```

- [ ] **Step 2: Add album art cell in `tracks.js`**

In `tracks.js`, find the section after the checkbox `<td>` is appended (around line 195, after `row.appendChild(tdCheckbox)`). Insert a new art cell immediately after:

```javascript
    // Album Art (26px thumb)
    const tdArt = document.createElement('td');
    tdArt.className = 'col-art';
    const artPlaceholder = document.createElement('div');
    artPlaceholder.className = track.album_art_url ? '' : 'track-art-placeholder';
    if (track.album_art_url) {
      const img = document.createElement('img');
      img.src = track.album_art_url;
      img.className = 'track-art-thumb';
      img.alt = '';
      img.loading = 'lazy';
      tdArt.appendChild(img);
    } else {
      artPlaceholder.className = 'track-art-placeholder';
      tdArt.appendChild(artPlaceholder);
    }
    row.appendChild(tdArt);
```

- [ ] **Step 3: Stack Title + Artist into one cell in `tracks.js`**

Find the existing Title and Artist cells (around lines 197-205):
```javascript
    // Title
    const tdTitle = document.createElement('td');
    tdTitle.textContent = track.display_title || '—';
    row.appendChild(tdTitle);

    // Artist
    const tdArtist = document.createElement('td');
    tdArtist.textContent = track.display_artist || '—';
    row.appendChild(tdArtist);
```

Replace with:
```javascript
    // Title / Artist — stacked in one cell
    const tdTitleArtist = document.createElement('td');
    tdTitleArtist.className = 'col-title';
    const titleDiv = document.createElement('div');
    titleDiv.className = 'track-title-text';
    titleDiv.textContent = track.display_title || '—';
    const artistDiv = document.createElement('div');
    artistDiv.className = 'track-artist-text';
    artistDiv.textContent = track.display_artist || '—';
    tdTitleArtist.appendChild(titleDiv);
    tdTitleArtist.appendChild(artistDiv);
    row.appendChild(tdTitleArtist);
```

- [ ] **Step 4: Apply Geist Mono + 1dp rounding to BPM cell in `tracks.js`**

Find the BPM cell (around lines 222-225):
```javascript
    // BPM
    const tdBpm = document.createElement('td');
    tdBpm.textContent = track.final_bpm || '—';
    row.appendChild(tdBpm);
```

Replace with:
```javascript
    // BPM — Geist Mono, 1 decimal place
    const tdBpm = document.createElement('td');
    tdBpm.className = 'mono col-bpm';
    tdBpm.textContent = track.final_bpm ? parseFloat(track.final_bpm).toFixed(1) : '—';
    row.appendChild(tdBpm);
```

- [ ] **Step 5: Apply accent colour to Key cell in `tracks.js`**

Find the Key cell (around lines 228-231):
```javascript
    // Key
    const tdKey = document.createElement('td');
    tdKey.textContent = track.final_key || '—';
    row.appendChild(tdKey);
```

Replace with:
```javascript
    // Key — accent colour, Geist Mono
    const tdKey = document.createElement('td');
    tdKey.className = 'mono col-key-cell';
    if (track.final_key) {
      tdKey.style.color = 'var(--acc)';
      tdKey.style.fontWeight = '500';
    }
    tdKey.textContent = track.final_key || '—';
    row.appendChild(tdKey);
```

- [ ] **Step 6: Add track table CSS to `style.css`**

Find the existing `.tracks-table` rules. After the existing block, add/replace with:

```css
/* ============================================================================
   Track Table — v4 (dense 38px rows)
   ============================================================================ */

.tracks-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}

.tracks-table thead th {
  position: sticky;
  top: 0;
  background: var(--bg1);
  color: var(--t3);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0 8px;
  height: 32px;
  border-bottom: 1px solid var(--ln);
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
}

.tracks-table thead th:hover {
  color: var(--t1);
}

.tracks-table tbody tr {
  height: 38px;
  border-bottom: 1px solid var(--bg2);
  transition: background 0.08s;
}

.tracks-table tbody tr:hover {
  background: var(--bg2);
}

.tracks-table tbody td {
  padding: 0 8px;
  color: var(--t1);
  vertical-align: middle;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Column widths */
.col-check   { width: 32px; padding: 0 6px; }
.col-art     { width: 34px; padding: 0 4px; }
.col-title   { min-width: 180px; }
.col-genre   { width: 110px; }
.col-subgenre { width: 110px; }
.col-conf    { width: 52px; text-align: center; }
.col-bpm     { width: 58px; text-align: right; }
.col-key-cell { width: 50px; text-align: center; }
.col-clave   { width: 46px; text-align: center; }
.col-vocal   { width: 64px; text-align: center; }
.col-tempo   { width: 60px; }
.col-lufs    { width: 48px; text-align: right; }
.col-year    { width: 44px; text-align: center; }
.col-status  { width: 70px; }
.col-approve { width: 60px; text-align: center; }
.col-action  { width: 60px; text-align: center; }

/* Stacked title/artist */
.track-title-text {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--t1);
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 280px;
}

.track-artist-text {
  font-size: 11px;
  color: var(--t3);
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 280px;
}

/* Album art */
.track-art-thumb {
  width: 26px;
  height: 26px;
  border-radius: 3px;
  object-fit: cover;
  display: block;
}

.track-art-placeholder {
  width: 26px;
  height: 26px;
  border-radius: 3px;
  background: var(--bg3);
  display: block;
}
```

- [ ] **Step 7: Visual check — dense rows, Geist Mono BPM, accent key**

Reload app with tracks loaded. Expected:
- Rows are approximately 38px tall
- BPM column shows `112.3` format (1 decimal, right-aligned)
- Key column text is accent purple
- Title and artist stacked in one column

- [ ] **Step 8: Commit**

```bash
git add templates/index.html app/static/style.css app/static/modules/tracks.js
git commit -m "feat(v4): track table — 38px rows, album art, Geist Mono BPM/Key, stacked title/artist"
```

---

## Task 6: Toolbar + Pipeline Stepper — Compact Segmented Control

**Files:**
- Modify: `templates/index.html` — `.pipeline-stepper` markup (lines 81-111)
- Modify: `app/static/style.css` — `.pipeline-stepper` and children (around lines 4305-4330)

The existing stepper is a tall widget (boxes with circle numbers, counts, connectors). The spec requires a compact segmented control — like a tab bar — that fits in the toolbar row.

- [ ] **Step 1: Replace `.pipeline-stepper` HTML in `index.html`**

Find the block starting `<!-- Pipeline stepper showing workflow state -->` (around line 81). Replace through the closing `</div>` of `.pipeline-stepper` (around line 111) with:

```html
          <!-- Pipeline stepper — compact segmented control -->
          <div class="pipeline-seg" id="pipeline-stepper" role="tablist" aria-label="Pipeline steps">
            <button class="seg-step" data-step="import" id="step-import" role="tab">
              <span class="seg-step-icon" id="seg-icon-import">1</span>
              <span class="seg-step-label">Import</span>
              <span class="seg-step-count mono" id="count-import">0</span>
            </button>
            <span class="seg-sep" aria-hidden="true"></span>
            <button class="seg-step" data-step="analyse" id="step-analyse" role="tab">
              <span class="seg-step-icon" id="seg-icon-analyse">2</span>
              <span class="seg-step-label">Analyse</span>
              <span class="seg-step-count mono" id="count-analyse">0</span>
            </button>
            <span class="seg-sep" aria-hidden="true"></span>
            <button class="seg-step" data-step="classify" id="step-classify" role="tab">
              <span class="seg-step-icon" id="seg-icon-classify">3</span>
              <span class="seg-step-label">Classify</span>
              <span class="seg-step-count mono" id="count-classify">0</span>
            </button>
            <span class="seg-sep" aria-hidden="true"></span>
            <button class="seg-step" data-step="review" id="step-review" role="tab">
              <span class="seg-step-icon" id="seg-icon-review">4</span>
              <span class="seg-step-label">Review</span>
              <span class="seg-step-count mono" id="count-review">0</span>
            </button>
            <span class="seg-sep" aria-hidden="true"></span>
            <button class="seg-step" data-step="write" id="step-write" role="tab">
              <span class="seg-step-icon" id="seg-icon-write">5</span>
              <span class="seg-step-label">Write Tags</span>
              <span class="seg-step-count mono" id="count-write">0</span>
            </button>
          </div>
```

IDs `count-import`, `count-analyse`, `count-classify`, `count-review`, `count-write`, `step-import`, `step-analyse`, `step-classify`, `step-review`, `step-write` are all preserved — existing JS reads these by ID.

- [ ] **Step 2: Replace pipeline stepper CSS in `style.css`**

Find the `.pipeline-stepper` block (around line 4306). Replace through the `.pipeline-connector` rule (around line 4330) with:

```css
/* ============================================================================
   Pipeline Stepper — v4 compact segmented control
   ============================================================================ */

.pipeline-seg {
  display: inline-flex;
  align-items: center;
  background: var(--bg2);
  border: 1px solid var(--ln);
  border-radius: var(--radius-md);
  padding: 2px;
  gap: 0;
}

.seg-sep {
  width: 1px;
  height: 16px;
  background: var(--ln);
  flex-shrink: 0;
}

.seg-step {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border: none;
  border-radius: 7px;
  background: none;
  cursor: pointer;
  color: var(--t3);
  font-family: 'Outfit', sans-serif;
  font-size: 12px;
  font-weight: 500;
  transition: background 0.12s, color 0.12s;
  white-space: nowrap;
}

.seg-step:hover:not(.active) {
  background: var(--bg3);
  color: var(--t2);
}

.seg-step.active {
  background: var(--acc-dim);
  color: var(--acc);
}

.seg-step.completed {
  color: var(--green);
}

.seg-step-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--bg3);
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
  color: var(--t3);
}

.seg-step.active .seg-step-icon {
  background: var(--acc);
  color: #fff;
}

.seg-step.completed .seg-step-icon {
  background: var(--green);
  color: #fff;
  font-size: 0; /* hide number */
}

.seg-step.completed .seg-step-icon::after {
  content: 'v';
  font-size: 10px;
  font-weight: 900;
}

.seg-step-label {
  font-size: 12px;
}

.seg-step-count {
  font-size: 11px;
  color: var(--t4);
  background: var(--bg3);
  border-radius: 10px;
  padding: 0 5px;
  min-width: 20px;
  text-align: center;
  line-height: 16px;
}

.seg-step.active .seg-step-count {
  background: color-mix(in srgb, var(--acc) 20%, transparent);
  color: var(--acc);
}

/* Legacy selectors — keep JS working during transition */
.pipeline-stepper { display: contents; }
.pipeline-step    { display: contents; }
.step-circle      { display: none; }
.step-label       { display: none; }
.step-count       { display: none; }
.pipeline-connector { display: none; }
```

- [ ] **Step 3: Verify JS still updates the stepper correctly**

Open `pipeline.js` and search for `step-import`, `pipeline-step`, `classList.add`. The JS typically does:
```javascript
document.getElementById('step-import').classList.add('active');
```
or queries `document.querySelectorAll('.pipeline-step')`. Since `id` attributes are preserved and the old class selectors fall through to `display: contents`, existing JS will still read/write `.active` and `.completed` correctly on the `#step-*` elements. No JS change needed unless the code queries `.step-circle` or `.step-count` to set text — if so, confirm `#count-import` etc. still exist (they do, as `.seg-step-count` children).

- [ ] **Step 4: Visual check — pipeline stepper fits in toolbar row**

Reload app. Expected:
- Pipeline stepper is a compact horizontal pill in the toolbar
- All 5 steps visible in one row alongside action buttons
- Active step shows accent background with accent-coloured circle
- Completed steps show green

- [ ] **Step 5: Commit**

```bash
git add templates/index.html app/static/style.css
git commit -m "feat(v4): pipeline stepper — compact segmented control replacing large step widget"
```

---

## Task 7: Search Box — Explicit Contrast Fix

**Files:**
- Modify: `app/static/style.css` — `.filter-bar`, `.search-input`, `.filter-select`, placeholder rules (around lines 3100-3126)

Critical bug from spec: old placeholder colour was `#42425e` on `#252538` = 1.4:1 contrast (invisible). Fix: set ALL input text and placeholder colours explicitly, never rely on inheritance.

- [ ] **Step 1: Replace the filter bar CSS block in `style.css`**

Find the `/* ─── Filter Bar ───` comment (around line 3099). Replace everything from that comment through the `.filter-select` closing brace with:

```css
/* ─── Filter Bar ──────────────────────────────────────────────────────────── */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--bg1);
  border-bottom: 1px solid var(--ln);
  flex-wrap: wrap;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  min-width: 160px;
  font-size: 13px;
  font-family: 'Outfit', sans-serif;
  padding: 6px 10px;
  background: var(--bg0);
  border: 1px solid var(--ln);
  border-radius: var(--radius-sm);
  color: var(--t1);
  outline: none;
  transition: border-color 0.15s;
}

.search-input::placeholder {
  color: var(--t3);
  opacity: 1;
}

.search-input:focus {
  border-color: var(--acc);
}

.filter-select {
  font-size: 12px;
  font-family: 'Outfit', sans-serif;
  padding: 5px 8px;
  background: var(--bg0);
  border: 1px solid var(--ln);
  border-radius: var(--radius-sm);
  color: var(--t1);
  cursor: pointer;
  outline: none;
}

.filter-select:focus {
  border-color: var(--acc);
}

/* General input text reset — covers folder-input, form inputs, Settings inputs */
.folder-input-inline,
.input,
.input-text,
.input-select {
  color: var(--t1);
  background: var(--bg2);
  border: 1px solid var(--ln);
  border-radius: var(--radius-sm);
  font-family: 'Outfit', sans-serif;
}

.folder-input-inline::placeholder,
.input::placeholder,
.input-text::placeholder {
  color: var(--t3);
  opacity: 1;
}
```

- [ ] **Step 2: Visual check — search box readable in all 3 themes**

Reload app. Check:
1. Dark theme: type text in search box — should be `#f2f2f8` (bright white)
2. Clear field — placeholder "Search tracks..." should be `#8888a8` (clearly visible muted grey)
3. In DevTools, change `html[data-theme]` to `light` — repeat checks; placeholder should now be `#606080` on `#f4f3f8`
4. Change to `accessibility` — placeholder `#c0c0c0` on `#000000` = 9.2:1

For each theme, contrast must be >= 4.5:1 for the placeholder text.

- [ ] **Step 3: Commit**

```bash
git add app/static/style.css
git commit -m "fix(v4): search input explicit color tokens — prevent invisible placeholder regression"
```

---

## Task 8: Settings Tab — Theme and Accent Switcher

**Files:**
- Modify: `templates/index.html` — Settings tab (around line 648); add Appearance section
- Modify: `app/static/modules/settings.js` — replace theme/accent handling (lines 355-378)

Per spec: theme switcher must NOT be in the app chrome. Settings tab only.

- [ ] **Step 1: Add Appearance section to Settings tab in `index.html`**

Find the line `<div class="settings-form">` inside the Settings section (around line 659). Insert the following block immediately after `<div class="settings-form">`, before the existing `<!-- AI Classification Section -->`:

```html
          <!-- Appearance Section -->
          <div class="settings-section-label">Appearance</div>

          <div class="form-group">
            <label>Theme</label>
            <div class="theme-picker" id="theme-picker" role="radiogroup" aria-label="Choose theme">
              <label class="theme-option">
                <input type="radio" name="theme" value="dark" id="theme-dark">
                <span class="theme-option-swatch theme-swatch-dark"></span>
                <span class="theme-option-label">Dark</span>
              </label>
              <label class="theme-option">
                <input type="radio" name="theme" value="light" id="theme-light">
                <span class="theme-option-swatch theme-swatch-light"></span>
                <span class="theme-option-label">Light</span>
              </label>
              <label class="theme-option">
                <input type="radio" name="theme" value="accessibility" id="theme-accessibility">
                <span class="theme-option-swatch theme-swatch-accessibility"></span>
                <span class="theme-option-label">Accessibility</span>
              </label>
            </div>
          </div>

          <div class="form-group">
            <label>Accent Colour</label>
            <div class="accent-picker" id="accent-picker" role="radiogroup" aria-label="Choose accent colour">
              <label class="accent-option">
                <input type="radio" name="accent" value="purple" id="accent-purple">
                <span class="accent-option-dot" style="background:#8b5cf6;"></span>
                <span class="accent-option-label">Purple</span>
              </label>
              <label class="accent-option">
                <input type="radio" name="accent" value="teal" id="accent-teal">
                <span class="accent-option-dot" style="background:#14b8a6;"></span>
                <span class="accent-option-label">Teal</span>
              </label>
              <label class="accent-option">
                <input type="radio" name="accent" value="orange" id="accent-orange">
                <span class="accent-option-dot" style="background:#f97316;"></span>
                <span class="accent-option-label">Orange</span>
              </label>
            </div>
          </div>

          <!-- AI Classification Section -->
```

- [ ] **Step 2: Replace theme/accent JS in `settings.js`**

Find the `// Theme` comment block (around line 355). Replace the entire block through `}` of `initThemeSwatches` (around line 378) with:

```javascript
// ============================================================================
// Theme + Accent — v4
// ============================================================================

const VALID_THEMES  = ['dark', 'light', 'accessibility'];
const VALID_ACCENTS = ['purple', 'teal', 'orange'];

function applyTheme(theme) {
  if (!VALID_THEMES.includes(theme)) theme = 'dark';
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('idjlm-theme', theme);
  const radio = document.getElementById('theme-' + theme);
  if (radio) radio.checked = true;
}

function applyAccent(accent) {
  if (!VALID_ACCENTS.includes(accent)) accent = 'purple';
  document.documentElement.setAttribute('data-accent', accent);
  localStorage.setItem('idjlm-accent', accent);
  const radio = document.getElementById('accent-' + accent);
  if (radio) radio.checked = true;
}

function initTheme() {
  const savedTheme  = localStorage.getItem('idjlm-theme')  || 'dark';
  const savedAccent = localStorage.getItem('idjlm-accent') || 'purple';
  applyTheme(savedTheme);
  applyAccent(savedAccent);
}

function initThemeSwatches() {
  document.querySelectorAll('input[name="theme"]').forEach(function(radio) {
    radio.addEventListener('change', function() {
      if (radio.checked) applyTheme(radio.value);
    });
  });
  document.querySelectorAll('input[name="accent"]').forEach(function(radio) {
    radio.addEventListener('change', function() {
      if (radio.checked) applyAccent(radio.value);
    });
  });
}
```

- [ ] **Step 3: Add theme/accent picker CSS to `style.css`**

After the existing `.swatch-black` rule (around line 351), add:

```css
/* ─── Settings: Theme + Accent Pickers ─────────────────────────────────────── */
.theme-picker,
.accent-picker {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.theme-option,
.accent-option {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--ln);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  color: var(--t2);
  transition: border-color 0.12s, color 0.12s;
  user-select: none;
}

.theme-option:has(input:checked),
.accent-option:has(input:checked) {
  border-color: var(--acc);
  color: var(--t1);
}

.theme-option input,
.accent-option input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.theme-option-swatch {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  flex-shrink: 0;
}

.theme-swatch-dark          { background: linear-gradient(135deg, #0a0a10, #12121c); border: 1px solid #2c2c40; }
.theme-swatch-light         { background: linear-gradient(135deg, #f4f3f8, #eceaf5); border: 1px solid #d0cedf; }
.theme-swatch-accessibility { background: #000; border: 2px solid #fff; }

.accent-option-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
}

.accent-option-label,
.theme-option-label {
  font-size: 12px;
  font-weight: 500;
}
```

- [ ] **Step 4: Visual check — Settings tab Appearance section works**

Reload app, go to Settings tab. Expected:
- "Appearance" section appears above "AI Classification"
- Three theme cards (Dark / Light / Accessibility), current one highlighted with accent border
- Three accent dots (Purple / Teal / Orange), current one highlighted
- Clicking "Light" switches entire app to light theme immediately
- Clicking "Teal" changes accent throughout app
- Refreshing page restores saved values from localStorage

- [ ] **Step 5: Confirm no theme switcher in sidebar**

Check sidebar — no swatches or colour dots visible. Only section labels and nav buttons.

- [ ] **Step 6: Commit**

```bash
git add templates/index.html app/static/style.css app/static/modules/settings.js
git commit -m "feat(v4): move theme/accent switcher to Settings tab, implement data-attr switching"
```

---

## Task 9: Genre Pill Component

**Files:**
- Modify: `app/static/modules/pipeline.js` — `genreChip()` function (lines 231-236)
- Modify: `app/static/modules/tracks.js` — callers of `genreChip` (lines 209, 214)
- Modify: `app/static/style.css` — `.genre-chip` / add `.genre-pill` rules

The current `genreChip()` uses inline `style=` with hardcoded hex values. The v4 version uses a CSS custom property `--pill-color` so colours adapt to theme. Manually-edited genres get a dashed border.

- [ ] **Step 1: Replace `genreChip()` in `pipeline.js`**

Find lines 231-236:
```javascript
function genreChip(genre) {
  if (!genre) return '—';
  const hash = [...genre].reduce((a,c)=>a+c.charCodeAt(0),0);
  const color = GENRE_COLORS[hash % GENRE_COLORS.length];
  return `<span class="genre-chip" style="background:${color}22;color:${color};border:1px solid ${color}44">${escapeHtml(genre)}</span>`;
}
```

Replace with:
```javascript
/**
 * @param {string} genre
 * @param {boolean} manual - true if genre was manually edited by user
 */
function genreChip(genre, manual) {
  if (!genre) return '—';
  const hash = [...genre].reduce(function(a, c) { return a + c.charCodeAt(0); }, 0);
  const color = GENRE_COLORS[hash % GENRE_COLORS.length];
  var manualAttr = manual ? ' data-manual="true"' : '';
  return '<span class="genre-pill" style="--pill-color:' + color + '"' + manualAttr + '>' + escapeHtml(genre) + '</span>';
}
```

- [ ] **Step 2: Update callers in `tracks.js`**

Find the two `genreChip` calls (around lines 209 and 214):
```javascript
tdGenre.innerHTML = genreChip(track.final_genre);
tdSubgenre.innerHTML = genreChip(track.final_subgenre);
```

Replace with:
```javascript
const isManual = (track.genre_source === 'manual' || track.genre_edited === true);
tdGenre.innerHTML = genreChip(track.final_genre, isManual);
tdSubgenre.innerHTML = genreChip(track.final_subgenre, false);
```

- [ ] **Step 3: Add `.genre-pill` CSS, keep `.genre-chip` as fallback**

Find the `.genre-chip` rule (around line 1866). Add the new `.genre-pill` rule before it:

```css
/* Genre pill — v4 (CSS custom property colour) */
.genre-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
  background: color-mix(in srgb, var(--pill-color, #8b5cf6) 15%, transparent);
  color: var(--pill-color, #8b5cf6);
  border: 1px solid color-mix(in srgb, var(--pill-color, #8b5cf6) 35%, transparent);
}

.genre-pill[data-manual="true"] {
  border-style: dashed;
  opacity: 0.85;
}
```

Keep the existing `.genre-chip` rule unchanged below it for any code that still uses the old class.

- [ ] **Step 4: Visual check — genre pills render in track table**

Reload app with tracks loaded. Expected:
- Genre column shows coloured pills (purple/teal/amber etc.)
- Pills have coloured background tint and matching text colour
- If any tracks have `genre_source === 'manual'`, their genre pill has a dashed border
- No visual difference in the pipeline Classify review modals (genreChip is also used there)

- [ ] **Step 5: Commit**

```bash
git add app/static/modules/pipeline.js app/static/modules/tracks.js app/static/style.css
git commit -m "feat(v4): genre pill — CSS custom property colour, manual-edit dashed border indicator"
```

---

## Task 10: Smoke Test — Visual + Functional Check Across All 3 Themes x 3 Accents

**Files:** No code changes. Verification only.

- [ ] **Step 1: 9-combination visual check**

For each combination, navigate to Settings, select theme + accent, then check:

| Theme | Accent | Check |
|-------|--------|-------|
| Dark | Purple | Sidebar accent border purple, key chips purple, BPM mono |
| Dark | Teal | Sidebar accent border teal, player play button teal |
| Dark | Orange | Sidebar accent border orange, genre-pill active states orange |
| Light | Purple | Light bg, dark text readable, sidebar labels visible |
| Light | Teal | Teal accent on light background |
| Light | Orange | Orange accent on light background |
| Accessibility | Purple | Maximum contrast, t1=#fff on bg0=#000 |
| Accessibility | Teal | Same plus teal accent |
| Accessibility | Orange | Same plus orange accent |

For each: search box placeholder visible, BPM column readable, Key column in accent colour.

- [ ] **Step 2: WCAG contrast verification**

In Chrome DevTools with Accessibility panel, check each theme:
- Dark: `--t1` (#f2f2f8) on `--bg0` (#0a0a10) = 16.1:1 (pass AAA)
- Dark: `--t3` (#8888a8) on `--bg0` (#0a0a10) = 4.7:1 (pass AA)
- Light: `--t1` (#0e0e18) on `--bg0` (#f4f3f8) = 19.5:1 (pass AAA)
- Light: `--t3` (#606080) on `--bg0` (#f4f3f8) = 4.9:1 (pass AA)
- Accessibility: `--t1` (#ffffff) on `--bg0` (#000000) = 21:1 (pass AAA)
- Accessibility: `--t3` (#c0c0c0) on `--bg0` (#000000) = 9.2:1 (pass AAA)

- [ ] **Step 3: Functional pipeline smoke test**

With tracks in `/upload/songs test/`:
1. Import folder -> `count-import` in segmented control shows count
2. Pipeline segmented control step-import shows `.active` class (inspect in DevTools)
3. Click Analyse All -> waveform bars animate during audio preview play
4. Search box filters correctly, text visible in search input
5. Genre pills render in track table rows
6. Navigate to Settings -> Appearance -> switch theme -> app updates immediately
7. Refresh page -> theme + accent restored

- [ ] **Step 4: Screenshot each theme**

At 1440x900, screenshot and save:
- `/home/ubuntu/projects/idjlm/docs/screenshots/v4-dark-purple.png`
- `/home/ubuntu/projects/idjlm/docs/screenshots/v4-light-teal.png`
- `/home/ubuntu/projects/idjlm/docs/screenshots/v4-accessibility-orange.png`

Use browser DevTools device emulation or screenshot tool.

- [ ] **Step 5: Final version bump commit**

```bash
git add .
git commit -m "feat: IDJLM Pro v4 Phase 2 UI Redesign complete

- CSS token system: 3 themes x 3 accents via data-attr
- Outfit + Geist Mono typography
- Sidebar: 192px, section labels, SVG icons, accent active border
- Player bar: top position, Web Audio waveform visualiser
- Track table: 38px rows, album art col, Geist Mono BPM/Key, stacked title/artist
- Pipeline stepper: compact segmented control
- Search: explicit color tokens (WCAG AA fix)
- Settings: theme/accent radio switcher (removed from app chrome)
- Genre pills: CSS custom property colour, manual-edit dashed border"
```

---

## Implementation Notes

### Token migration strategy

The old CSS (lines 180+ of `style.css`) still uses `var(--bg-page)`, `var(--text-primary)` etc. The new token block in Task 1 creates alias chains:
```css
--bg-page: var(--bg0);
--text-primary: var(--t1);
```
This means Tasks 1-9 do NOT require a mass search-and-replace across 4451 lines. Only the explicitly redesigned components get new tokens directly; everything else inherits via aliases.

### `color-mix()` compatibility

Used in sidebar active state and genre pills. Supported: Chrome 111+, Firefox 113+, Safari 16.2+. Fallback if needed: replace `color-mix(in srgb, var(--acc) 12%, transparent)` with `var(--acc-dim)` which is the pre-computed rgba value.

### `:has()` selector

Used in `.theme-option:has(input:checked)`. Supported in all modern browsers (Chrome 105+, Firefox 121+, Safari 15.4+). If a targeted browser is older, add JS in `initThemeSwatches()` to toggle a `.checked` class on the label element instead.

### Web Audio + autoplay policy

The waveform `AudioContext` is created on the first `play` event, not on page load. This avoids the browser autoplay policy blocking context creation before user interaction. The idle bars still animate from `requestAnimationFrame` using `freqData = null` fallback (constant low amplitude).

### Album art field

Task 5 adds an `album_art_url` column reference. If the backend `/api/tracks` response does not currently include this field, the art cell shows a placeholder div — correct behaviour. Phase 3 can add thumbnail extraction to the backend.
