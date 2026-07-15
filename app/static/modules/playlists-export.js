// ============================================================================
// playlists-export.js — Playlists tab + Smart Playlist Builder v2 + M3U export
// ============================================================================
// Owns:
//   - Playlists CRUD: initPlaylistsTab / loadPlaylists / renderPlaylistsList /
//                     selectPlaylist / createNewPlaylist / saveCurrentPlaylist /
//                     getPlaylistFilters / runCurrentPlaylist / applyPlaylistFilters /
//                     clearPlaylistFilters / renderPlaylistResults /
//                     toggleSelectAllPlaylistResults / addAllResultsToPlaylist /
//                     exportCurrentPlaylist / deleteCurrentPlaylist
//   - Smart Playlist Builder v2: rule chips UI, nested AND/OR groups,
//     client-side debounced match-count preview, inline rule editing
// Module-local state:
//   - playlistsTabInited, currentPlaylistId, currentPlaylistTracks
// Dependencies (window-globals): showSpinner / hideSpinner / apiFetch / showToast /
//   escapeHtml (core.js), store.state.taxonomy (core.js), store.state.tracks
// Init:
//   - initPlaylistsTab: called lazily from navigation.js switchTab
//   - initSmartBuilder: called by initPlaylistsTab
// ----------------------------------------------------------------------------

let playlistsTabInited = false;
let currentPlaylistId = null;
let currentPlaylistTracks = [];

function initPlaylistsTab() {
  if (playlistsTabInited) return;
  playlistsTabInited = true;

  document.getElementById('btn-new-playlist')?.addEventListener('click', () => createNewPlaylist());
  document.getElementById('btn-new-playlist-empty')?.addEventListener('click', () => createNewPlaylist());
  document.getElementById('btn-save-playlist')?.addEventListener('click', () => saveCurrentPlaylist());
  document.getElementById('btn-run-playlist')?.addEventListener('click', () => runCurrentPlaylist());
  document.getElementById('btn-export-playlist')?.addEventListener('click', () => exportCurrentPlaylist());
  document.getElementById('btn-delete-playlist')?.addEventListener('click', () => deleteCurrentPlaylist());
  document.getElementById('btn-add-all-to-playlist')?.addEventListener('click', () => addAllResultsToPlaylist());
  document.getElementById('pl-select-all')?.addEventListener('change', (e) => toggleSelectAllPlaylistResults(e.target.checked));

  initSmartBuilder();

  loadPlaylists();
}

async function loadPlaylists() {
  try {
    const data = await apiFetch('/api/playlists');
    renderPlaylistsList(data.playlists || []);
  } catch (e) {
    showToast('Failed to load playlists: ' + e.message, 'error');
  }
}

function renderPlaylistsList(playlists) {
  const container = document.getElementById('playlists-list');
  if (!container) return;
  container.innerHTML = '';

  if (!playlists.length) {
    container.innerHTML = '<div class="empty-state" style="padding: 24px 12px; text-align: center; color: var(--text-secondary); font-size: 13px;">No playlists yet. Click "+ New" to create one.</div>';
    return;
  }

  playlists.forEach(pl => {
    const div = document.createElement('div');
    div.className = 'playlist-item' + (currentPlaylistId === pl.id ? ' active' : '');
    div.innerHTML = `
      <div class="playlist-item-name">${escapeHtml(pl.name)}</div>
      <div class="playlist-item-meta">${pl.track_count} tracks</div>
    `;
    div.addEventListener('click', () => selectPlaylist(pl.id));
    container.appendChild(div);
  });
}

async function selectPlaylist(playlistId) {
  try {
    const pl = await apiFetch('/api/playlists/' + encodeURIComponent(playlistId));
    currentPlaylistId = pl.id;
    currentPlaylistTracks = pl.tracks || [];

    const nameInput = document.getElementById('playlist-name-input');
    if (nameInput) nameInput.value = pl.name || '';

    // Load rules into smart builder
    const filters = pl.filters || {};
    const rules = filters.rules ? filters : _legacyFiltersToRulesJS(filters);
    _populateSmartBuilder(rules);

    // Show editor, hide empty state
    const editor = document.getElementById('playlist-editor');
    const emptyState = document.getElementById('playlist-empty-state');
    if (editor) editor.style.display = 'block';
    if (emptyState) emptyState.style.display = 'none';

    // Refresh the list to highlight
    await loadPlaylists();
  } catch (e) {
    showToast('Failed to load playlist: ' + e.message, 'error');
  }
}

async function createNewPlaylist() {
  const name = prompt('Playlist name:', 'My Playlist');
  if (!name) return;

  try {
    const result = await apiFetch('/api/playlists', {
      method: 'POST',
      body: JSON.stringify({ name: name, tracks: [], filters: {} })
    });
    showToast('Playlist created', 'success');
    await loadPlaylists();
    await selectPlaylist(result.id);
  } catch (e) {
    showToast('Failed to create playlist: ' + e.message, 'error');
  }
}

async function saveCurrentPlaylist() {
  if (!currentPlaylistId) return;

  const nameInput = document.getElementById('playlist-name-input');
  const filters = getPlaylistFilters();

  try {
    await apiFetch('/api/playlists/' + encodeURIComponent(currentPlaylistId), {
      method: 'PUT',
      body: JSON.stringify({
        name: nameInput ? nameInput.value : 'Untitled',
        filters: filters,
        tracks: currentPlaylistTracks
      })
    });
    showToast('Playlist saved', 'success');
    await loadPlaylists();
  } catch (e) {
    showToast('Failed to save playlist: ' + e.message, 'error');
  }
}

function getPlaylistFilters() {
  return _buildRulesFromUI();
}

async function runCurrentPlaylist() {
  if (!currentPlaylistId) return;

  showSpinner('Running playlist...');
  try {
    const result = await apiFetch('/api/playlists/' + encodeURIComponent(currentPlaylistId) + '/run', { method: 'POST' });
    renderPlaylistResults(result.tracks || []);
    showToast(result.count + ' tracks found', 'info');
  } catch (e) {
    showToast('Failed to run playlist: ' + e.message, 'error');
  } finally {
    hideSpinner();
  }
}

async function applyPlaylistFilters() {
  showSpinner('Applying filters...');
  try {
    const rules = _buildRulesFromUI();
    const result = await apiFetch('/api/playlists/match-preview', {
      method: 'POST',
      body: JSON.stringify({ rules: rules })
    });
    renderPlaylistResults(result.tracks || []);
    showToast(result.count + ' tracks found', 'info');
  } catch (e) {
    showToast('Failed to apply filters: ' + e.message, 'error');
  } finally {
    hideSpinner();
  }
}

function clearPlaylistFilters() {
  _populateSmartBuilder({ combinator: 'AND', rules: [] });
  document.getElementById('pl-results-tbody').innerHTML = '<tr class="empty-state"><td colspan="10"><div class="empty-state-content"><div class="empty-icon">🎵</div><div class="empty-msg">Apply filters to find tracks</div></div></td></tr>';
  document.getElementById('pl-results-count').textContent = '0';
}

function renderPlaylistResults(tracks) {
  const tbody = document.getElementById('pl-results-tbody');
  const countEl = document.getElementById('pl-results-count');
  if (countEl) countEl.textContent = tracks.length;

  if (!tracks.length) {
    tbody.innerHTML = '<tr class="empty-state"><td colspan="10"><div class="empty-state-content"><div class="empty-icon">🎵</div><div class="empty-msg">No tracks match these filters</div></div></td></tr>';
    return;
  }

  tbody.innerHTML = '';
  tracks.forEach((track, idx) => {
    const tr = document.createElement('tr');
    const inPlaylist = currentPlaylistTracks.includes(track.file_path);
    tr.innerHTML = `
      <td class="checkbox-col"><input type="checkbox" class="pl-result-checkbox" data-path="${escapeHtml(track.file_path)}" ${inPlaylist ? 'checked' : ''} /></td>
      <td class="col-title">${escapeHtml(track.display_title || '')}</td>
      <td class="col-artist">${escapeHtml(track.display_artist || '')}</td>
      <td class="col-genre">${escapeHtml(track.final_genre || '')}</td>
      <td class="col-bpm">${track.final_bpm || '—'}</td>
      <td class="col-key">${escapeHtml(track.final_key || '—')}</td>
      <td class="col-energy">${track.analyzed_energy || '—'}</td>
      <td class="col-year">${track.final_year || '—'}</td>
      <td class="col-status"><span class="badge badge-${track.review_status || 'pending'}">${escapeHtml(track.review_status || 'pending')}</span></td>
      <td class="col-actions">
        <button class="btn btn-secondary btn-sm pl-add-btn" data-path="${escapeHtml(track.file_path)}" ${inPlaylist ? 'disabled' : ''}>${inPlaylist ? 'Added' : '+ Add'}</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach event listeners
  tbody.querySelectorAll('.pl-add-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const path = decodeURIComponent(e.target.dataset.path);
      if (!currentPlaylistTracks.includes(path)) {
        currentPlaylistTracks.push(path);
        e.target.textContent = 'Added';
        e.target.disabled = true;
      }
    });
  });
}

function toggleSelectAllPlaylistResults(checked) {
  document.querySelectorAll('.pl-result-checkbox').forEach(cb => cb.checked = checked);
}

async function addAllResultsToPlaylist() {
  document.querySelectorAll('.pl-result-checkbox:checked').forEach(cb => {
    const path = cb.dataset.path;
    if (!currentPlaylistTracks.includes(path)) {
      currentPlaylistTracks.push(path);
    }
  });
  showToast('Tracks added to playlist', 'success');
}

async function exportCurrentPlaylist() {
  if (!currentPlaylistId) return;
  window.location.href = '/api/playlists/' + encodeURIComponent(currentPlaylistId) + '/export-m3u';
  showToast('Downloading M3U...', 'info');
}

async function deleteCurrentPlaylist() {
  if (!currentPlaylistId) return;
  if (!confirm('Delete this playlist?')) return;

  try {
    await apiFetch('/api/playlists/' + encodeURIComponent(currentPlaylistId), { method: 'DELETE' });
    currentPlaylistId = null;
    currentPlaylistTracks = [];
    const editor = document.getElementById('playlist-editor');
    const emptyState = document.getElementById('playlist-empty-state');
    if (editor) editor.style.display = 'none';
    if (emptyState) emptyState.style.display = 'block';
    await loadPlaylists();
    showToast('Playlist deleted', 'success');
  } catch (e) {
    showToast('Failed to delete playlist: ' + e.message, 'error');
  }
}

// ============================================================================
// Smart Playlist Builder v2 — rule chips, nested AND/OR, live match count
// ============================================================================

const SMART_RULE_FIELDS = [
  { id: 'genre', label: 'Genre', type: 'text', suggestFrom: 'taxonomy' },
  { id: 'subgenre', label: 'Subgenre', type: 'text' },
  { id: 'artist', label: 'Artist', type: 'text' },
  { id: 'title', label: 'Title', type: 'text' },
  { id: 'bpm', label: 'BPM', type: 'number' },
  { id: 'key', label: 'Key', type: 'text', presetValues: ['1A','1B','2A','2B','3A','3B','4A','4B','5A','5B','6A','6B','7A','7B','8A','8B','9A','9B','10A','10B','11A','11B','12A','12B'] },
  { id: 'energy', label: 'Energy', type: 'number' },
  { id: 'year', label: 'Year', type: 'number' },
  { id: 'status', label: 'Status', type: 'text', presetValues: ['pending','approved','skipped','written'] },
];

const SMART_STRING_OPERATORS = [
  { id: 'equals', label: 'is' },
  { id: 'not_equals', label: 'is not' },
  { id: 'contains', label: 'contains' },
  { id: 'starts_with', label: 'starts with' },
];

const SMART_NUMBER_OPERATORS = [
  { id: 'equals', label: '=' },
  { id: 'not_equals', label: '!=' },
  { id: 'gt', label: '>' },
  { id: 'lt', label: '<' },
  { id: 'gte', label: '>=' },
  { id: 'lte', label: '<=' },
];

const TRACK_FIELD_MAP = {
  genre: 'final_genre',
  subgenre: 'final_subgenre',
  artist: 'display_artist',
  title: 'display_title',
  bpm: 'final_bpm',
  key: 'final_key',
  energy: 'analyzed_energy',
  year: 'final_year',
  status: 'review_status',
};

let _matchDebounceTimer = null;
let _editingRuleKey = null;

function initSmartBuilder() {
  const topCombinator = document.getElementById('pl-top-combinator');
  if (topCombinator) {
    topCombinator.addEventListener('change', () => {
      _debouncedRecompute();
    });
  }

  document.getElementById('btn-add-rule')?.addEventListener('click', () => _addRuleTo('pl-rules-container'));
  document.getElementById('btn-add-group')?.addEventListener('click', () => _addGroupTo('pl-rules-container'));

  _populateSmartBuilder({ combinator: 'AND', rules: [] });
}

function _legacyFiltersToRulesJS(filters) {
  const rules = [];
  if (filters.genre) rules.push({ field: 'genre', operator: 'equals', value: filters.genre });
  if (filters.subgenre) rules.push({ field: 'subgenre', operator: 'equals', value: filters.subgenre });
  if (filters.status) rules.push({ field: 'status', operator: 'equals', value: filters.status });
  if (filters.key) rules.push({ field: 'key', operator: 'equals', value: filters.key });
  if (filters.bpm_min) rules.push({ field: 'bpm', operator: 'gte', value: filters.bpm_min });
  if (filters.bpm_max) rules.push({ field: 'bpm', operator: 'lte', value: filters.bpm_max });
  if (filters.energy_min) rules.push({ field: 'energy', operator: 'gte', value: filters.energy_min });
  if (filters.energy_max) rules.push({ field: 'energy', operator: 'lte', value: filters.energy_max });
  if (filters.year_min) rules.push({ field: 'year', operator: 'gte', value: filters.year_min });
  if (filters.year_max) rules.push({ field: 'year', operator: 'lte', value: filters.year_max });
  return { combinator: 'AND', rules: rules };
}

function _buildRulesFromUI() {
  return _readGroupFromDOM('pl-rules-container', document.getElementById('pl-top-combinator')?.value || 'AND');
}

function _readGroupFromDOM(containerId, inheritedCombinator) {
  const container = document.getElementById(containerId);
  if (!container) return { combinator: inheritedCombinator, rules: [] };

  const combinator = container.closest('.rule-group')
    ? container.closest('.rule-group').querySelector('.combinator-select')?.value || 'AND'
    : (document.getElementById('pl-top-combinator')?.value || inheritedCombinator);

  const result = { combinator: combinator, rules: [] };
  const items = container.querySelectorAll(':scope > .rule-chip-wrapper, :scope > .rule-group');

  items.forEach(item => {
    if (item.classList.contains('rule-group')) {
      const groupBody = item.querySelector('.rule-group-body');
      if (groupBody) {
        result.rules.push(_readGroupFromDOM(groupBody.id, 'AND'));
      }
    } else if (item.classList.contains('rule-chip-wrapper')) {
      const field = item.dataset.field;
      const operator = item.dataset.operator;
      const value = item.dataset.value;
      if (field && operator && value !== undefined) {
        result.rules.push({ field: field, operator: operator, value: value });
      }
    }
  });

  return result;
}

function _debouncedRecompute() {
  clearTimeout(_matchDebounceTimer);
  _matchDebounceTimer = setTimeout(() => {
    _recomputeMatchCount();
  }, 300);
}

function _recomputeMatchCount() {
  const rules = _buildRulesFromUI();
  const tracks = store.state.tracks || [];
  let count = 0;

  if (!rules.rules || rules.rules.length === 0) {
    count = tracks.length;
  } else {
    count = tracks.filter(t => _groupMatchesTrack(t, rules)).length;
  }

  const badge = document.getElementById('pl-match-count-badge');
  if (badge) {
    badge.textContent = count + ' track' + (count !== 1 ? 's' : '') + ' match';
    badge.classList.remove('pulse');
    void badge.offsetWidth;
    badge.classList.add('pulse');
  }

  document.getElementById('pl-results-count').textContent = count;
}

function _groupMatchesTrack(track, group) {
  const combinator = group.combinator || 'AND';
  const rules = group.rules || [];
  if (!rules.length) return true;

  const results = rules.map(r => {
    if (r.combinator) return _groupMatchesTrack(track, r);
    return _singleRuleMatches(track, r);
  });

  return combinator === 'OR' ? results.some(Boolean) : results.every(Boolean);
}

function _singleRuleMatches(track, rule) {
  const fieldKey = TRACK_FIELD_MAP[rule.field] || rule.field;
  const trackVal = track[fieldKey];
  const op = rule.operator || 'equals';
  const val = rule.value;

  if (trackVal === undefined || trackVal === null) return false;

  switch (op) {
    case 'equals':
      return String(trackVal) === String(val);
    case 'not_equals':
      return String(trackVal) !== String(val);
    case 'contains':
      return String(trackVal).toLowerCase().indexOf(String(val).toLowerCase()) !== -1;
    case 'starts_with':
      return String(trackVal).toLowerCase().startsWith(String(val).toLowerCase());
    case 'gt':
      return parseFloat(trackVal) > parseFloat(val || 0);
    case 'lt':
      return parseFloat(trackVal) < parseFloat(val || 0);
    case 'gte':
      return parseFloat(trackVal) >= parseFloat(val || 0);
    case 'lte':
      return parseFloat(trackVal) <= parseFloat(val || 0);
    default:
      return true;
  }
}

function _populateSmartBuilder(group) {
  const topCombinator = document.getElementById('pl-top-combinator');
  if (topCombinator && group.combinator) {
    topCombinator.value = group.combinator;
  }

  const container = document.getElementById('pl-rules-container');
  if (!container) return;
  container.innerHTML = '';

  _renderRuleGroupInto(container, group);
  _recomputeMatchCount();
}

function _renderRuleGroupInto(container, group) {
  const rules = group.rules || [];

  if (!rules.length) {
    container.innerHTML = '<div class="rules-container-empty">No rules yet. Click "+ Add Rule" to start filtering.</div>';
    return;
  }

  rules.forEach((rule, idx) => {
    if (idx > 0) {
      const connector = document.createElement('div');
      connector.className = 'rule-connector';
      connector.innerHTML = '<span class="rule-connector-text">' + (group.combinator || 'AND') + '</span>';
      container.appendChild(connector);
    }

    if (rule.combinator) {
      _renderGroupElement(container, rule, idx);
    } else {
      _renderRuleChip(container, rule, idx);
    }
  });
}

function _renderGroupElement(container, group, idx) {
  const groupEl = document.createElement('div');
  groupEl.className = 'rule-group';

  const bodyId = 'pl-group-body-' + Date.now() + '-' + idx;
  groupEl.innerHTML = `
    <div class="rule-group-header">
      <span class="rule-group-label">Group</span>
      <select class="combinator-select">
        <option value="AND" ${group.combinator === 'AND' ? 'selected' : ''}>ALL of</option>
        <option value="OR" ${group.combinator === 'OR' ? 'selected' : ''}>ANY of</option>
      </select>
      <button class="rule-editor-cancel group-remove-btn" title="Remove group">&times;</button>
    </div>
    <div class="rule-group-body" id="${bodyId}"></div>
    <div class="rule-group-footer">
      <button class="btn btn-secondary btn-sm add-rule-in-group-btn">+ Add Rule</button>
      <button class="btn btn-secondary btn-sm add-group-in-group-btn">+ Add Group</button>
    </div>
  `;

  container.appendChild(groupEl);

  const body = groupEl.querySelector('#' + bodyId);
  _renderRuleGroupInto(body, group);

  groupEl.querySelector('.combinator-select')?.addEventListener('change', () => {
    _debouncedRecompute();
  });
  groupEl.querySelector('.group-remove-btn')?.addEventListener('click', () => {
    const parent = groupEl.parentElement;
    groupEl.remove();
    if (parent) _cleanupConnectors(parent);
    _debouncedRecompute();
  });
  groupEl.querySelector('.add-rule-in-group-btn')?.addEventListener('click', () => _addRuleTo(bodyId));
  groupEl.querySelector('.add-group-in-group-btn')?.addEventListener('click', () => _addGroupTo(bodyId));
}

function _renderRuleChip(container, rule, idx) {
  const wrapper = document.createElement('div');
  wrapper.className = 'rule-chip-wrapper';
  wrapper.dataset.field = rule.field;
  wrapper.dataset.operator = rule.operator;
  wrapper.dataset.value = rule.value;

  const fieldDef = SMART_RULE_FIELDS.find(f => f.id === rule.field) || { label: rule.field };
  const opDef = _getOperatorsForField(rule.field).find(o => o.id === rule.operator) || { label: rule.operator };

  wrapper.innerHTML = `
    <div class="rule-chip">
      <span class="rule-chip-field">${escapeHtml(fieldDef.label)}</span>
      <span class="rule-chip-operator">${escapeHtml(opDef.label)}</span>
      <span class="rule-chip-value">${escapeHtml(String(rule.value))}</span>
      <button class="rule-chip-remove" title="Remove rule">&times;</button>
    </div>
  `;

  container.appendChild(wrapper);

  wrapper.querySelector('.rule-chip')?.addEventListener('click', (e) => {
    if (e.target.classList.contains('rule-chip-remove')) return;
    _editRuleInline(wrapper, container);
  });

  wrapper.querySelector('.rule-chip-remove')?.addEventListener('click', (e) => {
    e.stopPropagation();
    wrapper.remove();
    _cleanupConnectors(container);
    _debouncedRecompute();
  });
}

function _editRuleInline(wrapper, parentContainer) {
  const field = wrapper.dataset.field;
  const operator = wrapper.dataset.operator;
  const value = wrapper.dataset.value;

  const editor = document.createElement('div');
  editor.className = 'rule-editor-row';
  editor.dataset.editing = wrapper;

  const fieldDef = SMART_RULE_FIELDS.find(f => f.id === field);
  const isNumeric = fieldDef && fieldDef.type === 'number';
  const operators = _getOperatorsForField(field);

  let valueHTML = '';
  if (fieldDef && fieldDef.presetValues) {
    valueHTML = '<select class="rule-editor-value">' +
      fieldDef.presetValues.map(v => '<option value="' + v + '" ' + (v === value ? 'selected' : '') + '>' + escapeHtml(v) + '</option>').join('') +
      '</select>';
  } else if (fieldDef && fieldDef.suggestFrom === 'taxonomy') {
    const genres = store.state.taxonomy ? Object.keys(store.state.taxonomy) : [];
    valueHTML = '<select class="rule-editor-value"><option value="">—</option>' +
      genres.map(g => '<option value="' + g + '" ' + (g === value ? 'selected' : '') + '>' + escapeHtml(g) + '</option>').join('') +
      '</select>';
  } else {
    valueHTML = '<input type="' + (isNumeric ? 'number' : 'text') + '" class="rule-editor-value" value="' + escapeHtml(value || '') + '" placeholder="value">';
  }

  editor.innerHTML = `
    <select class="rule-editor-field">
      ${SMART_RULE_FIELDS.map(f => '<option value="' + f.id + '" ' + (f.id === field ? 'selected' : '') + '>' + escapeHtml(f.label) + '</option>').join('')}
    </select>
    <select class="rule-editor-operator">
      ${operators.map(o => '<option value="' + o.id + '" ' + (o.id === operator ? 'selected' : '') + '>' + escapeHtml(o.label) + '</option>').join('')}
    </select>
    ${valueHTML}
    <div class="rule-editor-actions">
      <button class="rule-editor-ok" title="Apply">&#10003;</button>
      <button class="rule-editor-cancel" title="Cancel">&times;</button>
    </div>
  `;

  wrapper.replaceWith(editor);

  editor.querySelector('.rule-editor-field')?.addEventListener('change', (e) => {
    const newField = e.target.value;
    const newFieldDef = SMART_RULE_FIELDS.find(f => f.id === newField);
    const newOperators = _getOperatorsForField(newField);
    const opSelect = editor.querySelector('.rule-editor-operator');
    if (opSelect) {
      opSelect.innerHTML = newOperators.map(o => '<option value="' + o.id + '">' + escapeHtml(o.label) + '</option>').join('');
    }
    const valEl = editor.querySelector('.rule-editor-value');
    if (valEl) {
      if (newFieldDef && newFieldDef.presetValues) {
        valEl.outerHTML = '<select class="rule-editor-value">' +
          newFieldDef.presetValues.map(v => '<option value="' + v + '">' + escapeHtml(v) + '</option>').join('') +
          '</select>';
      } else if (newFieldDef && newFieldDef.suggestFrom === 'taxonomy') {
        const genres = store.state.taxonomy ? Object.keys(store.state.taxonomy) : [];
        valEl.outerHTML = '<select class="rule-editor-value"><option value="">\u2014</option>' +
          genres.map(g => '<option value="' + g + '">' + escapeHtml(g) + '</option>').join('') +
          '</select>';
      } else {
        const isNum = newFieldDef && newFieldDef.type === 'number';
        valEl.outerHTML = '<input type="' + (isNum ? 'number' : 'text') + '" class="rule-editor-value" value="" placeholder="value">';
      }
    }
  });

  editor.querySelector('.rule-editor-ok')?.addEventListener('click', () => {
    const newField = editor.querySelector('.rule-editor-field')?.value || field;
    const newOp = editor.querySelector('.rule-editor-operator')?.value || operator;
    const newVal = editor.querySelector('.rule-editor-value')?.value || '';

    const newWrapper = document.createElement('div');
    newWrapper.className = 'rule-chip-wrapper';
    newWrapper.dataset.field = newField;
    newWrapper.dataset.operator = newOp;
    newWrapper.dataset.value = newVal;

    const fieldDef2 = SMART_RULE_FIELDS.find(f => f.id === newField) || { label: newField };
    const opDef2 = _getOperatorsForField(newField).find(o => o.id === newOp) || { label: newOp };

    newWrapper.innerHTML = `
      <div class="rule-chip">
        <span class="rule-chip-field">${escapeHtml(fieldDef2.label)}</span>
        <span class="rule-chip-operator">${escapeHtml(opDef2.label)}</span>
        <span class="rule-chip-value">${escapeHtml(String(newVal))}</span>
        <button class="rule-chip-remove" title="Remove rule">&times;</button>
      </div>
    `;

    editor.replaceWith(newWrapper);

    newWrapper.querySelector('.rule-chip')?.addEventListener('click', (e2) => {
      if (e2.target.classList.contains('rule-chip-remove')) return;
      _editRuleInline(newWrapper, parentContainer);
    });
    newWrapper.querySelector('.rule-chip-remove')?.addEventListener('click', (e3) => {
      e3.stopPropagation();
      newWrapper.remove();
      _cleanupConnectors(parentContainer);
      _debouncedRecompute();
    });

    _debouncedRecompute();
  });

  editor.querySelector('.rule-editor-cancel')?.addEventListener('click', () => {
    editor.replaceWith(wrapper);
  });
}

function _addRuleTo(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const emptyMsg = container.querySelector('.rules-container-empty');
  if (emptyMsg) emptyMsg.remove();

  if (container.children.length > 0) {
    const combinator = container.closest('.rule-group')
      ? (container.closest('.rule-group').querySelector('.combinator-select')?.value || 'AND')
      : (document.getElementById('pl-top-combinator')?.value || 'AND');
    const connector = document.createElement('div');
    connector.className = 'rule-connector';
    connector.innerHTML = '<span class="rule-connector-text">' + combinator + '</span>';
    container.appendChild(connector);
  }

  const wrapper = document.createElement('div');
  wrapper.className = 'rule-chip-wrapper';
  wrapper.dataset.field = 'genre';
  wrapper.dataset.operator = 'equals';
  wrapper.dataset.value = '';

  container.appendChild(wrapper);
  _editRuleInline(wrapper, container);
  _debouncedRecompute();
}

function _addGroupTo(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const emptyMsg = container.querySelector('.rules-container-empty');
  if (emptyMsg) emptyMsg.remove();

  if (container.children.length > 0) {
    const combinator = container.closest('.rule-group')
      ? (container.closest('.rule-group').querySelector('.combinator-select')?.value || 'AND')
      : (document.getElementById('pl-top-combinator')?.value || 'AND');
    const connector = document.createElement('div');
    connector.className = 'rule-connector';
    connector.innerHTML = '<span class="rule-connector-text">' + combinator + '</span>';
    container.appendChild(connector);
  }

  const group = { combinator: 'AND', rules: [] };
  _renderGroupElement(container, group, Date.now());
  _debouncedRecompute();
}

function _cleanupConnectors(container) {
  const children = Array.from(container.children);
  const firstReal = children.findIndex(c => !c.classList.contains('rule-connector'));

  children.forEach((child, i) => {
    if (child.classList.contains('rule-connector')) {
      const prevReal = _findPrevReal(children, i);
      const nextReal = _findNextReal(children, i);
      if (!prevReal || !nextReal) {
        child.remove();
      }
    }
  });

  if (container.children.length === 0) {
    container.innerHTML = '<div class="rules-container-empty">No rules yet. Click "+ Add Rule" to start filtering.</div>';
  }
}

function _findPrevReal(children, i) {
  for (let j = i - 1; j >= 0; j--) {
    if (!children[j].classList.contains('rule-connector')) return children[j];
  }
  return null;
}

function _findNextReal(children, i) {
  for (let j = i + 1; j < children.length; j++) {
    if (!children[j].classList.contains('rule-connector')) return children[j];
  }
  return null;
}

function _getOperatorsForField(fieldId) {
  const fieldDef = SMART_RULE_FIELDS.find(f => f.id === fieldId);
  if (fieldDef && fieldDef.type === 'number') return SMART_NUMBER_OPERATORS;
  return SMART_STRING_OPERATORS;
}


// --- ES module bridge (0.4): expose to global scope for cross-module calls ---
window.initPlaylistsTab = initPlaylistsTab;
