// ============================================================================
// Drag-Drop Set Builder (IDJLM Phase 3.1)
// HTML5 DnD: library rows → setlist drop zone with live transition rating badge
// ============================================================================

let _dragCurrentTrack = null;
let _dragDropIndex = -1;
let _transitionScoreEl = null;
let _scorePollTimer = null;

function initDragDrop() {
  // Make library track rows draggable
  document.addEventListener('dragover', function(e) {
    if (e.target.closest('[draggable="true"]')) {
      e.preventDefault();
    }
  });

  // Capture drag start on track rows (event delegation)
  document.addEventListener('dragstart', function(e) {
    var row = e.target.closest('tr');
    if (!row) return;
    var filePath = row.dataset.filePath;
    if (!filePath) return;

    var track = findTrackByPath(filePath);
    if (!track) return;

    _dragCurrentTrack = track;
    row.classList.add('drag-source');
    e.dataTransfer.effectAllowed = 'copyMove';
    e.dataTransfer.setData('text/plain', filePath);

    // Create drag image
    var ghost = document.createElement('div');
    ghost.className = 'drag-ghost';
    ghost.textContent = (track.display_title || track.filename || 'Track');
    ghost.style.cssText = 'position:absolute;top:-9999px;left:-9999px;padding:8px 16px;background:var(--bg-secondary);border:1px solid var(--acc);border-radius:6px;color:var(--t1);font-size:13px;font-weight:600;white-space:nowrap;pointer-events:none;z-index:99999;';
    document.body.appendChild(ghost);
    e.dataTransfer.setDragImage(ghost, 0, 0);
    setTimeout(function() { document.body.removeChild(ghost); }, 0);
  });

  document.addEventListener('dragend', function(e) {
    var row = e.target.closest('tr');
    if (row) row.classList.remove('drag-source');
    _dragCurrentTrack = null;
    _dragDropIndex = -1;
    clearDropIndicator();
    hideTransitionBadge();
    if (_scorePollTimer) { clearTimeout(_scorePollTimer); _scorePollTimer = null; }
  });

  // Set up drop zones
  setupSetlistDropZone();
  setupPrepareDropZone();
}

function setupSetlistDropZone() {
  var container = document.getElementById('setlist-tracks');
  if (!container) return;

  container.addEventListener('dragover', function(e) {
    e.preventDefault();
    if (!_dragCurrentTrack) return;
    e.dataTransfer.dropEffect = 'copy';

    _dragDropIndex = calcDropIndex(container, e.clientY);
    showDropIndicator(container, _dragDropIndex);
    pollTransitionScore(container);
  });

  container.addEventListener('dragleave', function(e) {
    if (!container.contains(e.relatedTarget)) {
      clearDropIndicator();
      hideTransitionBadge();
    }
  });

  container.addEventListener('drop', function(e) {
    e.preventDefault();
    clearDropIndicator();
    hideTransitionBadge();
    if (!_dragCurrentTrack) return;

    var filePath = _dragCurrentTrack.file_path;
    var idx = _dragDropIndex >= 0 ? _dragDropIndex : store.state.setlist.length;

    if (!store.state.setlist.find(function(t) { return t.file_path === filePath; })) {
      if (idx >= store.state.setlist.length) {
        store.state.setlist.push(_dragCurrentTrack);
      } else {
        store.state.setlist.splice(idx, 0, _dragCurrentTrack);
      }
      saveSetlistToStorage();
      renderSetlist();
      window.showToast && window.showToast('Track added to setlist', 'success');
    } else {
      window.showToast && window.showToast('Track already in setlist', 'info');
    }
    _dragCurrentTrack = null;
    _dragDropIndex = -1;
  });
}

function setupPrepareDropZone() {
  var container = document.getElementById('prepare-panel-list');
  if (!container) return;

  container.addEventListener('dragover', function(e) {
    e.preventDefault();
    if (!_dragCurrentTrack) return;
    e.dataTransfer.dropEffect = 'copy';
    container.classList.add('drop-zone-active');
  });

  container.addEventListener('dragleave', function(e) {
    if (!container.contains(e.relatedTarget)) {
      container.classList.remove('drop-zone-active');
    }
  });

  container.addEventListener('drop', function(e) {
    e.preventDefault();
    container.classList.remove('drop-zone-active');
    if (!_dragCurrentTrack) return;
    addToPreparePanel(_dragCurrentTrack.file_path);
    _dragCurrentTrack = null;
  });
}

function calcDropIndex(container, clientY) {
  var children = container.querySelectorAll('.setlist-track-item');
  for (var i = 0; i < children.length; i++) {
    var rect = children[i].getBoundingClientRect();
    var midY = rect.top + rect.height / 2;
    if (clientY < midY) return i;
  }
  return children.length;
}

function showDropIndicator(container, index) {
  clearDropIndicator();
  var indicator = document.createElement('div');
  indicator.className = 'drop-indicator';
  indicator.style.cssText = 'height:3px;background:var(--acc);margin:2px 0;border-radius:2px;transition:all 0.15s;';

  var children = container.querySelectorAll('.setlist-track-item');
  if (index < children.length) {
    container.insertBefore(indicator, children[index]);
  } else {
    container.appendChild(indicator);
  }

  // Add drop-zone highlight
  if (_dragCurrentTrack && store.state.setlist.length > 0) {
    container.classList.add('drop-zone-active');
  }
}

function clearDropIndicator() {
  var indicators = document.querySelectorAll('.drop-indicator');
  for (var i = 0; i < indicators.length; i++) {
    indicators[i].parentNode && indicators[i].parentNode.removeChild(indicators[i]);
  }
  var zones = document.querySelectorAll('.drop-zone-active');
  for (var j = 0; j < zones.length; j++) {
    zones[j].classList.remove('drop-zone-active');
  }
}

function pollTransitionScore(container) {
  if (!_dragCurrentTrack || store.state.setlist.length === 0) {
    hideTransitionBadge();
    return;
  }

  if (_scorePollTimer) return;

  _scorePollTimer = setTimeout(function() {
    _scorePollTimer = null;
    showTransitionBadge();
  }, 300);
}

function getTransitionDetails(droppedTrack, index) {
  var setlist = store.state.setlist;
  var transitions = [];

  // Score transition from the track BEFORE the drop position
  if (index > 0 && setlist[index - 1]) {
    var prev = setlist[index - 1];
    transitions.push({
      from: prev,
      to: droppedTrack,
      label: '← Incoming'
    });
  }

  // Score transition to the track AFTER the drop position  
  if (index < setlist.length && setlist[index]) {
    var next = setlist[index];
    transitions.push({
      from: droppedTrack,
      to: next,
      label: 'Outgoing →'
    });
  }

  // If inserting at end, just rate from last track
  if (index >= setlist.length && setlist.length > 0) {
    var last = setlist[setlist.length - 1];
    transitions.push({
      from: last,
      to: droppedTrack,
      label: '← Incoming'
    });
  }

  return transitions;
}

function clientScoreTransition(trackA, trackB) {
  // Fast client-side score using mix_scorer logic replicated in JS
  var score = 0;
  var details = [];

  // BPM score (0-25)
  var bpmA = parseFloat(trackA.final_bpm || trackA.analyzed_bpm || 0);
  var bpmB = parseFloat(trackB.final_bpm || trackB.analyzed_bpm || 0);
  if (bpmA > 0 && bpmB > 0) {
    var bpmDiff = Math.abs(bpmA - bpmB);
    if (Math.abs(bpmA * 2 - bpmB) < 1 || Math.abs(bpmA / 2 - bpmB) < 1) {
      score += 25; details.push('BPM: double/half match');
    } else if (bpmDiff === 0) {
      score += 25; details.push('BPM: exact match');
    } else if (bpmDiff <= 2) {
      score += 20; details.push('BPM: ' + bpmDiff.toFixed(1) + ' diff');
    } else if (bpmDiff <= 5) {
      score += 15; details.push('BPM: ' + bpmDiff.toFixed(1) + ' diff');
    } else if (bpmDiff <= 8) {
      score += 8; details.push('BPM: ' + bpmDiff.toFixed(1) + ' diff');
    }
  }

  // Key score (0-35)
  var keyA = trackA.final_key || '';
  var keyB = trackB.final_key || '';
  if (keyA && keyB) {
    try {
      var numA = parseInt(keyA), numB = parseInt(keyB);
      var letterA = keyA[keyA.length - 1], letterB = keyB[keyB.length - 1];
      if (numA === numB && letterA === letterB) {
        score += 35; details.push('Key: same Camelot');
      } else if (numA === numB || (Math.abs(numA - numB) === 1 || Math.abs(numA - numB) === 11)) {
        score += 25; details.push('Key: adjacent Camelot');
      } else if (Math.abs(numA - numB) <= 2 || Math.abs(numA - numB) >= 10) {
        score += 10; details.push('Key: near Camelot');
      }
    } catch(e) {}
  }

  // Energy score (0-20)
  var eA = parseFloat(trackA.analyzed_energy) || 0;
  var eB = parseFloat(trackB.analyzed_energy) || 0;
  if (eA > 0 && eB > 0) {
    var eDiff = Math.abs(eA - eB);
    if (eDiff <= 0.5) { score += 20; }
    else if (eDiff <= 1) { score += 15; }
    else if (eDiff <= 2) { score += 10; }
    else if (eDiff <= 3) { score += 5; }
    details.push('Energy: ' + eDiff.toFixed(1) + ' diff');
  }

  // Genre score (0-20)
  var gA = (trackA.final_genre || '').toLowerCase();
  var gB = (trackB.final_genre || '').toLowerCase();
  if (gA && gB && gA === gB) {
    score += 20; details.push('Genre: same');
  }

  return { score: Math.min(100, score), details: details.join(' | ') || 'Insufficient data' };
}

function showTransitionBadge() {
  hideTransitionBadge();

  if (!_dragCurrentTrack || store.state.setlist.length === 0) return;

  var transitions = getTransitionDetails(_dragCurrentTrack, _dragDropIndex);

  var badge = document.createElement('div');
  badge.id = 'transition-rating-badge';
  badge.style.cssText = 'position:fixed;bottom:80px;right:24px;background:var(--bg-secondary);border:1px solid var(--border);border-radius:10px;padding:12px 16px;z-index:1000;font-size:12px;box-shadow:0 4px 24px rgba(0,0,0,0.4);max-width:280px;';

  var html = '<div style="font-weight:600;margin-bottom:8px;color:var(--t2);">Transition Rating</div>';

  transitions.forEach(function(tr) {
    var result = clientScoreTransition(tr.from, tr.to);
    var color = result.score >= 75 ? '#4caf50' : result.score >= 50 ? '#ff9800' : '#f44336';
    html += '<div style="margin-bottom:6px;">';
    html += '<div style="display:flex;justify-content:space-between;margin-bottom:2px;">';
    html += '<span style="color:var(--text-secondary);">' + window.escapeHtml(tr.label) + '</span>';
    html += '<span style="color:' + color + ';font-weight:700;">' + result.score + '%</span>';
    html += '</div>';
    html += '<div style="background:var(--border);height:4px;border-radius:2px;overflow:hidden;">';
    html += '<div style="width:' + result.score + '%;height:100%;background:' + color + ';border-radius:2px;"></div>';
    html += '</div>';
    html += '<div style="margin-top:2px;font-size:11px;color:var(--text-muted);">' + result.details + '</div>';
    html += '</div>';
  });

  // Preview the inserted track info
  html += '<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);">';
  html += '<div style="font-size:11px;color:var(--accent);">' + window.escapeHtml(_dragCurrentTrack.display_title || _dragCurrentTrack.filename || 'Track') + '</div>';
  html += '<div style="font-size:10px;color:var(--text-muted);">' + (_dragCurrentTrack.final_bpm || '?') + ' BPM · ' + (_dragCurrentTrack.final_key || '?') + ' · ' + (_dragCurrentTrack.final_genre || 'Unknown') + '</div>';
  html += '</div>';

  badge.innerHTML = html;
  document.body.appendChild(badge);
  _transitionScoreEl = badge;
}

function hideTransitionBadge() {
  if (_transitionScoreEl) {
    _transitionScoreEl.parentNode && _transitionScoreEl.parentNode.removeChild(_transitionScoreEl);
    _transitionScoreEl = null;
  }
  if (_scorePollTimer) {
    clearTimeout(_scorePollTimer);
    _scorePollTimer = null;
  }
}

// --- ES module bridge ---
window.initDragDrop = initDragDrop;
