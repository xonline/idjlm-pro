// ============================================================================
// IDJLM Pro — Vanilla JS Application
// ============================================================================

// Global state
window.tracks = [];
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

function initNavigation() {
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  const detailCloseBtn = document.getElementById('track-detail-close');
  if (detailCloseBtn) detailCloseBtn.addEventListener('click', closeTrackDetail);

  const detailOverlay = document.getElementById('track-detail-overlay');
  if (detailOverlay) detailOverlay.addEventListener('click', closeTrackDetail);
}

// ============================================================================
// Stats Panel
// ============================================================================

function updateStats() {
  apiFetch('/api/stats').then(data => {
    if (!data) return;
    const el = id => document.getElementById(id);
    if (el('stat-total'))       el('stat-total').textContent      = data.total      ?? 0;
    if (el('stat-analyzed'))    el('stat-analyzed').textContent   = data.analyzed   ?? 0;
    if (el('stat-classified'))  el('stat-classified').textContent = data.classified ?? 0;
    if (el('stat-approved'))    el('stat-approved').textContent   = data.approved   ?? 0;
    updateToolbarButtonStates(data);
    renderStatsDashboard();
  }).catch(() => {});
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
// Library Toolbar & Session Management
// ============================================================================

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

  async function openFolderPicker() {
    if (window.pywebview && window.pywebview.api) {
      // Native OS folder picker via pywebview
      const path = await window.pywebview.api.choose_folder();
      if (path) doImport(path);
    } else {
      // Dev-mode fallback: show text input
      if (folderInput)  folderInput.style.display  = 'inline-block';
      if (btnImport)    btnImport.style.display    = 'inline-block';
      if (folderInput)  folderInput.focus();
    }
  }

  if (btnGetStarted) btnGetStarted.addEventListener('click', openFolderPicker);
  if (btnChange)     btnChange.addEventListener('click', openFolderPicker);

  if (folderInput) {
    folderInput.addEventListener('keydown', e => { if (e.key === 'Enter') doImport(folderInput.value.trim()); });
  }
  if (btnImport) btnImport.addEventListener('click', () => doImport(folderInput ? folderInput.value.trim() : ''));

  async function doImport(folder) {
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
        showToast((result.count || result.tracks.length) + ' tracks imported — click Analyze All to extract BPM & key', 'success');
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
        if (result && result.op_id) {
          // Stream progress via SSE
          connectToProgress(
            result.op_id,
            result.total,
            (current, total, message) => {
              const pct = Math.round((current / total) * 100);
              showProgressInStatsBar(`${current} / ${total} analyzing...`);
              const fill = document.getElementById('stat-progress-fill');
              if (fill) fill.style.width = pct + '%';
            },
            (data) => {
              // SSE complete event
              hideProgressInStatsBar();
              const fill = document.getElementById('stat-progress-fill');
              if (fill) fill.style.width = '0%';
              // Refetch fresh track data from server
              apiFetch('/api/tracks').then(d => {
                window.tracks = d.tracks || [];
                renderTracks();
                updateStats();
              });
              updateToolbarButtonStates();
              showToast('Analysis complete', 'success');
              btnAnalyze.disabled = false;
            },
            (err) => {
              hideProgressInStatsBar();
              showToast('Analysis stream error: ' + err.message, 'error');
              btnAnalyze.disabled = false;
            }
          );
        }
      } catch (e) {
        hideProgressInStatsBar();
        showToast('Analysis failed: ' + e.message, 'error');
        btnAnalyze.disabled = false;
      }
    });
  }

  if (btnClassify) {
    btnClassify.addEventListener('click', async () => {
      btnClassify.disabled = true;
      showProgressInStatsBar('Classifying genres...');
      try {
        const result = await apiFetch('/api/classify', { method: 'POST' });
        if (result && result.op_id) {
          // Stream progress via SSE
          connectToProgress(
            result.op_id,
            result.total,
            (current, total, message) => {
              const pct = Math.round((current / total) * 100);
              showProgressInStatsBar(`${current} / ${total} classifying...`);
              const fill = document.getElementById('stat-progress-fill');
              if (fill) fill.style.width = pct + '%';
            },
            (data) => {
              // SSE complete event
              hideProgressInStatsBar();
              const fill = document.getElementById('stat-progress-fill');
              if (fill) fill.style.width = '0%';
              // Refetch fresh track data from server
              apiFetch('/api/tracks').then(d => {
                window.tracks = d.tracks || [];
                renderTracks();
                updateStats();
              });
              updateToolbarButtonStates();
              showToast('Classification complete', 'success');
              btnClassify.disabled = false;
            },
            (err) => {
              hideProgressInStatsBar();
              showToast('Classification stream error: ' + err.message, 'error');
              btnClassify.disabled = false;
            }
          );
        }
      } catch (e) {
        hideProgressInStatsBar();
        showToast('Classification failed: ' + e.message, 'error');
        btnClassify.disabled = false;
      }
    });
  }

  if (btnBulkApprove) {
    btnBulkApprove.addEventListener('click', async () => {
      const thresholdEl = document.getElementById('toolbar-threshold');
      const threshold = parseInt(thresholdEl ? (thresholdEl.value || thresholdEl.textContent) : '80') || 80;
      try {
        const result = await apiFetch('/api/review/bulk-approve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ min_confidence: threshold })
        });
        if (result) {
          // Refetch fresh track data from server
          apiFetch('/api/tracks').then(d => {
            window.tracks = d.tracks || [];
            renderTracks();
            updateStats();
          });
          showToast((result.approved_count ?? 0) + ' tracks approved', 'success');
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
        if (result && result.op_id) {
          // Stream progress via SSE
          connectToProgress(
            result.op_id,
            result.total,
            (current, total, message) => {
              const pct = Math.round((current / total) * 100);
              showProgressInStatsBar(`${current} / ${total} writing...`);
              const fill = document.getElementById('stat-progress-fill');
              if (fill) fill.style.width = pct + '%';
            },
            (data) => {
              // SSE complete event
              hideProgressInStatsBar();
              const fill = document.getElementById('stat-progress-fill');
              if (fill) fill.style.width = '0%';
              // Refetch fresh track data from server
              apiFetch('/api/tracks').then(d => {
                window.tracks = d.tracks || [];
                renderTracks();
                updateStats();
              });
              updateToolbarButtonStates();
              showToast('Tags written successfully', 'success');
              btnWriteTags.disabled = false;
            },
            (err) => {
              hideProgressInStatsBar();
              showToast('Write stream error: ' + err.message, 'error');
              btnWriteTags.disabled = false;
            }
          );
        }
      } catch (e) {
        hideProgressInStatsBar();
        showToast('Write failed: ' + e.message, 'error');
        btnWriteTags.disabled = false;
      }
    });
  }
}

function updateToolbarButtonStates(stats) {
  const s = stats || {};
  const total      = s.total      ?? (window.tracks ? window.tracks.length : 0);
  const analyzed   = s.analyzed   ?? (window.tracks ? window.tracks.filter(t => t.final_bpm).length : 0);
  const classified = s.classified ?? (window.tracks ? window.tracks.filter(t => t.final_genre && t.final_genre !== 'Unknown').length : 0);
  const approved   = s.approved   ?? (window.tracks ? window.tracks.filter(t => t.review_status === 'approved').length : 0);

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
  apiFetch('/api/session/exists').then(data => {
    if (!data || !data.exists) return;
    const banner = document.getElementById('resume-banner');
    const info   = document.getElementById('resume-info');
    if (banner && info) {
      info.textContent = 'Session: ' + (data.track_count || 0) + ' tracks from ' + (data.folder_path || 'previous session');
      banner.style.display = 'flex';
    }
    const btnResume  = document.getElementById('btn-resume-session');
    const btnDismiss = document.getElementById('btn-dismiss-session');
    if (btnResume) {
      btnResume.addEventListener('click', async () => {
        showSpinner('Loading session...');
        try {
          const result = await apiFetch('/api/session/load', { method: 'POST' });
          if (result) {
            window.tracks = result.tracks || [];
            renderTracks();
            updateStats();
            if (banner) banner.style.display = 'none';
            showToast('Session resumed', 'success');
          }
        } catch (e) {
          showToast('Failed to resume session: ' + e.message, 'error');
        } finally {
          hideSpinner();
        }
      });
    }
    if (btnDismiss) {
      btnDismiss.addEventListener('click', () => { if (banner) banner.style.display = 'none'; });
    }
  }).catch(() => {});
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
    container.innerHTML = '<div class="empty-state">No comments yet</div>';
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
// Stats Dashboard (Collection Summary, Key/Energy Distribution, Camelot Wheel)
// ============================================================================

function renderStatsDashboard() {
  const dashboard = document.getElementById('stats-dashboard');
  if (!dashboard) return;

  const tracks = window.tracks || [];
  if (!tracks.length) {
    dashboard.style.display = 'none';
    return;
  }

  dashboard.style.display = 'block';
  const total = tracks.length;
  const analyzed = tracks.filter(t => t.final_bpm).length;
  const classified = tracks.filter(t => t.final_genre && t.final_genre !== 'Unknown').length;
  const approved = tracks.filter(t => t.review_status === 'approved').length;

  // Collection summary
  document.getElementById('summary-total').textContent = total;
  document.getElementById('summary-analyzed-pct').textContent = total ? Math.round((analyzed / total) * 100) + '%' : '0%';
  document.getElementById('summary-classified-pct').textContent = total ? Math.round((classified / total) * 100) + '%' : '0%';
  document.getElementById('summary-approved-pct').textContent = total ? Math.round((approved / total) * 100) + '%' : '0%';

  // Key distribution chart
  if (typeof Chart !== 'undefined') {
    renderKeyDistChart(tracks);
    renderEnergyDistChart(tracks);
    renderCamelotWheel(tracks);
  }
}

function renderKeyDistChart(tracks) {
  const camelotKeys = ['1A','1B','2A','2B','3A','3B','4A','4B','5A','5B','6A','6B','7A','7B','8A','8B','9A','9B','10A','10B','11A','11B','12A','12B'];
  const counts = {};
  camelotKeys.forEach(k => counts[k] = 0);
  tracks.forEach(t => {
    if (t.final_key && counts.hasOwnProperty(t.final_key)) {
      counts[t.final_key]++;
    }
  });

  const labels = camelotKeys;
  const data = labels.map(k => counts[k]);
  const colors = labels.map(k => k.endsWith('A') ? 'rgba(96,165,250,0.7)' : 'rgba(139,92,246,0.7)');

  const ctx = document.getElementById('chart-key-dist');
  if (!ctx) return;

  if (chartInstances.keyDist) chartInstances.keyDist.destroy();

  chartInstances.keyDist = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Track Count',
        data: data,
        backgroundColor: colors,
        borderColor: labels.map(k => k.endsWith('A') ? '#60a5fa' : '#8b5cf6'),
        borderWidth: 1,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { color: '#888' }, grid: { color: '#2a2a3a' } },
        y: { ticks: { color: '#888', font: { size: 10 } }, grid: { color: '#2a2a3a' } }
      }
    }
  });
}

function renderEnergyDistChart(tracks) {
  const buckets = { '1-2': 0, '3-4': 0, '5-6': 0, '7-8': 0, '9-10': 0 };
  tracks.forEach(t => {
    const energy = parseFloat(t.analyzed_energy) || 0;
    if (energy <= 2) buckets['1-2']++;
    else if (energy <= 4) buckets['3-4']++;
    else if (energy <= 6) buckets['5-6']++;
    else if (energy <= 8) buckets['7-8']++;
    else buckets['9-10']++;
  });

  const labels = Object.keys(buckets);
  const data = Object.values(buckets);
  const colors = ['#34d399', '#60a5fa', '#fbbf24', '#f97316', '#f87171'];

  const ctx = document.getElementById('chart-energy-dist');
  if (!ctx) return;

  if (chartInstances.energyDist) chartInstances.energyDist.destroy();

  chartInstances.energyDist = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Track Count',
        data: data,
        backgroundColor: colors,
        borderWidth: 1,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { color: '#888' }, grid: { color: '#2a2a3a' } },
        x: { ticks: { color: '#888' }, grid: { color: '#2a2a3a' } }
      }
    }
  });
}

function renderCamelotWheel(tracks) {
  const svg = document.getElementById('camelot-wheel-svg');
  const statsEl = document.getElementById('camelot-wheel-stats');
  if (!svg) return;

  svg.innerHTML = '';

  // Count tracks per Camelot key
  const keyCounts = {};
  const allCamelotKeys = [];
  for (let i = 1; i <= 12; i++) { allCamelotKeys.push(`${i}A`); allCamelotKeys.push(`${i}B`); }
  allCamelotKeys.forEach(k => keyCounts[k] = 0);
  tracks.forEach(t => {
    if (t.final_key && keyCounts.hasOwnProperty(t.final_key)) {
      keyCounts[t.final_key]++;
    }
  });

  const maxCount = Math.max(...Object.values(keyCounts), 1);
  const size = 280;
  const center = size / 2;
  const outerR = 120;
  const innerR = 80;
  const coreR = 30;

  const getAngle = (pos) => ((pos - 1) * 30 - 90) * Math.PI / 180;

  // Draw outer ring (B = major keys)
  for (let i = 1; i <= 12; i++) {
    const key = `${i}B`;
    const count = keyCounts[key];
    const intensity = count / maxCount;
    const startAngle = getAngle(i);
    const endAngle = getAngle(i + 1 > 12 ? 1 : i + 1);

    const x1 = center + innerR * Math.cos(startAngle);
    const y1 = center + innerR * Math.sin(startAngle);
    const x2 = center + outerR * Math.cos(startAngle);
    const y2 = center + outerR * Math.sin(startAngle);
    const x3 = center + outerR * Math.cos(endAngle);
    const y3 = center + outerR * Math.sin(endAngle);
    const x4 = center + innerR * Math.cos(endAngle);
    const y4 = center + innerR * Math.sin(endAngle);

    const alpha = 0.15 + intensity * 0.65;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M ${x1} ${y1} L ${x2} ${y2} A ${outerR} ${outerR} 0 0 1 ${x3} ${y3} L ${x4} ${y4} A ${innerR} ${innerR} 0 0 0 ${x1} ${y1} Z`);
    path.setAttribute('fill', `rgba(139,92,246,${alpha})`);
    path.setAttribute('stroke', '#8b5cf6');
    path.setAttribute('stroke-width', '0.5');
    svg.appendChild(path);

    // Label
    const midAngle = (startAngle + endAngle) / 2;
    const labelR = (innerR + outerR) / 2;
    const lx = center + labelR * Math.cos(midAngle);
    const ly = center + labelR * Math.sin(midAngle);
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', lx);
    text.setAttribute('y', ly);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('font-size', '9');
    text.setAttribute('font-weight', '600');
    text.setAttribute('fill', '#c8c8e4');
    text.textContent = key;
    svg.appendChild(text);
  }

  // Draw inner ring (A = minor keys)
  for (let i = 1; i <= 12; i++) {
    const key = `${i}A`;
    const count = keyCounts[key];
    const intensity = count / maxCount;
    const startAngle = getAngle(i);
    const endAngle = getAngle(i + 1 > 12 ? 1 : i + 1);

    const x1 = center + coreR * Math.cos(startAngle);
    const y1 = center + coreR * Math.sin(startAngle);
    const x2 = center + innerR * Math.cos(startAngle);
    const y2 = center + innerR * Math.sin(startAngle);
    const x3 = center + innerR * Math.cos(endAngle);
    const y3 = center + innerR * Math.sin(endAngle);
    const x4 = center + coreR * Math.cos(endAngle);
    const y4 = center + coreR * Math.sin(endAngle);

    const alpha = 0.15 + intensity * 0.65;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M ${x1} ${y1} L ${x2} ${y2} A ${innerR} ${innerR} 0 0 1 ${x3} ${y3} L ${x4} ${y4} A ${coreR} ${coreR} 0 0 0 ${x1} ${y1} Z`);
    path.setAttribute('fill', `rgba(96,165,250,${alpha})`);
    path.setAttribute('stroke', '#60a5fa');
    path.setAttribute('stroke-width', '0.5');
    svg.appendChild(path);

    // Label
    const midAngle = (startAngle + endAngle) / 2;
    const labelR = (coreR + innerR) / 2;
    const lx = center + labelR * Math.cos(midAngle);
    const ly = center + labelR * Math.sin(midAngle);
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', lx);
    text.setAttribute('y', ly);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('font-size', '9');
    text.setAttribute('font-weight', '600');
    text.setAttribute('fill', '#c8c8e4');
    text.textContent = key;
    svg.appendChild(text);
  }

  // Center circle
  const centerCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  centerCircle.setAttribute('cx', center);
  centerCircle.setAttribute('cy', center);
  centerCircle.setAttribute('r', coreR - 2);
  centerCircle.setAttribute('fill', '#111119');
  centerCircle.setAttribute('stroke', '#21213a');
  svg.appendChild(centerCircle);

  const centerText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  centerText.setAttribute('x', center);
  centerText.setAttribute('y', center);
  centerText.setAttribute('text-anchor', 'middle');
  centerText.setAttribute('dominant-baseline', 'middle');
  centerText.setAttribute('font-size', '10');
  centerText.setAttribute('font-weight', '700');
  centerText.setAttribute('fill', '#8b5cf6');
  centerText.textContent = tracks.length;
  svg.appendChild(centerText);

  // Stats below wheel
  if (statsEl) {
    const sorted = Object.entries(keyCounts).filter(([, c]) => c > 0).sort((a, b) => b[1] - a[1]);
    statsEl.innerHTML = '<div style="display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:8px;">' +
      sorted.map(([key, count]) =>
        `<span class="camelot-key-badge" style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:10px;font-size:11px;background:var(--bg-subtle);border:1px solid var(--border);">
          <span style="color:${key.endsWith('A') ? '#60a5fa' : '#8b5cf6'};font-weight:600;">${key}</span>
          <span style="color:var(--text-secondary);">${count}</span>
        </span>`
      ).join('') + '</div>';
  }
}

// ============================================================================
// Import Tab
// ============================================================================

// initImportTab — replaced by initLibraryToolbar() in v2.4.0
function initImportTab() {}

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
  // Search input — handled by initSearchFeature() to avoid duplicate listeners

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
  select.innerHTML = '<option value="">All Genres</option>';
  Object.keys(window.taxonomy).forEach(genre => {
    const option = document.createElement('option');
    option.value = genre;
    option.textContent = genre;
    select.appendChild(option);
  });
}

function getFilteredTracks() {
  let filtered = [...(window.tracks || [])];

  // Genre filter
  const genreEl = document.getElementById('filter-genre');
  const genreFilter = genreEl ? genreEl.value : '';
  if (genreFilter) {
    filtered = filtered.filter(t => t.final_genre === genreFilter);
  }

  // Status filter
  const statusEl = document.getElementById('filter-status');
  const statusFilter = statusEl ? statusEl.value : '';
  if (statusFilter) {
    filtered = filtered.filter(t => t.review_status === statusFilter);
  }

  // Search
  const searchEl = document.getElementById('search-tracks');
  const search = searchEl ? searchEl.value.toLowerCase() : '';
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

function drawWaveformThumb(canvas, data) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  const midY = h / 2;
  const barW = Math.max(1, w / data.length);

  ctx.clearRect(0, 0, w, h);

  // Subtle center line
  ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, midY);
  ctx.lineTo(w, midY);
  ctx.stroke();

  // Bars — teal gradient matching app accent colour
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, 'rgba(0,210,190,0.9)');
  grad.addColorStop(1, 'rgba(0,210,190,0.3)');
  ctx.fillStyle = grad;

  data.forEach((amp, i) => {
    const barH = Math.max(1, amp * midY);
    const x = i * barW;
    // Draw mirrored bar (top + bottom)
    ctx.fillRect(x, midY - barH, barW - 1, barH);
    ctx.fillRect(x, midY, barW - 1, barH);
  });
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

function renderTracks() {
  const tbody = document.getElementById('tracks-tbody');
  const filtered = getFilteredTracks();
  const sorted = sortTracks(filtered);

  tbody.innerHTML = '';

  // Reset to page 1 when filter/sort changes
  window.currentPage = 1;

  if (!sorted.length) {
    const row = document.createElement('tr');
    row.className = 'empty-state';
    const cell = document.createElement('td');
    cell.colSpan = '15';
    cell.textContent = 'No tracks match filters';
    row.appendChild(cell);
    tbody.appendChild(row);
    const countEl = document.getElementById('tracks-count');
    if (countEl) countEl.textContent = '0 tracks';
    updatePaginationControls(sorted.length);
    return;
  }

  // Pagination: slice to current page
  const start = (window.currentPage - 1) * TRACKS_PER_PAGE;
  const end = start + TRACKS_PER_PAGE;
  const pageData = sorted.slice(start, end);

  pageData.forEach(track => {
    const row = document.createElement('tr');
    row.style.cursor = 'pointer';

    const confidenceClass = getConfidenceBadgeClass(track.confidence || 0);
    const statusBadge = getStatusBadge(track.review_status);

    // Checkbox (new column for bulk select)
    const tdCheckbox = document.createElement('td');
    tdCheckbox.className = 'checkbox-col';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.dataset.filePath = track.file_path;
    checkbox.addEventListener('click', (e) => e.stopPropagation());
    tdCheckbox.appendChild(checkbox);
    row.appendChild(tdCheckbox);

    // Title
    const tdTitle = document.createElement('td');
    tdTitle.textContent = track.display_title || '—';
    row.appendChild(tdTitle);

    // Artist
    const tdArtist = document.createElement('td');
    tdArtist.textContent = track.display_artist || '—';
    row.appendChild(tdArtist);

    // Genre (with color chip)
    const tdGenre = document.createElement('td');
    tdGenre.innerHTML = genreChip(track.final_genre);
    row.appendChild(tdGenre);

    // Sub-genre (with color chip)
    const tdSubgenre = document.createElement('td');
    tdSubgenre.innerHTML = genreChip(track.final_subgenre);
    row.appendChild(tdSubgenre);

    // Confidence (with colored badge)
    const tdConfidence = document.createElement('td');
    tdConfidence.innerHTML = confidenceBadge(track.confidence);
    row.appendChild(tdConfidence);

    // BPM
    const tdBpm = document.createElement('td');
    tdBpm.textContent = track.final_bpm || '—';
    row.appendChild(tdBpm);

    // Key
    const tdKey = document.createElement('td');
    tdKey.textContent = track.final_key || '—';
    row.appendChild(tdKey);

    // Clave
    const tdClave = document.createElement('td');
    if (track.latin_analysis_done && track.clave_pattern) {
      const claveBadge = document.createElement('span');
      claveBadge.className = `clave-badge ${track.clave_pattern === '2-3' ? 'clave-badge-2-3' : 'clave-badge-3-2'}`;
      claveBadge.textContent = track.clave_pattern;
      tdClave.appendChild(claveBadge);
    } else {
      tdClave.textContent = '—';
      tdClave.style.color = 'var(--text-muted)';
    }
    row.appendChild(tdClave);

    // Vocal
    const tdVocal = document.createElement('td');
    if (track.vocal_flag) {
      const vClass = track.vocal_flag === 'vocal' ? 'vocal-badge-vocal'
                   : track.vocal_flag === 'instrumental' ? 'vocal-badge-instrumental'
                   : 'vocal-badge-mostly';
      const vLabel = track.vocal_flag === 'vocal' ? 'Vocal'
                   : track.vocal_flag === 'instrumental' ? 'Instr.'
                   : 'Mostly Instr.';
      tdVocal.innerHTML = `<span class="vocal-badge ${vClass}">${vLabel}</span>`;
    } else {
      tdVocal.textContent = '—';
      tdVocal.style.color = 'var(--text-muted)';
    }
    row.appendChild(tdVocal);

    // Tempo category
    const tdTempo = document.createElement('td');
    if (track.tempo_category) {
      const tClass = track.tempo_category === 'fast' ? 'tempo-fast'
                   : track.tempo_category === 'slow' ? 'tempo-slow'
                   : 'tempo-medium';
      tdTempo.innerHTML = `<span class="tempo-badge ${tClass}">${track.tempo_category}</span>`;
    } else {
      tdTempo.textContent = '—';
      tdTempo.style.color = 'var(--text-muted)';
    }
    row.appendChild(tdTempo);

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

    // Approve cell
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
        try {
          await apiFetch('/api/tracks/by-path?path=' + encodeURIComponent(track.file_path), {
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
    row.appendChild(approveTd);

    // Action
    const tdAction = document.createElement('td');
    tdAction.style.textAlign = 'center';
    tdAction.style.display = 'flex';
    tdAction.style.gap = '4px';
    tdAction.style.justifyContent = 'center';

    const btnDetails = document.createElement('button');
    btnDetails.className = 'btn btn-secondary';
    btnDetails.style.padding = '4px 8px';
    btnDetails.style.fontSize = '12px';
    btnDetails.title = 'View details';
    btnDetails.textContent = '▼';
    btnDetails.addEventListener('click', (e) => {
      e.stopPropagation();
      openTrackDetail(track);
    });
    tdAction.appendChild(btnDetails);

    const btnPlay = document.createElement('button');
    btnPlay.className = 'btn btn-secondary';
    btnPlay.style.padding = '4px 8px';
    btnPlay.style.fontSize = '12px';
    btnPlay.title = 'Play preview';
    btnPlay.textContent = '▶';
    btnPlay.addEventListener('click', (e) => {
      e.stopPropagation();
      playTrack(track);
    });
    tdAction.appendChild(btnPlay);

    const btnSetlist = document.createElement('button');
    btnSetlist.className = 'btn btn-secondary';
    btnSetlist.style.padding = '4px 8px';
    btnSetlist.style.fontSize = '12px';
    btnSetlist.title = 'Add to setlist';
    btnSetlist.textContent = '+';
    btnSetlist.addEventListener('click', (e) => {
      e.stopPropagation();
      addTrackToSetlist(track.file_path);
    });
    tdAction.appendChild(btnSetlist);

    const btnEdit = document.createElement('button');
    btnEdit.className = 'btn btn-secondary';
    btnEdit.style.padding = '4px 8px';
    btnEdit.style.fontSize = '12px';
    btnEdit.title = 'Edit track';
    btnEdit.textContent = '✎';
    btnEdit.addEventListener('click', (e) => {
      e.stopPropagation();
      openEditModal(track.file_path);
    });
    tdAction.appendChild(btnEdit);
    row.appendChild(tdAction);

    tbody.appendChild(row);
  });

  const countEl = document.getElementById('tracks-count');
  if (countEl) {
    countEl.textContent = `${sorted.length} track${sorted.length !== 1 ? 's' : ''} (page ${window.currentPage})`;
  }
  updatePaginationControls(sorted.length);
}

// Pagination controls
function updatePaginationControls(totalTracks) {
  const totalPages = Math.ceil(totalTracks / TRACKS_PER_PAGE);
  let container = document.getElementById('tracks-pagination');

  if (!container) {
    // Fallback to pagination-info if tracks-pagination doesn't exist
    container = document.getElementById('pagination-info');
  }

  if (!container) return;
  container.innerHTML = '';
  container.style.display = 'flex';
  container.style.gap = '12px';
  container.style.justifyContent = 'center';
  container.style.padding = '12px 0';
  container.style.alignItems = 'center';

  if (totalPages <= 1) return;

  const prevBtn = document.createElement('button');
  prevBtn.className = 'btn btn-secondary';
  prevBtn.textContent = '← Prev';
  prevBtn.disabled = window.currentPage === 1;
  prevBtn.addEventListener('click', () => {
    if (window.currentPage > 1) {
      window.currentPage--;
      renderTracks();
    }
  });
  container.appendChild(prevBtn);

  const pageInfo = document.createElement('span');
  pageInfo.textContent = `Page ${window.currentPage} of ${totalPages}`;
  pageInfo.style.margin = '0 12px';
  pageInfo.style.alignSelf = 'center';
  container.appendChild(pageInfo);

  const nextBtn = document.createElement('button');
  nextBtn.className = 'btn btn-secondary';
  nextBtn.textContent = 'Next →';
  nextBtn.disabled = window.currentPage === totalPages;
  nextBtn.addEventListener('click', () => {
    if (window.currentPage < totalPages) {
      window.currentPage++;
      renderTracks();
    }
  });
  container.appendChild(nextBtn);
}

// Audio Player Control
function toggleAudioPlay(btn, filePath) {
  const audio = document.getElementById('audio-player');

  // If different file, stop current and play new
  const audioUrl = `/api/audio?path=${encodeURIComponent(filePath)}`;
  const isSameFile = audio.src.endsWith(audioUrl) || audio.src === audioUrl;
  if (currentAudioPlayer !== audio || !isSameFile) {
    // Stop any playing audio
    audio.pause();

    // Update all buttons
    document.querySelectorAll('.audio-play-btn').forEach(b => {
      b.classList.remove('playing');
      b.textContent = '▶';
    });

    // Set new source and play — wait for canplay before calling play()
    audio.src = audioUrl;
    currentAudioPlayer = audio;
    audio.load();

    btn.classList.add('playing');
    btn.textContent = '⏸';

    audio.addEventListener('canplay', function onCanPlay() {
      audio.removeEventListener('canplay', onCanPlay);
      audio.play().catch(err => {
        showToast('Could not play audio', 'error');
        console.error('Audio play error:', err);
        btn.classList.remove('playing');
        btn.textContent = '▶';
      });
    }, { once: true });

    audio.addEventListener('error', function onAudioError() {
      audio.removeEventListener('error', onAudioError);
      showToast('Could not load audio', 'error');
      btn.classList.remove('playing');
      btn.textContent = '▶';
    }, { once: true });

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
    const split = document.getElementById('checkbox-split-m3u').checked;
    const chunkSize = document.getElementById('select-chunk-size')?.value || '500';
    let url = '/api/export/m3u?status=approved';
    if (split) {
      url += `&split=true&chunk_size=${chunkSize}`;
    }
    window.location = url;
    exportMenu.style.display = 'none';
    showToast('Downloading playlist...', 'info');
  });

  // Export by genre
  btnExportByGenre.addEventListener('click', () => {
    showGenreSelector();
    exportMenu.style.display = 'none';
  });

  // Split M3U checkbox
  const checkboxSplitM3u = document.getElementById('checkbox-split-m3u');
  if (checkboxSplitM3u) {
    checkboxSplitM3u.addEventListener('change', () => {
      // Store checkbox state in session storage
      sessionStorage.setItem('splitM3u', checkboxSplitM3u.checked);
    });
  }

  // Export cue sheet
  const btnExportCueSheet = document.getElementById('btn-export-cue-sheet');
  if (btnExportCueSheet) {
    btnExportCueSheet.addEventListener('click', async () => {
      try {
        // Fetch cue sheet data
        const result = await apiFetch('/api/export/cue-sheet', {
          method: 'GET',
        });

        // Convert to JSON and trigger download
        const dataStr = JSON.stringify(result, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `cue-sheet-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        exportMenu.style.display = 'none';
        showToast('Cue sheet exported', 'success');
      } catch (error) {
        // Error already shown in apiFetch
      }
    });
  }

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
    btnSkip.setAttribute('data-skip-btn', '');
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
    btnApprove.setAttribute('data-approve-btn', '');
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

  if (btnSaveTaxonomy) {
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
  }

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
    countDiv.textContent = `${subgenres.length} comment${subgenres.length !== 1 ? 's' : ''}`;
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
    addBtn.textContent = '+ Add Comment';
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
  const name = prompt(`Add comment to ${genre}:`);
  if (name) {
    if (!window.taxonomy[genre].subgenres) {
      window.taxonomy[genre].subgenres = [];
    }
    window.taxonomy[genre].subgenres.push(name);
    renderTaxonomy();
  }
}

function removeSubgenre(genre, idx) {
  if (confirm('Remove this comment?')) {
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

  // Close modals with Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (modal.style.display !== 'none') modal.style.display = 'none';
      if (addGenreModal.style.display !== 'none') addGenreModal.style.display = 'none';
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
  // Replace the select element to remove any previously attached listeners (prevent leak)
  const oldGenreSelect = document.getElementById('modal-genre');
  const newGenreSelect = oldGenreSelect.cloneNode(true);
  oldGenreSelect.parentNode.replaceChild(newGenreSelect, oldGenreSelect);
  newGenreSelect.addEventListener('change', updateSubgenreOptions);

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
  optionDefault.textContent = 'Select Comment';
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
    const result = await apiFetch(`/api/tracks/by-path?path=${encodeURIComponent(currentEditPath)}`, {
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
    const anthropicInput = document.getElementById('settings-anthropic-key');
    const openrouterInput = document.getElementById('settings-openrouter-key');

    // Show placeholder text for existing keys — format: "sk-a...xyz1 — saved ✓"
    const keyLabel = (masked) => masked ? `${masked}  —  saved ✓` : 'saved ✓';
    if (response.has_gemini_key) {
      geminiInput.placeholder = keyLabel(response.gemini_api_key);
    } else {
      geminiInput.placeholder = 'Paste your Gemini API key';
    }
    if (response.has_openrouter_key && openrouterInput) {
      openrouterInput.placeholder = keyLabel(response.openrouter_api_key);
    } else if (openrouterInput) {
      openrouterInput.placeholder = 'Paste your OpenRouter API key';
    }
    if (response.has_anthropic_key && anthropicInput) {
      anthropicInput.placeholder = keyLabel(response.anthropic_api_key);
    } else if (anthropicInput) {
      anthropicInput.placeholder = 'Paste your Anthropic API key';
    }
    if (response.has_spotify) {
      spotifyIdInput.placeholder = keyLabel(response.spotify_client_id);
      spotifySecretInput.placeholder = keyLabel(response.spotify_client_secret);
    } else {
      spotifyIdInput.placeholder = 'Paste your Spotify Client ID';
      spotifySecretInput.placeholder = 'Paste your Spotify Client Secret';
    }

    // Clear the actual input values
    geminiInput.value = '';
    spotifyIdInput.value = '';
    spotifySecretInput.value = '';
    if (anthropicInput) anthropicInput.value = '';
    if (openrouterInput) openrouterInput.value = '';

    // Sync Round 2 fields if present
    const aiModelSelect = document.getElementById('settings-ai-model');
    if (aiModelSelect && response.ai_model) aiModelSelect.value = response.ai_model;
    const ollamaModelInput = document.getElementById('settings-ollama-model');
    if (ollamaModelInput && response.ollama_model) ollamaModelInput.value = response.ollama_model;
    const batchSizeInput = document.getElementById('settings-batch-size');
    if (batchSizeInput && response.classify_batch_size) batchSizeInput.value = response.classify_batch_size;
    const autoApproveInput = document.getElementById('settings-auto-approve');
    if (autoApproveInput && response.auto_approve_threshold !== undefined) {
      autoApproveInput.value = response.auto_approve_threshold;
      const valDisplay = document.getElementById('settings-auto-approve-value');
      if (valDisplay) valDisplay.textContent = response.auto_approve_threshold + '%';
    }

  } catch (error) {
    // Error already shown in apiFetch
  }
}

async function saveSettings() {
  try {
    const geminiKey = document.getElementById('settings-gemini-key').value.trim();
    const openrouterKey = document.getElementById('settings-openrouter-key').value.trim();
    const spotifyId = document.getElementById('settings-spotify-id').value.trim();
    const spotifySecret = document.getElementById('settings-spotify-secret').value.trim();
    const threshold = parseInt(document.getElementById('settings-auto-approve')?.value) || 80;

    // Always include threshold so there's always something to save
    const payload = { auto_approve_threshold: threshold };
    if (geminiKey) payload.gemini_api_key = geminiKey;
    if (openrouterKey) payload.openrouter_api_key = openrouterKey;
    if (spotifyId) payload.spotify_client_id = spotifyId;
    if (spotifySecret) payload.spotify_client_secret = spotifySecret;

    showSpinner('Saving settings...');
    const result = await apiFetch('/api/settings', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (result.saved) {
      // Also save taxonomy in the same pass
      await apiFetch('/api/taxonomy', {
        method: 'PUT',
        body: JSON.stringify({ genres: window.taxonomy }),
      });
      showToast('All settings saved', 'success');
      // Clear key inputs and reload to show masked values in placeholders
      document.getElementById('settings-gemini-key').value = '';
      document.getElementById('settings-openrouter-key').value = '';
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

const THEMES = ['dark', 'pro-booth', 'studio', 'pure-black'];

function initTheme() {
  const saved = localStorage.getItem('theme') || 'pure-black';
  applyTheme(saved);
}

function applyTheme(theme) {
  document.body.classList.remove('light', ...THEMES.filter(t => t !== 'dark'));
  if (theme !== 'dark') document.body.classList.add(theme);
  localStorage.setItem('theme', theme);
  document.querySelectorAll('.swatch').forEach(s => {
    s.classList.toggle('active', s.dataset.theme === theme);
  });
}

function initThemeSwatches() {
  document.querySelectorAll('.swatch').forEach(btn => {
    btn.addEventListener('click', () => applyTheme(btn.dataset.theme));
  });
}

// ============================================================================
// Round 2 Features: Progress Streaming, Track Detail Panel, Setlist Builder,
// Search, Bulk Select, Apple Music Sync, Enhanced Settings, Export
// ============================================================================

// SSE Progress streaming
function connectToProgress(opId, total, onProgress, onComplete, onError) {
  const eventSource = new EventSource(`/api/progress/${opId}`);

  eventSource.addEventListener('progress', (event) => {
    const data = JSON.parse(event.data);
    if (onProgress) {
      onProgress(data.current, data.total, data.message);
    }
  });

  eventSource.addEventListener('complete', (event) => {
    eventSource.close();
    const data = JSON.parse(event.data);
    if (onComplete) {
      onComplete(data);
    }
  });

  eventSource.addEventListener('error', (event) => {
    eventSource.close();
    if (onError) {
      // DOM Event objects don't have .message — synthesise an Error-like object
      const err = event instanceof Error ? event : new Error('Connection lost');
      onError(err);
    }
  });

  return eventSource;
}


// Track detail panel
function openTrackDetail(track) {
  const overlay = document.getElementById('track-detail-overlay');
  const panel = document.getElementById('track-detail-panel');

  if (!overlay || !panel) return;

  const detailContent = document.querySelector('.track-detail-content');
  if (!detailContent) return;

  // Format metadata
  const bpm = track.final_bpm || track.estimated_bpm || 'N/A';
  const key = track.final_key || track.estimated_key || 'N/A';
  const year = track.final_year || 'N/A';
  const duration = track.duration ? Math.round(track.duration) : 'N/A';
  const format = track.file_extension?.toUpperCase() || 'Unknown';
  const size = track.file_size ? (track.file_size / 1024 / 1024).toFixed(1) : 'N/A';

  // Build AI classification section
  let aiSection = '';
  if (track.final_genre || track.proposed_genre) {
    const genre = track.final_genre || track.proposed_genre;
    const subgenre = track.final_subgenre || track.proposed_subgenre || 'N/A';
    const confidence = track.confidence_score ? Math.round(track.confidence_score) : 'N/A';
    const reasoning = track.reasoning || '';

    aiSection = `
      <div class="track-detail-section">
        <h4>AI Classification</h4>
        <div class="track-detail-classification">
          <div class="classification-item">
            <span class="label">Genre:</span>
            <span class="value">${escapeHtml(genre)}</span>
          </div>
          <div class="classification-item">
            <span class="label">Comments:</span>
            <span class="value">${escapeHtml(subgenre)}</span>
          </div>
          <div class="classification-item">
            <span class="label">Confidence:</span>
            <span class="value">
              <span class="confidence-badge" style="background-color: ${confidence >= 80 ? '#4CAF50' : confidence >= 60 ? '#FF9800' : '#f44336'};">
                ${confidence}%
              </span>
            </span>
          </div>
          ${reasoning ? `<div class="classification-item" style="grid-column: 1/-1;"><span class="label">Reasoning:</span><span class="value reasoning-text">${escapeHtml(reasoning)}</span></div>` : ''}
        </div>
      </div>
    `;
  }

  detailContent.innerHTML = `
    <div class="track-detail-section">
      <h3 class="track-detail-title-header">${escapeHtml(track.display_title || 'Unknown')}</h3>
      <div class="track-detail-artist">${escapeHtml(track.display_artist || 'Unknown')}</div>
      <div class="track-detail-album">${escapeHtml(track.album || '')}</div>
    </div>

    <div class="track-detail-section">
      <h4>Metadata</h4>
      <div class="metadata-grid">
        <div class="metadata-item"><span class="label">BPM:</span> <span class="value">${escapeHtml(String(bpm))}</span></div>
        <div class="metadata-item"><span class="label">Key:</span> <span class="value">${escapeHtml(key)}</span></div>
        <div class="metadata-item"><span class="label">Year:</span> <span class="value">${escapeHtml(String(year))}</span></div>
        <div class="metadata-item"><span class="label">Duration:</span> <span class="value">${escapeHtml(String(duration))}s</span></div>
        <div class="metadata-item"><span class="label">Format:</span> <span class="value">${escapeHtml(format)}</span></div>
        <div class="metadata-item"><span class="label">Size:</span> <span class="value">${escapeHtml(String(size))} MB</span></div>
      </div>
    </div>

    ${aiSection}

    ${track.clave_pattern ? `
      <div class="track-detail-section">
        <h4>Clave Analysis</h4>
        <div style="display: flex; gap: 12px; align-items: center;">
          <span class="clave-badge ${track.clave_pattern === '2-3' ? 'clave-badge-2-3' : 'clave-badge-3-2'}">
            ${track.clave_pattern}
          </span>
          <span style="font-size: 12px; color: #999;">
            Confidence: ${track.clave_confidence ? Math.round(track.clave_confidence * 100) : '0'}%
          </span>
        </div>
      </div>
    ` : ''}

    <div class="track-detail-section">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <h4>Cue Points</h4>
        <button class="btn btn-small" data-action="analyze-cue-points" data-file-path="${track.file_path}">Run Cue Analysis</button>
      </div>
      <div id="cue-points-list" style="display: flex; flex-direction: column; gap: 8px;">
        ${track.suggested_cues && track.suggested_cues.length > 0 ? track.suggested_cues.map(cue => `
          <div class="cue-point-item">
            <span class="cue-point-dot ${cue.hot_cue ? 'cue-point-dot-hot' : cue.loop ? 'cue-point-dot-loop' : ''}"></span>
            <span class="cue-time">${formatTime(cue.time)}</span>
            <span class="cue-label">${escapeHtml(cue.label || 'Cue Point')}</span>
          </div>
        `).join('') : '<p style="color: #999; font-size: 12px;">No cue points analyzed yet</p>'}
      </div>
    </div>

    <div class="track-detail-section">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <h4>Mix Suggestions</h4>
        <button class="btn btn-small" data-action="find-mix-matches" data-file-path="${track.file_path}">Find Compatible Tracks</button>
      </div>
      <div id="mix-suggestions-list" style="display: flex; flex-direction: column; gap: 8px;">
        <p style="color: #999; font-size: 12px;">Click "Find Compatible Tracks" to discover mixes</p>
      </div>
    </div>

    <div class="track-detail-actions">
      <button class="btn btn-primary" onclick="addTrackToSetlist('${track.file_path.replace(/'/g, "\\'")}')">Add to Setlist</button>
    </div>
  `;

  overlay.style.display = 'block';
  panel.style.display = 'block';

  // Attach event listeners for track detail buttons
  const cueAnalysisBtn = panel.querySelector('[data-action="analyze-cue-points"]');
  const mixMatchesBtn = panel.querySelector('[data-action="find-mix-matches"]');

  if (cueAnalysisBtn) {
    cueAnalysisBtn.addEventListener('click', async () => {
      const filePath = cueAnalysisBtn.dataset.filePath;
      const currentTrack = window.tracks.find(t => t.file_path === filePath);
      if (!currentTrack) return;

      showSpinner('Analyzing cue points...');
      try {
        const result = await apiFetch('/api/analyze/latin', {
          method: 'POST',
          body: JSON.stringify({ paths: [filePath] }),
        });

        // Update track with cue analysis results
        if (result.analyzed && result.analyzed.length > 0) {
          const analyzed = result.analyzed[0];
          currentTrack.clave_pattern = analyzed.clave_pattern;
          currentTrack.clave_confidence = analyzed.clave_confidence;
          currentTrack.suggested_cues = analyzed.suggested_cues || [];
          currentTrack.latin_analysis_done = true;

          // Update the cue points list in the panel
          const cueList = panel.querySelector('#cue-points-list');
          if (cueList && currentTrack.suggested_cues.length > 0) {
            cueList.innerHTML = currentTrack.suggested_cues.map(cue => `
              <div class="cue-point-item">
                <span class="cue-point-dot ${cue.hot_cue ? 'cue-point-dot-hot' : cue.loop ? 'cue-point-dot-loop' : ''}"></span>
                <span class="cue-time">${formatTime(cue.time)}</span>
                <span class="cue-label">${escapeHtml(cue.label || 'Cue Point')}</span>
              </div>
            `).join('');
          }
        }

        showToast('Cue points analyzed', 'success');
      } catch (error) {
        // Error already shown
      } finally {
        hideSpinner();
      }
    });
  }

  if (mixMatchesBtn) {
    mixMatchesBtn.addEventListener('click', async () => {
      const filePath = mixMatchesBtn.dataset.filePath;
      const currentTrack = window.tracks.find(t => t.file_path === filePath);
      if (!currentTrack) return;

      showSpinner('Finding compatible tracks...');
      try {
        const result = await apiFetch(`/api/mixes/compatible/${encodeURIComponent(filePath)}`, {
          method: 'GET',
        });

        // Render mix suggestions
        const mixList = panel.querySelector('#mix-suggestions-list');
        if (mixList && result.compatible_tracks && result.compatible_tracks.length > 0) {
          mixList.innerHTML = result.compatible_tracks.map(match => `
            <div class="mix-suggestion-item">
              <div class="mix-suggestion-content">
                <div class="mix-suggestion-title">${escapeHtml(match.track.display_title || 'Unknown')}</div>
                <div class="mix-suggestion-artist">${escapeHtml(match.track.display_artist || 'Unknown')}</div>
              </div>
              <span class="mix-score-badge ${match.score >= 80 ? 'mix-score-high' : match.score >= 60 ? 'mix-score-medium' : 'mix-score-low'}">
                ${Math.round(match.score)}%
              </span>
            </div>
          `).join('');
        } else {
          mixList.innerHTML = '<p style="color: #999; font-size: 12px;">No compatible tracks found</p>';
        }

        showToast('Found compatible tracks', 'success');
      } catch (error) {
        // Error already shown
      } finally {
        hideSpinner();
      }
    });
  }
}

function closeTrackDetail() {
  const overlay = document.getElementById('track-detail-overlay');
  const panel = document.getElementById('track-detail-panel');

  if (overlay) overlay.style.display = 'none';
  if (panel) panel.style.display = 'none';
}

// Setlist builder
function initSetlistTab() {
  // Wire "Add to Setlist" / "Remove from Setlist" via event delegation (works for both
  // track table rows and setlist panel items regardless of render order)
  document.addEventListener('click', (e) => {
    if (e.target.dataset.action === 'add-to-setlist') {
      addTrackToSetlist(e.target.dataset.filePath);
    }
    if (e.target.dataset.action === 'remove-from-setlist') {
      removeTrackFromSetlist(e.target.dataset.filePath);
    }
  });

  // Wire M3U export button
  document.getElementById('btn-setlist-export')?.addEventListener('click', async () => {
    if (!window.setlist.length) return;
    const paths = window.setlist.map(t => t.file_path);
    try {
      const res = await fetch('/api/export/m3u', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_paths: paths }),
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'setlist.m3u';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('Setlist exported as M3U', 'success');
    } catch {
      showToast('Export failed', 'error');
    }
  });
}

function addTrackToSetlist(filePath) {
  const track = window.tracks.find(t => t.file_path === filePath);
  if (!track) return;

  if (!window.setlist.find(t => t.file_path === filePath)) {
    window.setlist.push(track);
    saveSetlistToStorage();
    renderSetlist();
    showToast('Track added to setlist', 'success');
  } else {
    showToast('Track already in setlist', 'info');
  }
}

function removeTrackFromSetlist(filePath) {
  window.setlist = window.setlist.filter(t => t.file_path !== filePath);
  saveSetlistToStorage();
  renderSetlist();
  showToast('Track removed from setlist', 'success');
}

function renderSetlist() {
  const currentContainer = document.getElementById('setlist-tracks');
  const suggestionsContainer = document.getElementById('setlist-suggestions-container');
  const emptyState = document.getElementById('setlist-empty-state');
  const mainPanel = document.getElementById('setlist-main');

  if (!currentContainer) return;

  // Show/hide empty state vs main panel
  if (emptyState) emptyState.style.display = window.setlist.length === 0 ? '' : 'none';
  if (mainPanel) mainPanel.style.display = window.setlist.length === 0 ? 'none' : '';

  // Render current setlist
  while (currentContainer.firstChild) currentContainer.removeChild(currentContainer.firstChild);
  let totalDuration = 0;

  window.setlist.forEach((track, idx) => {
    const duration = track.duration || 0;
    totalDuration += duration;

    const item = document.createElement('div');
    item.className = 'setlist-track-item';

    const numSpan = document.createElement('span');
    numSpan.className = 'setlist-track-number';
    numSpan.textContent = String(idx + 1);

    const infoDiv = document.createElement('div');
    infoDiv.className = 'setlist-track-info';
    const titleDiv = document.createElement('div');
    titleDiv.className = 'setlist-track-title';
    titleDiv.textContent = track.display_title || 'Unknown';
    const metaDiv = document.createElement('div');
    metaDiv.className = 'setlist-track-meta';
    metaDiv.textContent = `${track.display_artist || ''} — ${track.final_key || 'N/A'} @ ${track.final_bpm || '?'} BPM`;
    infoDiv.appendChild(titleDiv);
    infoDiv.appendChild(metaDiv);

    const durSpan = document.createElement('span');
    durSpan.className = 'setlist-track-duration';
    durSpan.textContent = `${Math.round(duration)}s`;

    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn btn-small';
    removeBtn.dataset.action = 'remove-from-setlist';
    removeBtn.dataset.filePath = track.file_path;
    removeBtn.textContent = 'Remove';

    item.appendChild(numSpan);
    item.appendChild(infoDiv);
    item.appendChild(durSpan);
    item.appendChild(removeBtn);
    currentContainer.appendChild(item);
  });

  // Render harmonic suggestions if setlist not empty
  if (suggestionsContainer) {
    while (suggestionsContainer.firstChild) suggestionsContainer.removeChild(suggestionsContainer.firstChild);
    if (window.setlist.length > 0) {
      const lastTrack = window.setlist[window.setlist.length - 1];
      const suggestions = findHarmonicCompatible(lastTrack);
      const header = document.createElement('p');
      header.style.cssText = 'color:var(--text-secondary);font-size:12px;';
      header.textContent = suggestions.length ? `${suggestions.length} compatible tracks found` : 'No compatible tracks found';
      suggestionsContainer.appendChild(header);
      suggestions.slice(0, 5).forEach(suggestion => {
        const item = document.createElement('div');
        item.className = 'setlist-suggestion-item';

        const infoDiv = document.createElement('div');
        infoDiv.className = 'setlist-suggestion-info';
        const titleDiv = document.createElement('div');
        titleDiv.className = 'suggestion-title';
        titleDiv.textContent = suggestion.track.display_title || 'Unknown';
        const metaDiv = document.createElement('div');
        metaDiv.className = 'suggestion-meta';
        metaDiv.textContent = `${suggestion.track.display_artist || ''} — ${suggestion.score.toFixed(0)}% match`;
        infoDiv.appendChild(titleDiv);
        infoDiv.appendChild(metaDiv);

        const addBtn = document.createElement('button');
        addBtn.className = 'btn btn-small';
        addBtn.dataset.action = 'add-to-setlist';
        addBtn.dataset.filePath = suggestion.track.file_path;
        addBtn.textContent = 'Add';

        item.appendChild(infoDiv);
        item.appendChild(addBtn);
        suggestionsContainer.appendChild(item);
      });
    } else {
      const hint = document.createElement('p');
      hint.style.cssText = 'color:var(--text-secondary);font-size:12px;';
      hint.textContent = 'Select a track to see compatible suggestions';
      suggestionsContainer.appendChild(hint);
    }
  }

  // Update footer counters using static HTML elements
  const countEl = document.getElementById('setlist-count');
  const durEl = document.getElementById('setlist-duration');
  const exportBtn = document.getElementById('btn-setlist-export');
  const mins = Math.floor(totalDuration / 60);
  const secs = Math.floor(totalDuration % 60);
  if (countEl) countEl.textContent = `${window.setlist.length} track${window.setlist.length !== 1 ? 's' : ''}`;
  if (durEl) durEl.textContent = `${mins}:${String(secs).padStart(2, '0')}`;
  if (exportBtn) exportBtn.disabled = window.setlist.length === 0;
}

function findHarmonicCompatible(track) {
  if (!track.final_key) return [];

  const camelotWheel = {
    '1A': ['12A', '2A', '1B'], '1B': ['12B', '2B', '1A'],
    '2A': ['1A', '3A', '2B'], '2B': ['1B', '3B', '2A'],
    '3A': ['2A', '4A', '3B'], '3B': ['2B', '4B', '3A'],
    '4A': ['3A', '5A', '4B'], '4B': ['3B', '5B', '4A'],
    '5A': ['4A', '6A', '5B'], '5B': ['4B', '6B', '5A'],
    '6A': ['5A', '7A', '6B'], '6B': ['5B', '7B', '6A'],
    '7A': ['6A', '8A', '7B'], '7B': ['6B', '8B', '7A'],
    '8A': ['7A', '9A', '8B'], '8B': ['7B', '9B', '8A'],
    '9A': ['8A', '10A', '9B'], '9B': ['8B', '10B', '9A'],
    '10A': ['9A', '11A', '10B'], '10B': ['9B', '11B', '10A'],
    '11A': ['10A', '12A', '11B'], '11B': ['10B', '12B', '11A'],
    '12A': ['11A', '1A', '12B'], '12B': ['11B', '1B', '12A'],
  };

  const compatible = camelotWheel[track.final_key] || [];
  const bpmTolerance = 5;

  const suggestions = window.tracks
    .filter(t => t.file_path !== track.file_path && !window.setlist.find(st => st.file_path === t.file_path))
    .map(t => {
      let score = 0;

      // Key compatibility (100 points max)
      if (compatible.includes(t.final_key)) {
        score += 100;
      } else if (t.final_key === track.final_key) {
        score += 80;
      } else {
        score += 20;
      }

      // BPM proximity (100 points max, decreasing with distance)
      const bpmDiff = Math.abs((t.final_bpm || 0) - (track.final_bpm || 0));
      if (bpmDiff <= bpmTolerance) {
        score += 100;
      } else if (bpmDiff <= 20) {
        score += 50;
      } else {
        score += 0;
      }

      // Genre match (50 points)
      if (t.final_genre === track.final_genre) {
        score += 50;
      }

      return { track: t, score: score / 2.5 }; // Normalize to 0-100
    })
    .sort((a, b) => b.score - a.score);

  return suggestions;
}

// ============================================================================
// Feature 10: Set Planner Tab
// ============================================================================

let setplanArcs = [];
let currentSetplanArc = 'warmup';
let generatedSetTracks = [];

async function loadSetplanArcs() {
  try {
    const res = await apiFetch('/api/setplan/arcs');
    setplanArcs = res;
    const sel = document.getElementById('arc-selector');
    if (!sel) return;
    sel.innerHTML = setplanArcs.map(a =>
      `<button class="arc-btn${a.id === 'warmup' ? ' active' : ''}" data-arc="${a.id}" title="${a.description}">${a.name}</button>`
    ).join('');
    sel.querySelectorAll('.arc-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        sel.querySelectorAll('.arc-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentSetplanArc = btn.dataset.arc;
        drawArcPreview();
      });
    });
    drawArcPreview();
  } catch(e) { console.error('Failed to load arcs', e); }
}

function drawArcPreview() {
  const arc = setplanArcs.find(a => a.id === currentSetplanArc);
  if (!arc) return;
  const canvas = document.getElementById('arc-canvas');
  if (!canvas) return;
  canvas.width = canvas.offsetWidth || 600;
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const curve = arc.energy_curve;
  const pts = curve.map((v, i) => ({
    x: (i / (curve.length - 1)) * (w - 20) + 10,
    y: h - 6 - ((v - 1) / 9) * (h - 12)
  }));
  // Fill
  ctx.beginPath();
  ctx.moveTo(pts[0].x, h);
  pts.forEach(p => ctx.lineTo(p.x, p.y));
  ctx.lineTo(pts[pts.length-1].x, h);
  ctx.closePath();
  ctx.fillStyle = 'rgba(0,210,190,0.15)';
  ctx.fill();
  // Line
  ctx.beginPath();
  ctx.moveTo(pts[0].x, pts[0].y);
  pts.forEach(p => ctx.lineTo(p.x, p.y));
  ctx.strokeStyle = 'var(--accent, #00d2be)';
  ctx.lineWidth = 2;
  ctx.stroke();
  document.getElementById('setplan-arc-preview').style.display = 'block';
}

async function generateSet() {
  const btn = document.getElementById('btn-generate-set');
  btn.disabled = true; btn.textContent = 'Generating...';
  try {
    const body = {
      arc: currentSetplanArc,
      duration_minutes: parseInt(document.getElementById('setplan-duration').value) || 60,
    };
    const genre = document.getElementById('setplan-genre').value;
    if (genre) body.genre = genre;
    const bpmMin = document.getElementById('setplan-bpm-min').value;
    const bpmMax = document.getElementById('setplan-bpm-max').value;
    if (bpmMin || bpmMax) body.bpm_range = [parseInt(bpmMin)||0, parseInt(bpmMax)||999];

    const res = await apiFetch('/api/setplan/generate', {
      method: 'POST',
      body: JSON.stringify(body)
    });
    const d = res;
    if (d.error) { alert(d.error); return; }
    generatedSetTracks = d.tracks;
    renderSetplanResults(d);
  } finally {
    btn.disabled = false; btn.textContent = 'Generate Set';
  }
}

function renderSetplanResults(d) {
  const el = document.getElementById('setplan-results');
  if (!d.tracks?.length) {
    el.innerHTML = '<p style="color:var(--text-muted)">No tracks found matching your filters. Try removing the genre or BPM constraints.</p>';
    return;
  }
  const s = d.stats;
  let html = `<div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem;font-size:0.85rem;color:var(--text-muted);">
    <span>${d.tracks.length} tracks</span>
    <span>~${s.estimated_duration_minutes} min</span>
    <span>BPM ${s.bpm_range?.[0]}–${s.bpm_range?.[1]}</span>
    <span>Energy ${s.energy_range?.[0]}–${s.energy_range?.[1]}</span>
  </div>`;
  html += `<table class="data-table" style="font-size:0.82rem;">
    <thead><tr><th>#</th><th>Title</th><th>Artist</th><th>Genre</th><th>BPM</th><th>Key</th><th>Energy</th><th>Tempo</th></tr></thead>
    <tbody>`;
  d.tracks.forEach((t, i) => {
    const energyColor = t.energy >= 8 ? 'var(--danger)' : t.energy >= 6 ? '#f0a500' : 'var(--accent)';
    html += `<tr>
      <td style="color:var(--text-muted)">${i+1}</td>
      <td>${t.title || '—'}</td>
      <td>${t.artist || '—'}</td>
      <td>${t.genre || '—'}</td>
      <td>${t.bpm || '—'}</td>
      <td><span class="badge">${t.key || '—'}</span></td>
      <td><span style="color:${energyColor};font-weight:600">${t.energy || '—'}</span></td>
      <td>${t.tempo_category ? `<span class="tempo-badge tempo-${t.tempo_category}">${t.tempo_category}</span>` : '—'}</td>
    </tr>`;
  });
  html += `</tbody></table>
    <div style="margin-top:0.75rem;display:flex;gap:0.5rem;">
      <button class="btn btn-primary" id="btn-export-setplan-m3u">Export as M3U</button>
    </div>`;
  el.innerHTML = html;
  document.getElementById('btn-export-setplan-m3u')?.addEventListener('click', exportSetplanM3U);
}

async function exportSetplanM3U() {
  const res = await fetch('/api/setplan/export-m3u', {
    method: 'POST',
    body: JSON.stringify({tracks: generatedSetTracks, filename: `set-${currentSetplanArc}.m3u`})
  });
  if (!res.ok) { alert('Export failed'); return; }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `set-${currentSetplanArc}.m3u`;
  a.click(); URL.revokeObjectURL(url);
}

function populateSetplanGenres() {
  const sel = document.getElementById('setplan-genre');
  if (!sel || !window.tracks) return;
  const genres = [...new Set(window.tracks.map(t => t.final_genre).filter(Boolean))].sort();
  const existing = [...sel.options].map(o => o.value);
  genres.forEach(g => {
    if (!existing.includes(g)) {
      const opt = document.createElement('option');
      opt.value = g; opt.textContent = g;
      sel.appendChild(opt);
    }
  });
}

// Text search with debounce
function initSearchFeature() {
  const searchInput = document.getElementById('search-tracks');
  const searchClearBtn = document.getElementById('search-clear');

  if (!searchInput) return;

  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchDebounceTimer);
    const query = e.target.value.toLowerCase();

    searchDebounceTimer = setTimeout(() => {
      window.tracks = window.tracks.map(t => ({
        ...t,
        _searchMatch: !query ||
          (t.display_title?.toLowerCase().includes(query)) ||
          (t.display_artist?.toLowerCase().includes(query)) ||
          (t.album?.toLowerCase().includes(query))
      }));
      renderTracks();
    }, 300);

    // Show/hide clear button
    if (searchClearBtn) {
      searchClearBtn.style.display = query ? 'block' : 'none';
    }
  });

  if (searchClearBtn) {
    searchClearBtn.addEventListener('click', () => {
      searchInput.value = '';
      window.tracks = window.tracks.map(t => ({ ...t, _searchMatch: true }));
      renderTracks();
      if (searchClearBtn) searchClearBtn.style.display = 'none';
    });
  }
}

// Bulk select with floating action bar
function initBulkSelectFeature() {
  const selectAllCheckbox = document.getElementById('select-all-checkbox');
  const trackTableBody = document.getElementById('tracks-tbody');

  if (!selectAllCheckbox || !trackTableBody) return;

  selectAllCheckbox.addEventListener('change', (e) => {
    const checkboxes = trackTableBody.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => {
      cb.checked = e.target.checked;
      if (e.target.checked) {
        window.selectedTracks.add(cb.dataset.filePath);
      } else {
        window.selectedTracks.delete(cb.dataset.filePath);
      }
    });
    updateBulkActionsBar();
  });

  trackTableBody.addEventListener('change', (e) => {
    if (e.target.type === 'checkbox') {
      if (e.target.checked) {
        window.selectedTracks.add(e.target.dataset.filePath);
      } else {
        window.selectedTracks.delete(e.target.dataset.filePath);
      }
      updateBulkActionsBar();
    }
  });

  document.addEventListener('click', (e) => {
    if (e.target.id === 'bulk-edit-btn') {
      showBulkEditModal();
    }
    if (e.target.id === 'bulk-add-setlist-btn') {
      window.selectedTracks.forEach(filePath => {
        addTrackToSetlist(filePath);
      });
      window.selectedTracks.clear();
      updateBulkActionsBar();
    }
    if (e.target.id === 'bulk-export-btn') {
      const modal = document.getElementById('export-format-modal');
      if (modal) modal.style.display = 'flex';
    }
  });

  // Wire bulk edit modal buttons
  const bulkEditModal = document.getElementById('bulk-edit-modal');
  const closeFn = () => { if (bulkEditModal) bulkEditModal.style.display = 'none'; };
  document.getElementById('bulk-edit-close')?.addEventListener('click', closeFn);
  document.getElementById('bulk-edit-cancel')?.addEventListener('click', closeFn);
  document.getElementById('bulk-edit-save')?.addEventListener('click', handleBulkEdit);
  bulkEditModal?.addEventListener('click', e => { if (e.target === bulkEditModal) closeFn(); });

  // Wire export format modal close + export buttons
  const exportModal = document.getElementById('export-format-modal');
  const closeExportFn = () => { if (exportModal) exportModal.style.display = 'none'; };
  document.getElementById('export-format-close')?.addEventListener('click', closeExportFn);
  exportModal?.addEventListener('click', e => { if (e.target === exportModal) closeExportFn(); });
  document.getElementById('btn-export-csv')?.addEventListener('click', () => { exportTracks('csv'); closeExportFn(); });
  document.getElementById('btn-export-json')?.addEventListener('click', () => { exportTracks('json'); closeExportFn(); });
  document.getElementById('btn-export-rekordbox')?.addEventListener('click', () => { exportTracks('rekordbox'); closeExportFn(); });
}

function updateBulkActionsBar() {
  const bar = document.getElementById('bulk-actions-bar');
  if (!bar) return;

  if (window.selectedTracks.size > 0) {
    bar.style.display = 'flex';
    bar.innerHTML = `
      <span class="bulk-actions-count">${window.selectedTracks.size} selected</span>
      <button class="btn btn-accent btn-small" id="bulk-analyze-btn">Analyse</button>
      <button class="btn btn-primary btn-small" id="bulk-edit-btn">Bulk Edit</button>
      <button class="btn btn-secondary btn-small" id="bulk-export-btn">Export</button>
      <button class="btn btn-secondary btn-small" id="bulk-add-setlist-btn">Add to Setlist</button>
    `;

    const bulkAnalyzeBtn = document.getElementById('bulk-analyze-btn');
    if (bulkAnalyzeBtn) {
      bulkAnalyzeBtn.addEventListener('click', async () => {
        const paths = Array.from(window.selectedTracks);
        bulkAnalyzeBtn.disabled = true;
        showProgressInStatsBar(`Analysing ${paths.length} track${paths.length !== 1 ? 's' : ''}...`);
        try {
          const result = await apiFetch('/api/analyze', {
            method: 'POST',
            body: JSON.stringify({ track_paths: paths })
          });
          if (result && result.op_id) {
            connectToProgress(
              result.op_id,
              result.total,
              (current, total) => {
                const pct = Math.round((current / total) * 100);
                showProgressInStatsBar(`${current} / ${total} analysing...`);
                const fill = document.getElementById('stat-progress-fill');
                if (fill) fill.style.width = pct + '%';
              },
              (data) => {
                hideProgressInStatsBar();
                const fill = document.getElementById('stat-progress-fill');
                if (fill) fill.style.width = '0%';
                // Refetch fresh track data from server
                apiFetch('/api/tracks').then(d => {
                  window.tracks = d.tracks || [];
                  renderTracks();
                  updateStats();
                });
                updateToolbarButtonStates();
                showToast(`Analysed ${paths.length} track${paths.length !== 1 ? 's' : ''}`, 'success');
              },
              (err) => {
                hideProgressInStatsBar();
                showToast('Analyse error: ' + err.message, 'error');
              }
            );
          }
        } catch (e) {
          hideProgressInStatsBar();
          showToast('Analyse failed: ' + e.message, 'error');
        }
      });
    }
  } else {
    bar.style.display = 'none';
  }
}

function showBulkEditModal() {
  const modal = document.getElementById('bulk-edit-modal');
  if (!modal) return;

  // Populate genre select from taxonomy
  const genreSelect = document.getElementById('bulk-genre');
  if (genreSelect && window.taxonomy) {
    while (genreSelect.firstChild) genreSelect.removeChild(genreSelect.firstChild);
    const defaultOpt = document.createElement('option');
    defaultOpt.value = '';
    defaultOpt.textContent = '— No change —';
    genreSelect.appendChild(defaultOpt);
    Object.keys(window.taxonomy).forEach(genre => {
      const opt = document.createElement('option');
      opt.value = genre;
      opt.textContent = genre;
      genreSelect.appendChild(opt);
    });
  }

  const countEl = document.getElementById('bulk-edit-count');
  if (countEl) countEl.textContent = `${window.selectedTracks.size} track${window.selectedTracks.size !== 1 ? 's' : ''} selected`;

  modal.style.display = 'flex';
}

// Apple Music sync button
function initAppleMusicSync() {
  const syncBtn = document.getElementById('apple-music-sync-btn');
  if (!syncBtn) return;

  syncBtn.addEventListener('click', async () => {
    showSpinner('Syncing with Apple Music...');
    try {
      const result = await apiFetch('/api/sync/apple-music', {
        method: 'POST',
        body: JSON.stringify({
          track_ids: Array.from(window.selectedTracks.size > 0 ? window.selectedTracks : window.tracks.map(t => t.file_path))
        })
      });
      showToast(result.message || 'Apple Music sync completed', 'success');
    } catch (error) {
      showToast('Apple Music sync failed', 'error');
    } finally {
      hideSpinner();
    }
  });
}

// Enhanced Settings tab with AI model selection
function updateSettingsSaveHandler() {
  const saveBtn = document.getElementById('settings-save-btn');
  if (!saveBtn) return;

  saveBtn.removeEventListener('click', saveSettings);
  saveBtn.addEventListener('click', saveSettingsRound2);
}

async function saveSettingsRound2() {
  try {
    const aiModel = document.getElementById('settings-ai-model')?.value || 'claude';
    const anthropicKey = document.getElementById('settings-anthropic-key')?.value.trim() || '';
    const ollamaModel = document.getElementById('settings-ollama-model')?.value.trim() || '';
    const batchSize = parseInt(document.getElementById('settings-batch-size')?.value) || 5;
    const autoApproveThreshold = parseInt(document.getElementById('settings-auto-approve')?.value) || 80;
    const geminiKey = document.getElementById('settings-gemini-key')?.value.trim() || '';
    const openrouterKey = document.getElementById('settings-openrouter-key')?.value.trim() || '';
    const spotifyId = document.getElementById('settings-spotify-id')?.value.trim() || '';
    const spotifySecret = document.getElementById('settings-spotify-secret')?.value.trim() || '';

    const payload = {
      ai_model: aiModel,
      classify_batch_size: batchSize,
      auto_approve_threshold: autoApproveThreshold,
    };

    if (anthropicKey) payload.anthropic_api_key = anthropicKey;
    if (ollamaModel) payload.ollama_model = ollamaModel;
    if (geminiKey) payload.gemini_api_key = geminiKey;
    if (openrouterKey) payload.openrouter_api_key = openrouterKey;
    if (spotifyId) payload.spotify_client_id = spotifyId;
    if (spotifySecret) payload.spotify_client_secret = spotifySecret;

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
      // Flash the save button green to confirm
      const saveBtn = document.getElementById('settings-save-btn');
      if (saveBtn) {
        const orig = saveBtn.textContent;
        saveBtn.textContent = '✓ Saved';
        saveBtn.style.background = '#22c55e';
        setTimeout(() => {
          saveBtn.textContent = orig;
          saveBtn.style.background = '';
        }, 2000);
      }
      // Clear sensitive inputs — loadSettings will populate placeholders with masked values
      await loadSettings();
    }
  } catch (error) {
    // Error already shown in apiFetch
  } finally {
    hideSpinner();
  }
}

// Export functionality (CSV, JSON, Rekordbox)
function initExportFeature() {
  const exportBtn = document.getElementById('export-menu-item');
  if (!exportBtn) return;

  exportBtn.addEventListener('click', () => {
    const modal = document.getElementById('export-format-modal');
    if (modal) modal.style.display = 'flex';
  });

  document.addEventListener('click', (e) => {
    if (e.target.id === 'export-csv-btn') {
      exportTracks('csv');
    }
    if (e.target.id === 'export-json-btn') {
      exportTracks('json');
    }
    if (e.target.id === 'export-rekordbox-btn') {
      exportTracks('rekordbox');
    }
  });
}

function exportTracks(format) {
  const tracks = window.selectedTracks.size > 0
    ? Array.from(window.selectedTracks).map(fp => window.tracks.find(t => t.file_path === fp))
    : window.tracks;

  let data, filename, mime;

  if (format === 'csv') {
    const headers = ['Title', 'Artist', 'Genre', 'Comments', 'BPM', 'Key', 'Year', 'File Path'];
    const rows = tracks.map(t => [
      t.display_title || '',
      t.display_artist || '',
      t.final_genre || '',
      t.final_subgenre || '',
      t.final_bpm || '',
      t.final_key || '',
      t.final_year || '',
      t.file_path || '',
    ]);
    data = [headers, ...rows].map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
    filename = 'idlm-export.csv';
    mime = 'text/csv';
  } else if (format === 'json') {
    data = JSON.stringify(tracks.map(t => ({
      title: t.display_title,
      artist: t.display_artist,
      genre: t.final_genre,
      subGenre: t.final_subgenre,
      bpm: t.final_bpm,
      key: t.final_key,
      year: t.final_year,
      filePath: t.file_path,
    })), null, 2);
    filename = 'idlm-export.json';
    mime = 'application/json';
  } else if (format === 'rekordbox') {
    // Rekordbox XML format
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PLAYLIST Name="IDJLM Export" Type="1">
    <PLAYLIST_TRACKS>
      ${tracks.map((t, idx) => `
      <TRACK TrackID="${idx + 1}">
        <NAME>${escapeHtml(t.display_title || '')}</NAME>
        <ARTIST>${escapeHtml(t.display_artist || '')}</ARTIST>
        <ALBUM>${escapeHtml(t.album || '')}</ALBUM>
        <YEAR>${t.final_year || ''}</YEAR>
        <BPM>${t.final_bpm || ''}</BPM>
        <GENRE>${escapeHtml(t.final_genre || '')}</GENRE>
        <COMMENTS>${escapeHtml(t.final_subgenre || '')}</COMMENTS>
      </TRACK>
      `).join('')}
    </PLAYLIST_TRACKS>
  </PLAYLIST>
</DJ_PLAYLISTS>`;
    data = xml;
    filename = 'idlm-export.xml';
    mime = 'application/xml';
  }

  const blob = new Blob([data], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  showToast(`Exported ${tracks.length} tracks as ${format.toUpperCase()}`, 'success');
}

// ============================================================================
// Bulk Edit Handler
// ============================================================================

async function handleBulkEdit() {
  const genreInput = document.getElementById('bulk-genre')?.value.trim();
  const subgenreInput = document.getElementById('bulk-subgenre')?.value.trim();
  const bpmInput = document.getElementById('bulk-bpm')?.value.trim();
  const yearInput = document.getElementById('bulk-year')?.value.trim();

  if (!genreInput && !subgenreInput && !bpmInput && !yearInput) {
    showToast('Please enter at least one field to update', 'info');
    return;
  }

  const payload = {
    track_paths: Array.from(window.selectedTracks),
  };

  if (genreInput) payload.genre = genreInput;
  if (subgenreInput) payload.subgenre = subgenreInput;
  if (bpmInput) payload.bpm = parseInt(bpmInput);
  if (yearInput) payload.year = parseInt(yearInput);

  showSpinner('Updating tracks...');
  try {
    const result = await apiFetch('/api/review/bulk-edit', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (result.updated) {
      showToast(`Updated ${result.updated} tracks`, 'success');
      window.selectedTracks.clear();
      updateBulkActionsBar();
      document.getElementById('bulk-edit-modal').style.display = 'none';
      // Reload tracks to reflect changes
      apiFetch('/api/tracks').then(data => {
        window.tracks = data.tracks || [];
        renderTracks();
      });
    }
  } catch (error) {
    showToast('Bulk edit failed', 'error');
  } finally {
    hideSpinner();
  }
}

// ============================================================================
// Initialization
// ============================================================================

// ─── Threshold localStorage persistence ───────────────────────────────────────
function initThresholdPersistence() {
  const input = document.getElementById('toolbar-threshold');
  if (!input) return;
  const saved = localStorage.getItem('idjlm-threshold');
  if (saved) input.value = saved;
  input.addEventListener('change', () => {
    localStorage.setItem('idjlm-threshold', input.value);
  });
  // Stop click on input from firing the parent button
  input.addEventListener('click', e => e.stopPropagation());
}

// ─── Keyboard shortcuts for track table ──────────────────────────────────────
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

function initOnboarding() {
  if (localStorage.getItem('idjlm-onboarded')) return;
  document.getElementById('onboarding-modal').style.display = 'flex';
  document.getElementById('onboarding-close').addEventListener('click', () => {
    document.getElementById('onboarding-modal').style.display = 'none';
    localStorage.setItem('idjlm-onboarded', '1');
  });
}

function saveSetlistToStorage() {
  localStorage.setItem('idjlm-setlist', JSON.stringify(window.setlist || []));
}

function loadSetlistFromStorage() {
  try {
    const saved = localStorage.getItem('idjlm-setlist');
    if (saved) window.setlist = JSON.parse(saved);
  } catch(e) {
    window.setlist = [];
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initLibraryToolbar();
  initTheme();
  initThemeSwatches();
  initNavigation();
  initEditModal();
  initAudioPlayer();
  initColumnToggle();
  initBulkSelectFeature();
  initSearchFeature();
  initSettingsTab();
  startStatsPolling();
  loadTaxonomy();
  loadSetlistFromStorage();
  initSetlistTab();
  renderTracks();
  renderSetlist();
  checkResumeSession();
  initThresholdPersistence();
  initOnboarding();
});

// ============================================================================
// Feature 1: Audio Player Bottom Bar
// ============================================================================

let currentPlayingTrack = null;
let currentTrackIndex = -1;

function initAudioPlayer() {
  const bar = document.getElementById('audio-player-bar');
  const audio = document.getElementById('audio-player');
  const playPauseBtn = document.getElementById('audio-play-pause');
  const prevBtn = document.getElementById('audio-prev');
  const nextBtn = document.getElementById('audio-next');
  const seekBar = document.getElementById('audio-seek');
  const timeDisplay = document.getElementById('audio-time');

  audio.addEventListener('timeupdate', () => {
    const duration = audio.duration || 0;
    const current = audio.currentTime || 0;
    seekBar.value = duration > 0 ? (current / duration) * 100 : 0;
    timeDisplay.textContent = formatTime(current) + ' / ' + formatTime(duration);
  });

  audio.addEventListener('ended', () => {
    playPauseBtn.textContent = '▶';
    nextBtn.click();
  });

  playPauseBtn.addEventListener('click', () => {
    if (audio.paused) {
      audio.play();
      playPauseBtn.textContent = '⏸';
    } else {
      audio.pause();
      playPauseBtn.textContent = '▶';
    }
  });

  prevBtn.addEventListener('click', () => {
    if (currentTrackIndex > 0) {
      currentTrackIndex--;
      playTrack(window.tracks[currentTrackIndex]);
    }
  });

  nextBtn.addEventListener('click', () => {
    if (currentTrackIndex < window.tracks.length - 1) {
      currentTrackIndex++;
      playTrack(window.tracks[currentTrackIndex]);
    }
  });

  seekBar.addEventListener('change', () => {
    const duration = audio.duration || 0;
    audio.currentTime = (seekBar.value / 100) * duration;
  });
}

function playTrack(track) {
  if (!track) return;

  const audio = document.getElementById('audio-player');
  const bar = document.getElementById('audio-player-bar');
  const playPauseBtn = document.getElementById('audio-play-pause');

  currentPlayingTrack = track;
  currentTrackIndex = window.tracks.indexOf(track);

  audio.src = `/api/audio?path=${encodeURIComponent(track.file_path)}`;
  document.getElementById('audio-track-title').textContent = track.display_title || 'Unknown';
  document.getElementById('audio-track-artist').textContent = track.display_artist || 'Unknown';

  bar.classList.remove('hidden');
  audio.load();

  audio.addEventListener('canplay', function onCanPlay() {
    audio.removeEventListener('canplay', onCanPlay);
    audio.play().catch(err => {
      showToast('Could not play audio', 'error');
      console.error('Audio error:', err);
      if (playPauseBtn) playPauseBtn.textContent = '▶';
    });
  }, { once: true });

  audio.addEventListener('error', function onAudioError() {
    audio.removeEventListener('error', onAudioError);
    showToast('Could not load audio — check file format', 'error');
    bar.classList.add('hidden');
  }, { once: true });
  playPauseBtn.textContent = '⏸';
}

function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

// ============================================================================
// Feature 2: Confidence Badges & Energy Bars
// ============================================================================

function confidenceBadge(score) {
  if (!score && score !== 0) return '—';
  const cls = score >= 80 ? 'high' : score >= 50 ? 'mid' : 'low';
  return `<span class="confidence-badge confidence-${cls}">${Math.round(score)}%</span>`;
}

function energyBar(energy) {
  if (!energy && energy !== 0) return '—';
  const pct = (energy / 10) * 100;
  const color = energy >= 8 ? '#f87171' : energy >= 5 ? '#fbbf24' : '#34d399';
  return `<div class="energy-bar-wrap"><div class="energy-bar" style="width:${pct}%;background:${color}"></div><span>${energy.toFixed(1)}</span></div>`;
}

// ============================================================================
// Feature 3: Genre Color Chips
// ============================================================================

const GENRE_COLORS = ['#8b5cf6','#06b6d4','#f59e0b','#10b981','#ef4444','#ec4899','#6366f1','#14b8a6'];

function genreChip(genre) {
  if (!genre) return '—';
  const hash = [...genre].reduce((a,c)=>a+c.charCodeAt(0),0);
  const color = GENRE_COLORS[hash % GENRE_COLORS.length];
  return `<span class="genre-chip" style="background:${color}22;color:${color};border:1px solid ${color}44">${escapeHtml(genre)}</span>`;
}

// ============================================================================
// Feature 4: Column Toggle
// ============================================================================

function initColumnToggle() {
  // Load saved column state from localStorage
  const saved = localStorage.getItem('idlm-column-toggle');
  window.columnVisibility = saved ? JSON.parse(saved) : {
    bpm: true,
    key: true,
    energy: true,
    genre: true,
    subgenre: true,
    confidence: true,
    year: true
  };
}

function getColumnToggleMenu() {
  const menu = document.createElement('div');
  menu.className = 'column-toggle-menu';

  const columns = [
    { key: 'genre', label: 'Genre' },
    { key: 'subgenre', label: 'Comments' },
    { key: 'bpm', label: 'BPM' },
    { key: 'key', label: 'Key' },
    { key: 'energy', label: 'Energy' },
    { key: 'confidence', label: 'Confidence' },
    { key: 'year', label: 'Year' }
  ];

  columns.forEach(col => {
    const item = document.createElement('label');
    item.className = 'column-toggle-item';
    const checked = window.columnVisibility[col.key];
    item.innerHTML = `<input type="checkbox" ${checked ? 'checked' : ''} data-column="${col.key}"> ${col.label}`;
    item.querySelector('input').addEventListener('change', (e) => {
      window.columnVisibility[col.key] = e.target.checked;
      localStorage.setItem('idlm-column-toggle', JSON.stringify(window.columnVisibility));
      renderTracks();
    });
    menu.appendChild(item);
  });

  return menu;
}

// ============================================================================
// Feature 5: Status Indicators
// ============================================================================

function statusDot(status) {
  const statusMap = {
    'pending': 'pending',
    'analyzed': 'analyzed',
    'classified': 'classified',
    'approved': 'approved',
    'error': 'error'
  };
  const cls = statusMap[status] || 'pending';
  return `<span class="status-dot status-${cls}" title="${status}"></span>`;
}

// ============================================================================
// Feature 6: Camelot Wheel Tab
// ============================================================================

function initWheelTab() {
  const wheelBtn = document.querySelector('[data-tab="wheel"]');
  if (wheelBtn) {
    wheelBtn.addEventListener('click', renderCamelotWheel);
  }
}

function renderCamelotWheel() {
  const svg = document.getElementById('camelot-wheel-svg');
  const stats = document.getElementById('wheel-stats');

  svg.innerHTML = '';

  // Camelot wheel: 12 positions, 2 per position (A=minor, B=major)
  const positions = [];
  for (let i = 1; i <= 12; i++) {
    positions.push({ num: i, key: `${i}A`, mode: 'minor' });
    positions.push({ num: i, key: `${i}B`, mode: 'major' });
  }

  const centerX = 225, centerY = 225, outerR = 200, innerR = 140;
  const segmentAngle = 360 / 24;

  // Draw segments
  positions.forEach((pos, idx) => {
    const startAngle = idx * segmentAngle - 90;
    const endAngle = (idx + 1) * segmentAngle - 90;

    const isMinor = pos.mode === 'minor';
    const startRad = (startAngle * Math.PI) / 180;
    const endRad = (endAngle * Math.PI) / 180;

    const r1 = isMinor ? innerR : innerR + (outerR - innerR) / 2;
    const r2 = isMinor ? innerR + (outerR - innerR) / 2 : outerR;

    const x1 = centerX + r1 * Math.cos(startRad);
    const y1 = centerY + r1 * Math.sin(startRad);
    const x2 = centerX + r2 * Math.cos(startRad);
    const y2 = centerY + r2 * Math.sin(startRad);
    const x3 = centerX + r2 * Math.cos(endRad);
    const y3 = centerY + r2 * Math.sin(endRad);
    const x4 = centerX + r1 * Math.cos(endRad);
    const y4 = centerY + r1 * Math.sin(endRad);

    const color = isMinor ? 'rgba(96,165,250,0.3)' : 'rgba(139,92,246,0.3)';
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.style.cursor = 'pointer';

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const d = `M ${x1} ${y1} L ${x2} ${y2} A ${r2} ${r2} 0 0 1 ${x3} ${y3} L ${x4} ${y4} A ${r1} ${r1} 0 0 0 ${x1} ${y1} Z`;
    path.setAttribute('d', d);
    path.setAttribute('fill', color);
    path.setAttribute('stroke', isMinor ? '#60a5fa' : '#8b5cf6');
    path.setAttribute('stroke-width', '0.5');

    g.appendChild(path);

    // Label
    const midAngle = ((startAngle + endAngle) / 2 * Math.PI) / 180;
    const labelR = (r1 + r2) / 2;
    const lx = centerX + labelR * Math.cos(midAngle);
    const ly = centerY + labelR * Math.sin(midAngle);

    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', lx);
    text.setAttribute('y', ly);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('font-size', '10');
    text.setAttribute('font-weight', '600');
    text.setAttribute('fill', isMinor ? '#60a5fa' : '#8b5cf6');
    text.textContent = pos.key;

    g.appendChild(text);

    // Click to filter
    g.addEventListener('click', () => {
      const filtered = window.tracks.filter(t => t.final_key === pos.key);
      showToast(`Found ${filtered.length} tracks in key ${pos.key}`, 'info');
    });

    svg.appendChild(g);
  });

  // Center circle
  const center = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  center.setAttribute('cx', centerX);
  center.setAttribute('cy', centerY);
  center.setAttribute('r', 30);
  center.setAttribute('fill', 'var(--bg-panel)');
  center.setAttribute('stroke', 'var(--border)');
  svg.appendChild(center);

  // Render stats
  const keyCounts = {};
  window.tracks.forEach(t => {
    if (t.final_key) {
      keyCounts[t.final_key] = (keyCounts[t.final_key] || 0) + 1;
    }
  });

  const sorted = Object.entries(keyCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12);

  stats.innerHTML = '<div class="wheel-stats-section"><h3>Top Keys</h3>' +
    '<div>' + sorted.map(([key, count]) =>
      `<div class="wheel-key-item"><span>${key}</span><span>${count}</span></div>`
    ).join('') + '</div></div>';
}

// ============================================================================
// Feature 7: Keyboard Shortcuts (Review Tab)
// ============================================================================

function initKeyboardShortcuts() {
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
    } else if (e.key === 'a') {
      e.preventDefault();
      const btn = document.querySelector('.review-item:first-child [data-approve-btn]');
      if (btn) btn.click();
    } else if (e.key === 's') {
      e.preventDefault();
      const btn = document.querySelector('.review-item:first-child [data-skip-btn]');
      if (btn) btn.click();
    } else if (e.code === 'Space') {
      e.preventDefault();
      document.getElementById('audio-play-pause').click();
    }
  });
}

// ============================================================================
// Feature 8: Duplicates Tab
// ============================================================================

function initDuplicatesTab() {
  const scanBtn = document.getElementById('btn-scan-duplicates');
  if (scanBtn) {
    scanBtn.addEventListener('click', scanForDuplicates);
  }
}

// ============================================================================
// Organise Tab Init (called lazily from switchTab on first visit)
// ============================================================================

let organiseTabInited = false;
function initOrganiseTab() {
  if (organiseTabInited) return;
  organiseTabInited = true;

  document.getElementById('btn-refresh-health')?.addEventListener('click', loadLibraryHealth);
  document.getElementById('btn-parse-filenames')?.addEventListener('click', parseFilenames);
  document.getElementById('btn-organise-preview')?.addEventListener('click', previewOrganise);
  document.getElementById('btn-organise-run')?.addEventListener('click', runOrganise);
  document.getElementById('btn-validate-keys')?.addEventListener('click', validateKeys);
  initDuplicatesTab();
  loadLibraryHealth();
}

// ============================================================================
// Set Planner Tab Init (called lazily from switchTab on first visit)
// ============================================================================

let setplanTabInited = false;
function initSetPlanTab() {
  if (setplanTabInited) return;
  setplanTabInited = true;

  document.getElementById('btn-generate-set')?.addEventListener('click', generateSet);

  // Populate genre filter from taxonomy
  const genreSelect = document.getElementById('setplan-genre');
  if (genreSelect && window.taxonomy) {
    Object.keys(window.taxonomy).forEach(genre => {
      const opt = document.createElement('option');
      opt.value = genre;
      opt.textContent = genre;
      genreSelect.appendChild(opt);
    });
  }

  loadSetplanArcs();
}

async function scanForDuplicates() {
  showSpinner('Scanning for duplicates...');
  try {
    const result = await apiFetch('/api/duplicates/scan', { method: 'POST' });
    renderDuplicates(result.duplicates || []);

    // Update badge
    const duplicatesBtn = document.querySelector('[data-tab="duplicates"]');
    if (result.duplicates && result.duplicates.length > 0) {
      let badge = duplicatesBtn.querySelector('.nav-badge');
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'nav-badge';
        duplicatesBtn.appendChild(badge);
      }
      badge.textContent = result.duplicates.length;
    }

    showToast(`Found ${result.duplicates ? result.duplicates.length : 0} duplicate pairs`, 'info');
  } catch (error) {
    showToast('Error scanning for duplicates', 'error');
  } finally {
    hideSpinner();
  }
}

function renderDuplicates(duplicates) {
  const container = document.getElementById('duplicates-results');
  container.innerHTML = '';

  if (!duplicates || duplicates.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'No duplicates found. Click "Scan for Duplicates" to begin.';
    container.appendChild(empty);
    return;
  }

  duplicates.forEach((pair, idx) => {
    const div = document.createElement('div');
    div.className = 'duplicate-pair';
    div.innerHTML = `<h3>Duplicate Pair ${idx + 1}</h3>`;

    [pair.track1, pair.track2].forEach(track => {
      const trackDiv = document.createElement('div');
      trackDiv.className = 'duplicate-track';
      trackDiv.innerHTML = `
        <div class="duplicate-track-info">
          <div>
            <div class="duplicate-track-title">${escapeHtml(track.display_title || 'Unknown')}</div>
            <div class="duplicate-track-meta">${escapeHtml(track.display_artist || 'Unknown')} — ${escapeHtml(track.file_path)}</div>
          </div>
          <button class="btn btn-secondary duplicate-remove-btn" data-path="${encodeURIComponent(track.file_path)}">Remove</button>
        </div>
      `;

      trackDiv.querySelector('.duplicate-remove-btn').addEventListener('click', async (e) => {
        const path = decodeURIComponent(e.target.dataset.path);
        await removeDuplicate(path);
      });

      div.appendChild(trackDiv);
    });

    container.appendChild(div);
  });
}

async function removeDuplicate(filePath) {
  showSpinner('Removing duplicate...');
  try {
    await apiFetch('/api/duplicates/remove', {
      method: 'POST',
      body: JSON.stringify({ file_path: filePath })
    });

    window.tracks = window.tracks.filter(t => t.file_path !== filePath);
    renderTracks();
    showToast('Track removed from library', 'success');

    // Rescan to refresh UI
    await scanForDuplicates();
  } catch (error) {
    showToast('Error removing duplicate', 'error');
  } finally {
    hideSpinner();
  }
}

// ============================================================================
// Feature 9: Organise Tab
// ============================================================================

async function loadLibraryHealth() {
  try {
    const res = await apiFetch('/api/library/health');
    document.getElementById('health-total').textContent = res.total;
    document.getElementById('health-analyzed').textContent = res.analyzed;
    document.getElementById('health-classified').textContent = res.classified;
    document.getElementById('health-approved').textContent = res.approved;
    document.getElementById('health-written').textContent = res.tags_written;
    document.getElementById('health-duplicates').textContent = res.duplicates;

    // Coverage bars
    const covEl = document.getElementById('health-coverage');
    const fields = [
      ['BPM', res.coverage.bpm],
      ['Key', res.coverage.key],
      ['Energy', res.coverage.energy],
      ['Artwork', res.coverage.artwork],
    ];
    covEl.innerHTML = fields.map(([label, val]) => {
      const pct = Math.round((val || 0) * 100);
      const color = pct >= 80 ? 'var(--accent)' : pct >= 50 ? '#f0a500' : 'var(--danger)';
      return `<div style="margin-bottom:0.5rem;">
        <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
          <span style="font-size:0.8rem;color:var(--text-muted)">${label}</span>
          <span style="font-size:0.8rem;color:var(--text-muted)">${pct}%</span>
        </div>
        <div style="height:6px;background:var(--border);border-radius:3px;">
          <div style="height:100%;width:${pct}%;background:${color};border-radius:3px;transition:width 0.3s;"></div>
        </div>
      </div>`;
    }).join('');

    // Genre breakdown
    const genreEl = document.getElementById('health-by-genre');
    if (res.by_genre && Object.keys(res.by_genre).length) {
      const sorted = Object.entries(res.by_genre).sort((a,b) => b[1]-a[1]);
      genreEl.innerHTML = `<div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.5rem;">By Genre</div>`
        + sorted.map(([g, n]) => `<span class="badge" style="margin:2px;">${g} <strong>${n}</strong></span>`).join('');
    }
  } catch(e) {
    console.error('Health load failed', e);
  }
}

async function parseFilenames() {
  const btn = document.getElementById('btn-parse-filenames');
  btn.disabled = true; btn.textContent = 'Scanning...';
  try {
    const res = await apiFetch('/api/organise/parse-filenames', {
      method: 'POST',
      body: JSON.stringify({all: true})
    });
    const data = res;
    const el = document.getElementById('filename-parse-results');
    if (!data.length) {
      el.innerHTML = '<p style="color:var(--text-muted)">No parseable filenames found (all tracks already have tags, or filenames don\'t match "Artist - Title" pattern).</p>';
      return;
    }
    const conflicting = data.filter(t => t.has_conflict);
    const noTag = data.filter(t => !t.has_conflict);
    let html = `<p style="margin-bottom:0.5rem;">${data.length} tracks with parseable filenames (${conflicting.length} conflicts, ${noTag.length} no existing tags).</p>`;
    html += `<table class="data-table" style="font-size:0.8rem;">
      <thead><tr><th>File</th><th>Parsed Artist</th><th>Parsed Title</th><th>Current Artist</th><th>Current Title</th><th></th></tr></thead>
      <tbody>`;
    data.forEach(t => {
      const rowStyle = t.has_conflict ? 'background:rgba(240,80,80,0.05);' : '';
      html += `<tr style="${rowStyle}">
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${t.filename}">${t.filename}</td>
        <td>${t.parsed_artist || '—'}</td>
        <td>${t.parsed_title || '—'}</td>
        <td>${t.current_artist || '—'}</td>
        <td>${t.current_title || '—'}</td>
        <td><button class="btn btn-sm btn-primary" onclick="applyFilenameTag('${encodeURIComponent(t.file_path)}','${encodeURIComponent(t.parsed_artist||'')}','${encodeURIComponent(t.parsed_title||'')}', this)">Apply</button></td>
      </tr>`;
    });
    html += `</tbody></table>`;
    html += `<div style="margin-top:0.75rem;"><button class="btn btn-primary" onclick="applyAllFilenameTags(${JSON.stringify(data)})">Apply All</button></div>`;
    el.innerHTML = html;
  } finally {
    btn.disabled = false; btn.textContent = 'Scan All Tracks';
  }
}

async function applyFilenameTag(encodedPath, encodedArtist, encodedTitle, btn) {
  btn.disabled = true;
  const path = decodeURIComponent(encodedPath);
  const artist = decodeURIComponent(encodedArtist);
  const title = decodeURIComponent(encodedTitle);
  await apiFetch('/api/organise/apply-filename-tags', {
    method: 'POST',
    body: JSON.stringify({updates: [{file_path: path, artist, title}]})
  });
  btn.textContent = '✓'; btn.style.background = 'var(--accent)';
}

async function applyAllFilenameTags(tracks) {
  const updates = tracks.filter(t => t.parsed_artist || t.parsed_title).map(t => ({
    file_path: t.file_path, artist: t.parsed_artist || t.current_artist, title: t.parsed_title || t.current_title
  }));
  const res = await apiFetch('/api/organise/apply-filename-tags', {
    method: 'POST',
    body: JSON.stringify({updates})
  });
  const d = res;
  alert(`Applied tags to ${d.updated} tracks. They are now set to "pending" for review.`);
}

async function previewOrganise() {
  const dest = document.getElementById('organise-dest').value.trim();
  if (!dest) { alert('Enter a destination folder first.'); return; }
  const pattern = document.getElementById('organise-pattern').value;
  const res = await apiFetch('/api/organise/folders', {
    method: 'POST',
    body: JSON.stringify({destination: dest, pattern, dry_run: true})
  });
  const d = res;
  const el = document.getElementById('organise-preview-results');
  if (d.error) { el.innerHTML = `<p style="color:var(--danger)">${d.error}</p>`; return; }
  const moves = d.moves || [];
  if (!moves.length) { el.innerHTML = '<p style="color:var(--text-muted)">No approved tracks to move.</p>'; return; }
  const overwrite = moves.filter(m => m.would_overwrite).length;
  el.innerHTML = `<p style="margin-bottom:0.5rem;">${moves.length} files to move${overwrite ? ` (${overwrite} would overwrite)` : ''}.</p>
    <div style="max-height:200px;overflow-y:auto;font-size:0.75rem;background:var(--bg-secondary);padding:0.75rem;border-radius:6px;">
      ${moves.slice(0, 50).map(m => `<div>${m.from.split('/').pop()} → <strong>${m.to.split('/').slice(-3).join('/')}</strong>${m.would_overwrite ? ' ⚠️' : ''}</div>`).join('')}
      ${moves.length > 50 ? `<div style="color:var(--text-muted)">... and ${moves.length - 50} more</div>` : ''}
    </div>`;
  document.getElementById('btn-organise-run').disabled = false;
  document.getElementById('btn-organise-run')._previewData = {dest, pattern};
}

async function runOrganise() {
  const previewData = document.getElementById('btn-organise-run')._previewData;
  if (!previewData) { showToast('Run a preview first', 'warning'); return; }
  if (!confirm(`This will physically move files. Continue?`)) return;
  const {dest, pattern} = previewData;
  const btn = document.getElementById('btn-organise-run');
  btn.disabled = true; btn.textContent = 'Moving...';
  const res = await apiFetch('/api/organise/folders', {
    method: 'POST',
    body: JSON.stringify({destination: dest, pattern, dry_run: false})
  });
  const d = res;
  if (d.error) { alert(d.error); }
  else { alert(`Moved ${d.moved} files successfully${d.errors?.length ? ` (${d.errors.length} errors)` : ''}.`); }
  btn.textContent = 'Move Files';
}

async function validateKeys() {
  const btn = document.getElementById('btn-validate-keys');
  btn.disabled = true; btn.textContent = 'Checking...';
  try {
    const res = await apiFetch('/api/validate/keys');
    const d = res;
    const el = document.getElementById('key-validation-results');
    if (d.error) { el.innerHTML = `<p style="color:var(--danger)">${d.error}</p>`; return; }
    if (!d.mismatches?.length) {
      el.innerHTML = `<p style="color:var(--accent)">✓ All ${d.total_checked} keys match (within 1 Camelot step). No corrections needed.</p>`;
      return;
    }
    let html = `<p style="margin-bottom:0.5rem;">${d.mismatch_count} mismatches out of ${d.total_checked} tracks checked.</p>
      <table class="data-table" style="font-size:0.8rem;">
        <thead><tr><th>Title</th><th>Artist</th><th>Stored Key</th><th>Detected Key</th><th>Distance</th><th></th></tr></thead>
        <tbody>`;
    d.mismatches.forEach(m => {
      html += `<tr>
        <td>${m.title || '—'}</td><td>${m.artist || '—'}</td>
        <td><span class="badge">${m.stored_key}</span></td>
        <td><span class="badge" style="background:var(--accent);">${m.analyzed_key}</span></td>
        <td>${m.distance}</td>
        <td><button class="btn btn-sm btn-primary" onclick="fixKey('${encodeURIComponent(m.file_path)}', this)">Use Detected</button></td>
      </tr>`;
    });
    html += `</tbody></table>
      <div style="margin-top:0.75rem;">
        <button class="btn btn-primary" onclick="fixAllKeys(${JSON.stringify(d.mismatches.map(m=>m.file_path))})">Fix All (${d.mismatch_count})</button>
      </div>`;
    el.innerHTML = html;
  } finally {
    btn.disabled = false; btn.textContent = 'Check Keys';
  }
}

async function fixKey(encodedPath, btn) {
  btn.disabled = true;
  await apiFetch('/api/validate/keys/fix', {
    method: 'POST',
    body: JSON.stringify({paths: [decodeURIComponent(encodedPath)], use_analyzed: true})
  });
  btn.textContent = '✓'; btn.style.background = 'var(--accent)';
}

async function fixAllKeys(paths) {
  const res = await apiFetch('/api/validate/keys/fix', {
    method: 'POST',
    body: JSON.stringify({paths, use_analyzed: true})
  });
  const d = res;
  alert(`Fixed ${d.fixed} key mismatches.`);
  validateKeys();
}

// ============================================================================
// Feature 9: Smart Playlist Builder
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
