// ============================================================================
// duplicates.js — Duplicates tab v2 (side-by-side compare cards + batch resolve)
// ============================================================================
// Phase 4.4: replace list UI with side-by-side compare cards showing bitrate,
// sample rate, file size, tag completeness, and mini-waveform. Pre-select the
// best-quality copy by heuristic. Batch-resolve selected groups.
// ----------------------------------------------------------------------------

function initDuplicatesTab() {
  const scanBtn = document.getElementById('btn-scan-duplicates');
  if (scanBtn) {
    scanBtn.addEventListener('click', scanForDuplicates);
  }
}

async function scanForDuplicates() {
  showSpinner('Scanning for duplicates...');
  try {
    const result = await apiFetch('/api/duplicates/scan', { method: 'POST' });
    renderDuplicates(result.duplicates || []);

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

    showToast(`Found ${result.duplicates ? result.duplicates.length : 0} duplicate groups`, 'info');
  } catch (error) {
    showToast('Error scanning for duplicates', 'error');
  } finally {
    hideSpinner();
  }
}

function _pickBestTrack(tracks) {
  if (!tracks || tracks.length <= 1) return 0;
  var scored = tracks.map(function(t, i) {
    var ai = t.audio_info || {};
    var tc = t.tag_completeness || {};
    var bitrate = ai.bitrate || 0;
    var tagPct = tc.overall_pct || 0;
    var mtime = ai.mtime || 0;
    return { idx: i, bitrate: bitrate, tagPct: tagPct, mtime: mtime };
  });
  scored.sort(function(a, b) {
    if (b.bitrate !== a.bitrate) return b.bitrate - a.bitrate;
    if (b.tagPct !== a.tagPct) return b.tagPct - a.tagPct;
    return b.mtime - a.mtime;
  });
  return scored[0].idx;
}

function _formatSize(bytes) {
  if (!bytes) return '—';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function _formatBitrate(br) {
  if (!br) return '—';
  if (br >= 1000) return (br / 1000).toFixed(0) + ' kbps';
  return br + ' bps';
}

function _drawMiniWaveform(canvas, waveformData) {
  if (window.renderMiniWaveform) {
    window.renderMiniWaveform(canvas, waveformData);
  }
}

function renderDuplicates(duplicates) {
  var container = document.getElementById('duplicates-results');
  container.innerHTML = '';

  if (!duplicates || duplicates.length === 0) {
    var empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.innerHTML = '<div class="empty-state-content"><div class="empty-icon">&#128269;</div><div class="empty-msg">No duplicates found</div><div class="empty-submsg">Click "Scan for Duplicates" to begin</div></div>';
    container.appendChild(empty);
    return;
  }

  // Batch-resolve toolbar
  var toolbar = document.createElement('div');
  toolbar.className = 'dup-batch-toolbar';
  toolbar.innerHTML = '<span class="dup-batch-label">Select groups to batch-resolve:</span>' +
    '<button class="btn btn-primary btn-sm" id="btn-batch-resolve">Batch Resolve Selected</button>' +
    '<button class="btn btn-secondary btn-sm" id="btn-select-all">Select All</button>';
  container.appendChild(toolbar);

  var storedData = [];

  duplicates.forEach(function(group, gIdx) {
    var tracks = group.tracks || [];
    var bestIdx = _pickBestTrack(tracks);
    storedData.push({ group: group, bestIdx: bestIdx, selectedKeep: bestIdx });

    var card = document.createElement('div');
    card.className = 'compare-card';
    card.dataset.groupIdx = gIdx;

    // Group header
    var header = document.createElement('div');
    header.className = 'compare-card-header';
    var groupLabel = group.group_label || '';
    var reasonLabels = { same_audio_content: 'Identical Audio', same_metadata: 'Same Artist + Title', fuzzy_filename: 'Similar Filename' };
    var reason = reasonLabels[group.reason] || 'Possible Duplicate';
    header.innerHTML = '<span class="compare-card-title">Group ' + (gIdx + 1) +
      (groupLabel ? ': <em>' + escapeHtml(groupLabel) + '</em>' : '') +
      '</span>' +
      '<span class="compare-card-reason">' + reason + '</span>' +
      '<label class="compare-card-check"><input type="checkbox" class="dup-batch-check" data-group-idx="' + gIdx + '" checked> Resolve</label>';
    card.appendChild(header);

    // Track cards (side-by-side)
    var tracksRow = document.createElement('div');
    tracksRow.className = 'compare-tracks-row';

    tracks.forEach(function(track, tIdx) {
      var ai = track.audio_info || {};
      var tc = track.tag_completeness || {};
      var isBest = tIdx === bestIdx;

      var tCard = document.createElement('div');
      tCard.className = 'compare-track-card' + (isBest ? ' compare-track-best' : '');
      tCard.dataset.trackIdx = tIdx;

      var qualityBadge = '';
      if (isBest) {
        qualityBadge = '<span class="compare-quality-badge">Best</span>';
      }

      // Waveform canvas placeholder
      var wfData = track.waveform_data;
      var wfHtml = '';
      if (wfData && wfData.length) {
        wfHtml = '<canvas class="compare-waveform-canvas" width="240" height="40"></canvas>';
      } else {
        wfHtml = '<div class="compare-waveform-empty">No waveform</div>';
      }

      tCard.innerHTML =
        '<div class="compare-track-header">' +
          '<label class="compare-keep-label">' +
            '<input type="radio" name="dup-keep-group-' + gIdx + '" value="' + tIdx + '"' + (isBest ? ' checked' : '') + '>' +
            '<span class="compare-track-name">' + escapeHtml(track.display_title || 'Unknown') + qualityBadge + '</span>' +
          '</label>' +
        '</div>' +
        '<div class="compare-track-body">' +
          wfHtml +
          '<div class="compare-stats">' +
            '<div class="compare-stat"><span class="compare-stat-label">Artist</span><span class="compare-stat-val">' + escapeHtml(track.display_artist || 'Unknown') + '</span></div>' +
            '<div class="compare-stat"><span class="compare-stat-label">Bitrate</span><span class="compare-stat-val">' + _formatBitrate(ai.bitrate) + '</span></div>' +
            '<div class="compare-stat"><span class="compare-stat-label">Sample Rate</span><span class="compare-stat-val">' + (ai.sample_rate ? ai.sample_rate + ' Hz' : '—') + '</span></div>' +
            '<div class="compare-stat"><span class="compare-stat-label">File Size</span><span class="compare-stat-val">' + _formatSize(ai.file_size) + '</span></div>' +
            '<div class="compare-stat"><span class="compare-stat-label">Path</span><span class="compare-stat-val compare-path" title="' + escapeHtml(track.file_path) + '">' + escapeHtml(track.file_path.split('/').slice(-2).join('/') || track.file_path) + '</span></div>' +
          '</div>' +
          '<div class="compare-completeness">' +
            '<div class="compare-completeness-bar">' +
              '<div class="compare-completeness-fill compare-tags-fill" style="width:' + tc.tag_pct + '%"></div>' +
              '<div class="compare-completeness-fill compare-meta-fill" style="width:' + tc.metadata_pct + '%"></div>' +
            '</div>' +
            '<div class="compare-completeness-legend">' +
              '<span>Tags: ' + tc.tag_count + '/' + tc.tag_total + '</span>' +
              '<span>Meta: ' + tc.metadata_count + '/' + tc.metadata_total + '</span>' +
              '<span class="compare-completeness-pct">' + tc.overall_pct + '%</span>' +
            '</div>' +
          '</div>' +
        '</div>';

      // Radio change handler
      tCard.querySelector('input[type="radio"]').addEventListener('change', function() {
        storedData[gIdx].selectedKeep = tIdx;
      });

      tracksRow.appendChild(tCard);
    });

    card.appendChild(tracksRow);
    container.appendChild(card);

    // Draw mini-waveforms after DOM insertion
    tracksRow.querySelectorAll('.compare-waveform-canvas').forEach(function(cv) {
      var parentCard = cv.closest('.compare-track-card');
      if (!parentCard) return;
      var tIdx2 = parseInt(parentCard.dataset.trackIdx);
      var trackData = tracks[tIdx2];
      if (trackData && trackData.waveform_data) {
        _drawMiniWaveform(cv, trackData.waveform_data);
      }
    });
  });

  // Batch-resolve button handler
  document.getElementById('btn-batch-resolve').addEventListener('click', function() {
    var checked = document.querySelectorAll('.dup-batch-check:checked');
    if (checked.length === 0) {
      showToast('No groups selected for batch resolve', 'warning');
      return;
    }
    var resolutions = [];
    checked.forEach(function(cb) {
      var gi = parseInt(cb.dataset.groupIdx);
      var data = storedData[gi];
      var tracks = data.group.tracks;
      var keepIdx = data.selectedKeep;
      var mergePaths = tracks.filter(function(_, i) { return i !== keepIdx; }).map(function(t) { return t.file_path; });
      if (mergePaths.length > 0) {
        resolutions.push({
          keep_path: tracks[keepIdx].file_path,
          merge_paths: mergePaths,
          field_strategy: 'best'
        });
      }
    });
    if (resolutions.length === 0) {
      showToast('No tracks to merge in selected groups', 'warning');
      return;
    }
    batchResolve(resolutions, checked);
  });

  // Select-all handler
  document.getElementById('btn-select-all').addEventListener('click', function() {
    var all = document.querySelectorAll('.dup-batch-check');
    var allChecked = Array.from(all).every(function(cb) { return cb.checked; });
    all.forEach(function(cb) { cb.checked = !allChecked; });
    this.textContent = allChecked ? 'Select All' : 'Deselect All';
  });
}

async function batchResolve(resolutions, checkboxes) {
  showSpinner('Batch-resolving duplicates...');
  try {
    var result = await apiFetch('/api/duplicates/batch-resolve', {
      method: 'POST',
      body: JSON.stringify({ resolutions: resolutions })
    });

    // Remove resolved tracks from local store
    var mergedPaths = new Set();
    (result.results || []).forEach(function(r) {
      (r.merged || 0);
    });
    resolutions.forEach(function(res) {
      res.merge_paths.forEach(function(p) { mergedPaths.add(p); });
    });
    store.set('tracks', store.state.tracks.filter(function(t) { return !mergedPaths.has(t.file_path); }));
    window.searchResults = null;

    // Collapse resolved groups visually
    checkboxes.forEach(function(cb) {
      var card = cb.closest('.compare-card');
      if (card) {
        card.classList.add('compare-card-resolved');
        cb.disabled = true;
        cb.parentElement.style.opacity = '0.5';
      }
    });

    // Update batch button
    var batchBtn = document.getElementById('btn-batch-resolve');
    if (batchBtn) batchBtn.textContent = 'Batch Resolve Selected';

    var errors = result.errors || [];
    if (errors.length > 0) {
      showToast('Resolved ' + result.resolved_groups + ' groups with ' + errors.length + ' errors', 'warning');
    } else {
      showToast('Batch-resolved ' + result.resolved_groups + ' groups (' + result.total_merged + ' tracks merged)', 'success');
    }
  } catch (error) {
    showToast('Error batch-resolving: ' + (error.message || 'Unknown error'), 'error');
  } finally {
    hideSpinner();
  }
}

async function removeDuplicate(filePath) {
  showSpinner('Removing duplicate...');
  try {
    await apiFetch('/api/duplicates/remove', {
      method: 'POST',
      body: JSON.stringify({ file_path: filePath })
    });

    store.set('tracks', store.state.tracks.filter(function(t) { return t.file_path !== filePath; }));
    window.searchResults = null;
    showToast('Track removed from library', 'success');
    await scanForDuplicates();
  } catch (error) {
    showToast('Error removing duplicate', 'error');
  } finally {
    hideSpinner();
  }
}


// --- ES module bridge (0.4): expose to global scope for cross-module calls ---
window.initDuplicatesTab = initDuplicatesTab;
