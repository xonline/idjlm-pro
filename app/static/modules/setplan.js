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
  window._currentDetailTrack = track;
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
  const lufs = track.analyzed_lufs != null ? track.analyzed_lufs + ' LUFS' : 'N/A';
  const lufsRange = track.analyzed_lufs_range != null ? track.analyzed_lufs_range + ' LU' : 'N/A';
  const truePeak = track.analyzed_true_peak != null ? track.analyzed_true_peak + ' dBTP' : 'N/A';

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
        <div class="metadata-item"><span class="label">LUFS:</span> <span class="value">${escapeHtml(lufs)}</span></div>
        <div class="metadata-item"><span class="label">LUFS Range:</span> <span class="value">${escapeHtml(lufsRange)}</span></div>
        <div class="metadata-item"><span class="label">True Peak:</span> <span class="value">${escapeHtml(truePeak)}</span></div>
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
      <button class="btn btn-primary" onclick="addTrackToSetlist('${track.file_path.replace(/'/g, "&#39;")}')">Add to Setlist</button>
      <button class="btn btn-secondary" onclick="showNextTrackAdvisor('${track.file_path.replace(/'/g, "&#39;")}')">Next Track Advisor</button>
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

      showSpinner('Analysing cue points...');
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

  // Render energy timeline
  renderEnergyTimeline();
}

function renderEnergyTimeline() {
  const panel = document.getElementById('energy-timeline-panel');
  const summaryEl = document.getElementById('energy-timeline-summary');
  const canvas = document.getElementById('chart-energy-timeline');

  if (!panel || !canvas) return;

  if (window.setlist.length < 2) {
    panel.style.display = 'none';
    return;
  }

  panel.style.display = '';

  const energies = window.setlist.map((t, idx) => {
    const energy = parseFloat(t.analyzed_energy) || parseFloat(t.energy) || 0;
    return { idx: idx + 1, energy: energy, title: t.display_title || 'Unknown' };
  });

  const validEnergies = energies.filter(e => e.energy > 0);
  if (validEnergies.length === 0) {
    panel.style.display = 'none';
    return;
  }

  const minE = Math.min(...validEnergies.map(e => e.energy));
  const maxE = Math.max(...validEnergies.map(e => e.energy));
  const range = maxE - minE;

  if (summaryEl) {
    if (range >= 4) {
      const arcType = maxE > minE ? 'Classic warm-up to peak to cool-down arc' : 'Flat energy';
      summaryEl.textContent = `Energy range: ${Math.round(minE)}-${Math.round(maxE)}. ${arcType}`;
    } else if (range >= 2) {
      summaryEl.textContent = `Energy range: ${Math.round(minE)}-${Math.round(maxE)}. Moderate variation — consider building more contrast.`;
    } else {
      summaryEl.textContent = `Energy range: ${Math.round(minE)}-${Math.round(maxE)}. Flat energy — consider adding variety.`;
    }
  }

  if (typeof Chart === 'undefined') return;

  if (chartInstances.energyTimeline) {
    chartInstances.energyTimeline.destroy();
  }

  const labels = energies.map(e => `#${e.idx}`);
  const data = energies.map(e => e.energy);

  chartInstances.energyTimeline = new Chart(canvas, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Energy',
        data: data,
        borderColor: '#8b5cf6',
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointRadius: 5,
        pointHoverRadius: 8,
        pointBackgroundColor: data.map(e => {
          if (e >= 8) return '#f87171';
          if (e >= 6) return '#fbbf24';
          if (e >= 4) return '#34d399';
          return '#60a5fa';
        }),
        pointBorderColor: 'transparent',
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: function(items) {
              if (items.length === 0) return '';
              const idx = items[0].dataIndex;
              return window.setlist[idx] ? (window.setlist[idx].display_title || 'Unknown') : '';
            },
            label: function(context) {
              const val = context.parsed.y;
              const track = window.setlist[context.dataIndex];
              const bpm = track && track.final_bpm ? track.final_bpm + ' BPM' : '';
              const key = track && track.final_key ? track.final_key : '';
              return [`Energy: ${val}/10`, bpm, key].filter(Boolean).join(' | ');
            }
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: 'Track Position', color: '#6a6a94' },
          ticks: { color: '#6a6a94', maxTicksLimit: 20 },
          grid: { color: 'rgba(42, 42, 58, 0.5)' }
        },
        y: {
          min: 0,
          max: 10,
          title: { display: true, text: 'Energy Level', color: '#6a6a94' },
          ticks: { color: '#6a6a94', stepSize: 2 },
          grid: { color: 'rgba(42, 42, 58, 0.5)' }
        }
      }
    }
  });
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

  // BPM transition analysis
  if (d.transitions && d.transitions.length > 0) {
    const smooth = s.smooth_transitions || 0;
    const challenging = s.challenging_transitions || 0;
    const total = d.transitions.length;
    const transitionColor = challenging > 0 ? 'var(--danger)' : smooth === total ? '#22c55e' : '#f0a500';
    html += `<div class="transitions-summary" style="padding:10px 14px;background:var(--bg-secondary);border-radius:8px;margin-bottom:12px;font-size:13px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
        <span style="font-weight:600;">🎵 BPM Transitions</span>
        <span style="color:${transitionColor};font-weight:700;">${smooth}/${total} smooth</span>
      </div>
      <div class="transitions-list" style="max-height:120px;overflow-y:auto;">`;
    d.transitions.forEach(tr => {
      const emoji = tr.rating === 'smooth' ? '🟢' : tr.rating === 'moderate' ? '🟡' : tr.rating === 'challenging' ? '🟠' : '🔴';
      const deltaStr = tr.bpm_delta > 0 ? `+${tr.bpm_delta}` : tr.bpm_delta;
      html += `<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid var(--border-color);">
        <span>${escapeHtml(tr.from)} → ${escapeHtml(tr.to)}</span>
        <span style="color:var(--text-muted);">${deltaStr} BPM (${tr.bpm_pct_change}%)</span>
        <span>${emoji} ${tr.rating}</span>
      </div>`;
    });
    html += `</div></div>`;
  }

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

