// ============================================================================
// Prepare Panel (IDJLM Phase 3.2)
// Serato-pattern staging list docked in right detail panel
// Drag tracks or press P to add; convertible to setlist
// ============================================================================

var prepareTracks = [];

function initPreparePanel() {
  var panel = document.getElementById('prepare-panel');
  if (!panel) return;

  var closeBtn = panel.querySelector('.prepare-panel-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', function() {
      panel.style.display = 'none';
    });
  }

  var toSetlistBtn = document.getElementById('btn-prepare-to-setlist');
  if (toSetlistBtn) {
    toSetlistBtn.addEventListener('click', convertPrepareToSetlist);
  }

  var clearBtn = document.getElementById('btn-prepare-clear');
  if (clearBtn) {
    clearBtn.addEventListener('click', clearPreparePanel);
  }

  // P hotkey to add selected track to prepare
  document.addEventListener('keydown', function(e) {
    if (e.key === 'p' && !e.ctrlKey && !e.metaKey && !e.altKey &&
        !e.target.closest('input,textarea,select,[contenteditable]')) {
      e.preventDefault();
      var selected = getSelectedTrack();
      if (selected) {
        addToPreparePanel(selected.file_path);
      }
    }
  });
}

function getSelectedTrack() {
  var selected = store.state.selectedTracks;
  if (selected && selected.size > 0) {
    var first = selected.values().next().value;
    return findTrackByPath(first);
  }
  return null;
}

function addToPreparePanel(filePath) {
  var track = findTrackByPath(filePath);
  if (!track) return;

  if (prepareTracks.find(function(t) { return t.file_path === filePath; })) {
    window.showToast && window.showToast('Already in prepare panel', 'info');
    return;
  }

  prepareTracks.push(track);
  renderPreparePanel();
  window.showToast && window.showToast('Added to prepare panel', 'success');
}

function removeFromPreparePanel(filePath) {
  prepareTracks = prepareTracks.filter(function(t) { return t.file_path !== filePath; });
  renderPreparePanel();
}

function clearPreparePanel() {
  prepareTracks = [];
  renderPreparePanel();
}

function convertPrepareToSetlist() {
  if (prepareTracks.length === 0) return;

  prepareTracks.forEach(function(track) {
    if (!store.state.setlist.find(function(st) { return st.file_path === track.file_path; })) {
      store.state.setlist.push(track);
    }
  });

  saveSetlistToStorage();
  renderSetlist();
  clearPreparePanel();
  window.showToast && window.showToast(prepareTracks.length + ' tracks added to setlist', 'success');
}

function renderPreparePanel() {
  var list = document.getElementById('prepare-panel-list');
  var countEl = document.getElementById('prepare-panel-count');
  var durEl = document.getElementById('prepare-panel-duration');
  var toSetlistBtn = document.getElementById('btn-prepare-to-setlist');

  if (!list) return;

  list.innerHTML = '';

  var totalDuration = 0;
  prepareTracks.forEach(function(track, idx) {
    totalDuration += (track.duration || 0);

    var item = document.createElement('div');
    item.className = 'prepare-track-item';

    var numSpan = document.createElement('span');
    numSpan.className = 'prepare-track-num';
    numSpan.textContent = String(idx + 1);

    var infoDiv = document.createElement('div');
    infoDiv.className = 'prepare-track-info';

    var titleDiv = document.createElement('div');
    titleDiv.className = 'prepare-track-title';
    titleDiv.textContent = track.display_title || track.filename || 'Unknown';

    var metaDiv = document.createElement('div');
    metaDiv.className = 'prepare-track-meta';
    var parts = [];
    if (track.final_key) parts.push(track.final_key);
    if (track.final_bpm) parts.push(Math.round(track.final_bpm) + ' BPM');
    if (track.final_genre) parts.push(track.final_genre);
    metaDiv.textContent = parts.join(' · ');

    infoDiv.appendChild(titleDiv);
    infoDiv.appendChild(metaDiv);

    var removeBtn = document.createElement('button');
    removeBtn.className = 'prepare-track-remove';
    removeBtn.innerHTML = '&#x2715;';
    removeBtn.title = 'Remove';
    removeBtn.addEventListener('click', function() {
      removeFromPreparePanel(track.file_path);
    });

    item.appendChild(numSpan);
    item.appendChild(infoDiv);
    item.appendChild(removeBtn);
    list.appendChild(item);
  });

  if (countEl) countEl.textContent = prepareTracks.length + ' track' + (prepareTracks.length !== 1 ? 's' : '');
  if (durEl) {
    var mins = Math.floor(totalDuration / 60);
    var secs = Math.floor(totalDuration % 60);
    durEl.textContent = mins + ':' + String(secs).padStart(2, '0');
  }
  if (toSetlistBtn) toSetlistBtn.disabled = prepareTracks.length === 0;

  var panel = document.getElementById('prepare-panel');
  if (panel) {
    panel.style.display = prepareTracks.length > 0 ? '' : 'none';
  }

  var emptyState = document.getElementById('prepare-panel-empty');
  if (emptyState) {
    emptyState.style.display = prepareTracks.length === 0 ? '' : 'none';
  }
}

// --- ES module bridge ---
window.addToPreparePanel = addToPreparePanel;
window.convertPrepareToSetlist = convertPrepareToSetlist;
window.initPreparePanel = initPreparePanel;
window.prepareTracks = prepareTracks;
window.renderPreparePanel = renderPreparePanel;
window.removeFromPreparePanel = removeFromPreparePanel;
