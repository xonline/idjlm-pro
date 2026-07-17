// ============================================================================
// Setlist Timeline View (IDJLM Phase 3.6)
// Horizontal lane: BPM curve + key path + energy fill + transition warnings
// Canvas-based, key clash (>6% BPM jump) detection from mix scorer
// ============================================================================

var _timelineChart = null;
var _timelineContainer = null;

function initSetlistTimeline() {
  _timelineContainer = document.getElementById('setlist-timeline-view');
  if (!_timelineContainer) return;

  var canvas = document.getElementById('setlist-timeline-canvas');
  if (!canvas) return;

  // Re-render when setlist changes
  store.subscribe('setlist', function() {
    renderSetlistTimeline();
  });

  // Initial render
  renderSetlistTimeline();
}

function renderSetlistTimeline() {
  var canvas = document.getElementById('setlist-timeline-canvas');
  var container = document.getElementById('setlist-timeline-view');
  if (!canvas || !container) return;

  var setlist = store.state.setlist;
  if (setlist.length < 2) {
    container.style.display = 'none';
    return;
  }
  container.style.display = '';

  var dpr = window.devicePixelRatio || 1;
  var W = canvas.clientWidth;
  var H = canvas.clientHeight;

  canvas.width = W * dpr;
  canvas.height = H * dpr;
  canvas.style.width = W + 'px';
  canvas.style.height = H + 'px';

  var ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  // Layout: 3 horizontal lanes
  // Lane 1 (top 0-33%): BPM curve
  // Lane 2 (middle 33-66%): Key path  
  // Lane 3 (bottom 66-100%): Energy fill
  var padding = { top: 20, right: 16, bottom: 12, left: 56 };
  var laneH = (H - padding.top - padding.bottom) / 3;
  var laneW = W - padding.left - padding.right;

  // Extract data
  var n = setlist.length;
  var bpms = setlist.map(function(t) { return parseFloat(t.final_bpm || t.analyzed_bpm || 0); });
  var keys = setlist.map(function(t) { return t.final_key || ''; });
  var energies = setlist.map(function(t) { return parseFloat(t.analyzed_energy) || 0; });

  // Filter valid values
  var validBpmIdx = [];
  var validBpmVals = [];
  bpms.forEach(function(b, i) { if (b > 0) { validBpmIdx.push(i); validBpmVals.push(b); } });
  var validEnIdx = [];
  var validEnVals = [];
  energies.forEach(function(e, i) { if (e > 0) { validEnIdx.push(i); validEnVals.push(e); } });

  var xForIndex = function(idx) {
    return padding.left + (idx / Math.max(1, n - 1)) * laneW;
  };

  // ===== Lane 1: BPM Curve =====
  var l1Top = padding.top;
  var l1Mid = l1Top + laneH / 2;

  var bpmMin = validBpmVals.length > 0 ? Math.min.apply(null, validBpmVals) : 60;
  var bpmMax = validBpmVals.length > 0 ? Math.max.apply(null, validBpmVals) : 180;
  var bpmRange = Math.max(1, bpmMax - bpmMin);

  var yForBpm = function(bpm) {
    return l1Top + laneH - 12 - ((bpm - bpmMin) / bpmRange) * (laneH - 24);
  };

  // Labels
  ctx.fillStyle = 'var(--text-muted, #6a6a94)';
  ctx.font = '10px Outfit, sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText('BPM', padding.left - 6, l1Mid + 3);
  ctx.fillText(Math.round(bpmMin), padding.left - 6, l1Top + laneH - 14);
  ctx.fillText(Math.round(bpmMax), padding.left - 6, l1Top + 14);

  // Grid lines
  ctx.strokeStyle = 'rgba(42, 42, 58, 0.3)';
  ctx.lineWidth = 0.5;
  for (var gi = 0; gi < n; gi++) {
    var gx = xForIndex(gi);
    ctx.beginPath();
    ctx.moveTo(gx, l1Top);
    ctx.lineTo(gx, l1Top + laneH * 3);
    ctx.stroke();
  }

  // BPM area fill
  if (validBpmIdx.length > 1) {
    ctx.fillStyle = 'rgba(0, 210, 190, 0.08)';
    ctx.beginPath();
    ctx.moveTo(xForIndex(validBpmIdx[0]), l1Top + laneH - 6);
    validBpmIdx.forEach(function(idx) {
      ctx.lineTo(xForIndex(idx), yForBpm(bpms[idx]));
    });
    ctx.lineTo(xForIndex(validBpmIdx[validBpmIdx.length - 1]), l1Top + laneH - 6);
    ctx.closePath();
    ctx.fill();

    // BPM line
    ctx.strokeStyle = 'var(--acc, #00d2be)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    validBpmIdx.forEach(function(idx, i) {
      var fx = xForIndex(idx);
      var fy = yForBpm(bpms[idx]);
      if (i === 0) ctx.moveTo(fx, fy);
      else ctx.lineTo(fx, fy);
    });
    ctx.stroke();

    // BPM dots
    validBpmIdx.forEach(function(idx) {
      var dx = xForIndex(idx);
      var dy = yForBpm(bpms[idx]);
      ctx.fillStyle = 'var(--acc, #00d2be)';
      ctx.beginPath();
      ctx.arc(dx, dy, 3.5, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  // Transition warnings (red markers for >6% BPM jumps)
  for (var ti = 0; ti < n - 1; ti++) {
    var b1 = bpms[ti], b2 = bpms[ti + 1];
    if (b1 > 0 && b2 > 0) {
      var pctDiff = Math.abs(b2 - b1) / b1 * 100;
      if (pctDiff > 6) {
        var x1 = xForIndex(ti), x2 = xForIndex(ti + 1);
        var midX = (x1 + x2) / 2;
        ctx.fillStyle = '#f44336';
        ctx.beginPath();
        ctx.arc(midX, l1Mid, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 8px Outfit, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('!', midX, l1Mid + 3);
      }
    }
  }

  // ===== Lane 2: Key Path =====
  var l2Top = padding.top + laneH;
  var l2Mid = l2Top + laneH / 2;

  ctx.fillStyle = 'var(--text-muted, #6a6a94)';
  ctx.font = '10px Outfit, sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText('KEY', padding.left - 6, l2Mid + 3);

  var keyColors = {
    'A': 'rgba(139, 92, 246, 1)',   // purple for minor
    'B': 'rgba(20, 184, 166, 1)',   // teal for major
  };

  // Draw key sequence as connected blocks
  var blockW = laneW / n;
  keys.forEach(function(key, ki) {
    var kx = xForIndex(ki);
    var mode = key ? key[key.length - 1] : '';
    var color = keyColors[mode] || 'rgba(106, 106, 148, 1)';

    // Key chip
    var chipW = Math.min(blockW - 4, 44);
    var chipH = 22;
    var chipX = kx - chipW / 2;
    var chipY = l2Mid - chipH / 2;

    ctx.fillStyle = color;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;

    // Rounded rect
    var r = 4;
    ctx.beginPath();
    ctx.moveTo(chipX + r, chipY);
    ctx.lineTo(chipX + chipW - r, chipY);
    ctx.quadraticCurveTo(chipX + chipW, chipY, chipX + chipW, chipY + r);
    ctx.lineTo(chipX + chipW, chipY + chipH - r);
    ctx.quadraticCurveTo(chipX + chipW, chipY + chipH, chipX + chipW - r, chipY + chipH);
    ctx.lineTo(chipX + r, chipY + chipH);
    ctx.quadraticCurveTo(chipX, chipY + chipH, chipX, chipY + chipH - r);
    ctx.lineTo(chipX, chipY + r);
    ctx.quadraticCurveTo(chipX, chipY, chipX + r, chipY);
    ctx.closePath();
    ctx.fill();

    // Key text
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 10px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(key || '?', kx, l2Mid);

    // Connecting lines between keys
    if (ki < n - 1 && key && keys[ki + 1]) {
      var nx = xForIndex(ki + 1);
      var isAdjacent = false;
      try {
        var num1 = parseInt(key), num2 = parseInt(keys[ki + 1]);
        var l1 = key[key.length - 1], l2 = keys[ki + 1][keys[ki + 1].length - 1];
        var dist = Math.abs(num1 - num2);
        if (dist > 6) dist = 12 - dist;
        isAdjacent = (dist <= 1 && l1 === l2) || (num1 === num2 && l1 !== l2);
      } catch(e) {}

      ctx.strokeStyle = isAdjacent ? 'rgba(255, 255, 255, 0.3)' : 'rgba(244, 67, 54, 0.5)';
      ctx.lineWidth = isAdjacent ? 1 : 1.5;
      ctx.setLineDash(isAdjacent ? [] : [3, 3]);
      ctx.beginPath();
      ctx.moveTo(kx + chipW / 2 + 4, l2Mid);
      ctx.lineTo(nx - chipW / 2 - 4, l2Mid);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  });

  // ===== Lane 3: Energy Fill =====
  var l3Top = padding.top + laneH * 2;
  var l3Mid = l3Top + laneH / 2;

  ctx.fillStyle = 'var(--text-muted, #6a6a94)';
  ctx.font = '10px Outfit, sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText('NRG', padding.left - 6, l3Mid + 3);

  if (validEnIdx.length > 1) {
    var yForEnergy = function(energy) {
      return l3Top + laneH - 8 - (energy / 10) * (laneH - 16);
    };

    // Energy fill
    ctx.fillStyle = 'rgba(139, 92, 246, 0.12)';
    ctx.beginPath();
    ctx.moveTo(xForIndex(validEnIdx[0]), l3Top + laneH - 4);
    validEnIdx.forEach(function(idx) {
      ctx.lineTo(xForIndex(idx), yForEnergy(energies[idx]));
    });
    ctx.lineTo(xForIndex(validEnIdx[validEnIdx.length - 1]), l3Top + laneH - 4);
    ctx.closePath();
    ctx.fill();

    // Energy line
    ctx.strokeStyle = '#8b5cf6';
    ctx.lineWidth = 2;
    ctx.beginPath();
    validEnIdx.forEach(function(idx, i) {
      var ex = xForIndex(idx);
      var ey = yForEnergy(energies[idx]);
      if (i === 0) ctx.moveTo(ex, ey);
      else ctx.lineTo(ex, ey);
    });
    ctx.stroke();

    // Energy dots with color coding
    validEnIdx.forEach(function(idx) {
      var dx = xForIndex(idx);
      var dy = yForEnergy(energies[idx]);
      var e = energies[idx];
      var color = e >= 8 ? '#f87171' : e >= 6 ? '#fbbf24' : e >= 4 ? '#34d399' : '#60a5fa';
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(dx, dy, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = 'var(--bg0, #0d0d1a)';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });
  }

  // Track position labels at bottom
  ctx.fillStyle = 'var(--text-muted, #6a6a94)';
  ctx.font = '9px Outfit, sans-serif';
  ctx.textAlign = 'center';
  for (var li = 0; li < n; li++) {
    ctx.fillText('#' + (li + 1), xForIndex(li), l3Top + laneH + 12);
  }

  // Track title labels at top
  ctx.font = '10px Outfit, sans-serif';
  ctx.textAlign = 'center';
  for (var ti2 = 0; ti2 < n; ti2++) {
    var t = setlist[ti2];
    var shortTitle = (t.display_title || t.filename || '?').substring(0, 12);
    if (shortTitle.length >= 12) shortTitle += '…';
    ctx.fillText(shortTitle, xForIndex(ti2), padding.top - 4);
  }
}

// Handle resize
window.addEventListener('resize', function() {
  renderSetlistTimeline();
});

// --- ES module bridge ---
window.initSetlistTimeline = initSetlistTimeline;
window.renderSetlistTimeline = renderSetlistTimeline;
