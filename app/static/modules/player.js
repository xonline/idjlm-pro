// ============================================================================
// player.js — Audio player (bottom bar) + render-template helpers
// ============================================================================
// Extracted from pipeline.js (Phase 0.3). No behaviour change.
// Owns:
//   - Audio player bottom bar (initAudioPlayer, playTrack, formatTime)
//   - Render-template helpers used by tracks.js renderTracks()
//     (confidenceBadge, energyBar, genreChip, statusDot, getColumnToggleMenu)
//   - Column toggle state (initColumnToggle)
// Loaded BEFORE tracks.js so renderTrack() finds the helpers at runtime.
// ----------------------------------------------------------------------------

// State shared with playTrack / initAudioPlayer
let currentPlayingTrack = null;
let currentTrackIndex = -1;

// ============================================================================
// Audio Player Bottom Bar
// ============================================================================

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
    playPauseBtn.textContent = '';
    const iconPlay = document.getElementById('icon-play');
    const iconPause = document.getElementById('icon-pause');
    if (iconPlay)  iconPlay.style.display  = 'block';
    if (iconPause) iconPause.style.display = 'none';
    nextBtn.click();
  });

  playPauseBtn.addEventListener('click', () => {
    if (audio.paused) {
      audio.play();
      playPauseBtn.textContent = '';
      const iconPlay = document.getElementById('icon-play');
      const iconPause = document.getElementById('icon-pause');
      if (iconPlay)  iconPlay.style.display  = 'none';
      if (iconPause) iconPause.style.display = 'block';
    } else {
      audio.pause();
      playPauseBtn.textContent = '';
      const iconPlay = document.getElementById('icon-play');
      const iconPause = document.getElementById('icon-pause');
      if (iconPlay)  iconPlay.style.display  = 'block';
      if (iconPause) iconPause.style.display = 'none';
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
      if (playPauseBtn) playPauseBtn.textContent = '';
      const ip = document.getElementById('icon-play');
      const ipu = document.getElementById('icon-pause');
      if (ip)  ip.style.display  = 'block';
      if (ipu) ipu.style.display = 'none';
    });
  }, { once: true });

  audio.addEventListener('error', function onAudioError() {
    audio.removeEventListener('error', onAudioError);
    showToast('Could not load audio — check file format', 'error');
    bar.classList.add('hidden');
  }, { once: true });
  playPauseBtn.textContent = '';
  const ip2 = document.getElementById('icon-play');
  const ipu2 = document.getElementById('icon-pause');
  if (ip2)  ip2.style.display  = 'none';
  if (ipu2) ipu2.style.display = 'block';
}

function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

// ============================================================================
// Render-template helpers used by tracks.js renderTracks()
// ============================================================================
// Confidence Badges & Energy Bars
// ----------------------------------------------------------------------------

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

// ----------------------------------------------------------------------------
// Genre Color Chips
// ----------------------------------------------------------------------------

const GENRE_COLORS = ['#8b5cf6','#06b6d4','#f59e0b','#10b981','#ef4444','#ec4899','#6366f1','#14b8a6'];

/**
 * @param {string} genre
 * @param {boolean} manual - true if genre was manually edited by user
 */
function genreChip(genre, manual) {
  if (!genre) return '—';
  const hash = [...genre].reduce(function(a, c) { return a + c.charCodeAt(0); }, 0);
  const color = GENRE_COLORS[hash % GENRE_COLORS.length];
  var manualAttr = manual ? ' data-manual="true"' : '';
  return '<span class="genre-pill" style="--pill-color:' + color + '"' + manualAttr + '>' + escapeHtml(genre) + '</span>';
}

// ----------------------------------------------------------------------------
// Column Toggle
// ----------------------------------------------------------------------------

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

// ----------------------------------------------------------------------------
// Status Indicators
// ----------------------------------------------------------------------------

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


// --- ES module bridge (0.4): expose to global scope for cross-module calls ---
window.confidenceBadge = confidenceBadge;
window.formatTime = formatTime;
window.genreChip = genreChip;
window.initAudioPlayer = initAudioPlayer;
window.initColumnToggle = initColumnToggle;
window.playTrack = playTrack;
