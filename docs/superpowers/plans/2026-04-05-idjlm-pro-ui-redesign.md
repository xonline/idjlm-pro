# IDJLM Pro UI Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 11-tab layout with a single Library screen where the entire pipeline (import → analyze → classify → approve → write) is accessible without switching tabs.

**Architecture:** Pure frontend refactor. HTML restructures sidebar (11 → 4 items) and Library tab (adds toolbar + stats bar + inline approve column). JS wires up the new toolbar and inline approve logic. No backend routes change.

**Tech Stack:** Flask (Jinja2 templates), vanilla JS, CSS custom properties (dark/light theme). No build step — edit files directly.

**Spec:** `docs/superpowers/specs/2026-04-05-idlm-pro-ui-redesign.md`

---

## File Map

| File | What changes |
|------|-------------|
| `templates/index.html` | Sidebar: 11 → 4 nav buttons. Library tab: add toolbar + stats bar. Track table: add Approve column. Taxonomy moves into Settings. Setlist folds into Set Planner. Duplicates folds into Organise. Wheel tab removed from sidebar. |
| `app/static/app.js` | `switchTab()`: updated for new tab names. New `initLibraryToolbar()`: handles folder import + pipeline buttons. `renderTracks()`: add inline Approve column. `updateStats()`: targets new inline stats bar IDs. Taxonomy init moves under Settings. |
| `app/static/style.css` | New: `.library-toolbar`, `.stats-bar`, `.pipeline-btn`, `.approve-col`, `.filter-bar`, `.resume-banner`. |

---

## Task 1: Restructure Sidebar to 4 Items

**Files:**
- Modify: `templates/index.html` lines 12–93 (sidebar nav + old stats panel)

- [ ] **Step 1: Replace sidebar nav section**

  Find the nav block (lines 12–93). Replace with:

  ```html
  <!-- SIDEBAR -->
  <nav class="sidebar">
    <div class="logo-container">
      <div class="logo-icon">🎛️</div>
      <div class="logo-text">IDJLM Pro</div>
    </div>
    <div class="nav-menu">
      <button class="nav-btn active" data-tab="library">
        <span class="nav-icon">📚</span> Library
      </button>
      <button class="nav-btn" data-tab="organise">
        <span class="nav-icon">📋</span> Organise
      </button>
      <button class="nav-btn" data-tab="setplan">
        <span class="nav-icon">🎛️</span> Set Planner
      </button>
      <button class="nav-btn" data-tab="settings">
        <span class="nav-icon">⚙️</span> Settings
      </button>
    </div>
    <button class="theme-toggle" id="btn-theme-toggle" title="Toggle theme">🌙</button>
  </nav>
  ```

- [ ] **Step 2: Verify sidebar renders with 4 items**

  Start the app: `source .venv/bin/activate && python -m flask run --port 5000`
  Open `http://localhost:5000`. Confirm sidebar shows exactly: Library, Organise, Set Planner, Settings.

- [ ] **Step 3: Commit**

  ```bash
  cd /home/ubuntu/dj-library-manager
  git add templates/index.html
  git commit -m "feat(ui): sidebar reduced to 4 nav items"
  ```

---

## Task 2: Build the Unified Library Tab (replaces Import + Tracks)

**Files:**
- Modify: `templates/index.html` — replace Import tab section (lines ~100–180) and Tracks tab section (lines ~183–247) with a single Library tab.

- [ ] **Step 1: Remove old Import and Tracks tab divs**

  Delete the entire `<div id="tab-import" class="tab">` block and the entire `<div id="tab-tracks" class="tab">` block.

- [ ] **Step 2: Insert Library tab in their place**

  ```html
  <!-- LIBRARY TAB -->
  <div id="tab-library" class="tab active">

    <!-- Toolbar -->
    <div class="library-toolbar">
      <div class="toolbar-import">
        <span class="toolbar-label">📁</span>
        <span id="folder-display" class="folder-display">No folder selected</span>
        <button class="btn btn-secondary btn-sm" id="btn-change-folder">Change</button>
        <input type="text" id="folder-input" class="folder-input-inline" placeholder="/path/to/music" style="display:none;" />
        <button class="btn btn-primary btn-sm" id="btn-import" style="display:none;">Import</button>
      </div>
      <div class="toolbar-pipeline">
        <button class="btn pipeline-btn" id="btn-analyze" disabled>▶ Analyze All</button>
        <button class="btn pipeline-btn" id="btn-classify" disabled>✦ Classify All</button>
        <button class="btn pipeline-btn" id="btn-bulk-approve-toolbar" disabled>✓ Approve &ge;<span id="toolbar-threshold">80</span>%</button>
        <button class="btn pipeline-btn pipeline-btn-write" id="btn-write-tags" disabled>✎ Write Tags</button>
      </div>
    </div>

    <!-- Stats bar -->
    <div class="stats-bar" id="library-stats-bar">
      <span class="stat-item"><span id="stat-total">0</span> tracks</span>
      <span class="stat-sep">•</span>
      <span class="stat-item"><span id="stat-analyzed">0</span> analyzed</span>
      <span class="stat-sep">•</span>
      <span class="stat-item"><span id="stat-classified">0</span> classified</span>
      <span class="stat-sep">•</span>
      <span class="stat-item"><span id="stat-approved">0</span> approved</span>
      <span class="stat-sep stat-progress-sep" id="stat-progress-sep" style="display:none;">•</span>
      <span class="stat-progress-wrap" id="stat-progress-wrap" style="display:none;">
        <span id="stat-progress-text"></span>
        <div class="stat-progress-bar"><div class="stat-progress-fill" id="stat-progress-fill"></div></div>
      </span>
    </div>

    <!-- Session resume banner -->
    <div class="resume-banner" id="resume-banner" style="display:none;">
      <span id="resume-info"></span>
      <button class="btn btn-sm btn-primary" id="btn-resume-session">Resume</button>
      <button class="btn btn-sm btn-secondary" id="btn-dismiss-session">Dismiss</button>
    </div>

    <!-- Filter bar -->
    <div class="filter-bar">
      <input type="text" id="search-tracks" class="search-input" placeholder="Search tracks..." />
      <select id="filter-genre" class="filter-select">
        <option value="">All Genres</option>
      </select>
      <select id="filter-status" class="filter-select">
        <option value="">All Status</option>
        <option value="pending">Pending</option>
        <option value="approved">Approved</option>
        <option value="skipped">Skipped</option>
        <option value="written">Written</option>
      </select>
      <select id="filter-sort" class="filter-select">
        <option value="display_title">Sort: Title</option>
        <option value="display_artist">Sort: Artist</option>
        <option value="final_genre">Sort: Genre</option>
        <option value="final_bpm">Sort: BPM</option>
        <option value="confidence">Sort: Confidence</option>
      </select>
    </div>

    <!-- Track table -->
    <div class="table-wrap">
      <table class="tracks-table" id="tracks-table">
        <thead>
          <tr>
            <th class="checkbox-col"><input type="checkbox" id="select-all-checkbox" /></th>
            <th data-sort="display_title">Title</th>
            <th data-sort="display_artist">Artist</th>
            <th class="wave-col">Wave</th>
            <th data-sort="final_genre">Genre</th>
            <th data-sort="final_subgenre">Sub-Genre</th>
            <th data-sort="confidence">Conf</th>
            <th data-sort="final_bpm">BPM</th>
            <th data-sort="final_key">Key</th>
            <th data-sort="clave_pattern">Clave</th>
            <th data-sort="vocal_flag">Vocal</th>
            <th data-sort="tempo_category">Tempo</th>
            <th data-sort="final_year">Year</th>
            <th data-sort="review_status">Status</th>
            <th class="approve-col">Approve</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody id="tracks-tbody">
          <tr class="empty-state">
            <td colspan="16">
              <div class="empty-state-content">
                <div class="empty-icon">📁</div>
                <div class="empty-msg">Pick a folder to get started</div>
                <button class="btn btn-primary" id="btn-get-started">Choose Folder</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="pagination-info" id="pagination-info"></div>

    <!-- Bulk action bar -->
    <div class="bulk-action-bar" id="bulk-action-bar" style="display:none;">
      <span id="bulk-selected-count">0 selected</span>
      <button class="btn btn-sm btn-primary" id="btn-bulk-approve-selected">Approve Selected</button>
      <button class="btn btn-sm btn-secondary" id="btn-bulk-skip-selected">Skip Selected</button>
      <button class="btn btn-sm btn-danger" id="btn-bulk-delete-selected">Delete Selected</button>
    </div>

  </div>
  ```

- [ ] **Step 3: Verify Library tab structure**

  Reload app. Library tab: toolbar row → stats row → filter row → empty-state table with "Pick a folder" button. No JS errors in console.

- [ ] **Step 4: Commit**

  ```bash
  git add templates/index.html
  git commit -m "feat(ui): Library tab with toolbar, stats bar, filter bar, track table"
  ```

---

## Task 3: Fold Tabs — Taxonomy → Settings, Setlist → Set Planner, Duplicates → Organise

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: Add Taxonomy section to bottom of Settings tab**

  Find `<div id="tab-settings" class="tab">`. Before its closing `</div>`, add:

  ```html
  <div class="settings-section" id="settings-taxonomy-section">
    <h2 class="settings-section-title">Taxonomy</h2>
    <p class="settings-section-desc">Define genres and sub-genres used by the AI classifier.</p>
    <button class="btn btn-secondary" id="btn-add-genre">+ Add Genre</button>
    <div id="taxonomy-list" class="taxonomy-list"></div>
    <button class="btn btn-primary" id="btn-save-taxonomy">Save Taxonomy</button>
  </div>
  ```

- [ ] **Step 2: Copy Setlist content into Set Planner tab**

  Find `<div id="tab-setplan" class="tab">`. At the bottom before its closing `</div>`, add a heading and copy the inner content of `<div id="tab-setlist" class="tab">` verbatim:

  ```html
  <h2 class="settings-section-title" style="margin-top:32px;padding:0 24px;">Manual Setlist</h2>
  <div id="setlist-subpanel" style="padding:0 24px 24px;">
    <!-- PASTE INNER HTML OF tab-setlist HERE -->
  </div>
  ```

- [ ] **Step 3: Copy Duplicates content into Organise tab**

  Find `<div id="tab-organise" class="tab">`. At the bottom before its closing `</div>`, add:

  ```html
  <h2 class="settings-section-title" style="margin-top:32px;padding:0 24px;">Duplicate Detector</h2>
  <div id="duplicates-subpanel" style="padding:0 24px 24px;">
    <!-- PASTE INNER HTML OF tab-duplicates HERE -->
  </div>
  ```

- [ ] **Step 4: Remove now-empty standalone tab divs**

  Delete these tab divs entirely:
  - `<div id="tab-review" class="tab">` and all contents
  - `<div id="tab-stats" class="tab">` and all contents
  - `<div id="tab-taxonomy" class="tab">` and all contents
  - `<div id="tab-setlist" class="tab">` and all contents (moved to setplan)
  - `<div id="tab-wheel" class="tab">` and all contents (still in edit modal)
  - `<div id="tab-duplicates" class="tab">` and all contents (moved to organise)

- [ ] **Step 5: Find all broken switchTab references**

  ```bash
  grep -n "switchTab\|data-tab=" /home/ubuntu/dj-library-manager/app/static/app.js | grep -v "library\|organise\|setplan\|settings" | head -30
  ```

  Note every line returned — fixed in Task 5 Step 4.

- [ ] **Step 6: Commit**

  ```bash
  git add templates/index.html
  git commit -m "feat(ui): fold taxonomy/setlist/duplicates into parent tabs; remove dead tab shells"
  ```

---

## Task 4: CSS — Toolbar, Stats Bar, Approve Column, Filter Bar

**Files:**
- Modify: `app/static/style.css` (append at end)

- [ ] **Step 1: Append all new styles**

  Append to the end of `style.css`:

  ```css
  /* ─── Library Toolbar ─────────────────────────────────────── */
  .library-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    background: var(--bg-panel);
    border-bottom: 1px solid var(--bg-subtle);
    flex-wrap: wrap;
  }
  .toolbar-import {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
  }
  .toolbar-label { font-size: 16px; flex-shrink: 0; }
  .folder-display {
    font-size: 12px;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 280px;
    flex: 1;
  }
  .folder-input-inline {
    flex: 1;
    max-width: 320px;
    font-size: 12px;
    padding: 4px 8px;
    background: var(--bg-deeper);
    border: 1px solid var(--bg-subtle);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
  }
  .toolbar-pipeline {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }
  .pipeline-btn {
    font-size: 11px;
    padding: 5px 10px;
    background: var(--bg-deeper);
    border: 1px solid var(--bg-subtle);
    color: var(--text-secondary);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .pipeline-btn:not(:disabled):hover {
    background: var(--accent-dim);
    color: var(--accent);
    border-color: var(--accent);
  }
  .pipeline-btn:disabled { opacity: 0.35; cursor: not-allowed; }
  .pipeline-btn-write:not(:disabled) { border-color: var(--green); color: var(--green); }
  .pipeline-btn-write:not(:disabled):hover {
    background: color-mix(in srgb, var(--green) 15%, transparent);
  }

  /* ─── Stats Bar ────────────────────────────────────────────── */
  .stats-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 16px;
    font-size: 12px;
    color: var(--text-secondary);
    background: var(--bg-panel);
    border-bottom: 1px solid var(--bg-subtle);
    flex-wrap: wrap;
  }
  .stat-item { color: var(--text-primary); }
  .stat-item span { font-weight: 600; color: var(--accent); }
  .stat-sep { color: var(--text-placeholder); }
  .stat-progress-wrap { display: flex; align-items: center; gap: 8px; font-size: 11px; }
  .stat-progress-bar {
    width: 120px;
    height: 4px;
    background: var(--bg-subtle);
    border-radius: 2px;
    overflow: hidden;
  }
  .stat-progress-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
    transition: width 0.3s ease;
    width: 0%;
  }

  /* ─── Resume Banner ────────────────────────────────────────── */
  .resume-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 16px;
    background: color-mix(in srgb, var(--accent) 10%, transparent);
    border-bottom: 1px solid var(--accent-dim);
    font-size: 13px;
    color: var(--text-secondary);
  }
  .resume-banner span { flex: 1; }

  /* ─── Filter Bar ───────────────────────────────────────────── */
  .filter-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: var(--bg-panel);
    border-bottom: 1px solid var(--bg-subtle);
    flex-wrap: wrap;
  }
  .search-input {
    flex: 1;
    min-width: 160px;
    font-size: 13px;
    padding: 5px 10px;
    background: var(--bg-deeper);
    border: 1px solid var(--bg-subtle);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
  }
  .filter-select {
    font-size: 12px;
    padding: 5px 8px;
    background: var(--bg-deeper);
    border: 1px solid var(--bg-subtle);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
  }

  /* ─── Approve Column ───────────────────────────────────────── */
  .approve-col { width: 64px; text-align: center; }
  .approve-btn {
    background: none;
    border: 1px solid var(--bg-subtle);
    border-radius: var(--radius-sm);
    padding: 2px 6px;
    font-size: 11px;
    cursor: pointer;
    color: var(--text-secondary);
    transition: all 0.15s;
  }
  .approve-btn:hover { border-color: var(--green); color: var(--green); }
  .approve-btn.approved {
    background: color-mix(in srgb, var(--green) 15%, transparent);
    border-color: var(--green);
    color: var(--green);
  }
  .approve-btn.skipped { color: var(--text-placeholder); }

  /* ─── Table wrap ───────────────────────────────────────────── */
  .table-wrap { flex: 1; overflow-y: auto; overflow-x: auto; }

  /* ─── Library tab fills viewport ──────────────────────────── */
  #tab-library { display: none; flex-direction: column; height: 100%; overflow: hidden; }
  #tab-library.active { display: flex; }

  /* ─── Settings section ─────────────────────────────────────── */
  .settings-section { margin-top: 24px; }
  .settings-section-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
  .settings-section-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 12px; }
  ```

- [ ] **Step 2: Verify visual rendering**

  Reload. Check: toolbar has two zones (folder left, buttons right). Stats bar is a slim row below. Filter bar below that. Table fills remaining height and scrolls independently.

- [ ] **Step 3: Commit**

  ```bash
  git add app/static/style.css
  git commit -m "feat(ui): CSS for toolbar, stats bar, approve column, filter bar"
  ```

---

## Task 5: JS — Update switchTab() and Global Init

**Files:**
- Modify: `app/static/app.js`

- [ ] **Step 1: Update switchTab() (~line 97)**

  Replace the existing `switchTab()` body with:

  ```javascript
  function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

    const tab = document.getElementById('tab-' + tabName);
    if (tab) tab.classList.add('active');

    const btn = document.querySelector('.nav-btn[data-tab="' + tabName + '"]');
    if (btn) btn.classList.add('active');

    if (tabName === 'organise') initOrganiseTab();
    if (tabName === 'setplan') initSetPlanTab();
    if (tabName === 'settings') initTaxonomyTab();
    if (tabName === 'library') renderTracks();
  }
  ```

- [ ] **Step 2: Update DOMContentLoaded block**

  Find the `DOMContentLoaded` block at the bottom of `app.js`. Remove calls to `initImportTab()`, `initReviewTab()`, `initStatsTab()`. Add calls to `initLibraryToolbar()` and `checkResumeSession()`:

  ```javascript
  document.addEventListener('DOMContentLoaded', () => {
    initLibraryToolbar();
    initThemeToggle();
    initNavigation();
    startStatsPolling();
    loadTaxonomy();
    renderTracks();
    checkResumeSession();
  });
  ```

- [ ] **Step 3: Update updateStats() to target new DOM IDs (~line 134)**

  Replace the body of `updateStats()` with:

  ```javascript
  function updateStats() {
    apiFetch('/api/stats').then(data => {
      if (!data) return;
      const el = id => document.getElementById(id);
      if (el('stat-total'))       el('stat-total').textContent      = data.total      ?? 0;
      if (el('stat-analyzed'))    el('stat-analyzed').textContent   = data.analyzed   ?? 0;
      if (el('stat-classified'))  el('stat-classified').textContent = data.classified ?? 0;
      if (el('stat-approved'))    el('stat-approved').textContent   = data.approved   ?? 0;
      updateToolbarButtonStates(data);
    }).catch(() => {});
  }
  ```

- [ ] **Step 4: Fix all broken switchTab calls identified in Task 3 Step 5**

  Use the line numbers from the grep output. Apply these replacements:
  - `switchTab('import')` → `switchTab('library')`
  - `switchTab('tracks')` → `switchTab('library')`
  - `switchTab('review')` → `switchTab('library')`
  - `switchTab('stats')` → `switchTab('library')`
  - `switchTab('taxonomy')` → `switchTab('settings')`
  - `switchTab('setlist')` → `switchTab('setplan')`

  Verify nothing remains:
  ```bash
  grep -n "switchTab" /home/ubuntu/dj-library-manager/app/static/app.js
  ```
  Expected output contains only: `library`, `organise`, `setplan`, `settings`.

- [ ] **Step 5: Commit**

  ```bash
  git add app/static/app.js
  git commit -m "feat(ui): update switchTab and DOMContentLoaded for 4-tab layout"
  ```

---

## Task 6: JS — initLibraryToolbar()

**Files:**
- Modify: `app/static/app.js`

- [ ] **Step 1: Add initLibraryToolbar() and helpers**

  Add these functions after the `updateStats()` block:

  ```javascript
  function initLibraryToolbar() {
    const folderDisplay  = document.getElementById('folder-display');
    const folderInput    = document.getElementById('folder-input');
    const btnChange      = document.getElementById('btn-change-folder');
    const btnImport      = document.getElementById('btn-import');
    const btnAnalyze     = document.getElementById('btn-analyze');
    const btnClassify    = document.getElementById('btn-classify');
    const btnWriteTags   = document.getElementById('btn-write-tags');
    const btnBulkApprove = document.getElementById('btn-bulk-approve-toolbar');
    const btnGetStarted  = document.getElementById('btn-get-started');

    function showFolderInput() {
      if (folderInput)  folderInput.style.display  = 'inline-block';
      if (btnImport)    btnImport.style.display    = 'inline-block';
      if (folderInput)  folderInput.focus();
    }

    if (btnGetStarted) btnGetStarted.addEventListener('click', showFolderInput);
    if (btnChange)     btnChange.addEventListener('click', showFolderInput);

    if (folderInput) {
      folderInput.addEventListener('keydown', e => { if (e.key === 'Enter') doImport(); });
    }
    if (btnImport) btnImport.addEventListener('click', doImport);

    async function doImport() {
      const folder = folderInput ? folderInput.value.trim() : '';
      if (!folder) return;
      if (folderInput)  folderInput.style.display  = 'none';
      if (btnImport)    btnImport.style.display    = 'none';
      if (folderDisplay) folderDisplay.textContent = folder;
      showSpinner();
      try {
        const result = await apiFetch('/api/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ folder_path: folder })
        });
        if (result && result.tracks) {
          window.tracks = result.tracks;
          renderTracks();
          updateStats();
          updateToolbarButtonStates();
          showToast(result.count + ' tracks imported — click Analyze All to extract BPM & key', 'success');
          apiFetch('/api/session/save', { method: 'POST' }).catch(() => {});
        }
      } catch (e) {
        showToast('Import failed: ' + e.message, 'error');
      } finally {
        hideSpinner();
      }
    }

    if (btnAnalyze) {
      btnAnalyze.addEventListener('click', async () => {
        btnAnalyze.disabled = true;
        showProgressInStatsBar('Analyzing audio...');
        try {
          const result = await apiFetch('/api/analyze', { method: 'POST' });
          if (result) {
            window.tracks = result.tracks || window.tracks;
            renderTracks();
            updateStats();
            showToast('Analysis complete', 'success');
          }
        } catch (e) {
          showToast('Analysis failed: ' + e.message, 'error');
          btnAnalyze.disabled = false;
        } finally {
          hideProgressInStatsBar();
          updateToolbarButtonStates();
        }
      });
    }

    if (btnClassify) {
      btnClassify.addEventListener('click', async () => {
        btnClassify.disabled = true;
        showProgressInStatsBar('Classifying genres...');
        try {
          const result = await apiFetch('/api/classify', { method: 'POST' });
          if (result) {
            window.tracks = result.tracks || window.tracks;
            renderTracks();
            updateStats();
            showToast('Classification complete', 'success');
          }
        } catch (e) {
          showToast('Classification failed: ' + e.message, 'error');
          btnClassify.disabled = false;
        } finally {
          hideProgressInStatsBar();
          updateToolbarButtonStates();
        }
      });
    }

    if (btnBulkApprove) {
      btnBulkApprove.addEventListener('click', async () => {
        const thresholdEl = document.getElementById('toolbar-threshold');
        const threshold = parseInt(thresholdEl ? thresholdEl.textContent : '80');
        try {
          const result = await apiFetch('/api/review/bulk-approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ threshold })
          });
          if (result) {
            window.tracks = result.tracks || window.tracks;
            renderTracks();
            updateStats();
            showToast((result.approved_count ?? '') + ' tracks approved', 'success');
          }
        } catch (e) {
          showToast('Bulk approve failed: ' + e.message, 'error');
        }
      });
    }

    if (btnWriteTags) {
      btnWriteTags.addEventListener('click', async () => {
        btnWriteTags.disabled = true;
        showProgressInStatsBar('Writing tags...');
        try {
          const result = await apiFetch('/api/review/write', { method: 'POST' });
          if (result) {
            window.tracks = result.tracks || window.tracks;
            renderTracks();
            updateStats();
            showToast('Tags written successfully', 'success');
          }
        } catch (e) {
          showToast('Write failed: ' + e.message, 'error');
          btnWriteTags.disabled = false;
        } finally {
          hideProgressInStatsBar();
          updateToolbarButtonStates();
        }
      });
    }
  }

  function updateToolbarButtonStates(stats) {
    const s = stats || {};
    const total      = s.total      ?? window.tracks.length;
    const analyzed   = s.analyzed   ?? window.tracks.filter(t => t.final_bpm).length;
    const classified = s.classified ?? window.tracks.filter(t => t.final_genre && t.final_genre !== 'Unknown').length;
    const approved   = s.approved   ?? window.tracks.filter(t => t.review_status === 'approved').length;

    const btnAnalyze     = document.getElementById('btn-analyze');
    const btnClassify    = document.getElementById('btn-classify');
    const btnBulkApprove = document.getElementById('btn-bulk-approve-toolbar');
    const btnWriteTags   = document.getElementById('btn-write-tags');

    if (btnAnalyze)     btnAnalyze.disabled     = total      === 0;
    if (btnClassify)    btnClassify.disabled     = analyzed   === 0;
    if (btnBulkApprove) btnBulkApprove.disabled  = classified === 0;
    if (btnWriteTags)   btnWriteTags.disabled     = approved   === 0;
  }

  function showProgressInStatsBar(text) {
    const sep  = document.getElementById('stat-progress-sep');
    const wrap = document.getElementById('stat-progress-wrap');
    const txt  = document.getElementById('stat-progress-text');
    if (sep)  sep.style.display  = 'inline';
    if (wrap) wrap.style.display = 'flex';
    if (txt)  txt.textContent    = text;
  }

  function hideProgressInStatsBar() {
    const sep  = document.getElementById('stat-progress-sep');
    const wrap = document.getElementById('stat-progress-wrap');
    if (sep)  sep.style.display  = 'none';
    if (wrap) wrap.style.display = 'none';
  }

  function checkResumeSession() {
    apiFetch('/api/session/info').then(data => {
      if (!data || !data.exists) return;
      const banner = document.getElementById('resume-banner');
      const info   = document.getElementById('resume-info');
      if (banner && info) {
        info.textContent = 'Session: ' + (data.count || 0) + ' tracks from ' + (data.folder_path || 'previous session');
        banner.style.display = 'flex';
      }
      const btnResume  = document.getElementById('btn-resume-session');
      const btnDismiss = document.getElementById('btn-dismiss-session');
      if (btnResume) {
        btnResume.addEventListener('click', async () => {
          const result = await apiFetch('/api/session/load', { method: 'POST' });
          if (result) {
            window.tracks = result.tracks || [];
            renderTracks();
            updateStats();
            updateToolbarButtonStates();
            if (banner) banner.style.display = 'none';
            showToast('Session resumed', 'success');
          }
        });
      }
      if (btnDismiss) {
        btnDismiss.addEventListener('click', () => { if (banner) banner.style.display = 'none'; });
      }
    }).catch(() => {});
  }
  ```

- [ ] **Step 2: Replace old initImportTab() with empty stub**

  Find `function initImportTab()` (around line 430). Replace the entire function body with:

  ```javascript
  // initImportTab — replaced by initLibraryToolbar() in v2.4.0
  function initImportTab() {}
  ```

- [ ] **Step 3: Verify import flow**

  Reload. Click "Choose Folder". Enter a valid path. Press Enter or click Import.
  Expected: tracks populate in table, toast "N tracks imported", Analyze All becomes enabled.

- [ ] **Step 4: Commit**

  ```bash
  git add app/static/app.js
  git commit -m "feat(ui): initLibraryToolbar — import, pipeline, session resume, progress"
  ```

---

## Task 7: JS — Inline Approve Column

**Files:**
- Modify: `app/static/app.js`

- [ ] **Step 1: Find the correct approve/status endpoint**

  ```bash
  grep -n "review_status\|approve\|PUT\|PATCH" /home/ubuntu/dj-library-manager/app/routes/review_routes.py /home/ubuntu/dj-library-manager/app/routes/track_routes.py 2>/dev/null | head -20
  ```

  Note the exact endpoint URL and method. This is the endpoint you will call when the user clicks the approve button.

- [ ] **Step 2: Add approve cell to renderTracks()**

  Find `renderTracks()` (around line 956). In the row-building section, just before the final action buttons cell is appended to `tr`, add an approve cell. The exact insertion point is after the status badge `<td>` is built and appended:

  ```javascript
  // Approve cell — add after status td, before action td
  const approveTd = document.createElement('td');
  approveTd.className = 'approve-col';
  if (track.proposed_genre) {
    const approveBtn = document.createElement('button');
    const st = track.review_status;
    approveBtn.className = 'approve-btn' + (st === 'approved' ? ' approved' : st === 'skipped' ? ' skipped' : '');
    approveBtn.textContent = st === 'approved' ? '✓' : st === 'skipped' ? '–' : '✓';
    approveBtn.title = st === 'approved' ? 'Approved — click to undo' : 'Click to approve';
    approveBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const newStatus = track.review_status === 'approved' ? 'pending' : 'approved';
      // Use the endpoint found in Step 1. Common pattern:
      // PUT /api/tracks/<path:file_path>  body: { review_status: newStatus }
      try {
        await apiFetch('/api/tracks/' + encodeURIComponent(track.file_path), {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ review_status: newStatus })
        });
        const found = window.tracks.find(x => x.file_path === track.file_path);
        if (found) found.review_status = newStatus;
        renderTracks();
        updateStats();
        updateToolbarButtonStates();
      } catch (err) {
        showToast('Could not update status', 'error');
      }
    });
    approveTd.appendChild(approveBtn);
  } else {
    const dash = document.createElement('span');
    dash.style.cssText = 'color:var(--text-placeholder);font-size:11px;';
    dash.textContent = '—';
    approveTd.appendChild(dash);
  }
  tr.appendChild(approveTd);
  ```

  If the endpoint found in Step 1 differs from `PUT /api/tracks/<path>`, update the URL accordingly.

- [ ] **Step 3: Verify inline approve works**

  Import tracks, run Classify All, click ✓ on a row. Expected: button turns green, approved count in stats bar increments, Write Tags button becomes enabled.

- [ ] **Step 4: Commit**

  ```bash
  git add app/static/app.js
  git commit -m "feat(ui): inline approve/unapprove per track row"
  ```

---

## Task 8: JS — Wire SSE Progress to Stats Bar

**Files:**
- Modify: `app/static/app.js`

- [ ] **Step 1: Find existing SSE progress handlers**

  ```bash
  grep -n "EventSource\|onmessage\|progress-bar\|status-message\|sse\|SSE" /home/ubuntu/dj-library-manager/app/static/app.js | head -20
  ```

  Note every line number. There are likely handlers inside the old analyze/classify button listeners.

- [ ] **Step 2: Update SSE handlers to call stats bar functions**

  For every SSE message handler that updates a progress bar, replace the old DOM update with:

  ```javascript
  // Replace old progress bar / status message update:
  // document.getElementById('progress-bar').style.width = pct + '%';
  // document.getElementById('status-message').textContent = msg;
  
  // New:
  const pct = data.percent ?? (data.total ? Math.round((data.current / data.total) * 100) : 0);
  showProgressInStatsBar((data.current ?? 0) + ' / ' + (data.total ?? 0) + ' ' + (data.step || ''));
  const fill = document.getElementById('stat-progress-fill');
  if (fill) fill.style.width = pct + '%';
  ```

  For the completion event (typically `data.status === 'complete'` or `data.type === 'done'`):

  ```javascript
  hideProgressInStatsBar();
  const fill = document.getElementById('stat-progress-fill');
  if (fill) fill.style.width = '0%';
  updateStats();
  updateToolbarButtonStates();
  ```

- [ ] **Step 3: Remove references to old progress DOM IDs**

  ```bash
  grep -n "progress-bar\|status-message\|import-progress" /home/ubuntu/dj-library-manager/app/static/app.js | head -10
  ```

  Delete or comment out any remaining references — those elements no longer exist.

- [ ] **Step 4: Commit**

  ```bash
  git add app/static/app.js
  git commit -m "feat(ui): SSE progress routed to stats bar"
  ```

---

## Task 9: Version Bump + End-to-End Verification

**Files:**
- Modify: `VERSION`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Bump version**

  ```bash
  echo "2.4.0" > /home/ubuntu/dj-library-manager/VERSION
  ```

- [ ] **Step 2: Prepend CHANGELOG entry**

  Add to top of `CHANGELOG.md` (after the `# Changelog` header):

  ```markdown
  ## [2.4.0] — 2026-04-05

  ### UI Redesign — Single Library View
  - **Sidebar trimmed to 4 items** — Library, Organise, Set Planner, Settings
  - **Library toolbar** — folder picker + Analyze All + Classify All + Approve ≥N% + Write Tags on one row
  - **Inline stats bar** — total/analyzed/classified/approved always visible; progress bar appears during pipeline runs
  - **Inline approve column** — approve/unapprove per row, no Review tab needed
  - **Removed standalone tabs** — Import, Review, Stats, Taxonomy, Setlist, Wheel, Duplicates; content folded into Library / Settings / Set Planner / Organise
  - **No backend changes** — all API routes unchanged
  ```

- [ ] **Step 3: End-to-end verification checklist**

  Work through each item. Fix before committing if any fail.

  1. ☐ App opens → Library tab shows immediately, 4 sidebar items
  2. ☐ "Choose Folder" → enter path → tracks populate without leaving the screen
  3. ☐ Analyze All runs → stats bar shows progress → BPM/key fills in rows
  4. ☐ Classify All runs → genre badges appear in rows
  5. ☐ ✓ button on classified row → turns green, approved count increments
  6. ☐ Write Tags runs → completes, toast shown
  7. ☐ Settings → Taxonomy section visible and editable
  8. ☐ Organise → Duplicate Detector section visible
  9. ☐ Set Planner → Manual Setlist section visible
  10. ☐ Audio preview ▶ still works per row
  11. ☐ Edit modal (…) still opens with full metadata
  12. ☐ Session resume banner appears on reload if tracks were imported

- [ ] **Step 4: Commit**

  ```bash
  git add VERSION CHANGELOG.md
  git commit -m "chore: bump to v2.4.0 — single library view UI redesign"
  ```

