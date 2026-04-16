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
let statsInterval = null;
let currentEditPath = null;
let currentAudioPlayer = null;
let isWatching = false;
let watchPollInterval = null;
let searchDebounceTimer = null;
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
