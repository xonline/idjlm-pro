// ============================================================================
// shortcuts.js — Keyboard shortcuts (track-table nav, review, global hotkeys)
// ============================================================================
// Extracted from pipeline.js (Phase 0.3). No behaviour change.
// Owns:
//   - initKeyboardNav: ArrowUp/ArrowDown/Space row-navigation on tracks table
//                     MutationObserver to re-apply selection across renderTracks()
//   - showKeyboardShortcuts / initKeyboardShortcuts: review-tab nav, global hotkeys
//   - registerGlobalShortcut: single registry for cross-module hotkeys (4.2)
// Load order: any. Independent of other modules.
// ----------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Global shortcut registry (single handler per key-combo — Phase 4.2)
// ---------------------------------------------------------------------------
// Modules call registerGlobalShortcut('cmdf', handlerFn) to register
// a callback. This avoids multiple keydown listeners on the same combo.
// Keys: 'cmdf' (Cmd+F / Ctrl+F), 'cmdk' (Cmd+K), etc.

const _globalShortcuts = {};

function registerGlobalShortcut(key, handler) {
  _globalShortcuts[key] = handler;
}

// Initialise the registry listener once
document.addEventListener('keydown', (e) => {
  // Cmd+F / Ctrl+F → global search popup
  if ((e.metaKey || e.ctrlKey) && (e.key === 'f' || e.key === 'F')) {
    // Do NOT intercept when focus is inside an input/textarea
    const tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) return;
    if (_globalShortcuts['cmdf']) {
      e.preventDefault();
      _globalShortcuts['cmdf']();
    }
  }
});

// ============================================================================
// Keyboard shortcuts for track table
// ============================================================================
// Space = approve/unapprove selected row
// ArrowUp / ArrowDown = navigate rows
(function initKeyboardNav() {
  let selectedIdx = -1;

  function getRows() {
    return Array.from(document.querySelectorAll('#tracks-tbody tr:not(.empty-state)'));
  }

  function selectRow(idx) {
    const rows = getRows();
    rows.forEach(r => r.classList.remove('row-selected'));
    if (idx < 0 || idx >= rows.length) { selectedIdx = -1; return; }
    selectedIdx = idx;
    rows[idx].classList.add('row-selected');
    rows[idx].scrollIntoView({ block: 'nearest' });
  }

  document.addEventListener('keydown', e => {
    // Ignore when typing in an input/textarea
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

    const rows = getRows();
    if (!rows.length) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectRow(Math.min(selectedIdx + 1, rows.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectRow(Math.max(selectedIdx - 1, 0));
    } else if (e.key === ' ' && selectedIdx >= 0) {
      e.preventDefault();
      const approveBtn = rows[selectedIdx].querySelector('.approve-btn');
      if (approveBtn) approveBtn.click();
    }
  });

  // Re-select same logical row after renderTracks() re-draws the table
  const origRender = window.renderTracks;
  if (typeof origRender === 'function') {
    // renderTracks is already defined — patch it
    const _orig = window.renderTracks || renderTracks;
  }
  // Hook via MutationObserver instead (renderTracks rebuilds innerHTML)
  const observer = new MutationObserver(() => {
    const rows = getRows();
    if (selectedIdx >= 0 && selectedIdx < rows.length) {
      rows[selectedIdx].classList.add('row-selected');
    }
  });
  const tbody = document.getElementById('tracks-tbody');
  if (tbody) observer.observe(tbody, { childList: true });
})();

// ============================================================================
// Keyboard Shortcuts Reference Modal
// ============================================================================

function showKeyboardShortcuts() {
  const modal = document.getElementById('shortcuts-modal');
  if (modal) modal.style.display = 'flex';
}

// ============================================================================
// Keyboard Shortcuts (review tab + global)
// ============================================================================

function initKeyboardShortcuts() {
  // Shortcuts modal: close handlers
  const shortcutsModal = document.getElementById('shortcuts-modal');
  const shortcutsCloseBtn = document.getElementById('shortcuts-close');
  const shortcutsDoneBtn = document.getElementById('shortcuts-done');

  const hideShortcutsModal = () => { if (shortcutsModal) shortcutsModal.style.display = 'none'; };
  if (shortcutsCloseBtn) shortcutsCloseBtn.addEventListener('click', hideShortcutsModal);
  if (shortcutsDoneBtn) shortcutsDoneBtn.addEventListener('click', hideShortcutsModal);
  if (shortcutsModal) {
    shortcutsModal.addEventListener('click', (e) => {
      if (e.target === shortcutsModal) hideShortcutsModal();
    });
  }

  // Show hints in review tab
  const reviewTab = document.getElementById('tab-review');
  let hintsAdded = false;

  const reviewBtn = document.querySelector('[data-tab="review"]');
  if (reviewBtn) {
    reviewBtn.addEventListener('click', () => {
      if (!hintsAdded) {
        const header = reviewTab.querySelector('.tab-header');
        const hints = document.createElement('div');
        hints.className = 'keyboard-hints';
        hints.innerHTML = `
          <div class="keyboard-hints-grid">
            <div class="keyboard-hint-item"><span class="keyboard-hint-key">↓/j</span> <span>Next</span></div>
            <div class="keyboard-hint-item"><span class="keyboard-hint-key">↑/k</span> <span>Prev</span></div>
            <div class="keyboard-hint-item"><span class="keyboard-hint-key">a</span> <span>Approve</span></div>
            <div class="keyboard-hint-item"><span class="keyboard-hint-key">s</span> <span>Skip</span></div>
            <div class="keyboard-hint-item"><span class="keyboard-hint-key">Space</span> <span>Play/Pause</span></div>
          </div>
        `;
        header.parentNode.insertBefore(hints, header.nextSibling);
        hintsAdded = true;
      }
    });
  }

  document.addEventListener('keydown', (e) => {
    const reviewTab = document.getElementById('tab-review');
    if (!reviewTab.classList.contains('active')) return;

    const items = document.querySelectorAll('.review-item');
    const currentBtn = document.querySelector('.review-item:first-child [data-approve-btn]');

    if (e.code === 'ArrowDown' || e.key === 'j') {
      e.preventDefault();
      // Next track
    } else if (e.code === 'ArrowUp' || e.key === 'k') {
      e.preventDefault();
      // Previous track
    } else if (e.key === 'a' || e.code === 'Enter') {
      e.preventDefault();
      const btn = document.querySelector('.review-item:first-child [data-approve-btn]');
      if (btn) btn.click();
    } else if (e.key === 's' || e.code === 'Delete' || e.code === 'Backspace') {
      e.preventDefault();
      const btn = document.querySelector('.review-item:first-child [data-skip-btn]');
      if (btn) btn.click();
    } else if (e.code === 'Space') {
      e.preventDefault();
      document.getElementById('audio-play-pause').click();
    }
  });

  // Global shortcut: ? or Cmd+/ to open keyboard shortcuts reference
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const shortcutsModal = document.getElementById('shortcuts-modal');
      if (shortcutsModal && shortcutsModal.style.display !== 'none') {
        shortcutsModal.style.display = 'none';
        return;
      }
    }
    if ((e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey) ||
        (e.key === '/' && (e.ctrlKey || e.metaKey))) {
      // Don't trigger when typing in an input/textarea
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag !== 'input' && tag !== 'textarea' && !e.target.isContentEditable) {
        e.preventDefault();
        showKeyboardShortcuts();
      }
    }
    // Single / to focus search (when not in an input)
    if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag !== 'input' && tag !== 'textarea' && !e.target.isContentEditable) {
        const searchInput = document.getElementById('search-tracks');
        if (searchInput) {
          e.preventDefault();
          searchInput.focus();
        }
      }
    }
    // Number keys 1-4 for tab switching
    const tabMap = { '1': 'library', '2': 'organise', '3': 'setplan', '4': 'settings' };
    if (tabMap[e.key] && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag !== 'input' && tag !== 'textarea' && !e.target.isContentEditable) {
        e.preventDefault();
        switchTab(tabMap[e.key]);
      }
    }
    // Ctrl+S to save session
    if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag !== 'input' && tag !== 'textarea' && !e.target.isContentEditable) {
        e.preventDefault();
        apiFetch('/api/session/save', { method: 'POST' }).then(() => {
          showToast('Session saved', 'success');
        }).catch(() => {});
      }
    }
  });
}


// --- ES module bridge (0.4): expose to global scope for cross-module calls ---
window.initKeyboardShortcuts = initKeyboardShortcuts;
window.showKeyboardShortcuts = showKeyboardShortcuts;
window.registerGlobalShortcut = registerGlobalShortcut;
