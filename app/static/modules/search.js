// ============================================================================
// search.js — Track search + global Cmd+F popup (Phase 4.2)
// ============================================================================
// Two surfaces:
//   1. initSearchFeature()  — existing filter-bar track search (debounced server)
//   2. initGlobalSearch()   — Cmd+F / Ctrl+F overlay popup with grouped results
//     (Tracks / Playlists / Setlists), arrow-key nav, Enter reveals, Esc closes.
//
// The popup queries:
//   - Library tracks  → /api/tracks/search?q=...
//   - Saved playlists → /api/playlists (filter by name client-side)
//   - Current setlist  → window.setlist (client-side)
// Selection reveals the item in its home view (Library / Playlists / Setlist tab).
// ----------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// 1. Existing filter-bar search (server-side, debounced)
// ---------------------------------------------------------------------------

function initSearchFeature() {
  const searchInput = document.getElementById('search-tracks');
  const searchClearBtn = document.getElementById('search-clear');

  if (!searchInput) return;

  searchInput.addEventListener('input', (e) => {
    clearTimeout(window.searchDebounceTimer);
    const query = e.target.value;

    if (searchClearBtn) {
      searchClearBtn.style.display = query ? 'block' : 'none';
    }

    window.searchDebounceTimer = setTimeout(async () => {
      const trimmed = query.trim();
      if (!trimmed) {
        window.searchResults = null;
        renderTracks();
        return;
      }

      const searchLabel = searchInput.placeholder;
      searchInput.placeholder = 'Searching...';

      try {
        const data = await apiFetch('/api/tracks/search?q=' + encodeURIComponent(trimmed));
        window.searchResults = data.tracks || [];
        renderTracks();
      } catch (err) {
        window.searchResults = null;
        renderTracks();
      } finally {
        searchInput.placeholder = searchLabel || 'Search tracks...';
      }
    }, 300);
  });

  if (searchClearBtn) {
    searchClearBtn.addEventListener('click', () => {
      searchInput.value = '';
      window.searchResults = null;
      renderTracks();
      if (searchClearBtn) searchClearBtn.style.display = 'none';
    });
  }
}


// ---------------------------------------------------------------------------
// 2. Global Cmd+F search popup (Phase 4.2 — Lexicon pattern)
// ---------------------------------------------------------------------------

let _gsState = null;
let _gsDebounce = null;

function initGlobalSearch() {
  // Build overlay DOM once
  if (!document.getElementById('global-search-overlay')) {
    _buildGlobalSearchDOM();
  }

  _gsState = {
    query: '',
    results: { tracks: [], playlists: [], setlist: [] },
    flatItems: [],   // ordered list for arrow navigation
    selectedIdx: -1,
    open: false,
    previouslyFocused: null,
  };

  // Register hotkey via the single global keydown handler in shortcuts.js
  if (typeof registerGlobalShortcut === 'function') {
    registerGlobalShortcut('cmdf', openGlobalSearch);
  } else {
    // Fallback: register directly (shortcuts.js not loaded yet in dev)
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'f') {
        const tag = (e.target.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) return;
        e.preventDefault();
        openGlobalSearch();
      }
    });
  }
}

function _buildGlobalSearchDOM() {
  // Inject the DOM once into the help
  const overlay = document.createElement('div');
  overlay.id = 'global-search-overlay';
  overlay.className = 'gs-overlay';
  overlay.style.display = 'none';
  overlay.innerHTML = `
    <div class="gs-popup">
      <div class="gs-input-wrap">
        <svg class="gs-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input type="text" id="gs-input" class="gs-input" placeholder="Search library, playlists, setlists..." autocomplete="off" spellcheck="false" />
        <kbd class="gs-esc-hint">ESC</kbd>
      </div>
      <div class="gs-results" id="gs-results">
        <div class="gs-empty">Type to search across your library, playlists, and setlist...</div>
      </div>
      <div class="gs-footer">
        <span class="gs-footer-item"><kbd>↑</kbd><kbd>↓</kbd> Navigate</span>
        <span class="gs-footer-item"><kbd>↵</kbd> Open</span>
        <span class="gs-footer-item"><kbd>ESC</kbd> Close</span>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  const input = overlay.querySelector('#gs-input');

  // Input → debounced search
  input.addEventListener('input', () => {
    clearTimeout(_gsDebounce);
    _gsDebounce = setTimeout(() => _runGlobalSearch(input.value), 200);
  });

  // Keyboard navigation within the popup input
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      _gsMoveSelection(1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      _gsMoveSelection(-1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      _gsActivateSelection();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closeGlobalSearch();
    }
  });

  // Click on overlay backdrop closes
  overlay.addEventListener('mousedown', (e) => {
    if (e.target === overlay) closeGlobalSearch();
  });
}

function openGlobalSearch() {
  if (!_gsState) return;
  const overlay = document.getElementById('global-search-overlay');
  if (!overlay) return;

  // Store currently focused element to restore on close
  _gsState.previouslyFocused = document.activeElement;
  _gsState.open = true;

  overlay.style.display = 'flex';
  const input = document.getElementById('gs-input');
  if (input) {
    input.value = '';
    input.focus();
  }

  // Reset results
  _gsState.results = { tracks: [], playlists: [], setlist: [] };
  _gsState.flatItems = [];
  _gsState.selectedIdx = -1;
  _renderGlobalSearchResults();
}

function closeGlobalSearch() {
  if (!_gsState) return;
  const overlay = document.getElementById('global-search-overlay');
  if (overlay) overlay.style.display = 'none';

  _gsState.open = false;
  _gsState.selectedIdx = -1;

  // Restore focus to whatever was focused before opening
  if (_gsState.previouslyFocused) {
    try {
      _gsState.previouslyFocused.focus({ preventScroll: true });
    } catch (_) {
      _gsState.previouslyFocused.focus();
    }
    _gsState.previouslyFocused = null;
  }
}

async function _runGlobalSearch(query) {
  if (!_gsState) return;
  const trimmed = (query || '').trim();
  _gsState.query = trimmed;

  if (!trimmed) {
    _gsState.results = { tracks: [], playlists: [], setlist: [] };
    _gsState.flatItems = [];
    _gsState.selectedIdx = -1;
    _renderGlobalSearchResults();
    return;
  }

  const qLower = trimmed.toLowerCase();

  // 1. Tracks — server-side search
  let tracks = [];
  try {
    const data = await apiFetch('/api/tracks/search?q=' + encodeURIComponent(trimmed));
    tracks = (data.tracks || []).slice(0, 20);
  } catch (_) {
    tracks = [];
  }

  // 2. Playlists — fetch all, filter by name client-side
  let playlists = [];
  try {
    const data = await apiFetch('/api/playlists');
    playlists = (data.playlists || []).filter(p =>
      p.name && p.name.toLowerCase().includes(qLower)
    ).slice(0, 10);
  } catch (_) {
    playlists = [];
  }

  // 3. Setlist — client-side search against window.setlist track names
  let setlistMatches = [];
  if (window.setlist && window.setlist.length) {
    setlistMatches = window.setlist.filter(t => {
      const title = (t.display_title || '').toLowerCase();
      const artist = (t.display_artist || '').toLowerCase();
      return title.includes(qLower) || artist.includes(qLower);
    }).slice(0, 10);
  }

  _gsState.results = { tracks, playlists, setlist: setlistMatches };

  // Build flat ordered list for keyboard navigation
  const flat = [];
  tracks.forEach(t => flat.push({ type: 'track', data: t }));
  playlists.forEach(p => flat.push({ type: 'playlist', data: p }));
  setlistMatches.forEach(t => flat.push({ type: 'setlist', data: t }));
  _gsState.flatItems = flat;
  _gsState.selectedIdx = flat.length > 0 ? 0 : -1;

  _renderGlobalSearchResults();
}

function _renderGlobalSearchResults() {
  const container = document.getElementById('gs-results');
  if (!container) return;

  const { tracks, playlists, setlist } = _gsState.results;

  if (!tracks.length && !playlists.length && !setlist.length) {
    if (_gsState.query) {
      container.innerHTML = '<div class="gs-empty">No results for "' + escapeHtml(_gsState.query) + '"</div>';
    } else {
      container.innerHTML = '<div class="gs-empty">Type to search across your library, playlists, and setlist...</div>';
    }
    return;
  }

  let html = '';
  let idx = 0;

  // Tracks group
  if (tracks.length) {
    html += '<div class="gs-group"><div class="gs-group-label">TRACKS <span class="gs-group-count">' + tracks.length + '</span></div>';
    tracks.forEach(track => {
      const selected = idx === _gsState.selectedIdx ? ' gs-item-selected' : '';
      const subtitle = escapeHtml(track.display_artist || '—') +
        (track.final_genre ? ' · ' + escapeHtml(track.final_genre) : '') +
        (track.final_bpm ? ' · ' + parseFloat(track.final_bpm).toFixed(1) + ' BPM' : '') +
        (track.final_key ? ' · ' + escapeHtml(track.final_key) : '');
      html += '<div class="gs-item' + selected + '" data-idx="' + idx + '" data-type="track">' +
        '<span class="gs-item-icon">🎵</span>' +
        '<div class="gs-item-body">' +
          '<div class="gs-item-title">' + escapeHtml(track.display_title || 'Unknown') + '</div>' +
          '<div class="gs-item-sub">' + subtitle + '</div>' +
        '</div></div>';
      idx++;
    });
    html += '</div>';
  }

  // Playlists group
  if (playlists.length) {
    html += '<div class="gs-group"><div class="gs-group-label">PLAYLISTS <span class="gs-group-count">' + playlists.length + '</span></div>';
    playlists.forEach(pl => {
      const selected = idx === _gsState.selectedIdx ? ' gs-item-selected' : '';
      html += '<div class="gs-item' + selected + '" data-idx="' + idx + '" data-type="playlist">' +
        '<span class="gs-item-icon">🎶</span>' +
        '<div class="gs-item-body">' +
          '<div class="gs-item-title">' + escapeHtml(pl.name || 'Untitled') + '</div>' +
          '<div class="gs-item-sub">Playlist · ' + (pl.track_count || 0) + ' tracks</div>' +
        '</div></div>';
      idx++;
    });
    html += '</div>';
  }

  // Setlist group
  if (setlist.length) {
    html += '<div class="gs-group"><div class="gs-group-label">SETLIST <span class="gs-group-count">' + setlist.length + '</span></div>';
    setlist.forEach(track => {
      const selected = idx === _gsState.selectedIdx ? ' gs-item-selected' : '';
      const pos = window.setlist.findIndex(t => t.file_path === track.file_path);
      const subtitle = escapeHtml(track.display_artist || '—') +
        (track.final_key ? ' · ' + escapeHtml(track.final_key) : '') +
        (track.final_bpm ? ' · ' + parseFloat(track.final_bpm).toFixed(1) + ' BPM' : '') +
        (pos >= 0 ? ' · #' + (pos + 1) : '');
      html += '<div class="gs-item' + selected + '" data-idx="' + idx + '" data-type="setlist">' +
        '<span class="gs-item-icon">🎺</span>' +
        '<div class="gs-item-body">' +
          '<div class="gs-item-title">' + escapeHtml(track.display_title || 'Unknown') + '</div>' +
          '<div class="gs-item-sub">' + subtitle + '</div>' +
        '</div></div>';
      idx++;
    });
    html += '</div>';
  }

  container.innerHTML = html;

  // Wire click handlers
  container.querySelectorAll('.gs-item').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const i = parseInt(el.dataset.idx);
      _gsState.selectedIdx = i;
      _gsActivateSelection();
    });
    el.addEventListener('mouseenter', () => {
      const i = parseInt(el.dataset.idx);
      _gsState.selectedIdx = i;
      _updateSelectionVisual();
    });
  });
}

function _updateSelectionVisual() {
  const container = document.getElementById('gs-results');
  if (!container) return;
  container.querySelectorAll('.gs-item').forEach(el => {
    if (parseInt(el.dataset.idx) === _gsState.selectedIdx) {
      el.classList.add('gs-item-selected');
    } else {
      el.classList.remove('gs-item-selected');
    }
  });
}

function _gsMoveSelection(dir) {
  if (!_gsState || _gsState.flatItems.length === 0) return;
  let next = _gsState.selectedIdx + dir;
  if (next < 0) next = 0;
  if (next >= _gsState.flatItems.length) next = _gsState.flatItems.length - 1;
  _gsState.selectedIdx = next;
  _updateSelectionVisual();

  // Scroll selected into view
  const container = document.getElementById('gs-results');
  if (container) {
    const sel = container.querySelector('.gs-item-selected');
    if (sel) sel.scrollIntoView({ block: 'nearest' });
  }
}

function _gsActivateSelection() {
  if (!_gsState || _gsState.selectedIdx < 0) return;
  const item = _gsState.flatItems[_gsState.selectedIdx];
  if (!item) return;

  closeGlobalSearch();

  if (item.type === 'track') {
    _revealTrack(item.data);
  } else if (item.type === 'playlist') {
    _revealPlaylist(item.data);
  } else if (item.type === 'setlist') {
    _revealSetlistTrack(item.data);
  }
}

function _revealTrack(track) {
  // Switch to Library tab, search for this track, highlight the row
  if (typeof switchTab === 'function') switchTab('library');

  // Use the regular search input to filter — wait for tab switch
  setTimeout(() => {
    const searchInput = document.getElementById('search-tracks');
    if (searchInput) {
      searchInput.value = track.display_title || '';
      searchInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    // Highlight the row after results render
    setTimeout(() => {
      _highlightTrackRow(track);
    }, 600);
  }, 100);
}

function _highlightTrackRow(track) {
  const tbody = document.getElementById('tracks-tbody');
  if (!tbody) return;
  const rows = tbody.querySelectorAll('tr:not(.empty-state)');
  for (const row of rows) {
    const titleEl = row.querySelector('.track-title-text');
    if (titleEl && titleEl.textContent === (track.display_title || '')) {
      row.classList.add('gs-flash');
      row.scrollIntoView({ block: 'center' });
      setTimeout(() => row.classList.remove('gs-flash'), 2000);
      break;
    }
  }
}

function _revealPlaylist(playlist) {
  // Switch to the playlists tab
  if (typeof switchTab === 'function') switchTab('playlists');

  // After the tab renders playlists list, try to select it
  setTimeout(() => {
    const items = document.querySelectorAll('#playlists-list .playlist-item');
    items.forEach(item => {
      const nameEl = item.querySelector('.playlist-item-name');
      if (nameEl && nameEl.textContent === (playlist.name || '')) {
        item.click();
        item.classList.add('gs-flash');
        item.scrollIntoView({ block: 'center' });
        setTimeout(() => item.classList.remove('gs-flash'), 2000);
      }
    });
  }, 400);
}

function _revealSetlistTrack(track) {
  // Switch to Set Planner tab which contains the setlist subpanel
  if (typeof switchTab === 'function') switchTab('setplan');

  setTimeout(() => {
    // Find the track item in the setlist and flash it
    const items = document.querySelectorAll('#setlist-tracks .setlist-track-item');
    const pos = window.setlist.findIndex(t => t.file_path === track.file_path);
    if (pos >= 0 && items[pos]) {
      items[pos].classList.add('gs-flash');
      items[pos].scrollIntoView({ block: 'center' });
      setTimeout(() => items[pos].classList.remove('gs-flash'), 2000);
    }
  }, 200);
}


// --- ES module bridge (0.4): expose to global scope for cross-module calls ---
window.initSearchFeature = initSearchFeature;
window.initGlobalSearch = initGlobalSearch;
window.openGlobalSearch = openGlobalSearch;
window.closeGlobalSearch = closeGlobalSearch;
