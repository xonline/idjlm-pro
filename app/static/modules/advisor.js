// ============================================================================
// Next Track Advisor
// ============================================================================

/**
 * Next Track Advisor — suggests next tracks combining harmonic, BPM, energy, and genre compatibility.
 */
function _advisorEscHtml(str) {
  return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

async function showNextTrackAdvisor(filePath) {
  try {
    const result = await apiFetch('/api/suggest_next', {
      method: 'POST',
      body: JSON.stringify({ file_path: filePath, limit: 5 })
    });

    const suggestions = result.suggestions || [];
    const modal = document.getElementById('advisor-modal');
    const body = document.getElementById('advisor-modal-body');

    if (!modal || !body) return;

    if (suggestions.length === 0) {
      body.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 24px 0;">No compatible tracks found in your library.</p>';
    } else {
      body.innerHTML = suggestions.map(s => {
        const score = Math.round(s.score || 0);
        const key = _advisorEscHtml(s.final_key || '—');
        const bpm = s.final_bpm ? Math.round(s.final_bpm) : '—';
        const title = _advisorEscHtml(s.display_title || 'Unknown');
        const artist = _advisorEscHtml(s.display_artist || '');
        const safePath = _advisorEscHtml(s.file_path || '');
        const barColor = score >= 75 ? '#4caf50' : score >= 50 ? '#ff9800' : '#f44336';
        return `
          <div class="advisor-card" style="border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
              <div>
                <div style="font-weight: 600; font-size: 14px;">${title}</div>
                <div style="color: var(--text-secondary); font-size: 12px; margin-top: 2px;">${artist}</div>
              </div>
              <button class="btn btn-secondary advisor-add-btn" data-path="${safePath}"
                style="font-size: 11px; padding: 4px 10px; white-space: nowrap; margin-left: 12px;">
                Add to Set Plan
              </button>
            </div>
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 6px;">
              <div style="flex: 1;">
                <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-secondary); margin-bottom: 3px;">
                  <span>Match</span><span>${score}%</span>
                </div>
                <div style="background: var(--border); border-radius: 4px; height: 6px; overflow: hidden;">
                  <div style="width: ${score}%; height: 100%; background: ${barColor}; border-radius: 4px; transition: width 0.3s;"></div>
                </div>
              </div>
              <div style="display: flex; gap: 10px; font-size: 11px; white-space: nowrap;">
                <span style="background: var(--bg-secondary, #1a1a2e); padding: 2px 8px; border-radius: 4px; font-family: monospace;">${key}</span>
                <span style="color: var(--text-secondary);">${bpm} BPM</span>
              </div>
            </div>
          </div>`;
      }).join('');

      // Attach Add to Set Plan listeners via JS (avoids inline onclick with path data)
      body.querySelectorAll('.advisor-add-btn').forEach(btn => {
        btn.addEventListener('click', () => {
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
  const modal = document.getElementById('advisor-modal');
  const closeBtn = document.getElementById('advisor-modal-close');
  if (!modal || !closeBtn) return;

  closeBtn.addEventListener('click', () => { modal.style.display = 'none'; });
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.style.display = 'none';
  });
}

