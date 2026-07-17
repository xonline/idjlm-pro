// ============================================================================
// Next Track Advisor (Phase 3.4 — Weighted Sliders)
// ============================================================================

var _advisorWeights = { key: 1.0, bpm: 1.0, energy: 1.0, genre: 1.0 };

function _advisorEscHtml(str) {
  return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function buildAdvisorWeightSection() {
  var labels = { key: 'Key', bpm: 'BPM', energy: 'Energy', genre: 'Genre' };
  var html = '<div class="advisor-weight-section"><div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:var(--text-secondary);margin-bottom:8px;">Weight Sliders</div>';
  ['key', 'bpm', 'energy', 'genre'].forEach(function(k) {
    html += '<div class="advisor-weight-label"><span>' + labels[k] + '</span><span id="adv-w-' + k + '-val">' + _advisorWeights[k].toFixed(1) + '</span></div>';
    html += '<input type="range" class="advisor-slider" id="adv-w-' + k + '" min="0" max="3" step="0.1" value="' + _advisorWeights[k] + '" data-weight="' + k + '">';
  });
  html += '</div>';
  return html;
}

function wireAdvisorWeights() {
  document.querySelectorAll('.advisor-slider').forEach(function(slider) {
    slider.addEventListener('input', function() {
      var k = this.dataset.weight;
      _advisorWeights[k] = parseFloat(this.value);
      var valEl = document.getElementById('adv-w-' + k + '-val');
      if (valEl) valEl.textContent = _advisorWeights[k].toFixed(1);
    });
  });
}

async function showNextTrackAdvisor(filePath) {
  var modal = document.getElementById('advisor-modal');
  var body = document.getElementById('advisor-modal-body');
  if (!modal || !body) return;

  // Render weight sliders
  body.innerHTML = buildAdvisorWeightSection() + '<div id="advisor-suggestions-wrap"></div>';
  wireAdvisorWeights();

  try {
    var result = await apiFetch('/api/suggest_next', {
      method: 'POST',
      body: JSON.stringify({
        file_path: filePath,
        limit: 5,
        key_weight: _advisorWeights.key,
        bpm_weight: _advisorWeights.bpm,
        energy_weight: _advisorWeights.energy,
        genre_weight: _advisorWeights.genre
      })
    });

    var suggestions = result.suggestions || [];
    var wrap = document.getElementById('advisor-suggestions-wrap');
    if (!wrap) return;

    if (suggestions.length === 0) {
      wrap.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 24px 0;">No compatible tracks found in your library.</p>';
    } else {
      wrap.innerHTML = suggestions.map(function(s) {
        var score = Math.round(s.score || 0);
        var key = _advisorEscHtml(s.final_key || '—');
        var bpm = s.final_bpm ? Math.round(s.final_bpm) : '—';
        var title = _advisorEscHtml(s.display_title || 'Unknown');
        var artist = _advisorEscHtml(s.display_artist || '');
        var safePath = _advisorEscHtml(s.file_path || '');
        var barColor = score >= 75 ? '#4caf50' : score >= 50 ? '#ff9800' : '#f44336';
        return '<div class="advisor-card" style="border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin-bottom:12px;">' +
          '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">' +
          '<div><div style="font-weight:600;font-size:14px;">' + title + '</div>' +
          '<div style="color:var(--text-secondary);font-size:12px;margin-top:2px;">' + artist + '</div></div>' +
          '<button class="btn btn-secondary advisor-add-btn" data-path="' + safePath + '" style="font-size:11px;padding:4px 10px;white-space:nowrap;margin-left:12px;">Add to Set Plan</button></div>' +
          '<div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">' +
          '<div style="flex:1;"><div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-secondary);margin-bottom:3px;"><span>Match</span><span>' + score + '%</span></div>' +
          '<div style="background:var(--border);border-radius:4px;height:6px;overflow:hidden;"><div style="width:' + score + '%;height:100%;background:' + barColor + ';border-radius:4px;transition:width 0.3s;"></div></div></div>' +
          '<div style="display:flex;gap:10px;font-size:11px;white-space:nowrap;">' +
          '<span style="background:var(--bg-secondary);padding:2px 8px;border-radius:4px;font-family:monospace;">' + key + '</span>' +
          '<span style="color:var(--text-secondary);">' + bpm + ' BPM</span></div></div></div>';
      }).join('');

      wrap.querySelectorAll('.advisor-add-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
          addTrackToSetlist(btn.dataset.path);
          modal.style.display = 'none';
        });
      });
    }

    modal.style.display = 'flex';
  } catch (e) {
    showToast('Failed to get suggestions', 'error');
  }
}

function initAdvisorModal() {
  var modal = document.getElementById('advisor-modal');
  var closeBtn = document.getElementById('advisor-modal-close');
  if (!modal || !closeBtn) return;

  closeBtn.addEventListener('click', function() { modal.style.display = 'none'; });
  modal.addEventListener('click', function(e) {
    if (e.target === modal) modal.style.display = 'none';
  });
}

// --- ES module bridge ---
window.initAdvisorModal = initAdvisorModal;
window.showNextTrackAdvisor = showNextTrackAdvisor;
