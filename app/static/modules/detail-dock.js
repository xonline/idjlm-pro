// ============================================================================
// Detail Dock v2 — permanently docked right panel (Phase 1.4)
// Art, 600-pt waveform + playhead, key/BPM/energy hero row, cues,
// compatible tracks list from /api/mixes/compatible/
// ============================================================================

function showInDock(track) {
  var dock = document.getElementById('detail-dock');
  if (!dock) return;
  dock.removeAttribute('hidden');
  var toggleBtn = document.getElementById('btn-toggle-detail-dock');
  if (toggleBtn) toggleBtn.setAttribute('aria-pressed', 'true');

  var body = document.getElementById('detail-dock-body');
  if (!body) return;

  // Render immediately with available track data
  body.innerHTML = buildDockHTML(track);

  // Freshen waveform peaks from server
  var encPath = encodeURIComponent(track.file_path);
  window.apiFetch('/api/tracks/' + encPath).then(function(full) {
    updateWaveform(full.waveform_peaks);
    updateArt(full);
  }).catch(function() {});

  // Fetch compatible tracks
  var compatContainer = body.querySelector('.dock-compat-list');
  if (compatContainer) {
    compatContainer.innerHTML = '<div class="dock-compat-loading"><span class="dock-spinner"></span> Loading compatible tracks...</div>';
    window.apiFetch('/api/mixes/compatible/' + encPath).then(function(data) {
      renderCompatible(compatContainer, data.compatible_tracks || []);
    }).catch(function() {
      compatContainer.innerHTML = '<div class="dock-compat-empty">Could not load compatible tracks</div>';
    });
  }

  // Fetch cues
  window.apiFetch('/api/tracks/' + encPath + '/cues').then(function(data) {
    var cueContainer = body.querySelector('.dock-cue-list');
    if (cueContainer) renderCues(cueContainer, data);
  }).catch(function() {});

  // Wire action buttons
  var addBtn = body.querySelector('.dock-add-setlist');
  if (addBtn) {
    addBtn.addEventListener('click', function() {
      if (window.addTrackToSetlist) window.addTrackToSetlist(track.file_path);
    });
  }
  var editBtn = body.querySelector('.dock-edit-track');
  if (editBtn) {
    editBtn.addEventListener('click', function() {
      if (window.openEditModal) window.openEditModal(track.file_path);
    });
  }

  // Wire compatible track clicks
  body.addEventListener('click', function(e) {
    var item = e.target.closest('.dock-compat-item');
    if (item && item.dataset.path) {
      var t = findTrackByPath(item.dataset.path);
      if (t) showInDock(t);
    }
  });
}

function findTrackByPath(filePath) {
  var tracks = store.state.tracks || [];
  for (var i = 0; i < tracks.length; i++) {
    if (tracks[i].file_path === filePath) return tracks[i];
  }
  return null;
}

function buildDockHTML(track) {
  var style = getComputedStyle(document.documentElement);
  var acc = style.getPropertyValue('--acc').trim() || '#8b5cf6';

  var title = window.escapeHtml(track.display_title || track.existing_title || track.filename || 'Unknown');
  var artist = window.escapeHtml(track.display_artist || track.existing_artist || 'Unknown');
  var album = window.escapeHtml(track.existing_album || '');

  var artUrl = track.album_art_url || track.deezer_cover_art || track.spotify_album_art || '';
  var artHtml = artUrl
    ? '<img class="dock-art" src="' + window.escapeHtml(artUrl) + '" alt="Album art" loading="lazy">'
    : '<div class="dock-art dock-art-placeholder">♫</div>';

  var bpm = track.final_bpm || track.analyzed_bpm || '--';
  var key = track.final_key || track.analyzed_key || '--';
  var energy = track.analyzed_energy != null ? track.analyzed_energy : '--';
  var energyHtml = '';
  if (typeof energy === 'number') {
    var dots = '';
    var scaled = Math.round(energy * 10);
    for (var i = 0; i < 10; i++) {
      dots += '<span class="dock-energy-dot" style="opacity:' + (i < scaled ? 1 : 0.15) + '"></span>';
    }
    energyHtml = dots;
  } else {
    energyHtml = '<span style="font-size:14px;color:var(--text-secondary)">--</span>';
  }

  var hasWaveform = track.waveform_peaks && track.waveform_peaks.length > 0;
  var waveformHtml = hasWaveform
    ? '<div class="dock-waveform-wrap"><canvas class="dock-waveform" id="dock-waveform-canvas" height="70"></canvas></div>'
    : '<div class="dock-waveform-nope">No waveform data — analyse this track first</div>';

  var metaHtml = '';
  var metaItems = [
    ['Year', track.final_year || '--'],
    ['Duration', track.duration ? Math.round(track.duration) + 's' : '--'],
    ['Format', track.filename ? track.filename.split('.').pop().toUpperCase() : '--'],
    ['LUFS', track.analyzed_lufs != null ? track.analyzed_lufs + ' dB' : '--'],
  ];
  metaHtml = '<div class="dock-meta-grid">';
  for (var mi = 0; mi < metaItems.length; mi++) {
    metaHtml += '<div class="dock-meta-item"><div class="dock-meta-label">' + metaItems[mi][0] + '</div><div class="dock-meta-value">' + window.escapeHtml(String(metaItems[mi][1])) + '</div></div>';
  }
  metaHtml += '</div>';

  var html = '';

  // Album art
  html += artHtml;

  // Title block
  html += '<div class="dock-title">' + title + '</div>';
  html += '<div class="dock-artist">' + artist + '</div>';
  if (album) html += '<div class="dock-album">' + album + '</div>';

  // Waveform
  html += waveformHtml;

  // Hero row: BPM / Key / Energy
  html += '<div class="dock-hero">';
  html += '<div class="dock-hero-cell"><div class="dock-hero-label">BPM</div><div class="dock-hero-value dock-hero-bpm">' + window.escapeHtml(String(bpm)) + '</div></div>';
  html += '<div class="dock-hero-cell"><div class="dock-hero-label">Key</div><div class="dock-hero-value dock-hero-key">' + window.escapeHtml(String(key)) + '</div></div>';
  html += '<div class="dock-hero-cell"><div class="dock-hero-label">Energy</div><div class="dock-hero-value dock-hero-energy">' + energyHtml + '</div></div>';
  html += '</div>';

  // Custom tags chips
  if (track.custom_tags && Object.keys(track.custom_tags).length > 0) {
    html += '<div class="dock-tag-list">';
    Object.keys(track.custom_tags).sort().forEach(function(k) {
      var v = track.custom_tags[k];
      if (v) {
        html += '<span class="dock-tag-chip"><span class="dock-tag-chip-key">' + window.escapeHtml(k) + '</span><span class="dock-tag-chip-value">' + window.escapeHtml(v) + '</span></span>';
      }
    });
    html += '</div>';
  }

  // Metadata grid
  html += metaHtml;

  // Cues section
  html += '<div><div class="dock-section-label">Cue Points</div><div class="dock-cue-list"><div class="dock-cue-empty">Loading cues...</div></div></div>';

  // Compatible tracks section
  html += '<div><div class="dock-section-label">Compatible Tracks</div><div class="dock-compat-list"><div class="dock-compat-loading"><span class="dock-spinner"></span> Loading...</div></div></div>';

  // Action buttons
  html += '<div class="dock-actions">';
  html += '<button class="btn btn-primary dock-add-setlist">+ Setlist</button>';
  html += '<button class="btn btn-secondary dock-edit-track">✎ Edit</button>';
  html += '</div>';

  return html;
}

function updateWaveform(peaks) {
  var canvas = document.getElementById('dock-waveform-canvas');
  if (!canvas || !peaks || !peaks.length) return;

  var W = canvas.clientWidth;
  var H = canvas.clientHeight;
  if (W === 0 || H === 0) { W = 292; H = 70; }
  canvas.width = W * 2;
  canvas.height = H * 2;
  canvas.style.width = W + 'px';
  canvas.style.height = H + 'px';

  var ctx = canvas.getContext('2d');
  ctx.scale(2, 2);
  ctx.clearRect(0, 0, W, H);

  var style = getComputedStyle(document.documentElement);
  var accColor = style.getPropertyValue('--acc').trim() || '#8b5cf6';
  var dimColor = style.getPropertyValue('--acc-dim').trim() || 'rgba(139,92,246,0.2)';

  var len = peaks.length;
  var midY = H / 2;

  ctx.strokeStyle = accColor;
  ctx.lineWidth = 1.5;
  ctx.beginPath();

  for (var i = 0; i < len; i++) {
    var x = (i / (len - 1)) * W;
    var amp = Math.max(0.01, peaks[i] || 0);
    var barH = amp * midY * 0.92;

    ctx.moveTo(x, midY - barH);
    ctx.lineTo(x, midY + barH);
  }
  ctx.stroke();

  // Fill below the waveform
  ctx.fillStyle = dimColor;
  ctx.beginPath();
  ctx.moveTo(0, midY);
  for (var j = 0; j < len; j++) {
    var x2 = (j / (len - 1)) * W;
    var amp2 = Math.max(0.01, peaks[j] || 0);
    var barH2 = amp2 * midY * 0.92;
    ctx.lineTo(x2, midY + barH2);
  }
  for (var k = len - 1; k >= 0; k--) {
    var x3 = (k / (len - 1)) * W;
    var amp3 = Math.max(0.01, peaks[k] || 0);
    var barH3 = amp3 * midY * 0.92;
    ctx.lineTo(x3, midY - barH3);
  }
  ctx.closePath();
  ctx.fill();
}

function updateArt(track) {
  var artUrl = track.album_art_url || track.deezer_cover_art || track.spotify_album_art || '';
  if (!artUrl) return;
  var artEl = document.querySelector('.dock-art');
  if (artEl && artEl.tagName !== 'IMG') {
    var img = document.createElement('img');
    img.className = 'dock-art';
    img.src = artUrl;
    img.alt = 'Album art';
    img.loading = 'lazy';
    artEl.parentNode.replaceChild(img, artEl);
  }
}

function renderCompatible(container, tracks) {
  if (!tracks || tracks.length === 0) {
    container.innerHTML = '<div class="dock-compat-empty">No compatible tracks found</div>';
    return;
  }
  var html = '';
  for (var i = 0; i < tracks.length; i++) {
    var t = tracks[i];
    var score = t.score || 0;
    var scoreClass = score >= 80 ? 'score-high' : score >= 60 ? 'score-mid' : 'score-low';
    var bpm = t.bpm != null ? Math.round(t.bpm) : '--';
    html += '<div class="dock-compat-item" data-path="' + window.escapeHtml(t.file_path || '') + '">';
    html += '<div class="dock-compat-info">';
    html += '<div class="dock-compat-title">' + window.escapeHtml(t.title || 'Unknown') + '</div>';
    html += '<div class="dock-compat-meta">' + (t.key || '--') + ' · ' + bpm + ' BPM</div>';
    html += '</div>';
    html += '<span class="dock-compat-score ' + scoreClass + '">' + score + '</span>';
    html += '</div>';
  }
  container.innerHTML = html;
}

function renderCues(container, data) {
  var cues = data.cues || [];
  var clavePattern = data.clave_pattern || null;

  if (!cues.length && !clavePattern) {
    container.innerHTML = '<div class="dock-cue-empty">No cue points available</div>';
    return;
  }
  var html = '';
  if (clavePattern) {
    html += '<div class="dock-cue-item"><span class="dock-cue-dot dock-cue-loop"></span><span class="dock-cue-time">CLAVE</span><span class="dock-cue-label">' + window.escapeHtml(clavePattern) + '</span></div>';
  }
  for (var i = 0; i < cues.length; i++) {
    var c = cues[i];
    var time = c.time != null ? formatTime(c.time) : '--';
    var label = c.label || c.type || 'Cue ' + (i + 1);
    var dotClass = 'dock-cue-dot';
    if (c.type === 'hot' || c.type === 'cue') dotClass += ' dock-cue-hot';
    else if (c.type === 'loop') dotClass += ' dock-cue-loop';
    html += '<div class="dock-cue-item"><span class="' + dotClass + '"></span><span class="dock-cue-time">' + time + '</span><span class="dock-cue-label">' + window.escapeHtml(label) + '</span></div>';
  }
  container.innerHTML = html;
}

function formatTime(secs) {
  if (secs == null) return '--';
  var m = Math.floor(secs / 60);
  var s = Math.floor(secs % 60);
  return m + ':' + (s < 10 ? '0' : '') + s;
}

function clearDock() {
  var body = document.getElementById('detail-dock-body');
  if (!body) return;
  body.innerHTML = '<div class="dock-empty"><div class="dock-empty-icon">♫</div><div class="dock-empty-text">Select a track to view details</div></div>';
}

function initDetailDock() {
  var toggleBtn = document.getElementById('btn-toggle-detail-dock');
  var dock = document.getElementById('detail-dock');
  var closeBtn = document.getElementById('detail-dock-close');

  if (toggleBtn) {
    toggleBtn.addEventListener('click', function() {
      if (dock.hasAttribute('hidden')) {
        dock.removeAttribute('hidden');
        toggleBtn.setAttribute('aria-pressed', 'true');
      } else {
        dock.setAttribute('hidden', '');
        toggleBtn.setAttribute('aria-pressed', 'false');
      }
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', function() {
      dock.setAttribute('hidden', '');
      if (toggleBtn) toggleBtn.setAttribute('aria-pressed', 'false');
    });
  }

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && dock && !dock.hasAttribute('hidden') && !e.target.closest('.modal')) {
      dock.setAttribute('hidden', '');
      if (toggleBtn) toggleBtn.setAttribute('aria-pressed', 'false');
    }
  });

  clearDock();
}

window.showInDock = showInDock;
window.initDetailDock = initDetailDock;
