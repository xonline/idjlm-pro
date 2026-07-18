// ============================================================================
// Stems — Stem Separation UI (Phase C.3)
// Renders stem controls in the detail dock and manages SSE progress.
// ============================================================================

var _stemsCurrentTrack = null;
var _stemsCurrentPath = null;

function initStems() {
  var dockBody = document.getElementById('detail-dock-body');
  if (!dockBody) return;

  var observer = new MutationObserver(function() {
    var container = dockBody.querySelector('.dock-stems-container');
    if (container) {
      loadStems();
    }
  });
  observer.observe(dockBody, { childList: true, subtree: true });
}

function loadStems() {
  var track = window._currentDetailTrack;
  if (!track) return;

  var container = document.querySelector('.dock-stems-container');
  if (!container) return;

  var encPath = encodeURIComponent(track.file_path);
  _stemsCurrentTrack = track;
  _stemsCurrentPath = encPath;

  container.innerHTML = '<div class="dock-stems-loading"><span class="dock-spinner"></span> Checking stems...</div>';

  window.apiFetch('/api/stem/' + encPath + '/stems').then(function(data) {
    if (data && data.stems && data.stems.length > 0) {
      renderStemList(container, data.stems, track);
    } else {
      renderSeparateButton(container, track);
    }
  }).catch(function() {
    renderSeparateButton(container, track);
  });
}

function renderSeparateButton(container, track) {
  var html = '';
  html += '<button class="dock-stem-separate-btn" id="btn-separate-stems">';
  html += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>';
  html += ' Separate Stems';
  html += '</button>';
  html += '<div class="dock-stems-hint">Extract vocals, drums, bass &amp; other stems</div>';
  container.innerHTML = html;

  var btn = container.querySelector('#btn-separate-stems');
  if (btn) {
    btn.addEventListener('click', function() {
      separateStems(track);
    });
  }
}

function renderStemList(container, stems, track) {
  var html = '';
  for (var i = 0; i < stems.length; i++) {
    var s = stems[i];
    var icon = getStemIcon(s.name);
    html += '<div class="dock-stem-item">';
    html += '<span class="dock-stem-icon">' + icon + '</span>';
    html += '<span class="dock-stem-name">' + capitalizeName(s.name) + '</span>';
    html += '<button class="dock-stem-play-btn" data-stem-path="' + window.escapeHtml(s.path) + '" data-stem-name="' + s.name + '" title="Play ' + s.name + '">';
    html += '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>';
    html += '</button>';
    html += '</div>';
  }

  html += '<div class="dock-stems-footer">';
  html += '<button class="dock-stem-reseparate-btn" id="btn-reseparate-stems">Re-separate</button>';
  html += '<button class="dock-stem-delete-btn" id="btn-delete-stems">Delete</button>';
  html += '</div>';

  container.innerHTML = html;

  container.querySelectorAll('.dock-stem-play-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var stemPath = this.dataset.stemPath;
      var stemName = this.dataset.stemName;
      playStem(track, stemName);
    });
  });

  var reseparateBtn = container.querySelector('#btn-reseparate-stems');
  if (reseparateBtn) {
    reseparateBtn.addEventListener('click', function() {
      separateStems(track);
    });
  }

  var deleteBtn = container.querySelector('#btn-delete-stems');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', function() {
      deleteStemsForTrack(track);
    });
  }
}

function separateStems(track) {
  var container = document.querySelector('.dock-stems-container');
  if (!container) return;

  container.innerHTML = '<div class="dock-stems-loading"><span class="dock-spinner"></span> Starting stem separation...</div>';

  window.apiFetch('/api/stem/separate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path: track.file_path })
  }).then(function(result) {
    if (result && result.op_id) {
      var opHandle = window.opsbar.registerOp({
        id: 'stems:' + result.op_id,
        label: 'Stem separation',
        kind: 'stems',
        onCancel: function() {
          window.apiFetch('/api/progress/' + result.op_id + '/cancel', { method: 'POST' });
        },
      });

      window.connectToProgress(
        result.op_id,
        result.total,
        function(current, total, message) {
          window.opsbar.progress(opHandle, current, total, message);
          if (container) {
            container.innerHTML = '<div class="dock-stems-loading"><span class="dock-spinner"></span> ' + window.escapeHtml(message) + ' (' + current + '/' + total + ')</div>';
          }
        },
        function(data) {
          if (data.cancelled) {
            window.opsbar.error(opHandle, 'cancelled');
            window.showToast('Stem separation cancelled', 'info');
            loadStems();
            return;
          }
          window.opsbar.complete(opHandle, data);
          window.showToast('Stem separation complete', 'success');
          loadStems();
        },
        function(err) {
          window.opsbar.error(opHandle, err.message || 'stream error');
          window.showToast('Stem separation failed: ' + err.message, 'error');
          if (container) {
            container.innerHTML = '<div class="dock-stems-error">Failed: ' + window.escapeHtml(err.message || 'unknown error') + '</div>';
          }
        }
      );
    } else if (result && result.error) {
      window.showToast('Stem separation error: ' + result.error, 'error');
      if (container) renderSeparateButton(container, track);
    }
  }).catch(function(err) {
    window.showToast('Stem separation request failed', 'error');
    if (container) renderSeparateButton(container, track);
  });
}

function playStem(track, stemName) {
  var audio = document.getElementById('audio-player');
  if (!audio) return;

  var encPath = encodeURIComponent(track.file_path);
  audio.src = '/api/stem/' + encPath + '/stem/' + stemName;
  document.getElementById('audio-track-title').textContent = (track.display_title || 'Unknown') + ' — ' + capitalizeName(stemName);
  document.getElementById('audio-track-artist').textContent = track.display_artist || 'Stem';

  var bar = document.getElementById('audio-player-bar');
  bar.classList.remove('hidden');
  audio.load();

  audio.addEventListener('canplay', function onCanPlay() {
    audio.removeEventListener('canplay', onCanPlay);
    audio.play().catch(function() {});
    var playPauseBtn = document.getElementById('audio-play-pause');
    if (playPauseBtn) playPauseBtn.textContent = '';
    var ip = document.getElementById('icon-play');
    var ipu = document.getElementById('icon-pause');
    if (ip) ip.style.display = 'none';
    if (ipu) ipu.style.display = 'block';
  }, { once: true });
}

function deleteStemsForTrack(track) {
  var encPath = encodeURIComponent(track.file_path);
  window.apiFetch('/api/stem/' + encPath, { method: 'DELETE' }).then(function(data) {
    if (data.deleted) {
      window.showToast('Stems deleted', 'info');
      loadStems();
    }
  }).catch(function(err) {
    window.showToast('Failed to delete stems', 'error');
  });
}

function getStemIcon(name) {
  var icons = {
    vocals: '\u{1F3A4}',
    drums: '\u{1F941}',
    bass: '\u{1F3B8}',
    other: '\u{266C}'
  };
  return icons[name] || '\u{266B}';
}

function capitalizeName(name) {
  if (!name) return '';
  return name.charAt(0).toUpperCase() + name.slice(1);
}

window.initStems = initStems;
window.loadStems = loadStems;
window.separateStems = separateStems;
