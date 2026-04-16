// ============================================================================
// Initialization
// ============================================================================

// ─── Threshold localStorage persistence ───────────────────────────────────────
function initThresholdPersistence() {
  const input = document.getElementById('toolbar-threshold');
  if (!input) return;
  const saved = localStorage.getItem('idjlm-threshold');
  if (saved) input.value = saved;
  input.addEventListener('change', () => {
    localStorage.setItem('idjlm-threshold', input.value);
  });
  // Stop click on input from firing the parent button
  input.addEventListener('click', e => e.stopPropagation());
}

// ─── Keyboard shortcuts for track table ──────────────────────────────────────
// Space = approve/unapprove selected row
// ArrowUp / ArrowDown = navigate rows
(function initKeyboardNav() {
  let selectedIdx = -1;

  function getRows() {
    return Array.from(document.querySelectorAll('#tracks-tbody tr:not(.empty-state)'));
  }

  function selectRow(idx) {
    const rows = getRows();
    rows.forEach(r => r.classList.remove('row-selected'));
    if (idx < 0 || idx >= rows.length) { selectedIdx = -1; return; }
    selectedIdx = idx;
    rows[idx].classList.add('row-selected');
    rows[idx].scrollIntoView({ block: 'nearest' });
  }

  document.addEventListener('keydown', e => {
    // Ignore when typing in an input/textarea
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

    const rows = getRows();
    if (!rows.length) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectRow(Math.min(selectedIdx + 1, rows.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectRow(Math.max(selectedIdx - 1, 0));
    } else if (e.key === ' ' && selectedIdx >= 0) {
      e.preventDefault();
      const approveBtn = rows[selectedIdx].querySelector('.approve-btn');
      if (approveBtn) approveBtn.click();
    }
  });

  // Re-select same logical row after renderTracks() re-draws the table
  const origRender = window.renderTracks;
  if (typeof origRender === 'function') {
    // renderTracks is already defined — patch it
    const _orig = window.renderTracks || renderTracks;
  }
  // Hook via MutationObserver instead (renderTracks rebuilds innerHTML)
  const observer = new MutationObserver(() => {
    const rows = getRows();
    if (selectedIdx >= 0 && selectedIdx < rows.length) {
      rows[selectedIdx].classList.add('row-selected');
    }
  });
  const tbody = document.getElementById('tracks-tbody');
  if (tbody) observer.observe(tbody, { childList: true });
})();

function initWorkflowGuide() {
  // Show workflow guide on first run (if no tracks imported yet)
  var guide = document.getElementById('workflow-guide');
  if (!guide) return;

  if (!localStorage.getItem('idjlm-workflow-seen')) {
    var store = window.tracks || [];
    if (store.length === 0) {
      guide.style.display = 'block';
    }
  }

  var closeBtn = document.getElementById('close-workflow-guide');
  if (closeBtn) {
    closeBtn.addEventListener('click', function() {
      guide.style.display = 'none';
      localStorage.setItem('idjlm-workflow-seen', '1');
    });
  }
}

function saveSetlistToStorage() {
  localStorage.setItem('idjlm-setlist', JSON.stringify(window.setlist || []));
}

function loadSetlistFromStorage() {
  try {
    const saved = localStorage.getItem('idjlm-setlist');
    if (saved) window.setlist = JSON.parse(saved);
  } catch(e) {
    window.setlist = [];
  }
}

// ============================================================================
// Feature 1: Audio Player Bottom Bar
// ============================================================================

let currentPlayingTrack = null;
let currentTrackIndex = -1;

function initAudioPlayer() {
  const bar = document.getElementById('audio-player-bar');
  const audio = document.getElementById('audio-player');
  const playPauseBtn = document.getElementById('audio-play-pause');
  const prevBtn = document.getElementById('audio-prev');
  const nextBtn = document.getElementById('audio-next');
  const seekBar = document.getElementById('audio-seek');
  const timeDisplay = document.getElementById('audio-time');

  audio.addEventListener('timeupdate', () => {
    const duration = audio.duration || 0;
    const current = audio.currentTime || 0;
    seekBar.value = duration > 0 ? (current / duration) * 100 : 0;
    timeDisplay.textContent = formatTime(current) + ' / ' + formatTime(duration);
  });

  audio.addEventListener('ended', () => {
    playPauseBtn.textContent = '▶';
    nextBtn.click();
  });

  playPauseBtn.addEventListener('click', () => {
    if (audio.paused) {
      audio.play();
      playPauseBtn.textContent = '⏸';
    } else {
      audio.pause();
      playPauseBtn.textContent = '▶';
    }
  });

  prevBtn.addEventListener('click', () => {
    if (currentTrackIndex > 0) {
      currentTrackIndex--;
      playTrack(window.tracks[currentTrackIndex]);
    }
  });

  nextBtn.addEventListener('click', () => {
    if (currentTrackIndex < window.tracks.length - 1) {
      currentTrackIndex++;
      playTrack(window.tracks[currentTrackIndex]);
    }
  });

  seekBar.addEventListener('change', () => {
    const duration = audio.duration || 0;
    audio.currentTime = (seekBar.value / 100) * duration;
  });
}

function playTrack(track) {
  if (!track) return;

  const audio = document.getElementById('audio-player');
  const bar = document.getElementById('audio-player-bar');
  const playPauseBtn = document.getElementById('audio-play-pause');

  currentPlayingTrack = track;
  currentTrackIndex = window.tracks.indexOf(track);

  audio.src = `/api/audio?path=${encodeURIComponent(track.file_path)}`;
  document.getElementById('audio-track-title').textContent = track.display_title || 'Unknown';
  document.getElementById('audio-track-artist').textContent = track.display_artist || 'Unknown';

  bar.classList.remove('hidden');
  audio.load();

  audio.addEventListener('canplay', function onCanPlay() {
    audio.removeEventListener('canplay', onCanPlay);
    audio.play().catch(err => {
      showToast('Could not play audio', 'error');
      console.error('Audio error:', err);
      if (playPauseBtn) playPauseBtn.textContent = '▶';
    });
  }, { once: true });

  audio.addEventListener('error', function onAudioError() {
    audio.removeEventListener('error', onAudioError);
    showToast('Could not load audio — check file format', 'error');
    bar.classList.add('hidden');
  }, { once: true });
  playPauseBtn.textContent = '⏸';
}

function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

// ============================================================================
// Feature 2: Confidence Badges & Energy Bars
// ============================================================================

function confidenceBadge(score) {
  if (!score && score !== 0) return '—';
  const cls = score >= 80 ? 'high' : score >= 50 ? 'mid' : 'low';
  return `<span class="confidence-badge confidence-${cls}">${Math.round(score)}%</span>`;
}

function energyBar(energy) {
  if (!energy && energy !== 0) return '—';
  const pct = (energy / 10) * 100;
  const color = energy >= 8 ? '#f87171' : energy >= 5 ? '#fbbf24' : '#34d399';
  return `<div class="energy-bar-wrap"><div class="energy-bar" style="width:${pct}%;background:${color}"></div><span>${energy.toFixed(1)}</span></div>`;
}

// ============================================================================
// Feature 3: Genre Color Chips
// ============================================================================

const GENRE_COLORS = ['#8b5cf6','#06b6d4','#f59e0b','#10b981','#ef4444','#ec4899','#6366f1','#14b8a6'];

function genreChip(genre) {
  if (!genre) return '—';
  const hash = [...genre].reduce((a,c)=>a+c.charCodeAt(0),0);
  const color = GENRE_COLORS[hash % GENRE_COLORS.length];
  return `<span class="genre-chip" style="background:${color}22;color:${color};border:1px solid ${color}44">${escapeHtml(genre)}</span>`;
}

// ============================================================================
// Feature 4: Column Toggle
// ============================================================================

function initColumnToggle() {
  // Load saved column state from localStorage
  const saved = localStorage.getItem('idlm-column-toggle');
  window.columnVisibility = saved ? JSON.parse(saved) : {
    bpm: true,
    key: true,
    energy: true,
    genre: true,
    subgenre: true,
    confidence: true,
    year: true
  };
}

function getColumnToggleMenu() {
  const menu = document.createElement('div');
  menu.className = 'column-toggle-menu';

  const columns = [
    { key: 'genre', label: 'Genre' },
    { key: 'subgenre', label: 'Comments' },
    { key: 'bpm', label: 'BPM' },
    { key: 'key', label: 'Key' },
    { key: 'energy', label: 'Energy' },
    { key: 'confidence', label: 'Confidence' },
    { key: 'year', label: 'Year' }
  ];

  columns.forEach(col => {
    const item = document.createElement('label');
    item.className = 'column-toggle-item';
    const checked = window.columnVisibility[col.key];
    item.innerHTML = `<input type="checkbox" ${checked ? 'checked' : ''} data-column="${col.key}"> ${col.label}`;
    item.querySelector('input').addEventListener('change', (e) => {
      window.columnVisibility[col.key] = e.target.checked;
      localStorage.setItem('idlm-column-toggle', JSON.stringify(window.columnVisibility));
      renderTracks();
    });
    menu.appendChild(item);
  });

  return menu;
}

// ============================================================================
// Feature 5: Status Indicators
// ============================================================================

function statusDot(status) {
  const statusMap = {
    'pending': 'pending',
    'analyzed': 'analyzed',
    'classified': 'classified',
    'approved': 'approved',
    'error': 'error'
  };
  const cls = statusMap[status] || 'pending';
  return `<span class="status-dot status-${cls}" title="${status}"></span>`;
}

// ============================================================================
// Feature 6: Camelot Wheel Tab (unused — no wheel tab in current UI)
// ============================================================================

function _initWheelTabUnused() {
  const wheelBtn = document.querySelector('[data-tab="wheel"]');
  if (wheelBtn) {
    wheelBtn.addEventListener('click', _renderCamelotWheelUnused);
  }
}

function _renderCamelotWheelUnused() {
  const svg = document.getElementById('camelot-wheel-svg');
  const stats = document.getElementById('wheel-stats');

  svg.innerHTML = '';

  // Camelot wheel: 12 positions, 2 per position (A=minor, B=major)
  const positions = [];
  for (let i = 1; i <= 12; i++) {
    positions.push({ num: i, key: `${i}A`, mode: 'minor' });
    positions.push({ num: i, key: `${i}B`, mode: 'major' });
  }

  const centerX = 225, centerY = 225, outerR = 200, innerR = 140;
  const segmentAngle = 360 / 24;

  // Draw segments
  positions.forEach((pos, idx) => {
    const startAngle = idx * segmentAngle - 90;
    const endAngle = (idx + 1) * segmentAngle - 90;

    const isMinor = pos.mode === 'minor';
    const startRad = (startAngle * Math.PI) / 180;
    const endRad = (endAngle * Math.PI) / 180;

    const r1 = isMinor ? innerR : innerR + (outerR - innerR) / 2;
    const r2 = isMinor ? innerR + (outerR - innerR) / 2 : outerR;

    const x1 = centerX + r1 * Math.cos(startRad);
    const y1 = centerY + r1 * Math.sin(startRad);
    const x2 = centerX + r2 * Math.cos(startRad);
    const y2 = centerY + r2 * Math.sin(startRad);
    const x3 = centerX + r2 * Math.cos(endRad);
    const y3 = centerY + r2 * Math.sin(endRad);
    const x4 = centerX + r1 * Math.cos(endRad);
    const y4 = centerY + r1 * Math.sin(endRad);

    const color = isMinor ? 'rgba(96,165,250,0.3)' : 'rgba(139,92,246,0.3)';
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.style.cursor = 'pointer';

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const d = `M ${x1} ${y1} L ${x2} ${y2} A ${r2} ${r2} 0 0 1 ${x3} ${y3} L ${x4} ${y4} A ${r1} ${r1} 0 0 0 ${x1} ${y1} Z`;
    path.setAttribute('d', d);
    path.setAttribute('fill', color);
    path.setAttribute('stroke', isMinor ? '#60a5fa' : '#8b5cf6');
    path.setAttribute('stroke-width', '0.5');

    g.appendChild(path);

    // Label
    const midAngle = ((startAngle + endAngle) / 2 * Math.PI) / 180;
    const labelR = (r1 + r2) / 2;
    const lx = centerX + labelR * Math.cos(midAngle);
    const ly = centerY + labelR * Math.sin(midAngle);

    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', lx);
    text.setAttribute('y', ly);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('font-size', '10');
    text.setAttribute('font-weight', '600');
    text.setAttribute('fill', isMinor ? '#60a5fa' : '#8b5cf6');
    text.textContent = pos.key;

    g.appendChild(text);

    // Click to filter
    g.addEventListener('click', () => {
      const filtered = window.tracks.filter(t => t.final_key === pos.key);
      showToast(`Found ${filtered.length} tracks in key ${pos.key}`, 'info');
    });

    svg.appendChild(g);
  });

  // Center circle
  const center = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  center.setAttribute('cx', centerX);
  center.setAttribute('cy', centerY);
  center.setAttribute('r', 30);
  center.setAttribute('fill', 'var(--bg-panel)');
  center.setAttribute('stroke', 'var(--border)');
  svg.appendChild(center);

  // Render stats
  const keyCounts = {};
  window.tracks.forEach(t => {
    if (t.final_key) {
      keyCounts[t.final_key] = (keyCounts[t.final_key] || 0) + 1;
    }
  });

  const sorted = Object.entries(keyCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12);

  stats.innerHTML = '<div class="wheel-stats-section"><h3>Top Keys</h3>' +
    '<div>' + sorted.map(([key, count]) =>
      `<div class="wheel-key-item"><span>${key}</span><span>${count}</span></div>`
    ).join('') + '</div></div>';
}

// ============================================================================
// Feature: Key Compatibility Graph
// ============================================================================

let keyGraphState = {
  nodes: [],
  edges: [],
  hoveredNode: null,
  selectedNode: null,
  animFrame: null,
};

function initKeyGraph() {
  const showBtn = document.getElementById('btn-show-key-graph');
  const closeBtn = document.getElementById('key-graph-close');
  const doneBtn = document.getElementById('key-graph-done');
  const sourceSelect = document.getElementById('key-graph-source');

  if (showBtn) {
    showBtn.addEventListener('click', () => {
      const modal = document.getElementById('key-graph-modal');
      if (modal) {
        modal.style.display = 'block';
        renderKeyCompatibilityGraph();
      }
    });
  }

  if (closeBtn) closeBtn.addEventListener('click', closeKeyGraph);
  if (doneBtn) doneBtn.addEventListener('click', closeKeyGraph);

  if (sourceSelect) {
    sourceSelect.addEventListener('change', () => renderKeyCompatibilityGraph());
  }

  const modal = document.getElementById('key-graph-modal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeKeyGraph();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal && modal.style.display === 'block') {
      closeKeyGraph();
    }
  });
}

function closeKeyGraph() {
  const modal = document.getElementById('key-graph-modal');
  if (modal) modal.style.display = 'none';
  if (keyGraphState.animFrame) {
    cancelAnimationFrame(keyGraphState.animFrame);
    keyGraphState.animFrame = null;
  }
}

function renderKeyCompatibilityGraph(tracks) {
  const canvas = document.getElementById('key-graph-canvas');
  const infoEl = document.getElementById('key-graph-info');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const container = canvas.parentElement;
  const dpr = window.devicePixelRatio || 1;
  const rect = container.getBoundingClientRect();

  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  canvas.style.width = rect.width + 'px';
  canvas.style.height = rect.height + 'px';
  ctx.scale(dpr, dpr);

  const W = rect.width;
  const H = rect.height;

  // Determine track source
  const sourceSelect = document.getElementById('key-graph-source');
  const source = sourceSelect ? sourceSelect.value : 'library';
  let sourceTracks = source === 'setlist' ? window.setlist : window.tracks;
  if (tracks) sourceTracks = tracks;

  // Filter to tracks with a valid key
  const keyedTracks = sourceTracks.filter(t => t.final_key && /^[0-9]+[ABab]$/.test(t.final_key));

  if (keyedTracks.length === 0) {
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#6a6a94';
    ctx.font = '14px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('No tracks with Camelot keys to display', W / 2, H / 2);
    if (infoEl) infoEl.textContent = '0 tracks';
    return;
  }

  // Limit nodes for performance
  const MAX_NODES = 200;
  const displayTracks = keyedTracks.slice(0, MAX_NODES);

  // Build nodes grouped by key
  const keyGroups = {};
  displayTracks.forEach((t, idx) => {
    const key = t.final_key.toUpperCase();
    if (!keyGroups[key]) keyGroups[key] = [];
    keyGroups[key].push({ index: idx, track: t });
  });

  const keys = Object.keys(keyGroups).sort((a, b) => {
    const numA = parseInt(a);
    const numB = parseInt(b);
    if (numA !== numB) return numA - numB;
    return a.localeCompare(b);
  });

  // Genre color map
  const genreColors = {};
  const palette = ['#8b5cf6', '#34d399', '#f59e0b', '#60a5fa', '#f87171', '#a78bfa', '#fbbf24', '#22d3a0', '#fb923c', '#818cf8', '#38bdf8', '#a3e635'];
  let colorIdx = 0;
  displayTracks.forEach(t => {
    const genre = t.final_genre || 'Unknown';
    if (!genreColors[genre]) {
      genreColors[genre] = palette[colorIdx % palette.length];
      colorIdx++;
    }
  });

  function getNodeColor(track) {
    const genre = track.final_genre || 'Unknown';
    return genreColors[genre] || '#888';
  }

  // Layout: position nodes by key, spread within key group
  const nodes = [];
  const keyCenters = {};
  const padding = 60;
  const usableW = W - padding * 2;
  const usableH = H - padding * 2;

  keys.forEach((key, ki) => {
    const angle = (ki / keys.length) * Math.PI * 2 - Math.PI / 2;
    const radius = Math.min(usableW, usableH) * 0.35;
    const cx = W / 2 + Math.cos(angle) * radius;
    const cy = H / 2 + Math.sin(angle) * radius;
    keyCenters[key] = { x: cx, y: cy };
  });

  displayTracks.forEach((t, idx) => {
    const key = t.final_key.toUpperCase();
    const group = keyGroups[key];
    const gi = group.findIndex(g => g.index === idx);
    const center = keyCenters[key];
    const spread = 30;

    let x, y;
    if (group.length === 1) {
      x = center.x;
      y = center.y;
    } else {
      const angle = (gi / group.length) * Math.PI * 2;
      x = center.x + Math.cos(angle) * spread;
      y = center.y + Math.sin(angle) * spread;
    }

    nodes.push({
      x: x,
      y: y,
      vx: 0,
      vy: 0,
      track: t,
      key: key,
      color: getNodeColor(t),
      radius: 8,
    });
  });

  // Build edges using isCompatibleKey
  const edges = [];
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      if (isCompatibleKey(nodes[i].key, nodes[j].key)) {
        edges.push({ source: i, target: j });
      }
    }
  }

  keyGraphState.nodes = nodes;
  keyGraphState.edges = edges;
  keyGraphState.hoveredNode = null;
  keyGraphState.selectedNode = null;

  if (infoEl) {
    infoEl.textContent = `${nodes.length} tracks, ${edges.length} connections`;
  }

  // Simple force-directed layout refinement
  const iterations = 60;
  const repulsion = 800;
  const attraction = 0.005;
  const damping = 0.85;
  const idealLength = 50;

  for (let iter = 0; iter < iterations; iter++) {
    const temp = 1 - iter / iterations;

    // Repulsion between all nodes
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[j].x - nodes[i].x;
        const dy = nodes[j].y - nodes[i].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = repulsion / (dist * dist) * temp;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        nodes[i].vx -= fx;
        nodes[i].vy -= fy;
        nodes[j].vx += fx;
        nodes[j].vy += fy;
      }
    }

    // Attraction along edges
    for (const edge of edges) {
      const a = nodes[edge.source];
      const b = nodes[edge.target];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - idealLength) * attraction * temp;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      a.vx += fx;
      a.vy += fy;
      b.vx -= fx;
      b.vy -= fy;
    }

    // Attract to key centers
    for (let i = 0; i < nodes.length; i++) {
      const center = keyCenters[nodes[i].key];
      if (center) {
        nodes[i].vx += (center.x - nodes[i].x) * 0.02 * temp;
        nodes[i].vy += (center.y - nodes[i].y) * 0.02 * temp;
      }
    }

    // Apply velocity with damping
    for (let i = 0; i < nodes.length; i++) {
      nodes[i].vx *= damping;
      nodes[i].vy *= damping;
      nodes[i].x += nodes[i].vx;
      nodes[i].y += nodes[i].vy;
      // Keep within bounds
      nodes[i].x = Math.max(20, Math.min(W - 20, nodes[i].x));
      nodes[i].y = Math.max(20, Math.min(H - 20, nodes[i].y));
    }
  }

  // Draw
  function draw() {
    ctx.clearRect(0, 0, W, H);

    // Draw edges
    for (const edge of edges) {
      const a = nodes[edge.source];
      const b = nodes[edge.target];
      const isHighlighted = keyGraphState.selectedNode !== null &&
        (keyGraphState.selectedNode === edge.source || keyGraphState.selectedNode === edge.target);

      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      if (isHighlighted) {
        ctx.strokeStyle = 'rgba(139, 92, 246, 0.8)';
        ctx.lineWidth = 2.5;
      } else {
        ctx.strokeStyle = 'rgba(139, 92, 246, 0.12)';
        ctx.lineWidth = 1;
      }
      ctx.stroke();
    }

    // Draw nodes
    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i];
      const isHovered = keyGraphState.hoveredNode === i;
      const isSelected = keyGraphState.selectedNode === i;
      const isConnected = keyGraphState.selectedNode !== null && edges.some(
        e => (e.source === keyGraphState.selectedNode && e.target === i) ||
             (e.target === keyGraphState.selectedNode && e.source === i)
      );

      const r = isHovered || isSelected ? 12 : node.radius;

      // Glow
      if (isHovered || isSelected) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 6, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(139, 92, 246, 0.2)';
        ctx.fill();
      }

      // Node circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
      ctx.fillStyle = isSelected ? '#8b5cf6' : node.color;
      ctx.fill();
      ctx.strokeStyle = isConnected ? '#fff' : 'rgba(255,255,255,0.3)';
      ctx.lineWidth = isSelected ? 3 : isConnected ? 2 : 1;
      ctx.stroke();

      // Label
      const label = node.track.display_title || 'Unknown';
      const shortLabel = label.length > 18 ? label.substring(0, 16) + '...' : label;
      ctx.fillStyle = isHovered || isSelected ? '#fff' : 'rgba(200, 200, 228, 0.8)';
      ctx.font = `${isHovered || isSelected ? '600' : '400'} 10px -apple-system, BlinkMacSystemFont, sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(shortLabel, node.x, node.y + r + 14);

      // Key label below
      ctx.fillStyle = 'rgba(106, 106, 148, 0.9)';
      ctx.font = '9px -apple-system, BlinkMacSystemFont, sans-serif';
      ctx.fillText(node.key, node.x, node.y + r + 25);
    }
  }

  draw();

  // Interaction: hover and click
  canvas.onmousemove = (e) => {
    const rect2 = canvas.getBoundingClientRect();
    const mx = e.clientX - rect2.left;
    const my = e.clientY - rect2.top;

    let found = null;
    for (let i = 0; i < nodes.length; i++) {
      const dx = mx - nodes[i].x;
      const dy = my - nodes[i].y;
      if (dx * dx + dy * dy < 225) { // 15px radius hit test
        found = i;
        break;
      }
    }

    keyGraphState.hoveredNode = found;
    draw();

    // Tooltip
    const tooltip = document.getElementById('key-graph-tooltip');
    if (tooltip) {
      if (found !== null) {
        const t = nodes[found].track;
        const connections = edges.filter(e => e.source === found || e.target === found).length;
        tooltip.innerHTML = `<div class="tooltip-title">${escapeHtml(t.display_title || 'Unknown')}</div>` +
          `<div>${escapeHtml(t.display_artist || 'Unknown')}</div>` +
          `<div>Key: ${nodes[found].key} | BPM: ${t.final_bpm || '?'}</div>` +
          `<div>Genre: ${escapeHtml(t.final_genre || 'Unknown')}</div>` +
          `<div style="margin-top:4px;color:#a78bfa;">${connections} harmonic connections</div>`;
        tooltip.style.display = 'block';
        tooltip.style.left = (e.clientX - rect2.left + 15) + 'px';
        tooltip.style.top = (e.clientY - rect2.top - 10) + 'px';
      } else {
        tooltip.style.display = 'none';
      }
    }

    canvas.style.cursor = found !== null ? 'pointer' : 'default';
  };

  canvas.onmouseleave = () => {
    keyGraphState.hoveredNode = null;
    draw();
    const tooltip = document.getElementById('key-graph-tooltip');
    if (tooltip) tooltip.style.display = 'none';
    canvas.style.cursor = 'default';
  };

  canvas.onclick = (e) => {
    const rect2 = canvas.getBoundingClientRect();
    const mx = e.clientX - rect2.left;
    const my = e.clientY - rect2.top;

    let found = null;
    for (let i = 0; i < nodes.length; i++) {
      const dx = mx - nodes[i].x;
      const dy = my - nodes[i].y;
      if (dx * dx + dy * dy < 225) {
        found = i;
        break;
      }
    }

    if (found !== null) {
      keyGraphState.selectedNode = keyGraphState.selectedNode === found ? null : found;
    } else {
      keyGraphState.selectedNode = null;
    }
    draw();
  };
}

// ============================================================================
// Keyboard Shortcuts Reference Modal
// ============================================================================

function showKeyboardShortcuts() {
  const modal = document.getElementById('shortcuts-modal');
  if (modal) modal.style.display = 'flex';
}

// ============================================================================
// Keyboard Shortcuts
// ============================================================================

function initKeyboardShortcuts() {
  // Shortcuts modal: close handlers
  const shortcutsModal = document.getElementById('shortcuts-modal');
  const shortcutsCloseBtn = document.getElementById('shortcuts-close');
  const shortcutsDoneBtn = document.getElementById('shortcuts-done');

  const hideShortcutsModal = () => { if (shortcutsModal) shortcutsModal.style.display = 'none'; };
  if (shortcutsCloseBtn) shortcutsCloseBtn.addEventListener('click', hideShortcutsModal);
  if (shortcutsDoneBtn) shortcutsDoneBtn.addEventListener('click', hideShortcutsModal);
  if (shortcutsModal) {
    shortcutsModal.addEventListener('click', (e) => {
      if (e.target === shortcutsModal) hideShortcutsModal();
    });
  }

  // Show hints in review tab
  const reviewTab = document.getElementById('tab-review');
  let hintsAdded = false;

  const reviewBtn = document.querySelector('[data-tab="review"]');
  if (reviewBtn) {
    reviewBtn.addEventListener('click', () => {
      if (!hintsAdded) {
        const header = reviewTab.querySelector('.tab-header');
        const hints = document.createElement('div');
        hints.className = 'keyboard-hints';
        hints.innerHTML = `
          <div class="keyboard-hints-grid">
            <div class="keyboard-hint-item"><span class="keyboard-hint-key">↓/j</span> <span>Next</span></div>
            <div class="keyboard-hint-item"><span class="keyboard-hint-key">↑/k</span> <span>Prev</span></div>
            <div class="keyboard-hint-item"><span class="keyboard-hint-key">a</span> <span>Approve</span></div>
            <div class="keyboard-hint-item"><span class="keyboard-hint-key">s</span> <span>Skip</span></div>
            <div class="keyboard-hint-item"><span class="keyboard-hint-key">Space</span> <span>Play/Pause</span></div>
          </div>
        `;
        header.parentNode.insertBefore(hints, header.nextSibling);
        hintsAdded = true;
      }
    });
  }

  document.addEventListener('keydown', (e) => {
    const reviewTab = document.getElementById('tab-review');
    if (!reviewTab.classList.contains('active')) return;

    const items = document.querySelectorAll('.review-item');
    const currentBtn = document.querySelector('.review-item:first-child [data-approve-btn]');

    if (e.code === 'ArrowDown' || e.key === 'j') {
      e.preventDefault();
      // Next track
    } else if (e.code === 'ArrowUp' || e.key === 'k') {
      e.preventDefault();
      // Previous track
    } else if (e.key === 'a' || e.code === 'Enter') {
      e.preventDefault();
      const btn = document.querySelector('.review-item:first-child [data-approve-btn]');
      if (btn) btn.click();
    } else if (e.key === 's' || e.code === 'Delete' || e.code === 'Backspace') {
      e.preventDefault();
      const btn = document.querySelector('.review-item:first-child [data-skip-btn]');
      if (btn) btn.click();
    } else if (e.code === 'Space') {
      e.preventDefault();
      document.getElementById('audio-play-pause').click();
    }
  });

  // Global shortcut: ? or Cmd+/ to open keyboard shortcuts reference
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const shortcutsModal = document.getElementById('shortcuts-modal');
      if (shortcutsModal && shortcutsModal.style.display !== 'none') {
        shortcutsModal.style.display = 'none';
        return;
      }
    }
    if ((e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey) ||
        (e.key === '/' && (e.ctrlKey || e.metaKey))) {
      // Don't trigger when typing in an input/textarea
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag !== 'input' && tag !== 'textarea' && !e.target.isContentEditable) {
        e.preventDefault();
        showKeyboardShortcuts();
      }
    }
    // Single / to focus search (when not in an input)
    if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag !== 'input' && tag !== 'textarea' && !e.target.isContentEditable) {
        const searchInput = document.getElementById('search-tracks');
        if (searchInput) {
          e.preventDefault();
          searchInput.focus();
        }
      }
    }
    // Number keys 1-4 for tab switching
    const tabMap = { '1': 'library', '2': 'organise', '3': 'setplan', '4': 'settings' };
    if (tabMap[e.key] && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag !== 'input' && tag !== 'textarea' && !e.target.isContentEditable) {
        e.preventDefault();
        switchTab(tabMap[e.key]);
      }
    }
    // Ctrl+S to save session
    if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag !== 'input' && tag !== 'textarea' && !e.target.isContentEditable) {
        e.preventDefault();
        apiFetch('/api/session/save', { method: 'POST' }).then(() => {
          showToast('Session saved', 'success');
        }).catch(() => {});
      }
    }
  });
}

// ============================================================================
// Feature 8: Duplicates Tab
// ============================================================================

function initDuplicatesTab() {
  const scanBtn = document.getElementById('btn-scan-duplicates');
  if (scanBtn) {
    scanBtn.addEventListener('click', scanForDuplicates);
  }
}

// ============================================================================
// Organise Tab Init (called lazily from switchTab on first visit)
// ============================================================================

let organiseTabInited = false;
function initOrganiseTab() {
  if (organiseTabInited) return;
  organiseTabInited = true;

  document.getElementById('btn-refresh-health')?.addEventListener('click', loadLibraryHealth);
  document.getElementById('btn-parse-filenames')?.addEventListener('click', parseFilenames);
  document.getElementById('btn-organise-preview')?.addEventListener('click', previewOrganise);
  document.getElementById('btn-organise-run')?.addEventListener('click', runOrganise);
  document.getElementById('btn-validate-keys')?.addEventListener('click', validateKeys);
  initDuplicatesTab();
  loadLibraryHealth();
}

// ============================================================================
// Set Planner Tab Init (called lazily from switchTab on first visit)
// ============================================================================

let setplanTabInited = false;
function initSetPlanTab() {
  if (setplanTabInited) return;
  setplanTabInited = true;

  document.getElementById('btn-generate-set')?.addEventListener('click', generateSet);

  // Populate genre filter from taxonomy
  const genreSelect = document.getElementById('setplan-genre');
  if (genreSelect && window.taxonomy) {
    Object.keys(window.taxonomy).forEach(genre => {
      const opt = document.createElement('option');
      opt.value = genre;
      opt.textContent = genre;
      genreSelect.appendChild(opt);
    });
  }

  loadSetplanArcs();
}

// ============================================================================
// Playlists Tab Init (called lazily from switchTab on first visit)
// ============================================================================

let playlistsTabInited = false;
let currentPlaylistId = null;
let currentPlaylistTracks = [];

function initPlaylistsTab() {
  if (playlistsTabInited) return;
  playlistsTabInited = true;

  document.getElementById('btn-new-playlist')?.addEventListener('click', () => createNewPlaylist());
  document.getElementById('btn-new-playlist-empty')?.addEventListener('click', () => createNewPlaylist());
  document.getElementById('btn-save-playlist')?.addEventListener('click', () => saveCurrentPlaylist());
  document.getElementById('btn-run-playlist')?.addEventListener('click', () => runCurrentPlaylist());
  document.getElementById('btn-export-playlist')?.addEventListener('click', () => exportCurrentPlaylist());
  document.getElementById('btn-delete-playlist')?.addEventListener('click', () => deleteCurrentPlaylist());
  document.getElementById('btn-apply-filters')?.addEventListener('click', () => applyPlaylistFilters());
  document.getElementById('btn-clear-filters')?.addEventListener('click', () => clearPlaylistFilters());
  document.getElementById('btn-add-all-to-playlist')?.addEventListener('click', () => addAllResultsToPlaylist());
  document.getElementById('pl-select-all')?.addEventListener('change', (e) => toggleSelectAllPlaylistResults(e.target.checked));

  // Populate genre filter from taxonomy
  populatePlaylistGenreFilter();

  loadPlaylists();
}

function populatePlaylistGenreFilter() {
  const genreSelect = document.getElementById('pl-filter-genre');
  const subgenreSelect = document.getElementById('pl-filter-subgenre');
  if (genreSelect && window.taxonomy) {
    Object.keys(window.taxonomy).forEach(genre => {
      const opt = document.createElement('option');
      opt.value = genre;
      opt.textContent = genre;
      genreSelect.appendChild(opt);
    });
  }
}

async function loadPlaylists() {
  try {
    const data = await apiFetch('/api/playlists');
    renderPlaylistsList(data.playlists || []);
  } catch (e) {
    showToast('Failed to load playlists: ' + e.message, 'error');
  }
}

function renderPlaylistsList(playlists) {
  const container = document.getElementById('playlists-list');
  if (!container) return;
  container.innerHTML = '';

  if (!playlists.length) {
    container.innerHTML = '<div class="empty-state" style="padding: 24px 12px; text-align: center; color: var(--text-secondary); font-size: 13px;">No playlists yet. Click "+ New" to create one.</div>';
    return;
  }

  playlists.forEach(pl => {
    const div = document.createElement('div');
    div.className = 'playlist-item' + (currentPlaylistId === pl.id ? ' active' : '');
    div.innerHTML = `
      <div class="playlist-item-name">${escapeHtml(pl.name)}</div>
      <div class="playlist-item-meta">${pl.track_count} tracks</div>
    `;
    div.addEventListener('click', () => selectPlaylist(pl.id));
    container.appendChild(div);
  });
}

async function selectPlaylist(playlistId) {
  try {
    const pl = await apiFetch('/api/playlists/' + encodeURIComponent(playlistId));
    currentPlaylistId = pl.id;
    currentPlaylistTracks = pl.tracks || [];

    const nameInput = document.getElementById('playlist-name-input');
    if (nameInput) nameInput.value = pl.name || '';

    // Load filters
    const filters = pl.filters || {};
    if (document.getElementById('pl-filter-genre')) document.getElementById('pl-filter-genre').value = filters.genre || '';
    if (document.getElementById('pl-filter-subgenre')) document.getElementById('pl-filter-subgenre').value = filters.subgenre || '';
    if (document.getElementById('pl-filter-status')) document.getElementById('pl-filter-status').value = filters.status || '';
    if (document.getElementById('pl-filter-key')) document.getElementById('pl-filter-key').value = filters.key || '';
    if (document.getElementById('pl-filter-bpm-min')) document.getElementById('pl-filter-bpm-min').value = filters.bpm_min || '';
    if (document.getElementById('pl-filter-bpm-max')) document.getElementById('pl-filter-bpm-max').value = filters.bpm_max || '';
    if (document.getElementById('pl-filter-energy-min')) document.getElementById('pl-filter-energy-min').value = filters.energy_min || '';
    if (document.getElementById('pl-filter-energy-max')) document.getElementById('pl-filter-energy-max').value = filters.energy_max || '';
    if (document.getElementById('pl-filter-year-min')) document.getElementById('pl-filter-year-min').value = filters.year_min || '';
    if (document.getElementById('pl-filter-year-max')) document.getElementById('pl-filter-year-max').value = filters.year_max || '';

    // Show editor, hide empty state
    const editor = document.getElementById('playlist-editor');
    const emptyState = document.getElementById('playlist-empty-state');
    if (editor) editor.style.display = 'block';
    if (emptyState) emptyState.style.display = 'none';

    // Refresh the list to highlight
    await loadPlaylists();
  } catch (e) {
    showToast('Failed to load playlist: ' + e.message, 'error');
  }
}

async function createNewPlaylist() {
  const name = prompt('Playlist name:', 'My Playlist');
  if (!name) return;

  try {
    const result = await apiFetch('/api/playlists', {
      method: 'POST',
      body: JSON.stringify({ name: name, tracks: [], filters: {} })
    });
    showToast('Playlist created', 'success');
    await loadPlaylists();
    await selectPlaylist(result.id);
  } catch (e) {
    showToast('Failed to create playlist: ' + e.message, 'error');
  }
}

async function saveCurrentPlaylist() {
  if (!currentPlaylistId) return;

  const nameInput = document.getElementById('playlist-name-input');
  const filters = getPlaylistFilters();

  try {
    await apiFetch('/api/playlists/' + encodeURIComponent(currentPlaylistId), {
      method: 'PUT',
      body: JSON.stringify({
        name: nameInput ? nameInput.value : 'Untitled',
        filters: filters,
        tracks: currentPlaylistTracks
      })
    });
    showToast('Playlist saved', 'success');
    await loadPlaylists();
  } catch (e) {
    showToast('Failed to save playlist: ' + e.message, 'error');
  }
}

function getPlaylistFilters() {
  return {
    genre: document.getElementById('pl-filter-genre')?.value || '',
    subgenre: document.getElementById('pl-filter-subgenre')?.value || '',
    status: document.getElementById('pl-filter-status')?.value || '',
    key: document.getElementById('pl-filter-key')?.value || '',
    bpm_min: document.getElementById('pl-filter-bpm-min')?.value || '',
    bpm_max: document.getElementById('pl-filter-bpm-max')?.value || '',
    energy_min: document.getElementById('pl-filter-energy-min')?.value || '',
    energy_max: document.getElementById('pl-filter-energy-max')?.value || '',
    year_min: document.getElementById('pl-filter-year-min')?.value || '',
    year_max: document.getElementById('pl-filter-year-max')?.value || '',
  };
}

async function runCurrentPlaylist() {
  if (!currentPlaylistId) return;

  showSpinner('Running playlist...');
  try {
    const result = await apiFetch('/api/playlists/' + encodeURIComponent(currentPlaylistId) + '/run', { method: 'POST' });
    renderPlaylistResults(result.tracks || []);
    showToast(result.count + ' tracks found', 'info');
  } catch (e) {
    showToast('Failed to run playlist: ' + e.message, 'error');
  } finally {
    hideSpinner();
  }
}

async function applyPlaylistFilters() {
  showSpinner('Applying filters...');
  try {
    const filters = getPlaylistFilters();
    const result = await apiFetch('/api/playlists/run', {
      method: 'POST',
      body: JSON.stringify({ filters: filters })
    });
    renderPlaylistResults(result.tracks || []);
    showToast(result.count + ' tracks found', 'info');
  } catch (e) {
    showToast('Failed to apply filters: ' + e.message, 'error');
  } finally {
    hideSpinner();
  }
}

function clearPlaylistFilters() {
  if (document.getElementById('pl-filter-genre')) document.getElementById('pl-filter-genre').value = '';
  if (document.getElementById('pl-filter-subgenre')) document.getElementById('pl-filter-subgenre').value = '';
  if (document.getElementById('pl-filter-status')) document.getElementById('pl-filter-status').value = '';
  if (document.getElementById('pl-filter-key')) document.getElementById('pl-filter-key').value = '';
  if (document.getElementById('pl-filter-bpm-min')) document.getElementById('pl-filter-bpm-min').value = '';
  if (document.getElementById('pl-filter-bpm-max')) document.getElementById('pl-filter-bpm-max').value = '';
  if (document.getElementById('pl-filter-energy-min')) document.getElementById('pl-filter-energy-min').value = '';
  if (document.getElementById('pl-filter-energy-max')) document.getElementById('pl-filter-energy-max').value = '';
  if (document.getElementById('pl-filter-year-min')) document.getElementById('pl-filter-year-min').value = '';
  if (document.getElementById('pl-filter-year-max')) document.getElementById('pl-filter-year-max').value = '';
  document.getElementById('pl-results-tbody').innerHTML = '<tr class="empty-state"><td colspan="10"><div class="empty-state-content"><div class="empty-icon">🎵</div><div class="empty-msg">Apply filters to find tracks</div></div></td></tr>';
  document.getElementById('pl-results-count').textContent = '0';
}

function renderPlaylistResults(tracks) {
  const tbody = document.getElementById('pl-results-tbody');
  const countEl = document.getElementById('pl-results-count');
  if (countEl) countEl.textContent = tracks.length;

  if (!tracks.length) {
    tbody.innerHTML = '<tr class="empty-state"><td colspan="10"><div class="empty-state-content"><div class="empty-icon">🎵</div><div class="empty-msg">No tracks match these filters</div></div></td></tr>';
    return;
  }

  tbody.innerHTML = '';
  tracks.forEach((track, idx) => {
    const tr = document.createElement('tr');
    const inPlaylist = currentPlaylistTracks.includes(track.file_path);
    tr.innerHTML = `
      <td class="checkbox-col"><input type="checkbox" class="pl-result-checkbox" data-path="${escapeHtml(track.file_path)}" ${inPlaylist ? 'checked' : ''} /></td>
      <td class="col-title">${escapeHtml(track.display_title || '')}</td>
      <td class="col-artist">${escapeHtml(track.display_artist || '')}</td>
      <td class="col-genre">${escapeHtml(track.final_genre || '')}</td>
      <td class="col-bpm">${track.final_bpm || '—'}</td>
      <td class="col-key">${escapeHtml(track.final_key || '—')}</td>
      <td class="col-energy">${track.analyzed_energy || '—'}</td>
      <td class="col-year">${track.final_year || '—'}</td>
      <td class="col-status"><span class="badge badge-${track.review_status || 'pending'}">${escapeHtml(track.review_status || 'pending')}</span></td>
      <td class="col-actions">
        <button class="btn btn-secondary btn-sm pl-add-btn" data-path="${escapeHtml(track.file_path)}" ${inPlaylist ? 'disabled' : ''}>${inPlaylist ? 'Added' : '+ Add'}</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach event listeners
  tbody.querySelectorAll('.pl-add-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const path = decodeURIComponent(e.target.dataset.path);
      if (!currentPlaylistTracks.includes(path)) {
        currentPlaylistTracks.push(path);
        e.target.textContent = 'Added';
        e.target.disabled = true;
      }
    });
  });
}

function toggleSelectAllPlaylistResults(checked) {
  document.querySelectorAll('.pl-result-checkbox').forEach(cb => cb.checked = checked);
}

async function addAllResultsToPlaylist() {
  document.querySelectorAll('.pl-result-checkbox:checked').forEach(cb => {
    const path = cb.dataset.path;
    if (!currentPlaylistTracks.includes(path)) {
      currentPlaylistTracks.push(path);
    }
  });
  showToast('Tracks added to playlist', 'success');
}

async function exportCurrentPlaylist() {
  if (!currentPlaylistId) return;
  window.location.href = '/api/playlists/' + encodeURIComponent(currentPlaylistId) + '/export-m3u';
  showToast('Downloading M3U...', 'info');
}

async function deleteCurrentPlaylist() {
  if (!currentPlaylistId) return;
  if (!confirm('Delete this playlist?')) return;

  try {
    await apiFetch('/api/playlists/' + encodeURIComponent(currentPlaylistId), { method: 'DELETE' });
    currentPlaylistId = null;
    currentPlaylistTracks = [];
    const editor = document.getElementById('playlist-editor');
    const emptyState = document.getElementById('playlist-empty-state');
    if (editor) editor.style.display = 'none';
    if (emptyState) emptyState.style.display = 'block';
    await loadPlaylists();
    showToast('Playlist deleted', 'success');
  } catch (e) {
    showToast('Failed to delete playlist: ' + e.message, 'error');
  }
}

async function scanForDuplicates() {
  showSpinner('Scanning for duplicates...');
  try {
    const result = await apiFetch('/api/duplicates/scan', { method: 'POST' });
    renderDuplicates(result.duplicates || []);

    // Update badge
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

    showToast(`Found ${result.duplicates ? result.duplicates.length : 0} duplicate pairs`, 'info');
  } catch (error) {
    showToast('Error scanning for duplicates', 'error');
  } finally {
    hideSpinner();
  }
}

function renderDuplicates(duplicates) {
  const container = document.getElementById('duplicates-results');
  container.innerHTML = '';

  if (!duplicates || duplicates.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'No duplicates found. Click "Scan for Duplicates" to begin.';
    container.appendChild(empty);
    return;
  }

  duplicates.forEach((group, idx) => {
    const div = document.createElement('div');
    div.className = 'duplicate-pair';
    const tracks = group.tracks || [group.track1, group.track2].filter(Boolean);
    div.innerHTML = `<h3>Duplicate Group ${idx + 1} (${tracks.length} tracks)</h3>`;

    // Radio group for selecting which track to keep
    const radioName = `dup-keep-group-${idx}`;

    tracks.forEach((track, tIdx) => {
      const trackDiv = document.createElement('div');
      trackDiv.className = 'duplicate-track';
      trackDiv.innerHTML = `
        <div class="duplicate-track-info">
          <label class="duplicate-track-label">
            <input type="radio" name="${radioName}" value="${tIdx}" class="duplicate-keep-radio" data-group-idx="${idx}" data-track-idx="${tIdx}">
            <div>
              <div class="duplicate-track-title">${escapeHtml(track.display_title || 'Unknown')}</div>
              <div class="duplicate-track-meta">${escapeHtml(track.display_artist || 'Unknown')} — ${escapeHtml(track.file_path)}</div>
            </div>
          </label>
          <button class="btn btn-secondary duplicate-remove-btn" data-path="${encodeURIComponent(track.file_path)}">Remove</button>
        </div>
      `;

      trackDiv.querySelector('.duplicate-remove-btn').addEventListener('click', async (e) => {
        const path = decodeURIComponent(e.target.dataset.path);
        await removeDuplicate(path);
      });

      div.appendChild(trackDiv);
    });

    // Merge button (hidden until a radio is selected)
    const mergeBtn = document.createElement('button');
    mergeBtn.className = 'btn btn-primary duplicate-merge-btn';
    mergeBtn.textContent = 'Merge into Selected';
    mergeBtn.style.display = 'none';
    mergeBtn.style.marginTop = '8px';
    mergeBtn.dataset.groupIdx = idx;
    div.appendChild(mergeBtn);

    // Summary div
    const summaryDiv = document.createElement('div');
    summaryDiv.className = 'duplicate-merge-summary';
    summaryDiv.style.display = 'none';
    div.appendChild(summaryDiv);

    // Show merge button when a radio is selected
    div.querySelectorAll('.duplicate-keep-radio').forEach(radio => {
      radio.addEventListener('change', () => {
        div.querySelectorAll('.duplicate-merge-btn').forEach(btn => btn.style.display = 'none');
        mergeBtn.style.display = 'inline-block';
      });
    });

    // Merge button click handler
    mergeBtn.addEventListener('click', async () => {
      const selectedRadio = div.querySelector(`input[name="${radioName}"]:checked`);
      if (!selectedRadio) {
        showToast('Please select a track to keep', 'warning');
        return;
      }
      const keepTrackIdx = parseInt(selectedRadio.dataset.trackIdx);
      const groupIdx = parseInt(selectedRadio.dataset.groupIdx);
      await mergeDuplicateGroup(groupIdx, keepTrackIdx, duplicates[groupIdx]);
    });

    container.appendChild(div);
  });
}

async function mergeDuplicateGroup(groupIdx, keepTrackIdx, group) {
  const tracks = group.tracks || [group.track1, group.track2].filter(Boolean);
  const keepTrack = tracks[keepTrackIdx];
  const mergeTracks = tracks.filter((_, i) => i !== keepTrackIdx);

  if (!keepTrack || mergeTracks.length === 0) {
    showToast('Nothing to merge', 'warning');
    return;
  }

  showSpinner('Merging duplicates...');
  try {
    const result = await apiFetch('/api/duplicates/merge', {
      method: 'POST',
      body: JSON.stringify({
        keep_path: keepTrack.file_path,
        merge_paths: mergeTracks.map(t => t.file_path),
        field_strategy: 'best'
      })
    });

    // Update local track store
    if (result.result) {
      const idx = window.tracks.findIndex(t => t.file_path === result.kept);
      if (idx >= 0) {
        window.tracks[idx] = result.result;
      }
    }
    window.tracks = window.tracks.filter(t => t.file_path !== result.kept || t.file_path === result.kept);
    // Remove merged tracks
    const mergedPaths = new Set(mergeTracks.map(t => t.file_path));
    window.tracks = window.tracks.filter(t => !mergedPaths.has(t.file_path));
    window.searchResults = null;

    renderTracks();

    // Show summary
    const container = document.getElementById('duplicates-results');
    const mergeSummary = container.querySelectorAll('.duplicate-merge-summary')[groupIdx];
    if (mergeSummary) {
      const fieldNames = (result.updated_fields || []).map(f => {
        const names = {
          final_genre: 'genre',
          final_subgenre: 'subgenre',
          final_bpm: 'BPM',
          final_key: 'key',
          final_year: 'year',
          analyzed_energy: 'energy',
          clave_pattern: 'clave',
          vocal_flag: 'vocal'
        };
        return names[f] || f;
      });
      const fieldsText = fieldNames.length > 0 ? ` Fields updated: ${fieldNames.join(', ')}` : '';
      mergeSummary.textContent = `Merged ${result.merged} duplicates into "${result.result.display_title}".${fieldsText}`;
      mergeSummary.style.display = 'block';
    }

    // Hide merge button and radios
    const dupGroup = container.querySelectorAll('.duplicate-pair')[groupIdx];
    if (dupGroup) {
      dupGroup.querySelectorAll('.duplicate-keep-radio').forEach(r => r.disabled = true);
      dupGroup.querySelectorAll('.duplicate-merge-btn').forEach(b => b.style.display = 'none');
      dupGroup.querySelectorAll('.duplicate-remove-btn').forEach(b => b.style.display = 'none');
    }

    showToast(`Merged ${result.merged} duplicates`, 'success');
  } catch (error) {
    showToast('Error merging duplicates: ' + (error.message || 'Unknown error'), 'error');
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

    window.tracks = window.tracks.filter(t => t.file_path !== filePath);
    window.searchResults = null;
    renderTracks();
    showToast('Track removed from library', 'success');

    // Rescan to refresh UI
    await scanForDuplicates();
  } catch (error) {
    showToast('Error removing duplicate', 'error');
  } finally {
    hideSpinner();
  }
}

// ============================================================================
// Feature 9: Organise Tab
// ============================================================================

async function loadLibraryHealth() {
  try {
    const res = await apiFetch('/api/library/health');
    document.getElementById('health-total').textContent = res.total;
    document.getElementById('health-analyzed').textContent = res.analyzed;
    document.getElementById('health-classified').textContent = res.classified;
    document.getElementById('health-approved').textContent = res.approved;
    document.getElementById('health-written').textContent = res.tags_written;
    document.getElementById('health-duplicates').textContent = res.duplicates;

    // Coverage bars
    const covEl = document.getElementById('health-coverage');
    const fields = [
      ['BPM', res.coverage.bpm],
      ['Key', res.coverage.key],
      ['Energy', res.coverage.energy],
      ['Artwork', res.coverage.artwork],
    ];
    covEl.innerHTML = fields.map(([label, val]) => {
      const pct = Math.round((val || 0) * 100);
      const color = pct >= 80 ? 'var(--accent)' : pct >= 50 ? '#f0a500' : 'var(--danger)';
      return `<div style="margin-bottom:0.5rem;">
        <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
          <span style="font-size:0.8rem;color:var(--text-muted)">${label}</span>
          <span style="font-size:0.8rem;color:var(--text-muted)">${pct}%</span>
        </div>
        <div style="height:6px;background:var(--border);border-radius:3px;">
          <div style="height:100%;width:${pct}%;background:${color};border-radius:3px;transition:width 0.3s;"></div>
        </div>
      </div>`;
    }).join('');

    // Genre breakdown
    const genreEl = document.getElementById('health-by-genre');
    if (res.by_genre && Object.keys(res.by_genre).length) {
      const sorted = Object.entries(res.by_genre).sort((a,b) => b[1]-a[1]);
      genreEl.innerHTML = `<div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.5rem;">By Genre</div>`
        + sorted.map(([g, n]) => `<span class="badge" style="margin:2px;">${g} <strong>${n}</strong></span>`).join('');
    }
  } catch(e) {
    console.error('Health load failed', e);
  }
}

async function parseFilenames() {
  const btn = document.getElementById('btn-parse-filenames');
  btn.disabled = true; btn.textContent = 'Scanning...';
  try {
    const res = await apiFetch('/api/organise/parse-filenames', {
      method: 'POST',
      body: JSON.stringify({all: true})
    });
    const data = res;
    const el = document.getElementById('filename-parse-results');
    if (!data.length) {
      el.innerHTML = '<p style="color:var(--text-muted)">No parseable filenames found (all tracks already have tags, or filenames don\'t match "Artist - Title" pattern).</p>';
      return;
    }
    const conflicting = data.filter(t => t.has_conflict);
    const noTag = data.filter(t => !t.has_conflict);
    let html = `<p style="margin-bottom:0.5rem;">${data.length} tracks with parseable filenames (${conflicting.length} conflicts, ${noTag.length} no existing tags).</p>`;
    html += `<table class="data-table" style="font-size:0.8rem;">
      <thead><tr><th>File</th><th>Parsed Artist</th><th>Parsed Title</th><th>Current Artist</th><th>Current Title</th><th></th></tr></thead>
      <tbody>`;
    data.forEach(t => {
      const rowStyle = t.has_conflict ? 'background:rgba(240,80,80,0.05);' : '';
      html += `<tr style="${rowStyle}">
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${t.filename}">${t.filename}</td>
        <td>${t.parsed_artist || '—'}</td>
        <td>${t.parsed_title || '—'}</td>
        <td>${t.current_artist || '—'}</td>
        <td>${t.current_title || '—'}</td>
        <td><button class="btn btn-sm btn-primary" onclick="applyFilenameTag('${encodeURIComponent(t.file_path)}','${encodeURIComponent(t.parsed_artist||'')}','${encodeURIComponent(t.parsed_title||'')}', this)">Apply</button></td>
      </tr>`;
    });
    html += `</tbody></table>`;
    html += `<div style="margin-top:0.75rem;"><button class="btn btn-primary" onclick="applyAllFilenameTags(${JSON.stringify(data)})">Apply All</button></div>`;
    el.innerHTML = html;
  } finally {
    btn.disabled = false; btn.textContent = 'Scan All Tracks';
  }
}

async function applyFilenameTag(encodedPath, encodedArtist, encodedTitle, btn) {
  btn.disabled = true;
  const path = decodeURIComponent(encodedPath);
  const artist = decodeURIComponent(encodedArtist);
  const title = decodeURIComponent(encodedTitle);
  await apiFetch('/api/organise/apply-filename-tags', {
    method: 'POST',
    body: JSON.stringify({updates: [{file_path: path, artist, title}]})
  });
  btn.textContent = '✓'; btn.style.background = 'var(--accent)';
}

async function applyAllFilenameTags(tracks) {
  const updates = tracks.filter(t => t.parsed_artist || t.parsed_title).map(t => ({
    file_path: t.file_path, artist: t.parsed_artist || t.current_artist, title: t.parsed_title || t.current_title
  }));
  const res = await apiFetch('/api/organise/apply-filename-tags', {
    method: 'POST',
    body: JSON.stringify({updates})
  });
  const d = res;
  alert(`Applied tags to ${d.updated} tracks. They are now set to "pending" for review.`);
}

async function previewOrganise() {
  const dest = document.getElementById('organise-dest').value.trim();
  if (!dest) { alert('Enter a destination folder first.'); return; }
  const pattern = document.getElementById('organise-pattern').value;
  const res = await apiFetch('/api/organise/folders', {
    method: 'POST',
    body: JSON.stringify({destination: dest, pattern, dry_run: true})
  });
  const d = res;
  const el = document.getElementById('organise-preview-results');
  if (d.error) { el.innerHTML = `<p style="color:var(--danger)">${d.error}</p>`; return; }
  const moves = d.moves || [];
  if (!moves.length) { el.innerHTML = '<p style="color:var(--text-muted)">No approved tracks to move.</p>'; return; }
  const overwrite = moves.filter(m => m.would_overwrite).length;
  el.innerHTML = `<p style="margin-bottom:0.5rem;">${moves.length} files to move${overwrite ? ` (${overwrite} would overwrite)` : ''}.</p>
    <div style="max-height:200px;overflow-y:auto;font-size:0.75rem;background:var(--bg-secondary);padding:0.75rem;border-radius:6px;">
      ${moves.slice(0, 50).map(m => `<div>${m.from.split('/').pop()} → <strong>${m.to.split('/').slice(-3).join('/')}</strong>${m.would_overwrite ? ' ⚠️' : ''}</div>`).join('')}
      ${moves.length > 50 ? `<div style="color:var(--text-muted)">... and ${moves.length - 50} more</div>` : ''}
    </div>`;
  document.getElementById('btn-organise-run').disabled = false;
  document.getElementById('btn-organise-run')._previewData = {dest, pattern};
}

async function runOrganise() {
  const previewData = document.getElementById('btn-organise-run')._previewData;
  if (!previewData) { showToast('Run a preview first', 'warning'); return; }
  if (!confirm(`This will physically move files. Continue?`)) return;
  const {dest, pattern} = previewData;
  const btn = document.getElementById('btn-organise-run');
  btn.disabled = true; btn.textContent = 'Moving...';
  const res = await apiFetch('/api/organise/folders', {
    method: 'POST',
    body: JSON.stringify({destination: dest, pattern, dry_run: false})
  });
  const d = res;
  if (d.error) { alert(d.error); }
  else { alert(`Moved ${d.moved} files successfully${d.errors?.length ? ` (${d.errors.length} errors)` : ''}.`); }
  btn.textContent = 'Move Files';
}

async function validateKeys() {
  const btn = document.getElementById('btn-validate-keys');
  btn.disabled = true; btn.textContent = 'Checking...';
  try {
    const res = await apiFetch('/api/validate/keys');
    const d = res;
    const el = document.getElementById('key-validation-results');
    if (d.error) { el.innerHTML = `<p style="color:var(--danger)">${d.error}</p>`; return; }
    if (!d.mismatches?.length) {
      el.innerHTML = `<p style="color:var(--accent)">✓ All ${d.total_checked} keys match (within 1 Camelot step). No corrections needed.</p>`;
      return;
    }
    let html = `<p style="margin-bottom:0.5rem;">${d.mismatch_count} mismatches out of ${d.total_checked} tracks checked.</p>
      <table class="data-table" style="font-size:0.8rem;">
        <thead><tr><th>Title</th><th>Artist</th><th>Stored Key</th><th>Detected Key</th><th>Distance</th><th></th></tr></thead>
        <tbody>`;
    d.mismatches.forEach(m => {
      html += `<tr>
        <td>${m.title || '—'}</td><td>${m.artist || '—'}</td>
        <td><span class="badge">${m.stored_key}</span></td>
        <td><span class="badge" style="background:var(--accent);">${m.analyzed_key}</span></td>
        <td>${m.distance}</td>
        <td><button class="btn btn-sm btn-primary" onclick="fixKey('${encodeURIComponent(m.file_path)}', this)">Use Detected</button></td>
      </tr>`;
    });
    html += `</tbody></table>
      <div style="margin-top:0.75rem;">
        <button class="btn btn-primary" onclick="fixAllKeys(${JSON.stringify(d.mismatches.map(m=>m.file_path))})">Fix All (${d.mismatch_count})</button>
      </div>`;
    el.innerHTML = html;
  } finally {
    btn.disabled = false; btn.textContent = 'Check Keys';
  }
}

async function fixKey(encodedPath, btn) {
  btn.disabled = true;
  await apiFetch('/api/validate/keys/fix', {
    method: 'POST',
    body: JSON.stringify({paths: [decodeURIComponent(encodedPath)], use_analyzed: true})
  });
  btn.textContent = '✓'; btn.style.background = 'var(--accent)';
}

async function fixAllKeys(paths) {
  const res = await apiFetch('/api/validate/keys/fix', {
    method: 'POST',
    body: JSON.stringify({paths, use_analyzed: true})
  });
  const d = res;
  alert(`Fixed ${d.fixed} key mismatches.`);
  validateKeys();
}

// ============================================================================
// Feature 9: Smart Playlist Builder
// ============================================================================

function initPlaylistBuilder() {
  // Add playlist builder to export section (review-footer area)
  const reviewFooter = document.querySelector('.review-footer');
  if (reviewFooter) {
    const builder = document.createElement('div');
    builder.className = 'playlist-builder';
    builder.innerHTML = `
      <h3>Build Custom Playlist</h3>
      <div class="playlist-filters">
        <div class="playlist-filter-group">
          <label>Min BPM</label>
          <input type="number" class="input-text" id="pb-bpm-min" min="40" max="200" placeholder="Min">
        </div>
        <div class="playlist-filter-group">
          <label>Max BPM</label>
          <input type="number" class="input-text" id="pb-bpm-max" min="40" max="200" placeholder="Max">
        </div>
        <div class="playlist-filter-group">
          <label>Min Energy</label>
          <input type="range" class="slider" id="pb-energy-min" min="1" max="10" value="1">
          <span id="pb-energy-min-val">1</span>
        </div>
        <div class="playlist-filter-group">
          <label>Max Energy</label>
          <input type="range" class="slider" id="pb-energy-max" min="1" max="10" value="10">
          <span id="pb-energy-max-val">10</span>
        </div>
        <div class="playlist-filter-group">
          <label>Key</label>
          <select class="input-select" id="pb-key">
            <option value="">Any Key</option>
          </select>
        </div>
        <div class="playlist-filter-group">
          <label>Genre</label>
          <select class="input-select" id="pb-genre">
            <option value="">Any Genre</option>
          </select>
        </div>
        <div class="playlist-filter-group">
          <label>Comments</label>
          <select class="input-select" id="pb-subgenre">
            <option value="">Any Comments</option>
          </select>
        </div>
        <div class="playlist-filter-group">
          <label>Status</label>
          <select class="input-select" id="pb-status">
            <option value="">All</option>
            <option value="approved">Approved Only</option>
          </select>
        </div>
      </div>
      <div class="playlist-filter-group">
        <label>Playlist Filename</label>
        <input type="text" class="input-text" id="pb-filename" placeholder="idlm-playlist">
      </div>
      <div class="playlist-export-buttons">
        <button class="btn btn-primary" id="btn-export-m3u">📥 Export M3U</button>
      </div>
    `;
    reviewFooter.parentNode.insertBefore(builder, reviewFooter);

    // Populate genre/key selects
    populatePlaylistFilters();

    // Event listeners
    document.getElementById('pb-energy-min').addEventListener('input', (e) => {
      document.getElementById('pb-energy-min-val').textContent = e.target.value;
    });
    document.getElementById('pb-energy-max').addEventListener('input', (e) => {
      document.getElementById('pb-energy-max-val').textContent = e.target.value;
    });

    document.getElementById('pb-genre').addEventListener('change', () => {
      populatePlaylistSubgenres();
    });

    document.getElementById('btn-export-m3u').addEventListener('click', exportCustomPlaylist);
  }
}

function populatePlaylistFilters() {
  const genreSelect = document.getElementById('pb-genre');
  const keySelect = document.getElementById('pb-key');

  // Populate genres
  Object.keys(window.taxonomy).forEach(genre => {
    const opt = document.createElement('option');
    opt.value = genre;
    opt.textContent = genre;
    genreSelect.appendChild(opt);
  });

  // Populate keys (unique from tracks)
  const keys = new Set();
  window.tracks.forEach(t => {
    if (t.final_key) keys.add(t.final_key);
  });

  [...keys].sort().forEach(key => {
    const opt = document.createElement('option');
    opt.value = key;
    opt.textContent = key;
    keySelect.appendChild(opt);
  });
}

function populatePlaylistSubgenres() {
  const genre = document.getElementById('pb-genre').value;
  const select = document.getElementById('pb-subgenre');

  select.innerHTML = '<option value="">Any Comments</option>';

  if (!genre) return;

  const subgenres = new Set();
  window.tracks
    .filter(t => t.final_genre === genre)
    .forEach(t => {
      if (t.final_subgenre) subgenres.add(t.final_subgenre);
    });

  [...subgenres].sort().forEach(sub => {
    const opt = document.createElement('option');
    opt.value = sub;
    opt.textContent = sub;
    select.appendChild(opt);
  });
}

function exportCustomPlaylist() {
  const bpmMin = document.getElementById('pb-bpm-min').value || '';
  const bpmMax = document.getElementById('pb-bpm-max').value || '';
  const energyMin = document.getElementById('pb-energy-min').value || '';
  const energyMax = document.getElementById('pb-energy-max').value || '';
  const key = document.getElementById('pb-key').value || '';
  const genre = document.getElementById('pb-genre').value || '';
  const subgenre = document.getElementById('pb-subgenre').value || '';
  const status = document.getElementById('pb-status').value || '';
  const filename = document.getElementById('pb-filename').value || 'idlm-playlist';

  const params = new URLSearchParams();
  if (bpmMin) params.append('bpm_min', bpmMin);
  if (bpmMax) params.append('bpm_max', bpmMax);
  if (energyMin) params.append('energy_min', energyMin);
  if (energyMax) params.append('energy_max', energyMax);
  if (key) params.append('key', key);
  if (genre) params.append('genre', genre);
  if (subgenre) params.append('subgenre', subgenre);
  if (status) params.append('status', status);
  params.append('filename', filename);

  window.location = `/api/export/m3u?${params.toString()}`;
  showToast('Downloading playlist...', 'info');
}

// ============================================================================
// Update Checker
// ============================================================================

let updateCheckResult = null;
let downloadPollInterval = null;

async function checkForUpdates() {
  const modal = document.getElementById('update-modal');
  const titleEl = document.getElementById('update-modal-title');
  const bodyEl = document.getElementById('update-modal-body');
  const footerEl = document.getElementById('update-modal-footer');

  if (!modal || !bodyEl || !footerEl) return;

  // Show loading state
  if (titleEl) titleEl.textContent = 'Checking for Updates...';
  bodyEl.innerHTML = '<p style="text-align:center;color:var(--text-secondary);font-size:13px;">Contacting GitHub...</p>';
  footerEl.innerHTML = '<button class="btn btn-secondary" id="update-cancel-check">Cancel</button>';
  const cancelBtn = document.getElementById('update-cancel-check');
  if (cancelBtn) cancelBtn.addEventListener('click', closeUpdateModal);

  modal.style.display = 'flex';

  try {
    const data = await apiFetch('/api/version/check');
    if (!data) {
      bodyEl.innerHTML = '<p style="text-align:center;color:var(--red);font-size:13px;">Could not check for updates.</p>';
      footerEl.innerHTML = '<button class="btn btn-primary" onclick="closeUpdateModal()">Close</button>';
      return;
    }

    updateCheckResult = data;

    if (data.error) {
      // Error from API (rate limit, network, etc.)
      bodyEl.innerHTML = '<p style="text-align:center;color:var(--red);font-size:13px;">' + escapeHtml(data.error) + '</p>';
      footerEl.innerHTML = '<button class="btn btn-primary" onclick="closeUpdateModal()">Close</button>';
      return;
    }

    if (!data.has_update) {
      // Up to date
      bodyEl.innerHTML =
        '<div style="text-align:center;padding:20px 0;">' +
        '<div style="font-size:48px;margin-bottom:12px;">&#9989;</div>' +
        '<p style="font-size:15px;font-weight:600;color:var(--text-loud);margin-bottom:4px;">You\'re up to date!</p>' +
        '<p style="font-size:13px;color:var(--text-secondary);">Running <strong>' + escapeHtml(data.current) + '</strong> — the latest version.</p>' +
        '</div>';
      footerEl.innerHTML = '<button class="btn btn-primary" onclick="closeUpdateModal()">Done</button>';
      // Clear notification badge
      clearUpdateBadge();
      return;
    }

    // Update available
    const publishedStr = data.published_at
      ? '<p class="update-published-at">Published: ' + new Date(data.published_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) + '</p>'
      : '';

    const releaseNotesHtml = formatReleaseNotes(data.release_notes || 'No release notes available.');

    let bodyHtml = '';
    bodyHtml += '<div class="update-version-info">';
    bodyHtml += '<div class="update-version-current"><span class="update-version-label">Current</span><span class="update-version-number">' + escapeHtml(data.current) + '</span></div>';
    bodyHtml += '<span class="update-version-arrow">&#8594;</span>';
    bodyHtml += '<div class="update-version-latest"><span class="update-version-label">Latest</span><span class="update-version-number">' + escapeHtml(data.latest) + '</span></div>';
    bodyHtml += '</div>';

    bodyHtml += publishedStr;
    bodyHtml += '<h3 style="font-size:14px;font-weight:600;color:var(--text-loud);margin:0 0 4px;">What\'s New</h3>';
    bodyHtml += '<div class="release-notes">' + releaseNotesHtml + '</div>';

    // Git pull section for source installs
    if (!data.is_macos || !data.download_url || data.download_url.includes('/releases/')) {
      bodyHtml += '<div class="update-git-pull-section">';
      bodyHtml += '<h4>Source Install</h4>';
      bodyHtml += '<p style="font-size:12px;color:var(--text-secondary);margin:0 0 8px;">Update via git pull:</p>';
      bodyHtml += '<button class="btn btn-secondary btn-sm" id="btn-git-pull" style="font-size:12px;padding:5px 12px;">Run git pull</button>';
      bodyHtml += '<div id="git-pull-output" style="display:none;"></div>';
      bodyHtml += '</div>';
    }

    bodyEl.innerHTML = bodyHtml;

    // Footer buttons
    let footerHtml = '';
    footerHtml += '<button class="btn btn-secondary" onclick="closeUpdateModal()">Later</button>';
    if (data.is_macos && data.download_url && !data.download_url.includes('/releases/tag')) {
      footerHtml += '<button class="btn btn-primary" id="btn-download-update">Download Update</button>';
    } else {
      footerHtml += '<button class="btn btn-secondary" id="btn-open-release" style="font-size:12px;">View on GitHub</button>';
    }
    footerEl.innerHTML = footerHtml;

    // Event listeners
    const downloadBtn = document.getElementById('btn-download-update');
    if (downloadBtn) {
      downloadBtn.addEventListener('click', () => downloadUpdate(data.download_url));
    }

    const openReleaseBtn = document.getElementById('btn-open-release');
    if (openReleaseBtn) {
      openReleaseBtn.addEventListener('click', () => {
        window.open(data.download_url || 'https://github.com/xonline/idjlm-pro/releases/latest', '_blank');
        closeUpdateModal();
      });
    }

    const gitPullBtn = document.getElementById('btn-git-pull');
    if (gitPullBtn) {
      gitPullBtn.addEventListener('click', runGitPull);
    }

    // Set notification badge if update available
    setUpdateBadge();

  } catch (e) {
    bodyEl.innerHTML = '<p style="text-align:center;color:var(--red);font-size:13px;">Could not check for updates: ' + escapeHtml(e.message) + '</p>';
    footerEl.innerHTML = '<button class="btn btn-primary" onclick="closeUpdateModal()">Close</button>';
  }
}

function formatReleaseNotes(text) {
  // Basic markdown-like formatting
  let html = escapeHtml(text);
  // Bold: **text**
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Inline code: `text`
  html = html.replace(/`(.*?)`/g, '<code>$1</code>');
  // Links: [text](url)
  html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // Headings: ### text
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  // Unordered lists: - text or * text
  html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
  // Wrap consecutive <li> in <ul>
  html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul>$1</ul>');
  // Line breaks
  html = html.replace(/\n/g, '<br>');
  // Clean up extra <br> around block elements
  html = html.replace(/<br>\s*(<h[1-3]>)/g, '$1');
  html = html.replace(/(<\/h[1-3]>)\s*<br>/g, '$1');
  html = html.replace(/<br>\s*(<ul>)/g, '$1');
  html = html.replace(/(<\/ul>)\s*<br>/g, '$1');
  return html;
}

async function downloadUpdate(url) {
  const bodyEl = document.getElementById('update-modal-body');
  const footerEl = document.getElementById('update-modal-footer');
  const titleEl = document.getElementById('update-modal-title');

  if (!bodyEl || !footerEl) return;

  // Show download progress
  if (titleEl) titleEl.textContent = 'Downloading Update';
  bodyEl.innerHTML =
    '<div class="download-progress">' +
    '<div class="download-progress-label"><span>Downloading...</span><span id="download-pct">0%</span></div>' +
    '<div class="download-progress-track"><div class="download-progress-fill" id="download-fill" style="width:0%"></div></div>' +
    '<div class="download-progress-size" id="download-size">0 MB of —</div>' +
    '</div>' +
    '<p class="update-status-text" id="download-status">Starting download...</p>';
  footerEl.innerHTML = '<button class="btn btn-secondary" id="btn-cancel-download" disabled>Cancel</button>';

  try {
    const result = await apiFetch('/api/version/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    });

    if (result && result.downloading) {
      // Poll for progress
      pollDownloadProgress();
    }
  } catch (e) {
    const statusEl = document.getElementById('download-status');
    if (statusEl) {
      statusEl.textContent = 'Download failed: ' + e.message;
      statusEl.className = 'update-status-text error';
    }
    footerEl.innerHTML = '<button class="btn btn-primary" onclick="closeUpdateModal()">Close</button>';
  }
}

function pollDownloadProgress() {
  if (downloadPollInterval) clearInterval(downloadPollInterval);

  downloadPollInterval = setInterval(async () => {
    try {
      const data = await apiFetch('/api/version/download/status');

      const fillEl = document.getElementById('download-fill');
      const pctEl = document.getElementById('download-pct');
      const sizeEl = document.getElementById('download-size');
      const statusEl = document.getElementById('download-status');
      const footerEl = document.getElementById('update-modal-footer');

      if (data.error) {
        clearInterval(downloadPollInterval);
        downloadPollInterval = null;
        if (statusEl) {
          statusEl.textContent = 'Download failed: ' + data.error;
          statusEl.className = 'update-status-text error';
        }
        if (footerEl) {
          footerEl.innerHTML = '<button class="btn btn-primary" onclick="closeUpdateModal()">Close</button>';
        }
        return;
      }

      if (data.downloaded && data.size) {
        const pct = Math.round((data.downloaded / data.size) * 100);
        const downloadedMB = (data.downloaded / (1024 * 1024)).toFixed(1);
        const totalMB = (data.size / (1024 * 1024)).toFixed(1);

        if (fillEl) fillEl.style.width = pct + '%';
        if (pctEl) pctEl.textContent = pct + '%';
        if (sizeEl) sizeEl.textContent = downloadedMB + ' MB of ' + totalMB + ' MB';
      } else if (data.downloading) {
        if (statusEl) statusEl.textContent = 'Connecting...';
      }

      if (data.done && data.path) {
        clearInterval(downloadPollInterval);
        downloadPollInterval = null;

        const path = data.path;
        if (fillEl) fillEl.style.width = '100%';
        if (pctEl) pctEl.textContent = '100%';
        if (sizeEl) sizeEl.textContent = (data.size / (1024 * 1024)).toFixed(1) + ' MB';

        if (statusEl) {
          statusEl.textContent = 'Download complete!';
          statusEl.className = 'update-status-text success';
        }

        if (footerEl) {
          footerEl.innerHTML =
            '<button class="btn btn-secondary" onclick="closeUpdateModal()">Later</button>' +
            '<button class="btn btn-primary" id="btn-open-dmg">Open DMG</button>';
          const openBtn = document.getElementById('btn-open-dmg');
          if (openBtn) {
            openBtn.addEventListener('click', () => openDmg(path));
          }
        }
      }

      if (data.done && data.error) {
        clearInterval(downloadPollInterval);
        downloadPollInterval = null;
      }
    } catch (e) {
      // Poll error — just retry next interval
    }
  }, 500);
}

async function openDmg(path) {
  try {
    const data = await apiFetch('/api/version/open-dmg', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path })
    });

    if (data && data.opened) {
      showToast('DMG opened — drag IDJLM Pro to Applications folder', 'success');
      closeUpdateModal();
    } else {
      showToast('Failed to open DMG: ' + (data.error || 'unknown error'), 'error');
    }
  } catch (e) {
    showToast('Failed to open DMG: ' + e.message, 'error');
  }
}

async function runGitPull() {
  const outputEl = document.getElementById('git-pull-output');
  const btnEl = document.getElementById('btn-git-pull');

  if (!outputEl || !btnEl) return;

  btnEl.disabled = true;
  btnEl.textContent = 'Running...';
  outputEl.style.display = 'block';
  outputEl.innerHTML = '<p style="color:var(--text-secondary);font-size:12px;">Running git pull...</p>';

  try {
    const data = await apiFetch('/api/version/git-pull');

    if (data && data.success) {
      outputEl.innerHTML = '<div class="update-git-output">' + escapeHtml(data.output || 'Already up to date.') + '</div>';
    } else {
      outputEl.innerHTML = '<div class="update-git-output" style="color:var(--red);">' + escapeHtml(data.error || data.output || 'git pull failed') + '</div>';
    }
  } catch (e) {
    outputEl.innerHTML = '<div class="update-git-output" style="color:var(--red);">' + escapeHtml(e.message) + '</div>';
  }

  btnEl.disabled = false;
  btnEl.textContent = 'Run git pull';
}

function closeUpdateModal() {
  const modal = document.getElementById('update-modal');
  if (modal) modal.style.display = 'none';
  if (downloadPollInterval) {
    clearInterval(downloadPollInterval);
    downloadPollInterval = null;
  }
}

function setUpdateBadge() {
  const navBtn = document.getElementById('nav-btn-settings');
  if (navBtn) navBtn.classList.add('update-available-badge');
}

function clearUpdateBadge() {
  const navBtn = document.getElementById('nav-btn-settings');
  if (navBtn) navBtn.classList.remove('update-available-badge');
}

function initUpdateChecker() {
  // Header version badge click
  const headerBadge = document.getElementById('header-version-badge');
  if (headerBadge) {
    headerBadge.addEventListener('click', checkForUpdates);
  }

  // Check for Updates button in Settings
  const checkBtn = document.getElementById('btn-check-updates');
  if (checkBtn) {
    checkBtn.addEventListener('click', checkForUpdates);
  }

  // Update modal close
  const closeBtn = document.getElementById('update-modal-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', closeUpdateModal);
  }

  // Close on background click
  const modal = document.getElementById('update-modal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeUpdateModal();
    });
  }
}

/* ============================================================
   Pipeline Stepper & Onboarding Wizard
   ============================================================ */

/** Update the pipeline stepper based on current track states */
function updatePipelineStepper() {
  var allTracks = window.tracks || [];
  if (!allTracks.length) return;

  var total = allTracks.length;
  var imported = total;
  var analyzed = allTracks.filter(function(t) { return t.analysis_done; }).length;
  var classified = allTracks.filter(function(t) { return t.classification_done; }).length;
  var approved = allTracks.filter(function(t) { return t.review_status === 'approved' || t.review_status === 'edited'; }).length;
  var written = allTracks.filter(function(t) { return t.tags_written; }).length;

  setStepStatus('import', imported, imported, total, imported > 0 ? 'completed' : '');
  setStepStatus('analyse', analyzed, total, analyzed > 0 ? (analyzed === total ? 'completed' : 'active') : '');
  setStepStatus('classify', classified, total, classified > 0 ? (classified === total ? 'completed' : 'active') : '');
  setStepStatus('review', approved, total, approved > 0 ? (approved === total ? 'completed' : 'active') : '');
  setStepStatus('write', written, total, written > 0 ? (written === total ? 'completed' : 'active') : '');
}

function setStepStatus(step, done, total, status) {
  var el = document.getElementById('step-' + step);
  var countEl = document.getElementById('count-' + step);
  if (!el || !countEl) return;
  el.classList.toggle('active', status === 'active');
  el.classList.toggle('completed', status === 'completed');
  countEl.textContent = done + '/' + total;
}

/** Show onboarding wizard if first run */
function showOnboardingIfNeeded() {
  if (localStorage.getItem('idjlm-onboarding-done')) return;
  var store = window.tracks || [];
  if (store.length > 0) return;
  var overlay = document.getElementById('onboarding-overlay');
  if (overlay) { overlay.style.display = 'flex'; updateOnboardingStep(1); }
}

function updateOnboardingStep(step) {
  for (var i = 1; i <= 3; i++) {
    var el = document.getElementById('onboard-step-' + i);
    if (el) el.style.display = i === step ? '' : 'none';
  }
  var fill = document.getElementById('onboard-progress-fill');
  var text = document.getElementById('onboard-progress-text');
  if (fill) fill.style.width = (step / 3 * 100) + '%';
  if (text) text.textContent = 'Step ' + step + ' of 3';
}

function completeOnboarding() {
  localStorage.setItem('idjlm-onboarding-done', 'true');
  var overlay = document.getElementById('onboarding-overlay');
  if (overlay) overlay.style.display = 'none';
}

function initOnboarding() {
  var closeBtn = document.getElementById('onboarding-close');
  if (closeBtn) closeBtn.addEventListener('click', completeOnboarding);

  var chooseBtn = document.getElementById('onboard-choose-folder');
  if (chooseBtn) {
    chooseBtn.addEventListener('click', async function() {
      if (window.pywebview && window.pywebview.api) {
        var path = await window.pywebview.api.choose_folder();
        if (path) {
          document.getElementById('onboard-folder-path').textContent = path;
          // Actually import the folder — not just show the path
          try {
            var result = await apiFetch('/api/import', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ folder_path: path })
            });
            if (result && result.tracks) {
              window.tracks = result.tracks;
              window.searchResults = null;
              renderTracks();
              updateStats();
              updatePipelineStepper();
              updateToolbarButtonStates();
              showToast((result.count || result.tracks.length) + ' tracks imported', 'success');
            }
          } catch (e) {
            showToast('Import failed: ' + e.message, 'error');
          }
          updateOnboardingStep(2);
        }
      } else {
        document.getElementById('btn-get-started')?.click();
        updateOnboardingStep(2);
      }
    });
  }

  var continueBtn = document.getElementById('onboard-continue');
  if (continueBtn) {
    continueBtn.addEventListener('click', function() {
      var sel = document.querySelector('.onboarding-provider.selected');
      var provider = sel ? sel.dataset.provider : 'gemini';
      var ps = document.getElementById('settings-provider');
      if (ps) { ps.value = provider; ps.dispatchEvent(new Event('change')); }
      updateOnboardingStep(3);
    });
  }

  document.querySelectorAll('.onboarding-provider').forEach(function(el) {
    el.addEventListener('click', function() {
      document.querySelectorAll('.onboarding-provider').forEach(function(e) { e.classList.remove('selected'); });
      el.classList.add('selected');
    });
  });

  var startBtn = document.getElementById('onboard-start-import');
  if (startBtn) {
    startBtn.addEventListener('click', function() { completeOnboarding(); });
  }

  // Skip API key setup
  var skipBtn = document.getElementById('onboard-skip-api');
  if (skipBtn) {
    skipBtn.addEventListener('click', function() { updateOnboardingStep(3); });
  }

  // Go to Settings from onboarding
  var settingsBtn = document.getElementById('onboard-go-settings');
  if (settingsBtn) {
    settingsBtn.addEventListener('click', function() {
      completeOnboarding();
      switchTab('settings');
    });
  }

  showOnboardingIfNeeded();
}

/* ============================================================
   API Key Test Button
   ============================================================ */
async function testApiKey(provider) {
  // Clear all status elements first
  document.querySelectorAll('[id^="key-test-status-"]').forEach(function(el) {
    el.innerHTML = '';
  });
  const statusEl = document.getElementById('key-test-status-' + provider);
  if (!statusEl) return;
  statusEl.innerHTML = '<span style="color:var(--text-muted);font-size:12px;">Testing ' + provider + '...</span>';

  try {
    const res = await apiFetch('/api/test_key', {
      method: 'POST',
      body: JSON.stringify({ provider: provider })
    });

    if (res.ok) {
      statusEl.innerHTML = '<span style="color:#22c55e;font-size:12px;">✓ Connected (' + res.latency_ms + 'ms)</span>';
      setTimeout(() => { statusEl.innerHTML = ''; }, 5000);
    } else {
      statusEl.innerHTML = '<span style="color:var(--danger);font-size:12px;">✗ ' + escapeHtml(res.error || 'Test failed') + '</span>';
    }
  } catch (e) {
    statusEl.innerHTML = '<span style="color:var(--danger);font-size:12px;">✗ ' + escapeHtml(e.message) + '</span>';
  }
}
