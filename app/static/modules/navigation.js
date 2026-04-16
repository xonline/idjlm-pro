
function switchTab(tabName) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

  const tab = document.getElementById('tab-' + tabName);
  if (tab) tab.classList.add('active');

  const btn = document.querySelector('.nav-btn[data-tab="' + tabName + '"]');
  if (btn) btn.classList.add('active');

  if (tabName === 'organise') initOrganiseTab();
  if (tabName === 'setplan') initSetPlanTab();
  if (tabName === 'playlists') initPlaylistsTab();
  if (tabName === 'settings') initSettingsTab();
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

  // Track detail panel buttons
  const detailAddSetlist = document.getElementById('btn-track-detail-add-setlist');
  if (detailAddSetlist) {
    detailAddSetlist.addEventListener('click', function() {
      if (window._currentDetailTrack) {
        addTrackToSetlist(window._currentDetailTrack.file_path);
      }
    });
  }
  const detailEditBtn = document.getElementById('btn-track-detail-edit');
  if (detailEditBtn) {
    detailEditBtn.addEventListener('click', function() {
      if (window._currentDetailTrack) {
        closeTrackDetail();
        openEditModal(window._currentDetailTrack.file_path);
      }
    });
  }

  // ESC key closes track detail panel
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      const panel = document.getElementById('track-detail-panel');
      if (panel && panel.style.display === 'block') {
        closeTrackDetail();
      }
    }
  });
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

