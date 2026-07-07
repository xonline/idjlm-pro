// ============================================================================
// playlists-export.js — Playlists tab + Smart Playlist Builder + M3U export
// ============================================================================
// Extracted from pipeline.js (Phase 0.3). No behaviour change.
// Owns:
//   - Playlists CRUD: initPlaylistsTab / loadPlaylists / renderPlaylistsList /
//                     selectPlaylist / createNewPlaylist / saveCurrentPlaylist /
//                     getPlaylistFilters / runCurrentPlaylist / applyPlaylistFilters /
//                     clearPlaylistFilters / renderPlaylistResults /
//                     toggleSelectAllPlaylistResults / addAllResultsToPlaylist /
//                     exportCurrentPlaylist / deleteCurrentPlaylist /
//                     populatePlaylistGenreFilter
//   - Smart Playlist Builder: initPlaylistBuilder / populatePlaylistFilters /
//                            populatePlaylistSubgenres / exportCustomPlaylist
// Module-local state:
//   - playlistsTabInited, currentPlaylistId, currentPlaylistTracks
// Dependencies (window-globals): showSpinner / hideSpinner / apiFetch / showToast /
//   escapeHtml (core.js), window.taxonomy (core.js)
// Init:
//   - initPlaylistsTab: called lazily from navigation.js switchTab
//   - initPlaylistBuilder: defined but never called (preserved for parity)
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
  document.getElementById('btn-apply-filters')?.addEventListener('click', () => applyPlaylistFilters());
  document.getElementById('btn-clear-filters')?.addEventListener('click', () => clearPlaylistFilters());
  document.getElementById('btn-add-all-to-playlist')?.addEventListener('click', () => addAllResultsToPlaylist());
  document.getElementById('pl-select-all')?.addEventListener('change', (e) => toggleSelectAllPlaylistResults(e.target.checked));

  // Populate genre filter from taxonomy
  populatePlaylistGenreFilter();

  loadPlaylists();
}

function populatePlaylistGenreFilter() {
  const genreSelect = document.getElementById('pl-filter-genre');
  const subgenreSelect = document.getElementById('pl-filter-subgenre');
  if (genreSelect && window.taxonomy) {
    Object.keys(window.taxonomy).forEach(genre => {
      const opt = document.createElement('option');
      opt.value = genre;
      opt.textContent = genre;
      genreSelect.appendChild(opt);
    });
  }
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

    // Load filters
    const filters = pl.filters || {};
    if (document.getElementById('pl-filter-genre')) document.getElementById('pl-filter-genre').value = filters.genre || '';
    if (document.getElementById('pl-filter-subgenre')) document.getElementById('pl-filter-subgenre').value = filters.subgenre || '';
    if (document.getElementById('pl-filter-status')) document.getElementById('pl-filter-status').value = filters.status || '';
    if (document.getElementById('pl-filter-key')) document.getElementById('pl-filter-key').value = filters.key || '';
    if (document.getElementById('pl-filter-bpm-min')) document.getElementById('pl-filter-bpm-min').value = filters.bpm_min || '';
    if (document.getElementById('pl-filter-bpm-max')) document.getElementById('pl-filter-bpm-max').value = filters.bpm_max || '';
    if (document.getElementById('pl-filter-energy-min')) document.getElementById('pl-filter-energy-min').value = filters.energy_min || '';
    if (document.getElementById('pl-filter-energy-max')) document.getElementById('pl-filter-energy-max').value = filters.energy_max || '';
    if (document.getElementById('pl-filter-year-min')) document.getElementById('pl-filter-year-min').value = filters.year_min || '';
    if (document.getElementById('pl-filter-year-max')) document.getElementById('pl-filter-year-max').value = filters.year_max || '';

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
  return {
    genre: document.getElementById('pl-filter-genre')?.value || '',
    subgenre: document.getElementById('pl-filter-subgenre')?.value || '',
    status: document.getElementById('pl-filter-status')?.value || '',
    key: document.getElementById('pl-filter-key')?.value || '',
    bpm_min: document.getElementById('pl-filter-bpm-min')?.value || '',
    bpm_max: document.getElementById('pl-filter-bpm-max')?.value || '',
    energy_min: document.getElementById('pl-filter-energy-min')?.value || '',
    energy_max: document.getElementById('pl-filter-energy-max')?.value || '',
    year_min: document.getElementById('pl-filter-year-min')?.value || '',
    year_max: document.getElementById('pl-filter-year-max')?.value || '',
  };
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
    const filters = getPlaylistFilters();
    const result = await apiFetch('/api/playlists/run', {
      method: 'POST',
      body: JSON.stringify({ filters: filters })
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
  if (document.getElementById('pl-filter-genre')) document.getElementById('pl-filter-genre').value = '';
  if (document.getElementById('pl-filter-subgenre')) document.getElementById('pl-filter-subgenre').value = '';
  if (document.getElementById('pl-filter-status')) document.getElementById('pl-filter-status').value = '';
  if (document.getElementById('pl-filter-key')) document.getElementById('pl-filter-key').value = '';
  if (document.getElementById('pl-filter-bpm-min')) document.getElementById('pl-filter-bpm-min').value = '';
  if (document.getElementById('pl-filter-bpm-max')) document.getElementById('pl-filter-bpm-max').value = '';
  if (document.getElementById('pl-filter-energy-min')) document.getElementById('pl-filter-energy-min').value = '';
  if (document.getElementById('pl-filter-energy-max')) document.getElementById('pl-filter-energy-max').value = '';
  if (document.getElementById('pl-filter-year-min')) document.getElementById('pl-filter-year-min').value = '';
  if (document.getElementById('pl-filter-year-max')) document.getElementById('pl-filter-year-max').value = '';
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
// Smart Playlist Builder
// ============================================================================

function initPlaylistBuilder() {
  // Add playlist builder to export section (review-footer area)
  const reviewFooter = document.querySelector('.review-footer');
  if (reviewFooter) {
    const builder = document.createElement('div');
    builder.className = 'playlist-builder';
    builder.innerHTML = `
      <h3>Build Custom Playlist</h3>
      <div class="playlist-filters">
        <div class="playlist-filter-group">
          <label>Min BPM</label>
          <input type="number" class="input-text" id="pb-bpm-min" min="40" max="200" placeholder="Min">
        </div>
        <div class="playlist-filter-group">
          <label>Max BPM</label>
          <input type="number" class="input-text" id="pb-bpm-max" min="40" max="200" placeholder="Max">
        </div>
        <div class="playlist-filter-group">
          <label>Min Energy</label>
          <input type="range" class="slider" id="pb-energy-min" min="1" max="10" value="1">
          <span id="pb-energy-min-val">1</span>
        </div>
        <div class="playlist-filter-group">
          <label>Max Energy</label>
          <input type="range" class="slider" id="pb-energy-max" min="1" max="10" value="10">
          <span id="pb-energy-max-val">10</span>
        </div>
        <div class="playlist-filter-group">
          <label>Key</label>
          <select class="input-select" id="pb-key">
            <option value="">Any Key</option>
          </select>
        </div>
        <div class="playlist-filter-group">
          <label>Genre</label>
          <select class="input-select" id="pb-genre">
            <option value="">Any Genre</option>
          </select>
        </div>
        <div class="playlist-filter-group">
          <label>Comments</label>
          <select class="input-select" id="pb-subgenre">
            <option value="">Any Comments</option>
          </select>
        </div>
        <div class="playlist-filter-group">
          <label>Status</label>
          <select class="input-select" id="pb-status">
            <option value="">All</option>
            <option value="approved">Approved Only</option>
          </select>
        </div>
      </div>
      <div class="playlist-filter-group">
        <label>Playlist Filename</label>
        <input type="text" class="input-text" id="pb-filename" placeholder="idlm-playlist">
      </div>
      <div class="playlist-export-buttons">
        <button class="btn btn-primary" id="btn-export-m3u">📥 Export M3U</button>
      </div>
    `;
    reviewFooter.parentNode.insertBefore(builder, reviewFooter);

    // Populate genre/key selects
    populatePlaylistFilters();

    // Event listeners
    document.getElementById('pb-energy-min').addEventListener('input', (e) => {
      document.getElementById('pb-energy-min-val').textContent = e.target.value;
    });
    document.getElementById('pb-energy-max').addEventListener('input', (e) => {
      document.getElementById('pb-energy-max-val').textContent = e.target.value;
    });

    document.getElementById('pb-genre').addEventListener('change', () => {
      populatePlaylistSubgenres();
    });

    document.getElementById('btn-export-m3u').addEventListener('click', exportCustomPlaylist);
  }
}

function populatePlaylistFilters() {
  const genreSelect = document.getElementById('pb-genre');
  const keySelect = document.getElementById('pb-key');

  // Populate genres
  Object.keys(window.taxonomy).forEach(genre => {
    const opt = document.createElement('option');
    opt.value = genre;
    opt.textContent = genre;
    genreSelect.appendChild(opt);
  });

  // Populate keys (unique from tracks)
  const keys = new Set();
  window.tracks.forEach(t => {
    if (t.final_key) keys.add(t.final_key);
  });

  [...keys].sort().forEach(key => {
    const opt = document.createElement('option');
    opt.value = key;
    opt.textContent = key;
    keySelect.appendChild(opt);
  });
}

function populatePlaylistSubgenres() {
  const genre = document.getElementById('pb-genre').value;
  const select = document.getElementById('pb-subgenre');

  select.innerHTML = '<option value="">Any Comments</option>';

  if (!genre) return;

  const subgenres = new Set();
  window.tracks
    .filter(t => t.final_genre === genre)
    .forEach(t => {
      if (t.final_subgenre) subgenres.add(t.final_subgenre);
    });

  [...subgenres].sort().forEach(sub => {
    const opt = document.createElement('option');
    opt.value = sub;
    opt.textContent = sub;
    select.appendChild(opt);
  });
}

function exportCustomPlaylist() {
  const bpmMin = document.getElementById('pb-bpm-min').value || '';
  const bpmMax = document.getElementById('pb-bpm-max').value || '';
  const energyMin = document.getElementById('pb-energy-min').value || '';
  const energyMax = document.getElementById('pb-energy-max').value || '';
  const key = document.getElementById('pb-key').value || '';
  const genre = document.getElementById('pb-genre').value || '';
  const subgenre = document.getElementById('pb-subgenre').value || '';
  const status = document.getElementById('pb-status').value || '';
  const filename = document.getElementById('pb-filename').value || 'idlm-playlist';

  const params = new URLSearchParams();
  if (bpmMin) params.append('bpm_min', bpmMin);
  if (bpmMax) params.append('bpm_max', bpmMax);
  if (energyMin) params.append('energy_min', energyMin);
  if (energyMax) params.append('energy_max', energyMax);
  if (key) params.append('key', key);
  if (genre) params.append('genre', genre);
  if (subgenre) params.append('subgenre', subgenre);
  if (status) params.append('status', status);
  params.append('filename', filename);

  window.location = `/api/export/m3u?${params.toString()}`;
  showToast('Downloading playlist...', 'info');
}


// --- ES module bridge (0.4): expose to global scope for cross-module calls ---
window.initPlaylistsTab = initPlaylistsTab;
