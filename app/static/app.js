// ============================================================================
// IDLM Pro — Vanilla JS Application
// ============================================================================

// Global state
window.tracks = [];
window.taxonomy = {};
window.currentSort = { field: 'display_title', direction: 'asc' };
let statsInterval = null;
let currentEditPath = null;
let currentAudioPlayer = null;
let isWatching = false;
let watchPollInterval = null;
let chartInstances = {
  genres: null,
  bpm: null,
  years: null,
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

function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.style.display = 'block';
  setTimeout(() => {
    toast.style.display = 'none';
  }, 4000);
}

function switchTab(tabName) {
  // Hide all tabs
  document.querySelectorAll('.tab').forEach(tab => {
    tab.classList.remove('active');
  });

  // Deactivate all nav buttons
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.remove('active');
  });

  // Show selected tab
  const tab = document.getElementById(`tab-${tabName}`);
  if (tab) {
    tab.classList.add('active');
  }

  // Activate nav button
  const btn = document.querySelector(`[data-tab="${tabName}"]`);
  if (btn) {
    btn.classList.add('active');
  }
}

// ============================================================================
// Stats Panel
// ============================================================================

async function updateStats() {
  try {
    const stats = await apiFetch('/api/stats');
    document.getElementById('stat-total').textContent = stats.total || 0;
    document.getElementById('stat-analyzed').textContent = stats.analyzed || 0;
    document.getElementById('stat-classified').textContent = stats.classified || 0;
    document.getElementById('stat-approved').textContent = stats.approved || 0;
    document.getElementById('stat-written').textContent = stats.written || 0;
  } catch (error) {
    // Silently fail on stats update
  }
}

function startStatsPolling() {
  if (statsInterval) clearInterval(statsInterval);
  statsInterval = setInterval(updateStats, 5000);
  updateStats();
}

function stopStatsPolling() {
  if (statsInterval) {
    clearInterval(statsInterval);
    statsInterval = null;
  }
}

// ============================================================================
// Stats Tab
// ============================================================================

function initStatsTab() {
  const statsBtn = document.querySelector('[data-tab="stats"]');
  if (statsBtn) {
    statsBtn.addEventListener('click', () => {
      renderStats();
    });
  }
}

function renderStats() {
  if (!window.tracks.length) {
    // Clear all charts
    Object.keys(chartInstances).forEach(key => {
      if (chartInstances[key]) {
        chartInstances[key].destroy();
        chartInstances[key] = null;
      }
    });
    document.getElementById('subgenre-list').innerHTML = '';
    return;
  }

  // Update stats cards
  const total = window.tracks.length;
  const classified = window.tracks.filter(t => t.final_genre).length;
  const approved = window.tracks.filter(t => t.review_status === 'approved').length;
  const written = window.tracks.filter(t => t.review_status === 'written').length;

  document.getElementById('stats-card-total').textContent = total;
  document.getElementById('stats-card-classified').textContent = classified;
  document.getElementById('stats-card-approved').textContent = approved;
  document.getElementById('stats-card-written').textContent = written;

  // Genre breakdown chart
  renderGenreChart();

  // BPM distribution chart
  renderBpmChart();

  // Year breakdown chart
  renderYearChart();

  // Sub-genre list
  renderSubgenreList();
}

function renderGenreChart() {
  const genreCounts = {};
  window.tracks.forEach(track => {
    const genre = track.final_genre || 'Unknown';
    genreCounts[genre] = (genreCounts[genre] || 0) + 1;
  });

  const labels = Object.keys(genreCounts).sort((a, b) => genreCounts[b] - genreCounts[a]);
  const data = labels.map(label => genreCounts[label]);

  const ctx = document.getElementById('chart-genres');
  if (!ctx) return;

  if (chartInstances.genres) {
    chartInstances.genres.destroy();
  }

  chartInstances.genres = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Track Count',
        data: data,
        backgroundColor: '#8b5cf6',
        borderColor: '#a78bfa',
        borderWidth: 1,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false,
        }
      },
      scales: {
        x: {
          ticks: { color: '#888' },
          grid: { color: '#2a2a3a' }
        },
        y: {
          ticks: { color: '#888' },
          grid: { color: '#2a2a3a' }
        }
      }
    }
  });
}

function renderBpmChart() {
  const ranges = {
    '60-79': 0,
    '80-89': 0,
    '90-99': 0,
    '100-109': 0,
    '110-119': 0,
    '120+': 0,
  };

  window.tracks.forEach(track => {
    const bpm = parseFloat(track.final_bpm) || 0;
    if (bpm < 80) ranges['60-79']++;
    else if (bpm < 90) ranges['80-89']++;
    else if (bpm < 100) ranges['90-99']++;
    else if (bpm < 110) ranges['100-109']++;
    else if (bpm < 120) ranges['110-119']++;
    else ranges['120+']++;
  });

  const labels = Object.keys(ranges);
  const data = Object.values(ranges);

  const ctx = document.getElementById('chart-bpm');
  if (!ctx) return;

  if (chartInstances.bpm) {
    chartInstances.bpm.destroy();
  }

  chartInstances.bpm = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Track Count',
        data: data,
        backgroundColor: '#34d399',
        borderColor: '#6ee7b7',
        borderWidth: 1,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false,
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { color: '#888' },
          grid: { color: '#2a2a3a' }
        },
        x: {
          ticks: { color: '#888' },
          grid: { color: '#2a2a3a' }
        }
      }
    }
  });
}

function renderYearChart() {
  const decades = {
    'Pre-2000': 0,
    '2000s': 0,
    '2010s': 0,
    '2020s': 0,
  };

  window.tracks.forEach(track => {
    const year = parseInt(track.final_year) || 0;
    if (year < 2000) decades['Pre-2000']++;
    else if (year < 2010) decades['2000s']++;
    else if (year < 2020) decades['2010s']++;
    else decades['2020s']++;
  });

  const labels = Object.keys(decades);
  const data = Object.values(decades);

  const ctx = document.getElementById('chart-years');
  if (!ctx) return;

  if (chartInstances.years) {
    chartInstances.years.destroy();
  }

  chartInstances.years = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Track Count',
        data: data,
        backgroundColor: '#fbbf24',
        borderColor: '#fcd34d',
        borderWidth: 1,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false,
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { color: '#888' },
          grid: { color: '#2a2a3a' }
        },
        x: {
          ticks: { color: '#888' },
          grid: { color: '#2a2a3a' }
        }
      }
    }
  });
}

function renderSubgenreList() {
  const subgenreCounts = {};
  window.tracks.forEach(track => {
    const subgenre = track.final_subgenre || 'Unclassified';
    subgenreCounts[subgenre] = (subgenreCounts[subgenre] || 0) + 1;
  });

  // Sort by count, get top 10
  const sorted = Object.entries(subgenreCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  const container = document.getElementById('subgenre-list');
  container.innerHTML = '';

  if (!sorted.length) {
    container.innerHTML = '<div class="empty-state">No sub-genres yet</div>';
    return;
  }

  sorted.forEach(([subgenre, count]) => {
    const item = document.createElement('div');
    item.className = 'subgenre-item';

    const nameSpan = document.createElement('span');
    nameSpan.className = 'subgenre-item-name';
    nameSpan.textContent = subgenre;

    const countBadge = document.createElement('span');
    countBadge.className = 'subgenre-item-count';
    countBadge.textContent = count;

    item.appendChild(nameSpan);
    item.appendChild(countBadge);
    container.appendChild(item);
  });
}

// ============================================================================
// Import Tab
// ============================================================================

function initImportTab() {
  const btnChooseFolder = document.getElementById('btn-choose-folder');
  const btnImport = document.getElementById('btn-import');
  const btnAnalyze = document.getElementById('btn-analyze');
  const btnClassify = document.getElementById('btn-classify');
  const btnReviewTab = document.getElementById('btn-review-tab');
  const folderInput = document.getElementById('folder-input');
  const chosenDisplay = document.getElementById('chosen-folder-display');
  const chosenPath = document.getElementById('chosen-folder-path');

  btnChooseFolder.addEventListener('click', async () => {
    btnChooseFolder.disabled = true;
    btnChooseFolder.textContent = 'Opening…';
    try {
      const result = await apiFetch('/api/pick-folder');
      if (result.cancelled || !result.path) return;
      folderInput.value = result.path;
      chosenPath.textContent = result.path;
      chosenDisplay.style.display = 'flex';
      // Auto-trigger import
      btnImport.click();
    } catch (e) {
      // error already shown
    } finally {
      btnChooseFolder.disabled = false;
      btnChooseFolder.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg> Choose Music Folder';
    }
  });
  const btnSaveSession = document.getElementById('btn-save-session');
  const btnToggleWatch = document.getElementById('btn-toggle-watch');
  const btnResumeSession = document.getElementById('btn-resume-session');
  const btnDismissSession = document.getElementById('btn-dismiss-session');

  // Check for previous session on load
  checkPreviousSession();

  // Save session button
  btnSaveSession.addEventListener('click', async () => {
    if (!window.tracks.length) {
      showToast('No tracks to save', 'error');
      return;
    }
    showSpinner('Saving session...');
    try {
      const result = await apiFetch('/api/session/save', {
        method: 'POST',
        body: JSON.stringify({ folder_path: folderInput.value.trim() }),
      });
      showToast(`Session saved: ${result.track_count} tracks`, 'success');
    } catch (error) {
      // Error already shown
    } finally {
      hideSpinner();
    }
  });

  // Resume session button
  btnResumeSession.addEventListener('click', async () => {
    showSpinner('Loading session...');
    try {
      const result = await apiFetch('/api/session/load', {
        method: 'POST',
      });
      window.tracks = result.tracks || [];
      renderTracks();
      renderReview();
      updateStats();
      showToast(`Loaded ${result.count} tracks`, 'success');
      document.getElementById('resume-session-banner').style.display = 'none';
      btnAnalyze.disabled = false;
    } catch (error) {
      // Error already shown
    } finally {
      hideSpinner();
    }
  });

  // Dismiss session button
  btnDismissSession.addEventListener('click', () => {
    document.getElementById('resume-session-banner').style.display = 'none';
  });

  // Toggle folder watcher
  btnToggleWatch.addEventListener('click', async () => {
    const isCurrentlyWatching = btnToggleWatch.dataset.watching === 'true';

    if (isCurrentlyWatching) {
      // Stop watching
      try {
        await apiFetch('/api/watch/stop', { method: 'POST' });
        isWatching = false;
        btnToggleWatch.dataset.watching = 'false';
        btnToggleWatch.textContent = '👁️ Watch Folder (Off)';
        document.getElementById('watch-status').textContent = '';
        if (watchPollInterval) {
          clearInterval(watchPollInterval);
          watchPollInterval = null;
        }
        showToast('Folder watcher stopped', 'info');
      } catch (error) {
        // Error already shown
      }
    } else {
      // Start watching
      const folderPath = folderInput.value.trim();
      if (!folderPath) {
        showToast('Please enter a folder path', 'error');
        return;
      }

      try {
        await apiFetch('/api/watch/start', {
          method: 'POST',
          body: JSON.stringify({ folder_path: folderPath }),
        });
        isWatching = true;
        btnToggleWatch.dataset.watching = 'true';
        btnToggleWatch.textContent = '👁️ Watch Folder (On)';
        document.getElementById('watch-status').textContent = `Watching: ${folderPath}`;
        showToast('Folder watcher started', 'success');

        // Start polling
        if (!watchPollInterval) {
          watchPollInterval = setInterval(pollFolderWatch, 5000);
        }
      } catch (error) {
        // Error already shown
      }
    }
  });

  btnImport.addEventListener('click', async () => {
    const folderPath = folderInput.value.trim();
    if (!folderPath) {
      showToast('No folder selected', 'error');
      return;
    }

    showSpinner('Importing tracks...');
    try {
      const result = await apiFetch('/api/import', {
        method: 'POST',
        body: JSON.stringify({ folder_path: folderPath }),
      });

      window.tracks = result.tracks || [];
      showToast(`Imported ${result.count} tracks`, 'success');
      btnAnalyze.disabled = false;
      startStatsPolling();
      renderTracks();
    } catch (error) {
      // Error already shown in apiFetch
    } finally {
      hideSpinner();
    }
  });

  btnAnalyze.addEventListener('click', async () => {
    if (!window.tracks.length) {
      showToast('No tracks to analyze', 'error');
      return;
    }

    const trackPaths = window.tracks.map(t => t.file_path);
    showSpinner('Analyzing audio...');
    try {
      const result = await apiFetch('/api/analyze', {
        method: 'POST',
        body: JSON.stringify({ track_paths: trackPaths }),
      });

      // Update tracks with analysis results
      result.analyzed.forEach(analyzed => {
        const track = window.tracks.find(t => t.file_path === analyzed.file_path);
        if (track) {
          Object.assign(track, analyzed);
        }
      });

      showToast(`Analyzed ${result.analyzed.length} tracks`, 'success');
      btnClassify.disabled = false;
      renderTracks();
      updateStats();
    } catch (error) {
      // Error already shown
    } finally {
      hideSpinner();
    }
  });

  btnClassify.addEventListener('click', async () => {
    if (!window.tracks.length) {
      showToast('No tracks to classify', 'error');
      return;
    }

    const trackPaths = window.tracks.map(t => t.file_path);
    showSpinner('Classifying genres...');
    try {
      const result = await apiFetch('/api/classify', {
        method: 'POST',
        body: JSON.stringify({ track_paths: trackPaths }),
      });

      // Update tracks with classification results
      result.classified.forEach(classified => {
        const track = window.tracks.find(t => t.file_path === classified.file_path);
        if (track) {
          Object.assign(track, classified);
        }
      });

      showToast(`Classified ${result.classified.length} tracks`, 'success');
      btnReviewTab.disabled = false;
      renderTracks();
      renderReview();
      updateStats();
    } catch (error) {
      // Error already shown
    } finally {
      hideSpinner();
    }
  });

  btnReviewTab.addEventListener('click', () => {
    switchTab('review');
  });
}

// Session & Watcher Helpers
async function checkPreviousSession() {
  try {
    const result = await apiFetch('/api/session/exists');
    if (result.exists) {
      const banner = document.getElementById('resume-session-banner');
      const text = document.getElementById('resume-banner-text');
      text.textContent = `Previous session found — ${result.track_count} tracks from ${result.folder_path}. Last saved: ${new Date(result.saved_at).toLocaleString()}`;
      banner.style.display = 'block';
    }
  } catch (error) {
    // Silently fail if no session exists
  }
}

async function pollFolderWatch() {
  try {
    const result = await apiFetch('/api/watch/poll');
    if (result.tracks && result.tracks.length > 0) {
      // Add new tracks to window.tracks
      window.tracks = window.tracks.concat(result.tracks);
      renderTracks();
      renderReview();
      updateStats();
      showToast(`${result.tracks.length} new track${result.tracks.length !== 1 ? 's' : ''} detected`, 'success');
    }
  } catch (error) {
    // Silently fail on poll errors
  }
}

// ============================================================================
// Tracks Tab
// ============================================================================

function initTracksTab() {
  const filterGenre = document.getElementById('filter-genre');
  const filterStatus = document.getElementById('filter-status');
  const searchInput = document.getElementById('search-tracks');

  // Load taxonomy for genre filter
  apiFetch('/api/taxonomy')
    .then(data => {
      window.taxonomy = data.genres || {};
      populateGenreFilters();
    });

  filterGenre.addEventListener('change', renderTracks);
  filterStatus.addEventListener('change', renderTracks);
  searchInput.addEventListener('input', renderTracks);

  // Sortable headers
  document.querySelectorAll('.tracks-table th.sortable').forEach(header => {
    header.addEventListener('click', () => {
      const field = header.dataset.sort;
      if (window.currentSort.field === field) {
        window.currentSort.direction = window.currentSort.direction === 'asc' ? 'desc' : 'asc';
      } else {
        window.currentSort.field = field;
        window.currentSort.direction = 'asc';
      }

      // Update visual indicators
      document.querySelectorAll('.tracks-table th.sortable').forEach(h => {
        h.classList.remove('sort-asc', 'sort-desc');
      });
      header.classList.add(`sort-${window.currentSort.direction}`);

      renderTracks();
    });
  });
}

function populateGenreFilters() {
  const select = document.getElementById('filter-genre');
  Object.keys(window.taxonomy).forEach(genre => {
    const option = document.createElement('option');
    option.value = genre;
    option.textContent = genre;
    select.appendChild(option);
  });
}

function getFilteredTracks() {
  let filtered = [...window.tracks];

  // Genre filter
  const genreFilter = document.getElementById('filter-genre').value;
  if (genreFilter) {
    filtered = filtered.filter(t => t.final_genre === genreFilter);
  }

  // Status filter
  const statusFilter = document.getElementById('filter-status').value;
  if (statusFilter) {
    filtered = filtered.filter(t => t.review_status === statusFilter);
  }

  // Search
  const search = document.getElementById('search-tracks').value.toLowerCase();
  if (search) {
    filtered = filtered.filter(t =>
      (t.display_title || '').toLowerCase().includes(search) ||
      (t.display_artist || '').toLowerCase().includes(search)
    );
  }

  return filtered;
}

function sortTracks(tracks) {
  const sorted = [...tracks];
  sorted.sort((a, b) => {
    let aVal = a[window.currentSort.field] || '';
    let bVal = b[window.currentSort.field] || '';

    // Handle numeric fields
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

function getConfidenceBadgeClass(confidence) {
  if (confidence >= 80) return 'confidence-high';
  if (confidence >= 60) return 'confidence-medium';
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

function renderTracks() {
  const tbody = document.getElementById('tracks-tbody');
  const filtered = getFilteredTracks();
  const sorted = sortTracks(filtered);

  tbody.innerHTML = '';

  if (!sorted.length) {
    const row = document.createElement('tr');
    row.className = 'empty-state';
    const cell = document.createElement('td');
    cell.colSpan = '10';
    cell.textContent = 'No tracks match filters';
    row.appendChild(cell);
    tbody.appendChild(row);
    document.getElementById('tracks-count').textContent = '0 tracks';
    return;
  }

  sorted.forEach(track => {
    const row = document.createElement('tr');
    row.style.cursor = 'pointer';
    row.addEventListener('click', () => openEditModal(track.file_path));

    const confidenceClass = getConfidenceBadgeClass(track.confidence || 0);
    const statusBadge = getStatusBadge(track.review_status);

    // Title
    const tdTitle = document.createElement('td');
    tdTitle.textContent = track.display_title || '—';
    row.appendChild(tdTitle);

    // Artist
    const tdArtist = document.createElement('td');
    tdArtist.textContent = track.display_artist || '—';
    row.appendChild(tdArtist);

    // Genre
    const tdGenre = document.createElement('td');
    tdGenre.textContent = track.final_genre || '—';
    row.appendChild(tdGenre);

    // Sub-genre
    const tdSubgenre = document.createElement('td');
    tdSubgenre.textContent = track.final_subgenre || '—';
    row.appendChild(tdSubgenre);

    // Confidence
    const tdConfidence = document.createElement('td');
    if (track.confidence) {
      const span = document.createElement('span');
      span.className = `confidence-value ${confidenceClass}`;
      span.textContent = `${Math.round(track.confidence)}%`;
      tdConfidence.appendChild(span);
    } else {
      tdConfidence.textContent = '—';
    }
    row.appendChild(tdConfidence);

    // BPM
    const tdBpm = document.createElement('td');
    tdBpm.textContent = track.final_bpm || '—';
    row.appendChild(tdBpm);

    // Key
    const tdKey = document.createElement('td');
    tdKey.textContent = track.final_key || '—';
    row.appendChild(tdKey);

    // Year
    const tdYear = document.createElement('td');
    tdYear.textContent = track.final_year || '—';
    row.appendChild(tdYear);

    // Status
    const tdStatus = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = `badge ${statusBadge}`;
    badge.textContent = track.review_status;
    tdStatus.appendChild(badge);
    row.appendChild(tdStatus);

    // Action
    const tdAction = document.createElement('td');
    tdAction.style.textAlign = 'center';
    const btnEdit = document.createElement('button');
    btnEdit.className = 'btn btn-secondary';
    btnEdit.style.padding = '4px 8px';
    btnEdit.style.fontSize = '12px';
    btnEdit.textContent = '✎';
    btnEdit.addEventListener('click', (e) => {
      e.stopPropagation();
      openEditModal(track.file_path);
    });
    tdAction.appendChild(btnEdit);
    row.appendChild(tdAction);

    tbody.appendChild(row);
  });

  document.getElementById('tracks-count').textContent = `${sorted.length} track${sorted.length !== 1 ? 's' : ''}`;
}

// Audio Player Control
function toggleAudioPlay(btn, filePath) {
  const audio = document.getElementById('audio-player');

  // If different file, stop current and play new
  if (currentAudioPlayer !== audio || audio.src !== `/api/audio/${encodeURIComponent(filePath)}`) {
    // Stop any playing audio
    audio.pause();

    // Update all buttons
    document.querySelectorAll('.audio-play-btn').forEach(b => {
      b.classList.remove('playing');
      b.textContent = '▶';
    });

    // Set new source and play
    audio.src = `/api/audio/${encodeURIComponent(filePath)}`;
    currentAudioPlayer = audio;

    audio.play().catch(err => {
      showToast('Could not play audio', 'error');
      console.error('Audio play error:', err);
    });

    btn.classList.add('playing');
    btn.textContent = '⏸';

    // Update progress bar
    const updateProgress = () => {
      const allBtns = document.querySelectorAll('.audio-play-btn');
      allBtns.forEach(b => {
        if (b.dataset.filePath === filePath) {
          const progress = b.closest('.review-item-audio')?.querySelector('.audio-progress-fill');
          if (progress && audio.duration) {
            const percent = (audio.currentTime / audio.duration) * 100;
            progress.style.width = percent + '%';
          }
        }
      });
    };

    audio.ontimeupdate = updateProgress;

    audio.onended = () => {
      btn.classList.remove('playing');
      btn.textContent = '▶';
      const progress = btn.closest('.review-item-audio')?.querySelector('.audio-progress-fill');
      if (progress) progress.style.width = '0%';
    };
  } else if (audio.paused) {
    // Resume
    audio.play();
    btn.classList.add('playing');
    btn.textContent = '⏸';
  } else {
    // Pause
    audio.pause();
    btn.classList.remove('playing');
    btn.textContent = '▶';
  }
}

// ============================================================================
// Review Tab
// ============================================================================

function initReviewTab() {
  const slider = document.getElementById('confidence-slider');
  const valueSpan = document.getElementById('confidence-value');
  const thresholdPct = document.getElementById('threshold-pct');
  const btnBulkApprove = document.getElementById('btn-bulk-approve');
  const btnWriteTags = document.getElementById('btn-write-tags');
  const btnExportPlaylist = document.getElementById('btn-export-playlist');
  const exportMenu = document.getElementById('export-menu');
  const btnExportAll = document.getElementById('btn-export-all-approved');
  const btnExportByGenre = document.getElementById('btn-export-by-genre');

  // Export dropdown toggle
  btnExportPlaylist.addEventListener('click', (e) => {
    e.stopPropagation();
    exportMenu.style.display = exportMenu.style.display === 'none' ? 'block' : 'none';
  });

  // Close dropdown when clicking elsewhere
  document.addEventListener('click', () => {
    exportMenu.style.display = 'none';
  });

  // Export all approved
  btnExportAll.addEventListener('click', () => {
    window.location = '/api/export/m3u?status=approved';
    exportMenu.style.display = 'none';
    showToast('Downloading playlist...', 'info');
  });

  // Export by genre
  btnExportByGenre.addEventListener('click', () => {
    showGenreSelector();
    exportMenu.style.display = 'none';
  });

  slider.addEventListener('input', () => {
    const value = slider.value;
    valueSpan.textContent = value + '%';
    thresholdPct.textContent = value;
  });

  btnBulkApprove.addEventListener('click', async () => {
    const threshold = parseInt(slider.value);
    showSpinner(`Bulk approving tracks ≥ ${threshold}%...`);
    try {
      const result = await apiFetch('/api/review/bulk-approve', {
        method: 'POST',
        body: JSON.stringify({ min_confidence: threshold }),
      });

      // Update tracks
      result.forEach(trackPath => {
        const track = window.tracks.find(t => t.file_path === trackPath);
        if (track) {
          track.review_status = 'approved';
        }
      });

      showToast(`Approved ${result.length} tracks`, 'success');
      renderReview();
      updateStats();
    } catch (error) {
      // Error shown in apiFetch
    } finally {
      hideSpinner();
    }
  });

  btnWriteTags.addEventListener('click', async () => {
    showSpinner('Writing tags to files...');
    try {
      const result = await apiFetch('/api/review/write', {
        method: 'POST',
        body: JSON.stringify({ track_paths: [] }), // Empty = all approved
      });

      // Update tracks
      result.forEach(trackPath => {
        const track = window.tracks.find(t => t.file_path === trackPath);
        if (track) {
          track.tags_written = true;
          track.review_status = 'written';
        }
      });

      showToast(`Tags written to ${result.length} files`, 'success');
      renderReview();
      renderTracks();
      updateStats();
    } catch (error) {
      // Error shown
    } finally {
      hideSpinner();
    }
  });
}

function getPendingTracks() {
  return window.tracks.filter(t => t.review_status === 'pending');
}

function renderReview() {
  const list = document.getElementById('review-list');
  const pending = getPendingTracks();
  const approvedCount = window.tracks.filter(t => t.review_status === 'approved').length;

  document.getElementById('approved-count').textContent = approvedCount;
  document.getElementById('btn-write-tags').disabled = approvedCount === 0;

  list.innerHTML = '';

  if (!pending.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'No pending tracks to review';
    list.appendChild(empty);
    return;
  }

  pending.forEach(track => {
    const item = document.createElement('div');
    item.className = 'review-item';

    const confidenceValue = track.confidence || 0;
    let confidenceClass = 'low';
    if (confidenceValue >= 80) confidenceClass = 'high';
    else if (confidenceValue >= 60) confidenceClass = 'medium';

    const existingChanged = track.existing_genre !== track.final_genre;

    // Header
    const header = document.createElement('div');
    header.className = 'review-item-header';

    const titleDiv = document.createElement('div');
    const titleStrong = document.createElement('div');
    titleStrong.className = 'review-item-title';
    titleStrong.textContent = track.display_title || track.filename;
    titleDiv.appendChild(titleStrong);

    const artistDiv = document.createElement('div');
    artistDiv.style.fontSize = '12px';
    artistDiv.style.color = '#888';
    artistDiv.style.marginTop = '4px';
    artistDiv.textContent = track.display_artist || 'Unknown Artist';
    titleDiv.appendChild(artistDiv);

    // Audio player
    const audioContainer = document.createElement('div');
    audioContainer.className = 'review-item-audio';
    const playBtn = document.createElement('button');
    playBtn.className = 'audio-play-btn';
    playBtn.textContent = '▶';
    playBtn.dataset.filePath = track.file_path;
    playBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleAudioPlay(playBtn, track.file_path);
    });
    audioContainer.appendChild(playBtn);

    const progressContainer = document.createElement('div');
    progressContainer.className = 'audio-progress';
    const progressFill = document.createElement('div');
    progressFill.className = 'audio-progress-fill';
    progressContainer.appendChild(progressFill);
    progressContainer.addEventListener('click', (e) => {
      if (currentAudioPlayer) {
        const percent = e.offsetX / progressContainer.offsetWidth;
        currentAudioPlayer.currentTime = percent * currentAudioPlayer.duration;
      }
    });
    audioContainer.appendChild(progressContainer);

    titleDiv.appendChild(audioContainer);
    header.appendChild(titleDiv);

    const confBadge = document.createElement('div');
    confBadge.className = `review-item-confidence ${confidenceClass}`;
    confBadge.textContent = `${Math.round(confidenceValue)}% confident`;
    header.appendChild(confBadge);

    item.appendChild(header);

    // Diff view
    const diff = document.createElement('div');
    diff.className = 'review-diff';

    // Left column - current
    const leftCol = document.createElement('div');
    leftCol.className = 'review-column';

    const leftTitle = document.createElement('div');
    leftTitle.className = 'review-column-title';
    leftTitle.textContent = 'Current Tags';
    leftCol.appendChild(leftTitle);

    const createField = (label, value) => {
      const field = document.createElement('div');
      field.className = 'review-field';
      const labelEl = document.createElement('div');
      labelEl.className = 'review-field-label';
      labelEl.textContent = label;
      const valueEl = document.createElement('div');
      valueEl.className = 'review-field-value';
      valueEl.textContent = value || '—';
      field.appendChild(labelEl);
      field.appendChild(valueEl);
      return field;
    };

    leftCol.appendChild(createField('Genre', track.existing_genre));
    leftCol.appendChild(createField('BPM', track.existing_bpm));
    leftCol.appendChild(createField('Key', track.existing_key));
    leftCol.appendChild(createField('Year', track.existing_year));

    diff.appendChild(leftCol);

    // Right column - proposed
    const rightCol = document.createElement('div');
    rightCol.className = 'review-column';

    const rightTitle = document.createElement('div');
    rightTitle.className = 'review-column-title';
    rightTitle.textContent = 'Proposed Tags';
    rightCol.appendChild(rightTitle);

    const genreField = document.createElement('div');
    genreField.className = `review-field ${existingChanged ? 'changed' : ''}`;
    const genreLabel = document.createElement('div');
    genreLabel.className = 'review-field-label';
    genreLabel.textContent = 'Genre';
    const genreValue = document.createElement('div');
    genreValue.className = 'review-field-value';
    const genreText = track.proposed_genre || '—';
    const subText = track.proposed_subgenre ? ` → ${track.proposed_subgenre}` : '';
    genreValue.textContent = genreText + subText;
    genreField.appendChild(genreLabel);
    genreField.appendChild(genreValue);
    rightCol.appendChild(genreField);

    rightCol.appendChild(createField('BPM (analyzed)', track.analyzed_bpm ? Math.round(track.analyzed_bpm) : ''));
    rightCol.appendChild(createField('Key (analyzed)', track.analyzed_key));
    rightCol.appendChild(createField('Energy Level', track.analyzed_energy ? `${track.analyzed_energy}/10` : ''));

    diff.appendChild(rightCol);
    item.appendChild(diff);

    // Reasoning
    if (track.reasoning) {
      const reasoningDiv = document.createElement('div');
      reasoningDiv.style.fontSize = '12px';
      reasoningDiv.style.color = '#888';
      reasoningDiv.style.marginBottom = '15px';
      reasoningDiv.style.padding = '10px';
      reasoningDiv.style.backgroundColor = '#2a2a3a';
      reasoningDiv.style.borderRadius = '4px';
      const reasoningStrong = document.createElement('strong');
      reasoningStrong.textContent = 'AI Reasoning: ';
      reasoningDiv.appendChild(reasoningStrong);
      const reasoningText = document.createTextNode(track.reasoning);
      reasoningDiv.appendChild(reasoningText);
      item.appendChild(reasoningDiv);
    }

    // Actions
    const actions = document.createElement('div');
    actions.className = 'review-actions';

    const btnSkip = document.createElement('button');
    btnSkip.className = 'btn btn-secondary';
    btnSkip.textContent = '✗ Skip';
    btnSkip.addEventListener('click', () => skipTrack(track.file_path));
    actions.appendChild(btnSkip);

    const btnEditReview = document.createElement('button');
    btnEditReview.className = 'btn btn-secondary';
    btnEditReview.textContent = '✎ Edit';
    btnEditReview.addEventListener('click', () => openEditModal(track.file_path));
    actions.appendChild(btnEditReview);

    const btnApprove = document.createElement('button');
    btnApprove.className = 'btn btn-primary';
    btnApprove.textContent = '✓ Approve';
    btnApprove.addEventListener('click', () => approveTrack(track.file_path));
    actions.appendChild(btnApprove);

    item.appendChild(actions);
    list.appendChild(item);
  });
}

async function approveTrack(filePath) {
  try {
    await apiFetch('/api/review/approve', {
      method: 'POST',
      body: JSON.stringify({ track_paths: [filePath] }),
    });

    const track = window.tracks.find(t => t.file_path === filePath);
    if (track) {
      track.review_status = 'approved';
    }

    renderReview();
    renderTracks();
    updateStats();
  } catch (error) {
    // Error shown in apiFetch
  }
}

async function skipTrack(filePath) {
  try {
    await apiFetch('/api/review/skip', {
      method: 'POST',
      body: JSON.stringify({ track_paths: [filePath] }),
    });

    const track = window.tracks.find(t => t.file_path === filePath);
    if (track) {
      track.review_status = 'skipped';
    }

    renderReview();
    renderTracks();
    updateStats();
  } catch (error) {
    // Error shown
  }
}

// Genre Selector for Export
function showGenreSelector() {
  // Get unique approved genres
  const genres = new Set();
  window.tracks.forEach(track => {
    if (track.review_status === 'approved' && track.final_genre) {
      genres.add(track.final_genre);
    }
  });

  if (!genres.size) {
    showToast('No approved tracks with genres found', 'error');
    return;
  }

  const modal = document.createElement('div');
  modal.className = 'genre-selector-modal';
  modal.id = 'genre-selector-modal';

  const content = document.createElement('div');
  content.className = 'genre-selector-content';

  const title = document.createElement('h3');
  title.textContent = 'Select Genre to Export';
  content.appendChild(title);

  const select = document.createElement('select');
  select.className = 'input-select';

  const option = document.createElement('option');
  option.value = '';
  option.textContent = 'All Genres';
  select.appendChild(option);

  Array.from(genres).sort().forEach(genre => {
    const opt = document.createElement('option');
    opt.value = genre;
    opt.textContent = genre;
    select.appendChild(opt);
  });

  content.appendChild(select);

  const buttons = document.createElement('div');
  buttons.className = 'genre-selector-buttons';

  const btnCancel = document.createElement('button');
  btnCancel.className = 'btn btn-secondary';
  btnCancel.textContent = 'Cancel';
  btnCancel.addEventListener('click', () => {
    modal.remove();
  });

  const btnExport = document.createElement('button');
  btnExport.className = 'btn btn-primary';
  btnExport.textContent = 'Export';
  btnExport.addEventListener('click', () => {
    const genre = select.value;
    const url = genre
      ? `/api/export/m3u?genre=${encodeURIComponent(genre)}&status=approved`
      : '/api/export/m3u?status=approved';
    window.location = url;
    showToast('Downloading playlist...', 'info');
    modal.remove();
  });

  buttons.appendChild(btnCancel);
  buttons.appendChild(btnExport);
  content.appendChild(buttons);

  modal.appendChild(content);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.remove();
    }
  });

  document.body.appendChild(modal);
  select.focus();
}

// ============================================================================
// Taxonomy Tab
// ============================================================================

function initTaxonomyTab() {
  const btnAddGenre = document.getElementById('btn-add-genre');
  const btnSaveTaxonomy = document.getElementById('btn-save-taxonomy');

  btnAddGenre.addEventListener('click', () => {
    showAddGenreModal();
  });

  btnSaveTaxonomy.addEventListener('click', async () => {
    showSpinner('Saving taxonomy...');
    try {
      await apiFetch('/api/taxonomy', {
        method: 'PUT',
        body: JSON.stringify({ genres: window.taxonomy }),
      });
      showToast('Taxonomy saved', 'success');
    } catch (error) {
      // Error shown
    } finally {
      hideSpinner();
    }
  });

  loadTaxonomy();
}

async function loadTaxonomy() {
  try {
    const data = await apiFetch('/api/taxonomy');
    window.taxonomy = data.genres || {};
    renderTaxonomy();
  } catch (error) {
    // Error shown
  }
}

function renderTaxonomy() {
  const list = document.getElementById('taxonomy-list');
  list.innerHTML = '';

  if (!Object.keys(window.taxonomy).length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'No genres defined. Add one to get started.';
    list.appendChild(empty);
    return;
  }

  Object.entries(window.taxonomy).forEach(([genre, data]) => {
    const genreEl = document.createElement('div');
    genreEl.className = 'taxonomy-genre';

    // Header
    const header = document.createElement('div');
    header.className = 'taxonomy-genre-header';
    header.addEventListener('click', () => toggleGenre(header));

    const textDiv = document.createElement('div');
    const titleDiv = document.createElement('div');
    titleDiv.className = 'taxonomy-genre-title';
    titleDiv.textContent = genre;
    textDiv.appendChild(titleDiv);

    const descDiv = document.createElement('div');
    descDiv.className = 'taxonomy-genre-desc';
    descDiv.textContent = data.description || '';
    textDiv.appendChild(descDiv);
    header.appendChild(textDiv);

    const rightDiv = document.createElement('div');
    rightDiv.style.display = 'flex';
    rightDiv.style.gap = '12px';
    rightDiv.style.alignItems = 'center';

    const countDiv = document.createElement('span');
    countDiv.style.color = '#888';
    countDiv.style.fontSize = '12px';
    const subgenres = data.subgenres || [];
    countDiv.textContent = `${subgenres.length} sub-genre${subgenres.length !== 1 ? 's' : ''}`;
    rightDiv.appendChild(countDiv);

    const toggleDiv = document.createElement('span');
    toggleDiv.className = 'taxonomy-toggle';
    toggleDiv.textContent = '▼';
    rightDiv.appendChild(toggleDiv);

    header.appendChild(rightDiv);
    genreEl.appendChild(header);

    // Subgenres container
    const subgenresDiv = document.createElement('div');
    subgenresDiv.className = 'taxonomy-subgenres';

    subgenres.forEach((sub, idx) => {
      const subEl = document.createElement('div');
      subEl.className = 'taxonomy-subgenre';

      const span = document.createElement('span');
      span.textContent = sub;
      subEl.appendChild(span);

      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'taxonomy-actions';

      const btnDel = document.createElement('button');
      btnDel.className = 'btn btn-secondary';
      btnDel.textContent = 'Delete';
      btnDel.addEventListener('click', () => removeSubgenre(genre, idx));
      actionsDiv.appendChild(btnDel);

      subEl.appendChild(actionsDiv);
      subgenresDiv.appendChild(subEl);
    });

    const addBtn = document.createElement('button');
    addBtn.className = 'btn btn-primary';
    addBtn.style.width = '100%';
    addBtn.style.marginTop = '10px';
    addBtn.textContent = '+ Add Sub-Genre';
    addBtn.addEventListener('click', () => addSubgenreForm(genre));
    subgenresDiv.appendChild(addBtn);

    genreEl.appendChild(subgenresDiv);
    list.appendChild(genreEl);
  });
}

function toggleGenre(header) {
  const subgenres = header.nextElementSibling;
  const toggle = header.querySelector('.taxonomy-toggle');

  subgenres.classList.toggle('open');
  toggle.classList.toggle('open');
}

function addSubgenreForm(genre) {
  const name = prompt(`Add sub-genre to ${genre}:`);
  if (name) {
    if (!window.taxonomy[genre].subgenres) {
      window.taxonomy[genre].subgenres = [];
    }
    window.taxonomy[genre].subgenres.push(name);
    renderTaxonomy();
  }
}

function removeSubgenre(genre, idx) {
  if (confirm('Remove this sub-genre?')) {
    window.taxonomy[genre].subgenres.splice(idx, 1);
    renderTaxonomy();
  }
}

function showAddGenreModal() {
  document.getElementById('add-genre-modal').style.display = 'flex';
  document.getElementById('new-genre-name').focus();
}

// ============================================================================
// Camelot Wheel
// ============================================================================

const CAMELOT_MAP = {
  '1A': 'Abm', '1B': 'B',
  '2A': 'Ebm', '2B': 'F#',
  '3A': 'Bbm', '3B': 'Db',
  '4A': 'Fm', '4B': 'Ab',
  '5A': 'Cm', '5B': 'Eb',
  '6A': 'Gm', '6B': 'Bb',
  '7A': 'Dm', '7B': 'F',
  '8A': 'Am', '8B': 'C',
  '9A': 'Em', '9B': 'G',
  '10A': 'Bm', '10B': 'D',
  '11A': 'F#m', '11B': 'A',
  '12A': 'Dbm', '12B': 'E',
};

function createCamelotWheel(highlightKey) {
  const svg = document.getElementById('camelot-wheel');
  if (!svg) return;

  svg.innerHTML = '';
  const size = 200;
  const center = size / 2;
  const outerRadius = 80;
  const innerRadius = 50;

  // Helper to calculate angle in degrees (0 = top, clockwise)
  const getAngle = (position) => {
    return (position - 1) * 30 - 90; // -90 to start at top, position 1 at top
  };

  // Helper to convert angle to radians and get point
  const getPoint = (angle, radius) => {
    const rad = (angle * Math.PI) / 180;
    return {
      x: center + radius * Math.cos(rad),
      y: center + radius * Math.sin(rad),
    };
  };

  // Draw outer ring (Major/B keys)
  for (let i = 1; i <= 12; i++) {
    const angle = getAngle(i);
    const p1 = getPoint(angle, outerRadius);
    const p2 = getPoint(angle + 30, outerRadius);
    const pc = getPoint(angle + 15, outerRadius - 10);

    const keyStr = `${i}B`;
    const isHighlighted = highlightKey === keyStr;
    const isCompatible = isCompatibleKey(highlightKey, keyStr);

    const color = isHighlighted ? '#8b5cf6' : (isCompatible ? '#34d399' : '#888');

    // Wedge path
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const d = `M ${center} ${center} L ${p1.x} ${p1.y} A ${outerRadius} ${outerRadius} 0 0 1 ${p2.x} ${p2.y} Z`;
    path.setAttribute('d', d);
    path.setAttribute('fill', color);
    path.setAttribute('opacity', '0.3');
    path.setAttribute('stroke', color);
    path.setAttribute('stroke-width', '1');
    svg.appendChild(path);

    // Key text
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', pc.x);
    text.setAttribute('y', pc.y);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('font-size', '11');
    text.setAttribute('font-weight', '600');
    text.setAttribute('fill', color);
    text.textContent = keyStr;
    svg.appendChild(text);
  }

  // Draw inner ring (Minor/A keys)
  for (let i = 1; i <= 12; i++) {
    const angle = getAngle(i);
    const p1 = getPoint(angle, innerRadius);
    const p2 = getPoint(angle + 30, innerRadius);
    const pc = getPoint(angle + 15, innerRadius + 10);

    const keyStr = `${i}A`;
    const isHighlighted = highlightKey === keyStr;
    const isCompatible = isCompatibleKey(highlightKey, keyStr);

    const color = isHighlighted ? '#8b5cf6' : (isCompatible ? '#34d399' : '#888');

    // Wedge path
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const d = `M ${center} ${center} L ${p1.x} ${p1.y} A ${innerRadius} ${innerRadius} 0 0 1 ${p2.x} ${p2.y} Z`;
    path.setAttribute('d', d);
    path.setAttribute('fill', color);
    path.setAttribute('opacity', '0.3');
    path.setAttribute('stroke', color);
    path.setAttribute('stroke-width', '1');
    svg.appendChild(path);

    // Key text
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', pc.x);
    text.setAttribute('y', pc.y);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('font-size', '11');
    text.setAttribute('font-weight', '600');
    text.setAttribute('fill', color);
    text.textContent = keyStr;
    svg.appendChild(text);
  }

  // Draw center circle
  const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  circle.setAttribute('cx', center);
  circle.setAttribute('cy', center);
  circle.setAttribute('r', '10');
  circle.setAttribute('fill', '#2a2a3a');
  svg.appendChild(circle);
}

function isCompatibleKey(key1, key2) {
  if (!key1 || !key2 || key1 === key2) return false;

  // Extract number from key (1-12)
  const num1 = parseInt(key1);
  const num2 = parseInt(key2);

  // Compatible if same number (±1 position) or adjacent number
  const numDiff = Math.min(Math.abs(num1 - num2), 12 - Math.abs(num1 - num2));
  return numDiff === 1;
}

// ============================================================================
// Edit Modal
// ============================================================================

function initEditModal() {
  const modal = document.getElementById('edit-modal');
  const addGenreModal = document.getElementById('add-genre-modal');
  const closeBtn = document.getElementById('modal-close');
  const addGenreCloseBtn = document.getElementById('add-genre-close');
  const cancelBtn = document.getElementById('modal-cancel');
  const addGenreCancelBtn = document.getElementById('add-genre-cancel');
  const saveBtn = document.getElementById('modal-save');
  const addGenreSaveBtn = document.getElementById('add-genre-save');

  closeBtn.addEventListener('click', () => {
    modal.style.display = 'none';
  });

  addGenreCloseBtn.addEventListener('click', () => {
    addGenreModal.style.display = 'none';
  });

  cancelBtn.addEventListener('click', () => {
    modal.style.display = 'none';
  });

  addGenreCancelBtn.addEventListener('click', () => {
    addGenreModal.style.display = 'none';
  });

  saveBtn.addEventListener('click', saveTrackEdits);
  addGenreSaveBtn.addEventListener('click', addNewGenre);

  // Close on background click
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.style.display = 'none';
    }
  });

  addGenreModal.addEventListener('click', (e) => {
    if (e.target === addGenreModal) {
      addGenreModal.style.display = 'none';
    }
  });
}

function openEditModal(filePath) {
  const track = window.tracks.find(t => t.file_path === filePath);
  if (!track) return;

  currentEditPath = filePath;

  // Populate current info
  document.getElementById('modal-title').textContent = track.display_title || track.filename;
  document.getElementById('modal-artist').textContent = track.display_artist || 'Unknown';
  document.getElementById('modal-filename').textContent = track.filename;

  // Populate editable fields
  document.getElementById('modal-genre').value = track.final_genre || '';
  document.getElementById('modal-bpm').value = track.final_bpm || '';
  document.getElementById('modal-key').value = track.final_key || '';
  document.getElementById('modal-year').value = track.final_year || '';
  document.getElementById('modal-comment').value = track.final_comment || '';

  // Populate genre options
  const genreSelect = document.getElementById('modal-genre');
  genreSelect.innerHTML = '';
  const optionDefault = document.createElement('option');
  optionDefault.value = '';
  optionDefault.textContent = 'Select Genre';
  genreSelect.appendChild(optionDefault);

  Object.keys(window.taxonomy).forEach(genre => {
    const option = document.createElement('option');
    option.value = genre;
    option.textContent = genre;
    genreSelect.appendChild(option);
  });
  genreSelect.value = track.final_genre || '';

  // Populate subgenre options based on selected genre
  updateSubgenreOptions();
  genreSelect.addEventListener('change', updateSubgenreOptions);

  // Populate analysis results
  document.getElementById('modal-analyzed-bpm').textContent = track.analyzed_bpm
    ? Math.round(track.analyzed_bpm)
    : '—';
  document.getElementById('modal-energy').textContent = track.analyzed_energy
    ? `${track.analyzed_energy}/10`
    : '—';
  document.getElementById('modal-confidence').textContent = track.confidence
    ? `${Math.round(track.confidence)}%`
    : '—';
  document.getElementById('modal-reasoning').textContent = track.reasoning || 'N/A';

  // Render Camelot wheel
  createCamelotWheel(track.final_key || '');

  document.getElementById('edit-modal').style.display = 'flex';
}

function updateSubgenreOptions() {
  const genreSelect = document.getElementById('modal-genre');
  const subgenreSelect = document.getElementById('modal-subgenre');
  const selectedGenre = genreSelect.value;

  subgenreSelect.innerHTML = '';
  const optionDefault = document.createElement('option');
  optionDefault.value = '';
  optionDefault.textContent = 'Select Sub-Genre';
  subgenreSelect.appendChild(optionDefault);

  if (selectedGenre && window.taxonomy[selectedGenre]) {
    const subgenres = window.taxonomy[selectedGenre].subgenres || [];
    subgenres.forEach(sub => {
      const option = document.createElement('option');
      option.value = sub;
      option.textContent = sub;
      subgenreSelect.appendChild(option);
    });
  }

  // Restore current value if available
  const track = window.tracks.find(t => t.file_path === currentEditPath);
  if (track && track.final_subgenre) {
    subgenreSelect.value = track.final_subgenre;
  }
}

async function saveTrackEdits() {
  if (!currentEditPath) return;

  const override = {
    override_genre: document.getElementById('modal-genre').value || undefined,
    override_subgenre: document.getElementById('modal-subgenre').value || undefined,
    override_bpm: document.getElementById('modal-bpm').value || undefined,
    override_key: document.getElementById('modal-key').value || undefined,
    override_year: document.getElementById('modal-year').value || undefined,
    override_comment: document.getElementById('modal-comment').value || undefined,
  };

  showSpinner('Saving changes...');
  try {
    const result = await apiFetch(`/api/tracks/${encodeURIComponent(currentEditPath)}`, {
      method: 'PUT',
      body: JSON.stringify(override),
    });

    const track = window.tracks.find(t => t.file_path === currentEditPath);
    if (track) {
      Object.assign(track, result);
    }

    showToast('Track updated', 'success');
    renderTracks();
    renderReview();

    document.getElementById('edit-modal').style.display = 'none';
  } catch (error) {
    // Error shown
  } finally {
    hideSpinner();
  }
}

function addNewGenre() {
  const name = document.getElementById('new-genre-name').value.trim();
  const description = document.getElementById('new-genre-description').value.trim();

  if (!name) {
    showToast('Genre name required', 'error');
    return;
  }

  window.taxonomy[name] = {
    description: description,
    subgenres: [],
  };

  showToast(`Added genre: ${name}`, 'success');
  renderTaxonomy();

  document.getElementById('add-genre-modal').style.display = 'none';
  document.getElementById('new-genre-name').value = '';
  document.getElementById('new-genre-description').value = '';
}

// ============================================================================
// Settings Tab
// ============================================================================

function initSettingsTab() {
  const btnSaveSettings = document.getElementById('btn-save-settings');

  btnSaveSettings.addEventListener('click', async () => {
    await saveSettings();
  });

  // Load settings when tab is activated
  document.querySelectorAll('.nav-btn').forEach(btn => {
    if (btn.dataset.tab === 'settings') {
      btn.addEventListener('click', loadSettings);
    }
  });

  // Load settings on init
  loadSettings();
}

async function loadSettings() {
  try {
    const response = await apiFetch('/api/settings');

    // Populate form fields with placeholder text for masked values
    const geminiInput = document.getElementById('settings-gemini-key');
    const spotifyIdInput = document.getElementById('settings-spotify-id');
    const spotifySecretInput = document.getElementById('settings-spotify-secret');

    // Show placeholder text for existing keys (masked values)
    if (response.has_gemini_key) {
      geminiInput.placeholder = response.gemini_api_key || 'Key is set';
    }
    if (response.has_spotify) {
      spotifyIdInput.placeholder = response.spotify_client_id || 'Value is set';
      spotifySecretInput.placeholder = response.spotify_client_secret || 'Value is set';
    }

    // Clear the actual input values
    geminiInput.value = '';
    spotifyIdInput.value = '';
    spotifySecretInput.value = '';

  } catch (error) {
    // Error already shown in apiFetch
  }
}

async function saveSettings() {
  try {
    const geminiKey = document.getElementById('settings-gemini-key').value.trim();
    const spotifyId = document.getElementById('settings-spotify-id').value.trim();
    const spotifySecret = document.getElementById('settings-spotify-secret').value.trim();

    // Build payload with only non-empty values
    const payload = {};
    if (geminiKey) payload.gemini_api_key = geminiKey;
    if (spotifyId) payload.spotify_client_id = spotifyId;
    if (spotifySecret) payload.spotify_client_secret = spotifySecret;

    // Don't send empty request
    if (Object.keys(payload).length === 0) {
      showToast('No settings to save', 'info');
      return;
    }

    showSpinner('Saving settings...');
    const result = await apiFetch('/api/settings', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (result.saved) {
      showToast('Settings saved successfully', 'success');
      // Clear inputs and reload to show masked values in placeholders
      document.getElementById('settings-gemini-key').value = '';
      document.getElementById('settings-spotify-id').value = '';
      document.getElementById('settings-spotify-secret').value = '';
      await loadSettings();
    }

  } catch (error) {
    // Error already shown in apiFetch
  } finally {
    hideSpinner();
  }
}

// ============================================================================
// Theme
// ============================================================================

function initTheme() {
  if (localStorage.getItem('theme') === 'light') {
    document.body.classList.add('light');
    document.getElementById('theme-icon').textContent = '🌙';
    document.getElementById('theme-label').textContent = 'Dark Mode';
  }
}

function toggleTheme() {
  const isLight = document.body.classList.toggle('light');
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
  document.getElementById('theme-icon').textContent = isLight ? '🌙' : '☀️';
  document.getElementById('theme-label').textContent = isLight ? 'Dark Mode' : 'Light Mode';
}

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  // Theme
  initTheme();
  document.getElementById('btn-theme-toggle').addEventListener('click', toggleTheme);

  // Nav tab switching
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      switchTab(btn.dataset.tab);
    });
  });

  // Initialize tabs
  initImportTab();
  initTracksTab();
  initReviewTab();
  initTaxonomyTab();
  initStatsTab();
  initSettingsTab();
  initEditModal();

  // Load initial data
  apiFetch('/api/taxonomy')
    .then(data => {
      window.taxonomy = data.genres || {};
      populateGenreFilters();
      renderTaxonomy();
    });

  updateStats();

  // Focus on first input
  const folderInput = document.getElementById('folder-input');
  if (folderInput) {
    folderInput.focus();
  }
});
