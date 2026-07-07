// ============================================================================
// IDJLM Pro — Vanilla JS Application
// ============================================================================

// Global state
window.tracks = [];
window.searchResults = null; // null = no active search; array = server-side search results
window.taxonomy = {};
window.currentSort = { field: 'display_title', direction: 'asc' };
window.setlist = [];
window.selectedTracks = new Set();
window.currentPage = 1;
const TRACKS_PER_PAGE = 100;
window.statsInterval = null;
window.currentEditPath = null;
window.currentAudioPlayer = null;
let isWatching = false;
let watchPollInterval = null;
window.searchDebounceTimer = null;
let chartInstances = {
  genres: null,
  bpm: null,
  years: null,
  keyDist: null,
  energyDist: null,
  decadeDist: null,
  genreEra: null,
  energyTimeline: null,
};

// ============================================================================
// Utility: HTML Escaping & Safe DOM Creation
// ============================================================================

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function createElement(tag, className, content) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (typeof content === 'string') {
    el.textContent = content;
  } else if (content instanceof HTMLElement) {
    el.appendChild(content);
  }
  return el;
}

// ============================================================================
// API Wrapper
// ============================================================================

async function apiFetch(url, options = {}) {
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API error: ${response.status} - ${error}`);
    }

    return await response.json();
  } catch (error) {
    console.error('API fetch error:', error);
    showToast(error.message, 'error');
    throw error;
  }
}

// ============================================================================
// UI Utilities
// ============================================================================

// showSpinner / hideSpinner
// ----------------------------------------------------------------------------
// UI utilities: synchronous-blocking-only.
//
// Use showSpinner ONLY for fast synchronous calls (<2s perceived) where the
// user is waiting on the resolution before the next interaction makes sense.
// Examples that legitimately use it:
//   - Saving settings / taxonomy (editor.js, taxonomy.js, settings.js,
//     classify.js)
//   - Scanning for duplicates (pipeline.js 1322) — sync on session
//   - Removing a single duplicate (pipeline.js 1506) — single track op
//
// For LONG-RUNNING STREAMING OPERATIONS (analysis, classification, tag write,
// cue analysis, setplan generation) use the opsbar:
//   window.opsbar.registerOp({ id, label, kind, onCancel });     // start chip
//   window.opsbar.progress(handle, current, total, message?);    // stream
//   window.opsbar.complete(handle, summary?);                    // success
//   window.opsbar.error(handle, message);                        // failure
//
// See modules/opsbar.js for the full API. The legacy shims
// showProgressInStatsBar / hideProgressInStatsBar are preserved there for
// callers that haven't migrated yet.
// ----------------------------------------------------------------------------

function showSpinner(message = 'Processing...') {
  const overlay = document.getElementById('spinner-overlay');
  const msg = document.getElementById('spinner-message');
  msg.textContent = message;
  overlay.style.display = 'flex';
}

function hideSpinner() {
  const overlay = document.getElementById('spinner-overlay');
  overlay.style.display = 'none';
}

function showToast(message, type = 'info', options = {}) {
  const toast = document.getElementById('toast');
  toast.className = `toast ${type}`;
  toast.textContent = '';

  // Create message span
  const msgSpan = document.createElement('span');
  msgSpan.textContent = message;
  toast.appendChild(msgSpan);

  // Optional action button
  if (options.action && options.onAction) {
    const btn = document.createElement('button');
    btn.className = 'toast-action-btn';
    btn.textContent = options.action;
    btn.addEventListener('click', () => {
      toast.style.display = 'none';
      options.onAction();
    });
    toast.appendChild(btn);
  }

  toast.style.display = 'block';
  const duration = options.duration || 4000;
  setTimeout(() => { toast.style.display = 'none'; }, duration);
}

/** Undo last write — restore tags from backup */
async function undoLastWrite() {
  try {
    const result = await apiFetch('/api/organise/backups/latest', { method: 'GET' });
    if (result && result.backups && result.backups.length > 0) {
      const latestBackup = result.backups[0];
      await apiFetch('/api/organise/backups/' + latestBackup.id + '/restore', { method: 'POST' });
      // Refetch tracks
      const d = await apiFetch('/api/tracks');
      window.tracks = d.tracks || [];
      window.searchResults = null;
      renderTracks();
      updateStats();
      showToast('Tags restored from backup', 'success');
    } else {
      showToast('No backup found — undo not available', 'info');
    }
  } catch (e) {
    showToast('Undo failed: ' + e.message, 'error');
  }
}


window.chartInstances = chartInstances;

// --- ES module bridge (0.4): expose to global scope for cross-module calls ---
window.TRACKS_PER_PAGE = TRACKS_PER_PAGE;
window.apiFetch = apiFetch;
window.createElement = createElement;
window.escapeHtml = escapeHtml;
window.hideSpinner = hideSpinner;
window.showSpinner = showSpinner;
window.showToast = showToast;
window.undoLastWrite = undoLastWrite;
