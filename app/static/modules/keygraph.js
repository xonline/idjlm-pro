// ============================================================================
// keygraph.js — Key Compatibility Graph (force-directed canvas)
// ============================================================================
// Extracted from pipeline.js (Phase 0.3). No behaviour change.
// Owns:
//   - keyGraphState module-level state
//   - initKeyGraph / closeKeyGraph / renderKeyCompatibilityGraph
// Dependencies (window-globals, resolved by load order):
//   - isCompatibleKey: camelot.js (loaded earlier)
//   - window.tracks / window.setlist: core.js
//   - escapeHtml / showToast: core.js
// ----------------------------------------------------------------------------

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

  // Build edges using isCompatibleKey (camelot.js)
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


// --- ES module bridge (0.4): expose to global scope for cross-module calls ---
window.initKeyGraph = initKeyGraph;
