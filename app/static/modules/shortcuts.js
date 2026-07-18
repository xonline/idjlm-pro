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
// For simple keys (no modifiers): 'a', 'r', 'e', 'x', 'arrowup', 'arrowdown', 'space', etc.

const _globalShortcuts = {};
const _globalShortcutMeta = {}; // key -> { key, description, context, handler }

function registerGlobalShortcut(key, handler, meta) {
  _globalShortcuts[key] = handler;
  if (meta) {
    _globalShortcutMeta[key] = meta;
  }
}

function getGlobalShortcutMeta() {
  return _globalShortcutMeta;
}

// Initialise the registry listener once - handles ALL registered shortcuts
document.addEventListener('keydown', (e) => {
  // Skip if focus is in an input/textarea/select
  const tag = (e.target.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable) return;

  // Build key identifier
  let keyId = '';
  if (e.ctrlKey || e.metaKey) keyId += 'ctrl+';
  if (e.altKey) keyId += 'alt+';
  if (e.shiftKey) keyId += 'shift+';
  keyId += e.key.toLowerCase();

  // Also try without modifiers for simple keys
  const simpleKey = e.key.toLowerCase();

  // Check exact match first (with modifiers)
  if (_globalShortcuts[keyId]) {
    e.preventDefault();
    _globalShortcuts[keyId]();
    return;
  }

  // Check simple key match (for keys registered without modifiers)
  if (!_globalShortcuts[simpleKey]) return;
  // Only trigger simple keys if no modifiers are pressed (except shift which we handle)
  if (!e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault();
    _globalShortcuts[simpleKey]();
  }
});

// ============================================================================
// Keyboard shortcuts for track table (Phase 2: handled by tracks.js)
// ============================================================================
// ArrowUp/ArrowDown/Space/a/r/e/x now handled by tracks.js keyboard v2.
// This module only provides the MutationObserver for backward compat.
(function initKeyboardNav() {
  const tbody = document.getElementById('tracks-tbody');
  if (tbody) {
    const observer = new MutationObserver(() => {});
    observer.observe(tbody, { childList: true });
  }
})();

// ============================================================================
// Keyboard Shortcuts Reference Modal
// ============================================================================

function showKeyboardShortcuts() {
  const modal = document.getElementById('shortcuts-modal');
  if (!modal) return;
  
  // Build shortcuts list from registry
  const meta = getGlobalShortcutMeta();
  const sections = {};
  
  // Group by context
  Object.values(meta).forEach(m => {
    const ctx = m.context || 'General';
    if (!sections[ctx]) sections[ctx] = [];
    sections[ctx].push(m);
  });
  
  // Always include the hardcoded global shortcuts for ? / Cmd+/ etc
  if (!sections['Global']) sections['Global'] = [];
  
  let html = '';
  for (const [ctx, items] of Object.entries(sections)) {
    html += `<div class="shortcut-group"><div class="shortcut-group-heading">${ctx}</div><div class="shortcut-group-items">`;
    for (const item of items) {
      html += `<div class="shortcut-row"><span class="shortcut-key">${formatKey(item.key)}</span><span class="shortcut-desc">${item.description}</span></div>`;
    }
    html += '</div></div>';
  }
  
  const body = modal.querySelector('.modal-body');
  if (body) body.innerHTML = html;
  
  modal.style.display = 'flex';
}

function formatKey(key) {
  return key
    .replace('ctrl+', '⌘')
    .replace('alt+', '⌥')
    .replace('shift+', '⇧')
    .replace('arrowup', '↑')
    .replace('arrowdown', '↓')
    .replace('arrowleft', '←')
    .replace('arrowright', '→')
    .toUpperCase();
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
window.getGlobalShortcutMeta = getGlobalShortcutMeta;
