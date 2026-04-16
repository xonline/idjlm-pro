// ============================================================================
// Stats Tab
// ============================================================================

function initStatsTab() {
  const statsBtn = document.querySelector('[data-tab="stats"]');
  if (statsBtn) {
    statsBtn.addEventListener('click', () => {
      renderStats();
    });
  }
}

function renderStats() {
  if (!window.tracks.length) {
    // Clear all charts
    Object.keys(chartInstances).forEach(key => {
      if (chartInstances[key]) {
        chartInstances[key].destroy();
        chartInstances[key] = null;
      }
    });
    document.getElementById('subgenre-list').innerHTML = '';
    return;
  }

  // Update stats cards
  const total = window.tracks.length;
  const classified = window.tracks.filter(t => t.final_genre).length;
  const approved = window.tracks.filter(t => t.review_status === 'approved').length;
  const written = window.tracks.filter(t => t.review_status === 'written').length;

  document.getElementById('stats-card-total').textContent = total;
  document.getElementById('stats-card-classified').textContent = classified;
  document.getElementById('stats-card-approved').textContent = approved;
  document.getElementById('stats-card-written').textContent = written;

  // Genre breakdown chart
  renderGenreChart();

  // BPM distribution chart
  renderBpmChart();

  // Year breakdown chart
  renderYearChart();

  // Sub-genre list
  renderSubgenreList();
}

function renderGenreChart() {
  const genreCounts = {};
  window.tracks.forEach(track => {
    const genre = track.final_genre || 'Unknown';
    genreCounts[genre] = (genreCounts[genre] || 0) + 1;
  });

  const labels = Object.keys(genreCounts).sort((a, b) => genreCounts[b] - genreCounts[a]);
  const data = labels.map(label => genreCounts[label]);

  const ctx = document.getElementById('chart-genres');
  if (!ctx) return;

  if (chartInstances.genres) {
    chartInstances.genres.destroy();
  }

  chartInstances.genres = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Track Count',
        data: data,
        backgroundColor: '#8b5cf6',
        borderColor: '#a78bfa',
        borderWidth: 1,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false,
        }
      },
      scales: {
        x: {
          ticks: { color: '#888' },
          grid: { color: '#2a2a3a' }
        },
        y: {
          ticks: { color: '#888' },
          grid: { color: '#2a2a3a' }
        }
      }
    }
  });
}

function renderBpmChart() {
  const ranges = {
    '60-79': 0,
    '80-89': 0,
    '90-99': 0,
    '100-109': 0,
    '110-119': 0,
    '120+': 0,
  };

  window.tracks.forEach(track => {
    const bpm = parseFloat(track.final_bpm) || 0;
    if (bpm < 80) ranges['60-79']++;
    else if (bpm < 90) ranges['80-89']++;
    else if (bpm < 100) ranges['90-99']++;
    else if (bpm < 110) ranges['100-109']++;
    else if (bpm < 120) ranges['110-119']++;
    else ranges['120+']++;
  });

  const labels = Object.keys(ranges);
  const data = Object.values(ranges);

  const ctx = document.getElementById('chart-bpm');
  if (!ctx) return;

  if (chartInstances.bpm) {
    chartInstances.bpm.destroy();
  }

  chartInstances.bpm = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Track Count',
        data: data,
        backgroundColor: '#34d399',
        borderColor: '#6ee7b7',
        borderWidth: 1,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false,
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { color: '#888' },
          grid: { color: '#2a2a3a' }
        },
        x: {
          ticks: { color: '#888' },
          grid: { color: '#2a2a3a' }
        }
      }
    }
  });
}

function renderYearChart() {
  const decades = {
    'Pre-2000': 0,
    '2000s': 0,
    '2010s': 0,
    '2020s': 0,
  };

  window.tracks.forEach(track => {
    const year = parseInt(track.final_year) || 0;
    if (year < 2000) decades['Pre-2000']++;
    else if (year < 2010) decades['2000s']++;
    else if (year < 2020) decades['2010s']++;
    else decades['2020s']++;
  });

  const labels = Object.keys(decades);
  const data = Object.values(decades);

  const ctx = document.getElementById('chart-years');
  if (!ctx) return;

  if (chartInstances.years) {
    chartInstances.years.destroy();
  }

  chartInstances.years = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Track Count',
        data: data,
        backgroundColor: '#fbbf24',
        borderColor: '#fcd34d',
        borderWidth: 1,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false,
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { color: '#888' },
          grid: { color: '#2a2a3a' }
        },
        x: {
          ticks: { color: '#888' },
          grid: { color: '#2a2a3a' }
        }
      }
    }
  });
}

function renderSubgenreList() {
  const subgenreCounts = {};
  window.tracks.forEach(track => {
    const subgenre = track.final_subgenre || 'Unclassified';
    subgenreCounts[subgenre] = (subgenreCounts[subgenre] || 0) + 1;
  });

  // Sort by count, get top 10
  const sorted = Object.entries(subgenreCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  const container = document.getElementById('subgenre-list');
  container.innerHTML = '';

  if (!sorted.length) {
    container.innerHTML = '<div class="empty-state">No comments yet</div>';
    return;
  }

  sorted.forEach(([subgenre, count]) => {
    const item = document.createElement('div');
    item.className = 'subgenre-item';

    const nameSpan = document.createElement('span');
    nameSpan.className = 'subgenre-item-name';
    nameSpan.textContent = subgenre;

    const countBadge = document.createElement('span');
    countBadge.className = 'subgenre-item-count';
    countBadge.textContent = count;

    item.appendChild(nameSpan);
    item.appendChild(countBadge);
    container.appendChild(item);
  });
}

// ============================================================================
// Stats Dashboard (Collection Summary, Key/Energy Distribution, Camelot Wheel)
// ============================================================================

function renderStatsDashboard() {
  const dashboard = document.getElementById('stats-dashboard');
  if (!dashboard) return;

  const tracks = window.tracks || [];
  const hasTracks = tracks.length > 0;

  dashboard.style.display = 'block';
  const total = tracks.length;
  const analyzed = tracks.filter(t => t.final_bpm).length;
  const classified = tracks.filter(t => t.final_genre && t.final_genre !== 'Unknown').length;
  const approved = tracks.filter(t => t.review_status === 'approved').length;

  // Collection summary
  document.getElementById('summary-total').textContent = total;
  document.getElementById('summary-analysed-pct').textContent = total ? Math.round((analyzed / total) * 100) + '%' : '0%';
  document.getElementById('summary-classified-pct').textContent = total ? Math.round((classified / total) * 100) + '%' : '0%';
  document.getElementById('summary-approved-pct').textContent = total ? Math.round((approved / total) * 100) + '%' : '0%';

  // Average LUFS
  const lufsTracks = tracks.filter(t => t.analyzed_lufs != null);
  const avgLufsEl = document.getElementById('summary-avg-lufs');
  if (avgLufsEl) {
    if (lufsTracks.length > 0) {
      const avgLufs = lufsTracks.reduce((sum, t) => sum + t.analyzed_lufs, 0) / lufsTracks.length;
      avgLufsEl.textContent = avgLufs.toFixed(1) + ' LUFS';
    } else {
      avgLufsEl.textContent = '\u2014';
    }
  }

  // Key distribution chart
  if (typeof Chart !== 'undefined') {
    renderKeyDistChart(tracks);
    renderEnergyDistChart(tracks);
    renderCamelotWheel(tracks);
  }

  // Age analysis — load once (only when we have tracks)
  if (hasTracks && !ageAnalysisData) {
    initAgeAnalysis();
    loadAgeAnalysis();
  }
}

function renderKeyDistChart(tracks) {
  const camelotKeys = ['1A','1B','2A','2B','3A','3B','4A','4B','5A','5B','6A','6B','7A','7B','8A','8B','9A','9B','10A','10B','11A','11B','12A','12B'];
  const counts = {};
  camelotKeys.forEach(k => counts[k] = 0);
  tracks.forEach(t => {
    if (t.final_key && counts.hasOwnProperty(t.final_key)) {
      counts[t.final_key]++;
    }
  });

  const labels = camelotKeys;
  const data = labels.map(k => counts[k]);
  const colors = labels.map(k => k.endsWith('A') ? 'rgba(96,165,250,0.7)' : 'rgba(139,92,246,0.7)');

  const ctx = document.getElementById('chart-key-dist');
  if (!ctx) return;

  if (chartInstances.keyDist) chartInstances.keyDist.destroy();

  chartInstances.keyDist = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Track Count',
        data: data,
        backgroundColor: colors,
        borderColor: labels.map(k => k.endsWith('A') ? '#60a5fa' : '#8b5cf6'),
        borderWidth: 1,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { color: '#888' }, grid: { color: '#2a2a3a' } },
        y: { ticks: { color: '#888', font: { size: 10 } }, grid: { color: '#2a2a3a' } }
      }
    }
  });
}

function renderEnergyDistChart(tracks) {
  const buckets = { '1-2': 0, '3-4': 0, '5-6': 0, '7-8': 0, '9-10': 0 };
  tracks.forEach(t => {
    const energy = parseFloat(t.analyzed_energy) || 0;
    if (energy <= 2) buckets['1-2']++;
    else if (energy <= 4) buckets['3-4']++;
    else if (energy <= 6) buckets['5-6']++;
    else if (energy <= 8) buckets['7-8']++;
    else buckets['9-10']++;
  });

  const labels = Object.keys(buckets);
  const data = Object.values(buckets);
  const colors = ['#34d399', '#60a5fa', '#fbbf24', '#f97316', '#f87171'];

  const ctx = document.getElementById('chart-energy-dist');
  if (!ctx) return;

  if (chartInstances.energyDist) chartInstances.energyDist.destroy();

  chartInstances.energyDist = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Track Count',
        data: data,
        backgroundColor: colors,
        borderWidth: 1,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { color: '#888' }, grid: { color: '#2a2a3a' } },
        x: { ticks: { color: '#888' }, grid: { color: '#2a2a3a' } }
      }
    }
  });
}

// ============================================================================
// Age Analysis
// ============================================================================

let ageAnalysisData = null;

function initAgeAnalysis() {
  const refreshBtn = document.getElementById('btn-refresh-age');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', loadAgeAnalysis);
  }
}

async function loadAgeAnalysis() {
  try {
    const data = await apiFetch('/api/stats/age');
    ageAnalysisData = data;
    renderAgeAnalysis(data);
  } catch (e) {
    // Error shown by apiFetch
  }
}

function renderAgeAnalysis(data) {
  if (!data) return;

  // Summary card
  document.getElementById('age-median-year').textContent = data.median_year || '--';

  const oldestTrack = data.oldest_tracks && data.oldest_tracks[0];
  document.getElementById('age-oldest-track').textContent = oldestTrack
    ? oldestTrack.title + ' (' + oldestTrack.year + ')'
    : '--';

  const newestTrack = data.newest_tracks && data.newest_tracks[data.newest_tracks.length - 1];
  document.getElementById('age-newest-track').textContent = newestTrack
    ? newestTrack.title + ' (' + newestTrack.year + ')'
    : '--';

  // Top decade
  const byDecade = data.by_decade || {};
  let topDecade = '--';
  let topDecadeCount = 0;
  Object.entries(byDecade).forEach(([decade, count]) => {
    if (decade !== 'Unknown' && count > topDecadeCount) {
      topDecadeCount = count;
      topDecade = decade;
    }
  });
  document.getElementById('age-top-decade').textContent = topDecade;

  // Decade distribution chart
  renderDecadeChart(byDecade);

  // Genre-Era stacked bar chart
  renderGenreEraChart(data.by_genre_decade || {});

  // Era labels
  renderEraLabels(data.era_labels || {});

  // Genre-decade table
  renderGenreDecadeTable(data.by_genre_decade || {}, Object.keys(byDecade).filter(d => d !== 'Unknown'));
}

function renderDecadeChart(byDecade) {
  const ctx = document.getElementById('chart-decade-dist');
  if (!ctx) return;

  if (chartInstances.decadeDist) chartInstances.decadeDist.destroy();

  const decadeOrder = Object.keys(byDecade).filter(d => d !== 'Unknown').sort();
  if (byDecade['Unknown'] !== undefined) decadeOrder.push('Unknown');

  const labels = decadeOrder;
  const data = labels.map(d => byDecade[d]);

  const decadeColors = {
    '1960s': '#f87171', '1970s': '#fb923c', '1980s': '#fbbf24',
    '1990s': '#a3e635', '2000s': '#34d399', '2010s': '#60a5fa',
    '2020s': '#8b5cf6', 'Unknown': '#6b7280'
  };

  chartInstances.decadeDist = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Track Count',
        data: data,
        backgroundColor: labels.map(d => decadeColors[d] || '#888'),
        borderWidth: 1,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { color: '#888' }, grid: { color: '#2a2a3a' } },
        y: { ticks: { color: '#888' }, grid: { color: '#2a2a3a' } }
      }
    }
  });
}

function renderGenreEraChart(byGenreDecade) {
  const ctx = document.getElementById('chart-genre-era');
  if (!ctx) return;

  if (chartInstances.genreEra) chartInstances.genreEra.destroy();

  const genres = Object.keys(byGenreDecade).sort((a, b) => {
    const totalA = Object.values(byGenreDecade[a]).reduce((s, v) => s + v, 0);
    const totalB = Object.values(byGenreDecade[b]).reduce((s, v) => s + v, 0);
    return totalB - totalA;
  }).slice(0, 10);

  const allDecades = new Set();
  genres.forEach(g => Object.keys(byGenreDecade[g]).forEach(d => allDecades.add(d)));
  const decades = Array.from(allDecades).sort();

  const decadeColors = {
    '1960s': '#f87171', '1970s': '#fb923c', '1980s': '#fbbf24',
    '1990s': '#a3e635', '2000s': '#34d399', '2010s': '#60a5fa',
    '2020s': '#8b5cf6', 'Unknown': '#6b7280'
  };

  const datasets = decades.map(decade => ({
    label: decade,
    data: genres.map(g => byGenreDecade[g][decade] || 0),
    backgroundColor: decadeColors[decade] || '#888',
  }));

  chartInstances.genreEra = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: genres,
      datasets: datasets,
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: { color: '#888', boxWidth: 12, padding: 8, font: { size: 10 } }
        }
      },
      scales: {
        x: { stacked: true, beginAtZero: true, ticks: { color: '#888' }, grid: { color: '#2a2a3a' } },
        y: { stacked: true, ticks: { color: '#888', font: { size: 10 } }, grid: { color: '#2a2a3a' } }
      }
    }
  });
}

function renderEraLabels(eraLabels) {
  const container = document.getElementById('era-labels-list');
  if (!container) return;

  if (!Object.keys(eraLabels).length) {
    container.innerHTML = '<p style="color:var(--text-secondary);font-size:12px;">No era data available</p>';
    return;
  }

  container.innerHTML = Object.entries(eraLabels)
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) =>
      '<div class="era-label-item">' +
      '<span class="era-label-name">' + escapeHtml(name) + '</span>' +
      '<span class="era-label-count">' + count + '</span>' +
      '</div>'
    ).join('');
}

function renderGenreDecadeTable(byGenreDecade, decades) {
  const container = document.getElementById('genre-decade-table-wrap');
  if (!container) return;

  const genres = Object.keys(byGenreDecade).sort((a, b) => {
    const totalA = Object.values(byGenreDecade[a]).reduce((s, v) => s + v, 0);
    const totalB = Object.values(byGenreDecade[b]).reduce((s, v) => s + v, 0);
    return totalB - totalA;
  }).slice(0, 15);

  if (!genres.length) {
    container.innerHTML = '<p style="color:var(--text-secondary);font-size:12px;">No genre-decade data</p>';
    return;
  }

  let html = '<table class="genre-decade-table"><thead><tr>';
  html += '<th>Genre</th>';
  decades.forEach(d => { html += '<th>' + escapeHtml(d) + '</th>'; });
  html += '<th>Total</th></tr></thead><tbody>';

  genres.forEach(genre => {
    html += '<tr><td class="genre-col">' + escapeHtml(genre) + '</td>';
    let total = 0;
    decades.forEach(d => {
      const count = byGenreDecade[genre][d] || 0;
      total += count;
      html += '<td class="count-cell">' + (count || '') + '</td>';
    });
    html += '<td class="total-col">' + total + '</td></tr>';
  });

  html += '</tbody></table>';
  container.innerHTML = html;
}

function renderCamelotWheel(tracks) {
  const svg = document.getElementById('camelot-wheel-svg');
  const statsEl = document.getElementById('camelot-wheel-stats');
  if (!svg) return;

  svg.innerHTML = '';

  // Count tracks per Camelot key
  const keyCounts = {};
  const allCamelotKeys = [];
  for (let i = 1; i <= 12; i++) { allCamelotKeys.push(`${i}A`); allCamelotKeys.push(`${i}B`); }
  allCamelotKeys.forEach(k => keyCounts[k] = 0);
  tracks.forEach(t => {
    if (t.final_key && keyCounts.hasOwnProperty(t.final_key)) {
      keyCounts[t.final_key]++;
    }
  });

  const maxCount = Math.max(...Object.values(keyCounts), 1);
  const size = 280;
  const center = size / 2;
  const outerR = 120;
  const innerR = 80;
  const coreR = 30;

  const getAngle = (pos) => ((pos - 1) * 30 - 90) * Math.PI / 180;

  // Draw outer ring (B = major keys)
  for (let i = 1; i <= 12; i++) {
    const key = `${i}B`;
    const count = keyCounts[key];
    const intensity = count / maxCount;
    const startAngle = getAngle(i);
    const endAngle = getAngle(i + 1 > 12 ? 1 : i + 1);

    const x1 = center + innerR * Math.cos(startAngle);
    const y1 = center + innerR * Math.sin(startAngle);
    const x2 = center + outerR * Math.cos(startAngle);
    const y2 = center + outerR * Math.sin(startAngle);
    const x3 = center + outerR * Math.cos(endAngle);
    const y3 = center + outerR * Math.sin(endAngle);
    const x4 = center + innerR * Math.cos(endAngle);
    const y4 = center + innerR * Math.sin(endAngle);

    const alpha = 0.15 + intensity * 0.65;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M ${x1} ${y1} L ${x2} ${y2} A ${outerR} ${outerR} 0 0 1 ${x3} ${y3} L ${x4} ${y4} A ${innerR} ${innerR} 0 0 0 ${x1} ${y1} Z`);
    path.setAttribute('fill', `rgba(139,92,246,${alpha})`);
    path.setAttribute('stroke', '#8b5cf6');
    path.setAttribute('stroke-width', '0.5');
    svg.appendChild(path);

    // Label
    const midAngle = (startAngle + endAngle) / 2;
    const labelR = (innerR + outerR) / 2;
    const lx = center + labelR * Math.cos(midAngle);
    const ly = center + labelR * Math.sin(midAngle);
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', lx);
    text.setAttribute('y', ly);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('font-size', '9');
    text.setAttribute('font-weight', '600');
    text.setAttribute('fill', '#c8c8e4');
    text.textContent = key;
    svg.appendChild(text);
  }

  // Draw inner ring (A = minor keys)
  for (let i = 1; i <= 12; i++) {
    const key = `${i}A`;
    const count = keyCounts[key];
    const intensity = count / maxCount;
    const startAngle = getAngle(i);
    const endAngle = getAngle(i + 1 > 12 ? 1 : i + 1);

    const x1 = center + coreR * Math.cos(startAngle);
    const y1 = center + coreR * Math.sin(startAngle);
    const x2 = center + innerR * Math.cos(startAngle);
    const y2 = center + innerR * Math.sin(startAngle);
    const x3 = center + innerR * Math.cos(endAngle);
    const y3 = center + innerR * Math.sin(endAngle);
    const x4 = center + coreR * Math.cos(endAngle);
    const y4 = center + coreR * Math.sin(endAngle);

    const alpha = 0.15 + intensity * 0.65;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M ${x1} ${y1} L ${x2} ${y2} A ${innerR} ${innerR} 0 0 1 ${x3} ${y3} L ${x4} ${y4} A ${coreR} ${coreR} 0 0 0 ${x1} ${y1} Z`);
    path.setAttribute('fill', `rgba(96,165,250,${alpha})`);
    path.setAttribute('stroke', '#60a5fa');
    path.setAttribute('stroke-width', '0.5');
    svg.appendChild(path);

    // Label
    const midAngle = (startAngle + endAngle) / 2;
    const labelR = (coreR + innerR) / 2;
    const lx = center + labelR * Math.cos(midAngle);
    const ly = center + labelR * Math.sin(midAngle);
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', lx);
    text.setAttribute('y', ly);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('font-size', '9');
    text.setAttribute('font-weight', '600');
    text.setAttribute('fill', '#c8c8e4');
    text.textContent = key;
    svg.appendChild(text);
  }

  // Center circle
  const centerCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  centerCircle.setAttribute('cx', center);
  centerCircle.setAttribute('cy', center);
  centerCircle.setAttribute('r', coreR - 2);
  centerCircle.setAttribute('fill', '#111119');
  centerCircle.setAttribute('stroke', '#21213a');
  svg.appendChild(centerCircle);

  const centerText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  centerText.setAttribute('x', center);
  centerText.setAttribute('y', center);
  centerText.setAttribute('text-anchor', 'middle');
  centerText.setAttribute('dominant-baseline', 'middle');
  centerText.setAttribute('font-size', '10');
  centerText.setAttribute('font-weight', '700');
  centerText.setAttribute('fill', '#8b5cf6');
  centerText.textContent = tracks.length;
  svg.appendChild(centerText);

  // Stats below wheel
  if (statsEl) {
    const sorted = Object.entries(keyCounts).filter(([, c]) => c > 0).sort((a, b) => b[1] - a[1]);
    statsEl.innerHTML = '<div style="display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:8px;">' +
      sorted.map(([key, count]) =>
        `<span class="camelot-key-badge" style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:10px;font-size:11px;background:var(--bg-subtle);border:1px solid var(--border);">
          <span style="color:${key.endsWith('A') ? '#60a5fa' : '#8b5cf6'};font-weight:600;">${key}</span>
          <span style="color:var(--text-secondary);">${count}</span>
        </span>`
      ).join('') + '</div>';
  }
}

