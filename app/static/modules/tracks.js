// ============================================================================
// Tracks Tab — Phase 2: Pro-grade Track Table
// Virtualized scrolling, customizable columns, mini-waveform, genre stripes,
// inline editing, keyboard layer v2, context menu v2
// ============================================================================

let lastClickedRowIdx = null;
let keyCompatTrack = null;
let visibleRange = { start: 0, end: 0 };
let totalFilteredSorted = [];
let _scrollRAF = null;
let _inlineEditActive = null;

// ---------------------------------------------------------------------------
// Phase 2.2 — Column Definitions & State
// ---------------------------------------------------------------------------
const COLUMN_DEFS = [
  { id: 'check', label: '', width: 32, fixed: true, sortField: null },
  { id: 'art', label: '', width: 34, fixed: true, sortField: null },
  { id: 'waveform', label: 'Wave', width: 80, fixed: false, sortField: null, defaultVisible: true },
  { id: 'title', label: 'Title / Artist', minWidth: 180, fixed: false, sortField: 'display_title', defaultVisible: true },
  { id: 'genre', label: 'Genre', width: 110, fixed: false, sortField: 'final_genre', defaultVisible: true },
  { id: 'subgenre', label: 'Sub-genre', width: 110, fixed: false, sortField: 'final_subgenre', defaultVisible: true },
  { id: 'confidence', label: 'Conf', width: 52, fixed: false, sortField: 'confidence', defaultVisible: true },
  { id: 'bpm', label: 'BPM', width: 68, fixed: false, sortField: 'final_bpm', defaultVisible: true },
  { id: 'key', label: 'Key', width: 56, fixed: false, sortField: 'final_key', defaultVisible: true },
  { id: 'clave', label: 'Clave', width: 46, fixed: false, sortField: 'clave_pattern', defaultVisible: true },
  { id: 'vocal', label: 'Vocal', width: 64, fixed: false, sortField: 'vocal_flag', defaultVisible: true },
  { id: 'tempo', label: 'Tempo', width: 60, fixed: false, sortField: 'tempo_category', defaultVisible: true },
  { id: 'lufs', label: 'LUFS', width: 48, fixed: false, sortField: 'analyzed_lufs', defaultVisible: true },
  { id: 'year', label: 'Year', width: 44, fixed: false, sortField: 'final_year', defaultVisible: true },
  { id: 'status', label: 'Status', width: 70, fixed: false, sortField: 'review_status', defaultVisible: true },
  { id: 'approve', label: '', width: 60, fixed: true, sortField: null },
  { id: 'action', label: '', width: 100, fixed: true, sortField: null },
];

let columnState = null;

function getColumnState() {
  if (columnState) return columnState;
  try {
    const saved = localStorage.getItem('idjlm_columns');
    if (saved) {
      columnState = JSON.parse(saved);
      return columnState;
    }
  } catch {}
  columnState = COLUMN_DEFS.map((c, i) => ({
    id: c.id,
    visible: c.defaultVisible !== false,
    order: i,
  }));
  return columnState;
}

function saveColumnState() {
  try {
    localStorage.setItem('idjlm_columns', JSON.stringify(columnState));
  } catch {}
}

function getVisibleColumns() {
  const state = getColumnState();
  const orderMap = {};
  state.forEach(s => { orderMap[s.id] = s; });
  const cols = COLUMN_DEFS
    .filter(c => orderMap[c.id] && orderMap[c.id].visible)
    .sort((a, b) => orderMap[a.id].order - orderMap[b.id].order);
  return cols;
}

// ---------------------------------------------------------------------------
// Phase 2.4 — Genre Colour System
// ---------------------------------------------------------------------------
const GENRE_COLORS = {
  'Salsa': '#e74c3c',
  'Bachata': '#3498db',
  'Kizomba': '#f1c40f',
  'Cha Cha': '#2ecc71',
  'Merengue': '#e67e22',
  'Reggaeton': '#9b59b6',
  'Cumbia': '#1abc9c',
  'Rumba': '#e91e63',
  'Son': '#00bcd4',
  'Guaracha': '#ff9800',
  'Tango': '#795548',
  'Samba': '#4caf50',
  'Pop': '#2196f3',
  'Rock': '#f44336',
  'Electronic': '#00e5ff',
  'Hip Hop': '#ff5722',
  'R&B': '#e040fb',
  'Jazz': '#ffd740',
  'Classical': '#78909c',
  'Other': '#607d8b',
};

function getGenreColor(genre) {
  if (!genre) return 'transparent';
  if (GENRE_COLORS[genre]) return GENRE_COLORS[genre];
  let hash = 0;
  for (let i = 0; i < genre.length; i++) {
    hash = genre.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = ((hash % 360) + 360) % 360;
  return `hsl(${hue}, 65%, 55%)`;
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function getCamelotCompatibleKeys(key) {
  if (!key) return new Set();
  const match = key.match(/^(\d+)([AB])$/i);
  if (!match) return new Set();
  const num = parseInt(match[1]);
  const mode = match[2].toUpperCase();
  const compatible = new Set();
  compatible.add(key.toUpperCase());
  compatible.add(`${((num - 2 + 12) % 12) + 1}${mode}`);
  compatible.add(`${(num % 12) + 1}${mode}`);
  compatible.add(`${num}${mode === 'A' ? 'B' : 'A'}`);
  return compatible;
}

function getConfidenceBadgeClass(confidence) {
  if (confidence >= 80) return 'confidence-high';
  if (confidence >= 60) return 'confidence-mid';
  return 'confidence-low';
}

function getStatusBadge(status) {
  const badges = {
    pending: 'badge-pending',
    approved: 'badge-approved',
    skipped: 'badge-skipped',
    written: 'badge-written',
  };
  return badges[status] || 'badge-pending';
}

// ---------------------------------------------------------------------------
// initTracksTab — setup listeners
// ---------------------------------------------------------------------------

function initTracksTab() {
  const filterGenre = document.getElementById('filter-genre');
  const filterStatus = document.getElementById('filter-status');

  apiFetch('/api/taxonomy')
    .then(data => {
      store.set('taxonomy', data.genres || {});
      populateGenreFilters();
    });

  filterGenre.addEventListener('change', renderTracks);
  filterStatus.addEventListener('change', renderTracks);

  const filterBpmMin = document.getElementById('filter-bpm-min');
  const filterBpmMax = document.getElementById('filter-bpm-max');
  if (filterBpmMin) filterBpmMin.addEventListener('input', renderTracks);
  if (filterBpmMax) filterBpmMax.addEventListener('input', renderTracks);

  document.querySelectorAll('.tracks-table th.sortable').forEach(header => {
    header.addEventListener('click', () => {
      const field = header.dataset.sort;
      if (window.currentSort.field === field) {
        window.currentSort.direction = window.currentSort.direction === 'asc' ? 'desc' : 'asc';
      } else {
        window.currentSort.field = field;
        window.currentSort.direction = 'asc';
      }
      document.querySelectorAll('.tracks-table th.sortable').forEach(h => {
        h.classList.remove('sort-asc', 'sort-desc');
      });
      header.classList.add(`sort-${window.currentSort.direction}`);
      renderTracks();
    });
  });

  initVirtualScroll();
  initColumnPicker();
  initInlineEditSystem();
  initColumnPickerButton();

  if (window.searchResults !== null) renderTracks();
}

function populateGenreFilters() {
  const select = document.getElementById('filter-genre');
  select.innerHTML = '<option value="">All Genres</option>';
  Object.keys(store.state.taxonomy).forEach(genre => {
    const option = document.createElement('option');
    option.value = genre;
    option.textContent = genre;
    select.appendChild(option);
  });
}

function getFilteredTracks() {
  let filtered = window.searchResults !== null
    ? [...window.searchResults]
    : [...(store.state.tracks || [])];

  const genreEl = document.getElementById('filter-genre');
  const genreFilter = genreEl ? genreEl.value : '';
  if (genreFilter) {
    filtered = filtered.filter(t => t.final_genre === genreFilter);
  }

  const statusEl = document.getElementById('filter-status');
  const statusFilter = statusEl ? statusEl.value : '';
  if (statusFilter) {
    filtered = filtered.filter(t => t.review_status === statusFilter);
  }

  const bpmMinEl = document.getElementById('filter-bpm-min');
  const bpmMaxEl = document.getElementById('filter-bpm-max');
  const bpmMin = bpmMinEl ? parseFloat(bpmMinEl.value) : NaN;
  const bpmMax = bpmMaxEl ? parseFloat(bpmMaxEl.value) : NaN;
  if (!isNaN(bpmMin)) {
    filtered = filtered.filter(t => {
      const bpm = parseFloat(t.final_bpm) || parseFloat(t.analyzed_bpm) || 0;
      return bpm >= bpmMin;
    });
  }
  if (!isNaN(bpmMax)) {
    filtered = filtered.filter(t => {
      const bpm = parseFloat(t.final_bpm) || parseFloat(t.analyzed_bpm) || 0;
      return bpm <= bpmMax;
    });
  }

  if (window.activeChips && window.activeChips.size > 0) {
    const chipFilters = {};
    window.activeChips.forEach(key => {
      const colonIdx = key.indexOf(':');
      if (colonIdx === -1) return;
      const group = key.substring(0, colonIdx);
      const value = key.substring(colonIdx + 1);
      if (!chipFilters[group]) chipFilters[group] = new Set();
      chipFilters[group].add(value);
    });
    if (chipFilters.genre) filtered = filtered.filter(t => chipFilters.genre.has(t.final_genre));
    if (chipFilters.year) filtered = filtered.filter(t => chipFilters.year.has(t.final_year));
    if (chipFilters.status) filtered = filtered.filter(t => chipFilters.status.has(t.review_status));
    if (chipFilters.key) filtered = filtered.filter(t => chipFilters.key.has(t.final_key));
  }

  return filtered;
}

function sortTracks(tracks) {
  const sorted = [...tracks];
  sorted.sort((a, b) => {
    let aVal = a[window.currentSort.field] || '';
    let bVal = b[window.currentSort.field] || '';
    if (window.currentSort.field === 'confidence' || window.currentSort.field === 'final_bpm' || window.currentSort.field === 'final_year') {
      aVal = parseFloat(aVal) || 0;
      bVal = parseFloat(bVal) || 0;
    } else {
      aVal = String(aVal).toLowerCase();
      bVal = String(bVal).toLowerCase();
    }
    if (aVal < bVal) return window.currentSort.direction === 'asc' ? -1 : 1;
    if (aVal > bVal) return window.currentSort.direction === 'asc' ? 1 : -1;
    return 0;
  });
  return sorted;
}

// ---------------------------------------------------------------------------
// Phase 2.1 — Virtual Scrolling
// ---------------------------------------------------------------------------

const ROW_HEIGHT = 38;
const SCROLL_BUFFER = 10;

function getTableWrap() {
  return document.querySelector('.table-wrap');
}

function initVirtualScroll() {
  const wrap = getTableWrap();
  if (!wrap) return;
  wrap.addEventListener('scroll', () => {
    if (_scrollRAF) cancelAnimationFrame(_scrollRAF);
    _scrollRAF = requestAnimationFrame(() => {
      renderVisibleRows();
    });
  });
}

function renderTracks() {
  const tbody = document.getElementById('tracks-tbody');
  const table = document.getElementById('tracks-table');
  const filtered = getFilteredTracks();
  const sorted = sortTracks(filtered);
  totalFilteredSorted = sorted;

  tbody.innerHTML = '';
  lastClickedRowIdx = null;

  updatePipelineStepper();

  if (!sorted.length) {
    const row = document.createElement('tr');
    row.className = 'empty-state';
    const cell = document.createElement('td');
    cell.colSpan = '17';
    cell.textContent = 'No tracks match filters';
    row.appendChild(cell);
    tbody.appendChild(row);
    const countEl = document.getElementById('tracks-count');
    if (countEl) countEl.textContent = '0 tracks';
    updateVirtualScrollHeight(0);
    if (table) {
      table.setAttribute('aria-rowcount', '0');
      table.removeAttribute('aria-rowindex');
    }
    updateTrackCount(sorted.length);
    return;
  }

  if (table) {
    table.setAttribute('role', 'grid');
    table.setAttribute('aria-rowcount', String(sorted.length));
  }
  updateVirtualScrollHeight(sorted.length);
  renderVisibleRows();
  updateTrackCount(sorted.length);
  updateFilterChips();
}

function updateVirtualScrollHeight(count) {
  const wrap = getTableWrap();
  if (!wrap) return;
  const totalHeight = count * ROW_HEIGHT;
  const existing = wrap.querySelector('.vscroll-spacer');
  if (existing) {
    existing.style.height = totalHeight + 'px';
  } else {
    const spacer = document.createElement('div');
    spacer.className = 'vscroll-spacer';
    spacer.style.cssText = `height:${totalHeight}px;pointer-events:none;`;
    wrap.insertBefore(spacer, wrap.querySelector('.tracks-table'));
  }
}

function renderVisibleRows() {
  const tbody = document.getElementById('tracks-tbody');
  if (!tbody) return;
  const sorted = totalFilteredSorted;
  if (!sorted.length) return;

  const wrap = getTableWrap();
  const scrollTop = wrap ? wrap.scrollTop : 0;
  const containerHeight = wrap ? wrap.clientHeight : 600;

  const visibleStart = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - SCROLL_BUFFER);
  const visibleEnd = Math.min(sorted.length, Math.ceil((scrollTop + containerHeight) / ROW_HEIGHT) + SCROLL_BUFFER);

  visibleRange = { start: visibleStart, end: visibleEnd };

  tbody.innerHTML = '';

  const table = tbody.closest('.tracks-table') || document.getElementById('tracks-table');
  if (table) {
    table.style.transform = `translateY(${visibleStart * ROW_HEIGHT}px)`;
  }

  for (let i = visibleStart; i < visibleEnd; i++) {
    const track = sorted[i];
    const row = buildTrackRow(track, i);
    tbody.appendChild(row);
  }

  if (typeof updateBulkActionsBar === 'function') updateBulkActionsBar();
}

// ---------------------------------------------------------------------------
// Phase 2.7 — Keyboard integration hooks
// ---------------------------------------------------------------------------

let _keyboardSelectedIdx = -1;

function getKeyboardSelectedIndex() {
  return _keyboardSelectedIdx;
}

function setKeyboardSelectedIndex(idx) {
  _keyboardSelectedIdx = idx;
  if (idx >= 0 && idx < totalFilteredSorted.length) {
    scrollToRow(idx);
  }
}

function scrollToRow(idx) {
  const wrap = getTableWrap();
  if (!wrap) return;
  const targetTop = idx * ROW_HEIGHT;
  const viewBottom = wrap.scrollTop + wrap.clientHeight;
  if (targetTop < wrap.scrollTop || targetTop + ROW_HEIGHT > viewBottom) {
    wrap.scrollTop = targetTop - wrap.clientHeight / 2 + ROW_HEIGHT / 2;
  }
  renderVisibleRows();
}

function focusKeyboardRow(idx) {
  if (idx < 0 || idx >= totalFilteredSorted.length) return;
  _keyboardSelectedIdx = idx;
  scrollToRow(idx);
  const track = totalFilteredSorted[idx];
  if (track) {
    const cb = document.querySelector(`input[data-file-path="${CSS.escape(track.file_path)}"]`);
    if (cb) {
      cb.checked = true;
      const tr = cb.closest('tr');
      if (tr) tr.classList.add('row-selected');
    }
    store.state.selectedTracks.add(track.file_path);
    if (typeof updateBulkActionsBar === 'function') updateBulkActionsBar();
  }
}

// Keyboard v2: A = approve+advance, R = reclassify, E = inline edit, X = select
// Uses registerGlobalShortcut from shortcuts.js (checks input focus + modifiers globally)
// Each handler checks for active library tab locally.

function approveKeyboardSelectedHandler() {
  const tab = document.getElementById('tab-library');
  if (!tab || !tab.classList.contains('active')) return;
  approveKeyboardSelected();
}

function reclassifyKeyboardSelectedHandler() {
  const tab = document.getElementById('tab-library');
  if (!tab || !tab.classList.contains('active')) return;
  reclassifyKeyboardSelected();
}

function editInlineKeyboardSelectedHandler() {
  const tab = document.getElementById('tab-library');
  if (!tab || !tab.classList.contains('active')) return;
  editInlineKeyboardSelected();
}

function toggleKeyboardSelectionHandler() {
  const tab = document.getElementById('tab-library');
  if (!tab || !tab.classList.contains('active')) return;
  toggleKeyboardSelection();
}

function moveKeyboardSelectionDownHandler() {
  const tab = document.getElementById('tab-library');
  if (!tab || !tab.classList.contains('active')) return;
  const newIdx = Math.min(_keyboardSelectedIdx + 1, totalFilteredSorted.length - 1);
  focusKeyboardRow(newIdx);
}

function moveKeyboardSelectionUpHandler() {
  const tab = document.getElementById('tab-library');
  if (!tab || !tab.classList.contains('active')) return;
  const newIdx = Math.max(_keyboardSelectedIdx - 1, 0);
  focusKeyboardRow(newIdx);
}

function extendKeyboardSelectionDownHandler() {
  const tab = document.getElementById('tab-library');
  if (!tab || !tab.classList.contains('active')) return;
  if (_keyboardSelectedIdx < 0) return;
  const newIdx = Math.min(_keyboardSelectedIdx + 1, totalFilteredSorted.length - 1);
  extendKeyboardSelectionTo(newIdx);
}

function extendKeyboardSelectionUpHandler() {
  const tab = document.getElementById('tab-library');
  if (!tab || !tab.classList.contains('active')) return;
  if (_keyboardSelectedIdx < 0) return;
  const newIdx = Math.max(_keyboardSelectedIdx - 1, 0);
  extendKeyboardSelectionTo(newIdx);
}

function extendKeyboardSelectionTo(targetIdx) {
  if (_keyboardSelectedIdx < 0) return;
  const start = Math.min(_keyboardSelectedIdx, targetIdx);
  const end = Math.max(_keyboardSelectedIdx, targetIdx);
  for (let i = start; i <= end; i++) {
    const track = totalFilteredSorted[i];
    if (!track) continue;
    store.state.selectedTracks.add(track.file_path);
  }
  focusKeyboardRow(targetIdx);
  if (typeof updateBulkActionsBar === 'function') updateBulkActionsBar();
  renderVisibleRows();
}

function toggleKeyboardSelectionSpaceHandler() {
  const tab = document.getElementById('tab-library');
  if (!tab || !tab.classList.contains('active')) return;
  if (_keyboardSelectedIdx < 0) return;
  const track = totalFilteredSorted[_keyboardSelectedIdx];
  if (!track) return;
  const cb = document.querySelector(`input[data-file-path="${CSS.escape(track.file_path)}"]`);
  if (cb) {
    cb.checked = !cb.checked;
    if (cb.checked) {
      store.state.selectedTracks.add(track.file_path);
      cb.closest('tr')?.classList.add('row-selected');
    } else {
      store.state.selectedTracks.delete(track.file_path);
      cb.closest('tr')?.classList.remove('row-selected');
    }
    if (typeof updateBulkActionsBar === 'function') updateBulkActionsBar();
  }
}

// Register global shortcuts (called after DOM ready / module load)
if (typeof registerGlobalShortcut === 'function') {
  registerGlobalShortcut('a', approveKeyboardSelectedHandler, { description: 'Approve + advance', context: 'library' });
  registerGlobalShortcut('r', reclassifyKeyboardSelectedHandler, { description: 'Re-classify', context: 'library' });
  registerGlobalShortcut('e', editInlineKeyboardSelectedHandler, { description: 'Inline edit genre', context: 'library' });
  registerGlobalShortcut('x', toggleKeyboardSelectionHandler, { description: 'Toggle selection', context: 'library' });
  registerGlobalShortcut('arrowdown', moveKeyboardSelectionDownHandler, { description: 'Next row', context: 'library' });
  registerGlobalShortcut('arrowup', moveKeyboardSelectionUpHandler, { description: 'Previous row', context: 'library' });
  registerGlobalShortcut('space', toggleKeyboardSelectionSpaceHandler, { description: 'Toggle selection (alt)', context: 'library' });
} else {
  // Fallback: direct listener if registry not available
  document.addEventListener('keydown', (e) => {
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const tab = document.getElementById('tab-library');
    if (!tab || !tab.classList.contains('active')) return;
    if (e.key === 'a' || e.key === 'A') { e.preventDefault(); approveKeyboardSelected(); }
    else if (e.key === 'r' || e.key === 'R') { e.preventDefault(); reclassifyKeyboardSelected(); }
    else if (e.key === 'e' || e.key === 'E') { e.preventDefault(); editInlineKeyboardSelected(); }
    else if (e.key === 'x' || e.key === 'X') { e.preventDefault(); toggleKeyboardSelection(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); moveKeyboardSelectionDownHandler(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); moveKeyboardSelectionUpHandler(); }
    else if (e.key === ' ' && _keyboardSelectedIdx >= 0) { e.preventDefault(); toggleKeyboardSelectionSpaceHandler(); }
  });
}

function approveKeyboardSelected() {
  const track = totalFilteredSorted[_keyboardSelectedIdx];
  if (!track || !track.proposed_genre) return;
  const newStatus = track.review_status === 'approved' ? 'pending' : 'approved';
  apiFetch('/api/tracks/by-path?path=' + encodeURIComponent(track.file_path), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ review_status: newStatus })
  }).then(() => {
    const found = store.state.tracks.find(x => x.file_path === track.file_path);
    if (found) found.review_status = newStatus;
    store.notify('tracks');
    if (typeof updateStats === 'function') updateStats();
    if (typeof updateToolbarButtonStates === 'function') updateToolbarButtonStates();
    const nextIdx = Math.min(_keyboardSelectedIdx + 1, totalFilteredSorted.length - 1);
    focusKeyboardRow(nextIdx);
  }).catch(() => showToast('Could not update status', 'error'));
}

function reclassifyKeyboardSelected() {
  const track = totalFilteredSorted[_keyboardSelectedIdx];
  if (!track) return;
  if (typeof reclassifySingleTrack === 'function') {
    reclassifySingleTrack(track);
  }
}

function editInlineKeyboardSelected() {
  const track = totalFilteredSorted[_keyboardSelectedIdx];
  if (!track) return;
  const cols = getVisibleColumns();
  const genreCol = cols.find(c => c.id === 'genre');
  if (genreCol) {
    const cell = document.querySelector(`tr[data-idx="${_keyboardSelectedIdx}"] .col-genre`);
    if (cell) startInlineEdit(cell, 'final_genre', track.final_genre, track);
  }
}

function toggleKeyboardSelection() {
  const track = totalFilteredSorted[_keyboardSelectedIdx];
  if (!track) return;
  if (store.state.selectedTracks.has(track.file_path)) {
    store.state.selectedTracks.delete(track.file_path);
  } else {
    store.state.selectedTracks.add(track.file_path);
  }
  if (typeof updateBulkActionsBar === 'function') updateBulkActionsBar();
  renderVisibleRows();
}

// ---------------------------------------------------------------------------
// Phase 2.2 — Column Picker
// ---------------------------------------------------------------------------

function initColumnPickerButton() {
  const btn = document.getElementById('btn-column-picker');
  const picker = document.getElementById('column-picker');
  if (!btn || !picker) return;
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const visible = picker.style.display !== 'none';
    picker.style.display = visible ? 'none' : 'block';
    if (!visible) renderColumnPickerList();
  });
  document.addEventListener('click', (e) => {
    if (picker && !picker.contains(e.target) && e.target !== btn) {
      picker.style.display = 'none';
    }
  });
}

function renderColumnPickerList() {
  const list = document.getElementById('column-picker-list');
  if (!list) return;
  const state = getColumnState();
  list.innerHTML = '';
  const ordered = COLUMN_DEFS
    .map(c => ({ def: c, state: state.find(s => s.id === c.id) }))
    .sort((a, b) => (a.state?.order ?? 999) - (b.state?.order ?? 999));

  ordered.forEach(({ def, st }) => {
    if (def.id === 'check' || def.id === 'art' || def.id === 'approve' || def.id === 'action') return;
    const item = document.createElement('div');
    item.className = 'column-picker-item';
    item.draggable = true;

    const label = document.createElement('label');
    label.className = 'column-picker-label';

    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.checked = st ? st.visible : true;
    chk.addEventListener('change', () => {
      if (st) {
        st.visible = chk.checked;
        saveColumnState();
        renderTracks();
      }
    });

    const name = document.createElement('span');
    name.textContent = def.label || def.id;
    name.className = 'column-picker-name';

    const grippy = document.createElement('span');
    grippy.className = 'column-picker-grippy';
    grippy.textContent = '⠿';

    label.appendChild(chk);
    label.appendChild(name);
    item.appendChild(grippy);
    item.appendChild(label);

    item.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', def.id);
      item.classList.add('dragging');
    });
    item.addEventListener('dragend', () => {
      item.classList.remove('dragging');
    });
    item.addEventListener('dragover', (e) => {
      e.preventDefault();
      item.classList.add('drag-over');
    });
    item.addEventListener('dragleave', () => {
      item.classList.remove('drag-over');
    });
    item.addEventListener('drop', (e) => {
      e.preventDefault();
      item.classList.remove('drag-over');
      const draggedId = e.dataTransfer.getData('text/plain');
      const targetId = def.id;
      if (draggedId === targetId) return;
      const s = getColumnState();
      const draggedState = s.find(x => x.id === draggedId);
      const targetState = s.find(x => x.id === targetId);
      if (draggedState && targetState) {
        const temp = draggedState.order;
        draggedState.order = targetState.order;
        targetState.order = temp;
        saveColumnState();
        renderColumnPickerList();
        renderTracks();
      }
    });

    list.appendChild(item);
  });
}

// ---------------------------------------------------------------------------
// Phase 2.6 — Inline Cell Editing
// ---------------------------------------------------------------------------

function initInlineEditSystem() {
  document.addEventListener('click', (e) => {
    const cell = e.target.closest('.inline-editable');
    if (!cell) {
      if (_inlineEditActive) cancelInlineEdit();
      return;
    }
    e.stopPropagation();
    const field = cell.dataset.field;
    const idx = parseInt(cell.dataset.rowIdx);
    const track = totalFilteredSorted[idx];
    if (!track || !field) return;
    startInlineEdit(cell, field, track[field], track);
  });

  document.addEventListener('keydown', (e) => {
    if (!_inlineEditActive) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      cancelInlineEdit();
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      commitInlineEdit();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      commitInlineEdit();
      moveToNextInlineEdit(e.shiftKey ? -1 : 1);
    }
  });
}

let _inlineState = null;

function startInlineEdit(cell, field, value, track) {
  if (_inlineEditActive) cancelInlineEdit();

  _inlineState = { cell, field, originalValue: value, track };

  cell.classList.add('editing');
  cell.innerHTML = '';

  const isGenre = field === 'final_genre' || field === 'final_subgenre';
  const isNumeric = field === 'final_bpm' || field === 'final_year';
  const isComment = field === 'final_comment';

  if (isGenre) {
    const select = document.createElement('select');
    select.className = 'inline-edit-select';
    if (field === 'final_genre') {
      const empty = document.createElement('option');
      empty.value = ''; empty.textContent = '—';
      select.appendChild(empty);
      Object.keys(store.state.taxonomy).forEach(g => {
        const opt = document.createElement('option');
        opt.value = g; opt.textContent = g;
        if (g === value) opt.selected = true;
        select.appendChild(opt);
      });
    } else {
      const parentGenre = track.final_genre;
      const empty = document.createElement('option');
      empty.value = ''; empty.textContent = '—';
      select.appendChild(empty);
      if (parentGenre && store.state.taxonomy[parentGenre]) {
        (store.state.taxonomy[parentGenre].subgenres || []).forEach(sg => {
          const opt = document.createElement('option');
          opt.value = sg; opt.textContent = sg;
          if (sg === value) opt.selected = true;
          select.appendChild(opt);
        });
      }
    }
    select.addEventListener('change', () => { _inlineState.newValue = select.value; });
    cell.appendChild(select);
    select.focus();
  } else if (isNumeric) {
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'inline-edit-input mono';
    input.value = value || '';
    input.addEventListener('input', () => { _inlineState.newValue = input.value; });
    cell.appendChild(input);
    input.focus();
    input.select();
  } else if (isComment) {
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'inline-edit-input';
    input.value = value || '';
    input.addEventListener('input', () => { _inlineState.newValue = input.value; });
    cell.appendChild(input);
    input.focus();
    input.select();
  }

  _inlineEditActive = true;
}

function cancelInlineEdit() {
  if (!_inlineEditActive || !_inlineState) return;
  const { cell, originalValue } = _inlineState;
  cell.classList.remove('editing');
  cell.textContent = originalValue || '—';
  _inlineEditActive = false;
  _inlineState = null;
}

async function commitInlineEdit() {
  if (!_inlineEditActive || !_inlineState) return;
  const { cell, field, track, newValue } = _inlineState;
  let val = newValue;
  if (val === undefined) {
    const input = cell.querySelector('input, select');
    val = input ? input.value : '';
  }
  cell.classList.remove('editing');

  const origVal = track[field];
  if (val === origVal || (!val && !origVal)) {
    cell.textContent = val || '—';
    _inlineEditActive = false;
    _inlineState = null;
    return;
  }

  const overrideKey = field.startsWith('final_') ? 'override_' + field.slice(6) : field;

  try {
    await apiFetch('/api/tracks/by-path?path=' + encodeURIComponent(track.file_path), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [overrideKey]: val || undefined })
    });
    track[field] = val;
    store.notify('tracks');
    showToast('Updated ' + field, 'success');
  } catch {
    showToast('Failed to update ' + field, 'error');
  }

  cell.textContent = val || '—';
  _inlineEditActive = false;
  _inlineState = null;
}

function moveToNextInlineEdit(dir) {
  const currentIdx = _inlineState ? totalFilteredSorted.indexOf(_inlineState.track) : -1;
  if (currentIdx < 0) return;
  const cols = getVisibleColumns();
  const currentColIdx = cols.findIndex(c => c.id === _inlineState?.field);
  if (currentColIdx < 0) return;
  const nextCol = cols[currentColIdx + dir];
  if (!nextCol) {
    const nextRow = totalFilteredSorted[currentIdx + dir];
    if (nextRow) {
      scrollToRow(currentIdx + dir);
      const nextCell = document.querySelector(`tr[data-idx="${currentIdx + dir}"] .col-${nextCol.id}`);
      if (nextCell) startInlineEdit(nextCell, nextCol.sortField || nextCol.id, nextRow[nextCol.sortField || nextCol.id], nextRow);
    }
    return;
  }
  const nextCell = document.querySelector(`tr[data-idx="${currentIdx}"] .col-${nextCol.id}`);
  if (nextCell && nextCol.sortField) {
    startInlineEdit(nextCell, nextCol.sortField, totalFilteredSorted[currentIdx][nextCol.sortField], totalFilteredSorted[currentIdx]);
  }
}

// ---------------------------------------------------------------------------
// Phase 2.3 — Mini-waveform column
// ---------------------------------------------------------------------------

function renderMiniWaveformColumn(canvas, track) {
  if (!canvas || !track) return;
  const waveformData = track.waveform_data || track.analyzed_waveform;
  if (!waveformData || !waveformData.length) {
    canvas.style.display = 'none';
    return;
  }
  canvas.style.display = '';
  const W = canvas.clientWidth || 74;
  const H = canvas.clientHeight || 30;
  canvas.width = W * 2;
  canvas.height = H * 2;
  canvas.style.width = W + 'px';
  canvas.style.height = H + 'px';
  const ctx = canvas.getContext('2d');
  const style = getComputedStyle(document.documentElement);
  const accColor = style.getPropertyValue('--acc').trim() || '#8b5cf6';
  const dimColor = style.getPropertyValue('--acc-dim').trim() || 'rgba(139,92,246,0.12)';
  const POINTS = 60;
  const gap = 1;
  const barW = Math.max(1, (W * 2 - gap * (POINTS - 1)) / POINTS);
  const step = Math.max(1, Math.floor(waveformData.length / POINTS));
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (let i = 0; i < POINTS; i++) {
    const segStart = i * step;
    const segEnd = Math.min((i + 1) * step, waveformData.length);
    let maxAmp = 0;
    for (let j = segStart; j < segEnd; j++) {
      maxAmp = Math.max(maxAmp, Number(waveformData[j]) || 0);
    }
    const amp = Math.max(0.02, maxAmp);
    const barH = Math.max(2, amp * H * 1.6);
    const x = i * (barW + gap);
    const y = (H * 2 - barH) / 2;
    ctx.fillStyle = amp > 0.15 ? accColor : dimColor;
    ctx.fillRect(x, y, barW - 1, barH);
  }
}

// ---------------------------------------------------------------------------
// Phase 2.8 — Context Menu v2
// ---------------------------------------------------------------------------

let _ctxEscHandler = null;

function showTrackContextMenu(track, x, y) {
  const existing = document.getElementById('track-ctx-menu');
  if (existing) existing.remove();
  if (_ctxEscHandler) { document.removeEventListener('keydown', _ctxEscHandler); _ctxEscHandler = null; }

  const menu = document.createElement('div');
  menu.id = 'track-ctx-menu';
  menu.className = 'ctx-menu';
  menu.style.cssText = `position:fixed;left:${x}px;top:${y}px;z-index:9999;`;

  const items = [
    { icon: '▶', label: 'Play', action: () => playTrackInBrowser(track) },
    { icon: '✎', label: 'Edit Tags (modal)', action: () => openSingleTrackEdit(track) },
    { type: 'sep' },
    { icon: '+', label: 'Add to Setlist', action: () => {
        if (typeof addTrackToSetlist === 'function') addTrackToSetlist(track.file_path);
      }
    },
    { icon: '◎', label: 'Find Compatible', action: () => {
        showToast('Finding compatible tracks...', 'info');
        if (typeof showInDock === 'function') showInDock(track);
      }
    },
    { icon: '🔄', label: 'Re-analyse', action: () => {
        showToast('Queued re-analysis for ' + (track.display_title || track.filename), 'info');
        apiFetch('/api/analyse?path=' + encodeURIComponent(track.file_path), { method: 'POST' })
          .then(() => showToast('Analysis complete', 'success'))
          .catch(() => showToast('Analysis failed', 'error'));
      }
    },
    { type: 'sep' },
    { icon: '📂', label: 'Show File Path', action: () => { showToast(track.file_path, 'info'); } },
  ];

  items.forEach(item => {
    if (item.type === 'sep') {
      const sep = document.createElement('div');
      sep.className = 'ctx-menu-sep';
      menu.appendChild(sep);
      return;
    }
    const el = document.createElement('div');
    el.className = 'ctx-menu-item';
    el.innerHTML = `<span class="ctx-menu-icon">${item.icon}</span><span>${item.label}</span>`;
    el.addEventListener('click', () => { menu.remove(); item.action(); });
    menu.appendChild(el);
  });

  document.body.appendChild(menu);

  requestAnimationFrame(() => {
    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) menu.style.left = Math.max(0, x - rect.width) + 'px';
    if (rect.bottom > window.innerHeight) menu.style.top = Math.max(0, y - rect.height) + 'px';
  });

  function closeMenu() {
    menu.remove();
    if (_ctxEscHandler) { document.removeEventListener('keydown', _ctxEscHandler); _ctxEscHandler = null; }
  }
  setTimeout(() => {
    document.addEventListener('click', closeMenu, { once: true });
  }, 0);
  _ctxEscHandler = (e) => { if (e.key === 'Escape') closeMenu(); };
  document.addEventListener('keydown', _ctxEscHandler);
}

// ---------------------------------------------------------------------------
// Row builder — builds a single track <tr> with all Phase 2 enhancements
// ---------------------------------------------------------------------------

function buildTrackRow(track, globalIdx) {
  const row = document.createElement('tr');
  row.style.cursor = 'pointer';
  row.dataset.idx = globalIdx;
  row.setAttribute('role', 'row');
  row.setAttribute('aria-rowindex', String(globalIdx + 1));

  const cols = getVisibleColumns();
  const genreColor = getGenreColor(track.final_genre);
  if (genreColor && genreColor !== 'transparent') {
    row.style.borderLeft = `3px solid ${genreColor}`;
  }

  const confidenceClass = getConfidenceBadgeClass(track.confidence || 0);
  const statusBadge = getStatusBadge(track.review_status);

  cols.forEach(col => {
    switch (col.id) {
      case 'check':
        row.appendChild(buildCheckboxCell(track, globalIdx));
        break;
      case 'art':
        row.appendChild(buildArtCell(track));
        break;
      case 'waveform':
        row.appendChild(buildWaveformCell(track));
        break;
      case 'title':
        row.appendChild(buildTitleCell(track));
        break;
      case 'genre':
        row.appendChild(buildGenreCell(track, globalIdx));
        break;
      case 'subgenre':
        row.appendChild(buildSubgenreCell(track, globalIdx));
        break;
      case 'confidence':
        row.appendChild(buildConfidenceCell(track));
        break;
      case 'bpm':
        row.appendChild(buildBpmCell(track, globalIdx));
        break;
      case 'key':
        row.appendChild(buildKeyCell(track));
        break;
      case 'clave':
        row.appendChild(buildClaveCell(track));
        break;
      case 'vocal':
        row.appendChild(buildVocalCell(track));
        break;
      case 'tempo':
        row.appendChild(buildTempoCell(track));
        break;
      case 'lufs':
        row.appendChild(buildLufsCell(track));
        break;
      case 'year':
        row.appendChild(buildYearCell(track, globalIdx));
        break;
      case 'status':
        row.appendChild(buildStatusCell(track));
        break;
      case 'approve':
        row.appendChild(buildApproveCell(track));
        break;
      case 'action':
        row.appendChild(buildActionCell(track));
        break;
    }
  });

  // Row events
  row.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    e.stopPropagation();
    showTrackContextMenu(track, e.clientX, e.clientY);
  });

  row.addEventListener('dblclick', (e) => {
    e.preventDefault();
    e.stopPropagation();
    showTrackContextMenu(track, e.clientX, e.clientY);
  });

  row.addEventListener('click', (e) => {
    if (e.target.closest('.inline-editable') || e.target.closest('.editing')) return;
    if (e.target.type === 'checkbox' || e.target.closest('button, input, select')) return;
    if (e.shiftKey) return;
    if (keyCompatTrack && keyCompatTrack.file_path === track.file_path) {
      keyCompatTrack = null;
    } else {
      keyCompatTrack = track;
    }
    renderVisibleRows();
  });

  row.addEventListener('click', (e) => {
    if (e.target.closest('.inline-editable, .editing') || e.target.closest('button, input, select')) return;
    const cb = row.querySelector('input[type="checkbox"]');
    if (!cb) return;
    cb.checked = !cb.checked;
    cb.dispatchEvent(new MouseEvent('click', { bubbles: false, shiftKey: e.shiftKey }));
  });

  if (keyCompatTrack) {
    const compatKeys = getCamelotCompatibleKeys(keyCompatTrack.final_key || keyCompatTrack.estimated_key);
    const trackKey = (track.final_key || track.estimated_key || '').toUpperCase();
    const isSelf = track.file_path === keyCompatTrack.file_path;
    if (isSelf) row.classList.add('key-compat-self');
    else if (trackKey && compatKeys.has(trackKey)) row.classList.add('key-compat-match');
    else row.classList.add('key-compat-dim');
  }

  return row;
}

// ---- Cell builders ----

function buildCheckboxCell(track, globalIdx) {
  const td = document.createElement('td');
  td.className = 'checkbox-col';
  const cb = document.createElement('input');
  cb.type = 'checkbox';
  cb.dataset.filePath = track.file_path;
  if (store.state.selectedTracks?.has(track.file_path)) {
    cb.checked = true;
  }
  cb.addEventListener('click', (e) => {
    e.stopPropagation();
    const tbody = document.getElementById('tracks-tbody');
    const allRows = Array.from(tbody.querySelectorAll('tr'));
    const currentIdx = allRows.indexOf(e.target.closest('tr'));

    if (e.shiftKey && lastClickedRowIdx !== null) {
      const lo = Math.min(lastClickedRowIdx, currentIdx);
      const hi = Math.max(lastClickedRowIdx, currentIdx);
      const targetChecked = cb.checked;
      for (let i = lo; i <= hi; i++) {
        const r = allRows[i];
        if (!r) continue;
        const c = r.querySelector('input[type="checkbox"]');
        if (!c) continue;
        c.checked = targetChecked;
        if (targetChecked) { store.state.selectedTracks.add(c.dataset.filePath); r.classList.add('row-selected'); }
        else { store.state.selectedTracks.delete(c.dataset.filePath); r.classList.remove('row-selected'); }
      }
    } else {
      if (cb.checked) { store.state.selectedTracks.add(track.file_path); }
      else { store.state.selectedTracks.delete(track.file_path); }
      lastClickedRowIdx = currentIdx;
    }
    if (typeof updateBulkActionsBar === 'function') updateBulkActionsBar();
  });
  td.appendChild(cb);
  return td;
}

function buildArtCell(track) {
  const td = document.createElement('td');
  td.className = 'col-art';
  if (track.album_art_url) {
    const img = document.createElement('img');
    img.src = track.album_art_url;
    img.className = 'track-art-thumb';
    img.alt = '';
    img.loading = 'lazy';
    td.appendChild(img);
  } else {
    const ph = document.createElement('div');
    ph.className = 'track-art-placeholder';
    td.appendChild(ph);
  }
  return td;
}

function buildWaveformCell(track) {
  const td = document.createElement('td');
  td.className = 'col-waveform';
  const canvas = document.createElement('canvas');
  canvas.className = 'mini-waveform-canvas';
  canvas.width = 148;
  canvas.height = 60;
  canvas.style.cssText = 'width:74px;height:30px;display:block;border-radius:3px;';
  td.appendChild(canvas);
  requestAnimationFrame(() => renderMiniWaveformColumn(canvas, track));
  return td;
}

function buildTitleCell(track) {
  const td = document.createElement('td');
  td.className = 'col-title';
  const titleDiv = document.createElement('div');
  titleDiv.className = 'track-title-text';
  titleDiv.textContent = track.display_title || '—';
  const artistDiv = document.createElement('div');
  artistDiv.className = 'track-artist-text';
  artistDiv.textContent = track.display_artist || '—';
  td.appendChild(titleDiv);
  td.appendChild(artistDiv);
  return td;
}

function buildGenreCell(track, globalIdx) {
  const td = document.createElement('td');
  td.className = 'col-genre inline-editable';
  td.dataset.field = 'final_genre';
  td.dataset.rowIdx = globalIdx;
  td.title = 'Click to edit';
  const isManual = (track.genre_source === 'manual' || track.genre_edited === true);
  td.innerHTML = genreChip(track.final_genre, isManual);
  return td;
}

function buildSubgenreCell(track, globalIdx) {
  const td = document.createElement('td');
  td.className = 'col-subgenre inline-editable';
  td.dataset.field = 'final_subgenre';
  td.dataset.rowIdx = globalIdx;
  td.title = 'Click to edit';
  td.innerHTML = genreChip(track.final_subgenre, false);
  return td;
}

function buildConfidenceCell(track) {
  const td = document.createElement('td');
  td.innerHTML = confidenceBadge(track.confidence);
  return td;
}

function buildBpmCell(track, globalIdx) {
  const td = document.createElement('td');
  td.className = 'mono col-bpm col-bpm-emph inline-editable';
  td.dataset.field = 'final_bpm';
  td.dataset.rowIdx = globalIdx;
  td.title = 'Click to edit';
  td.textContent = track.final_bpm ? parseFloat(track.final_bpm).toFixed(1) : '—';
  return td;
}

function buildKeyCell(track) {
  const td = document.createElement('td');
  td.className = 'mono col-key-cell col-key-emph';
  if (track.final_key) {
    td.style.color = 'var(--acc)';
  }
  td.textContent = track.final_key || '—';
  return td;
}

function buildClaveCell(track) {
  const td = document.createElement('td');
  if (track.latin_analysis_done && track.clave_pattern) {
    const badge = document.createElement('span');
    badge.className = `clave-badge ${track.clave_pattern === '2-3' ? 'clave-badge-2-3' : 'clave-badge-3-2'}`;
    badge.textContent = track.clave_pattern;
    td.appendChild(badge);
  } else {
    td.textContent = '—';
    td.style.color = 'var(--text-muted)';
  }
  return td;
}

function buildVocalCell(track) {
  const td = document.createElement('td');
  if (track.vocal_flag) {
    const vClass = track.vocal_flag === 'vocal' ? 'vocal-badge-vocal'
      : track.vocal_flag === 'instrumental' ? 'vocal-badge-instrumental'
      : 'vocal-badge-mostly';
    const vLabel = track.vocal_flag === 'vocal' ? 'Vocal'
      : track.vocal_flag === 'instrumental' ? 'Instr.'
      : 'Mostly Instr.';
    td.innerHTML = `<span class="vocal-badge ${vClass}">${vLabel}</span>`;
  } else {
    td.textContent = '—';
    td.style.color = 'var(--text-muted)';
  }
  return td;
}

function buildTempoCell(track) {
  const td = document.createElement('td');
  if (track.tempo_category) {
    const tClass = track.tempo_category === 'fast' ? 'tempo-fast'
      : track.tempo_category === 'slow' ? 'tempo-slow'
      : 'tempo-medium';
    td.innerHTML = `<span class="tempo-badge ${tClass}">${track.tempo_category}</span>`;
  } else {
    td.textContent = '—';
    td.style.color = 'var(--text-muted)';
  }
  return td;
}

function buildLufsCell(track) {
  const td = document.createElement('td');
  if (track.analyzed_lufs != null) {
    const lufsVal = track.analyzed_lufs;
    const lufsClass = (lufsVal >= -14 && lufsVal <= -8) ? 'lufs-good'
      : (lufsVal >= -18 && lufsVal < -14) || (lufsVal > -8 && lufsVal <= -6) ? 'lufs-quiet'
      : 'lufs-loud';
    td.innerHTML = `<span class="${lufsClass}">${lufsVal}</span>`;
  } else {
    td.textContent = '—';
    td.style.color = 'var(--text-muted)';
  }
  return td;
}

function buildYearCell(track, globalIdx) {
  const td = document.createElement('td');
  td.className = 'col-year inline-editable';
  td.dataset.field = 'final_year';
  td.dataset.rowIdx = globalIdx;
  td.title = 'Click to edit';
  td.textContent = track.final_year || '—';
  return td;
}

function buildStatusCell(track) {
  const td = document.createElement('td');
  const badge = document.createElement('span');
  badge.className = `badge ${getStatusBadge(track.review_status)}`;
  badge.textContent = track.review_status;
  td.appendChild(badge);
  return td;
}

function buildApproveCell(track) {
  const td = document.createElement('td');
  td.className = 'approve-col';
  if (track.proposed_genre) {
    const btn = document.createElement('button');
    const st = track.review_status;
    btn.className = 'approve-btn' + (st === 'approved' ? ' approved' : st === 'skipped' ? ' skipped' : '');
    btn.textContent = st === 'approved' ? '✓' : st === 'skipped' ? '–' : '✓';
    btn.title = st === 'approved' ? 'Approved — click to undo' : 'Click to approve';
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const newStatus = track.review_status === 'approved' ? 'pending' : 'approved';
      try {
        await apiFetch('/api/tracks/by-path?path=' + encodeURIComponent(track.file_path), {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ review_status: newStatus })
        });
        const found = store.state.tracks.find(x => x.file_path === track.file_path);
        if (found) found.review_status = newStatus;
        store.notify('tracks');
        if (typeof updateStats === 'function') updateStats();
        if (typeof updateToolbarButtonStates === 'function') updateToolbarButtonStates();
      } catch { showToast('Could not update status', 'error'); }
    });
    td.appendChild(btn);
  } else {
    const dash = document.createElement('span');
    dash.style.cssText = 'color:var(--text-placeholder);font-size:11px;';
    dash.textContent = '—';
    td.appendChild(dash);
  }
  return td;
}

function buildActionCell(track) {
  const td = document.createElement('td');
  td.style.textAlign = 'center';
  td.style.display = 'flex';
  td.style.gap = '4px';
  td.style.justifyContent = 'center';

  const btnDetails = document.createElement('button');
  btnDetails.className = 'btn btn-secondary';
  btnDetails.style.padding = '4px 8px';
  btnDetails.style.fontSize = '12px';
  btnDetails.title = 'View details';
  btnDetails.textContent = '▼';
  btnDetails.addEventListener('click', (e) => {
    e.stopPropagation();
    if (typeof openTrackDetail === 'function') openTrackDetail(track);
    if (window.showInDock) showInDock(track);
  });
  td.appendChild(btnDetails);

  const btnPlay = document.createElement('button');
  btnPlay.className = 'btn btn-secondary';
  btnPlay.style.padding = '4px 8px';
  btnPlay.style.fontSize = '12px';
  btnPlay.title = 'Play preview';
  btnPlay.textContent = '▶';
  btnPlay.addEventListener('click', (e) => { e.stopPropagation(); playTrack(track); });
  td.appendChild(btnPlay);

  const btnSetlist = document.createElement('button');
  btnSetlist.className = 'btn btn-secondary';
  btnSetlist.style.padding = '4px 8px';
  btnSetlist.style.fontSize = '12px';
  btnSetlist.title = 'Add to setlist';
  btnSetlist.textContent = '+';
  btnSetlist.addEventListener('click', (e) => { e.stopPropagation(); if (typeof addTrackToSetlist === 'function') addTrackToSetlist(track.file_path); });
  td.appendChild(btnSetlist);

  const btnEdit = document.createElement('button');
  btnEdit.className = 'btn btn-secondary';
  btnEdit.style.padding = '4px 8px';
  btnEdit.style.fontSize = '12px';
  btnEdit.title = 'Edit track';
  btnEdit.textContent = '✎';
  btnEdit.addEventListener('click', (e) => { e.stopPropagation(); openSingleTrackEdit(track); });
  td.appendChild(btnEdit);

  return td;
}

// ---------------------------------------------------------------------------
// Track count display
// ---------------------------------------------------------------------------

function updateTrackCount(count) {
  const countEl = document.getElementById('tracks-count');
  if (!countEl) return;
  countEl.textContent = `${count} track${count !== 1 ? 's' : ''}`;
}

// ---------------------------------------------------------------------------
// Column picker init on DOM ready
// ---------------------------------------------------------------------------

function initColumnPicker() {
  const state = getColumnState();
  // Apply column visibility to thead
  document.querySelectorAll('.tracks-table thead th[data-col]').forEach(th => {
    const colId = th.dataset.col;
    const s = state.find(x => x.id === colId);
    if (s && !s.visible) th.style.display = 'none';
  });
}

// ---------------------------------------------------------------------------
// Audio Player Control (unchanged from v1)
// ---------------------------------------------------------------------------

function toggleAudioPlay(btn, filePath) {
  const audio = document.getElementById('audio-player');
  const audioUrl = `/api/audio?path=${encodeURIComponent(filePath)}`;
  const isSameFile = audio.src.endsWith(audioUrl) || audio.src === audioUrl;
  if (window.currentAudioPlayer !== audio || !isSameFile) {
    audio.pause();
    document.querySelectorAll('.audio-play-btn').forEach(b => {
      b.classList.remove('playing');
      b.textContent = '▶';
    });
    audio.src = audioUrl;
    window.currentAudioPlayer = audio;
    audio.load();
    btn.classList.add('playing');
    btn.textContent = '⏸';
    audio.addEventListener('canplay', function onCanPlay() {
      audio.removeEventListener('canplay', onCanPlay);
      audio.play().catch(() => { showToast('Could not play audio', 'error'); });
    }, { once: true });
    audio.addEventListener('error', function onAudioError() {
      audio.removeEventListener('error', onAudioError);
      showToast('Could not load audio', 'error');
      btn.classList.remove('playing');
      btn.textContent = '▶';
    }, { once: true });
  } else if (audio.paused) {
    audio.play();
    btn.classList.add('playing');
    btn.textContent = '⏸';
  } else {
    audio.pause();
    btn.classList.remove('playing');
    btn.textContent = '▶';
  }
}

// ---------------------------------------------------------------------------
// Legacy helpers
// ---------------------------------------------------------------------------

function playTrackInBrowser(track) {
  const existing = document.getElementById('inline-audio-player');
  if (existing) existing.remove();
  const player = document.createElement('div');
  player.id = 'inline-audio-player';
  player.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9000;background:var(--bg-secondary);border:1px solid var(--border-color);border-radius:10px;padding:12px 16px;display:flex;flex-direction:column;gap:8px;box-shadow:0 4px 20px rgba(0,0,0,0.4);max-width:340px;';
  const header = document.createElement('div');
  header.style.cssText = 'display:flex;align-items:center;gap:8px;';
  const title = document.createElement('div');
  title.style.cssText = 'font-size:12px;color:var(--text-secondary);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
  title.textContent = track.display_title || track.file_path?.split('/').pop() || 'Unknown';
  const closeBtn = document.createElement('button');
  closeBtn.textContent = 'X';
  closeBtn.style.cssText = 'background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:14px;padding:2px;flex-shrink:0;';
  closeBtn.addEventListener('click', () => player.remove());
  header.appendChild(title);
  header.appendChild(closeBtn);
  const audio = document.createElement('audio');
  audio.controls = true;
  audio.style.cssText = 'width:100%;height:32px;';
  audio.src = '/api/audio?path=' + encodeURIComponent(track.file_path);
  player.appendChild(header);
  player.appendChild(audio);
  document.body.appendChild(player);
  audio.play().catch(() => {});
}

function openSingleTrackEdit(track) {
  if (typeof openEditModal === 'function') {
    openEditModal(track.file_path);
  } else {
    showToast('Edit modal not available', 'error');
  }
}

function reclassifySingleTrack(track) {
  const inSelection = store.state.selectedTracks?.has(track.file_path);
  const multiSelected = store.state.selectedTracks?.size > 1;
  if (!(inSelection && multiSelected)) {
    if (!store.state.selectedTracks) store.set('selectedTracks', new Set());
    store.state.selectedTracks.clear();
    store.state.selectedTracks.add(track.file_path);
    if (typeof updateBulkActionsBar === 'function') updateBulkActionsBar();
  }
  if (typeof showReclassifyModal === 'function') {
    showReclassifyModal();
  } else {
    showToast('Re-classify modal not available', 'error');
  }
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

window.renderTracks = renderTracks;
window.toggleAudioPlay = toggleAudioPlay;
window.buildTrackRow = buildTrackRow;
window.getColumnState = getColumnState;
window.getGenreColor = getGenreColor;
window.getKeyboardSelectedIndex = getKeyboardSelectedIndex;
window.scrollToRow = scrollToRow;

store.subscribe('tracks', renderTracks);
