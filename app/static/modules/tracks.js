// ============================================================================
// Tracks Tab
// ============================================================================

function initTracksTab() {
  const filterGenre = document.getElementById('filter-genre');
  const filterStatus = document.getElementById('filter-status');
  const searchInput = document.getElementById('search-tracks');

  // Load taxonomy for genre filter
  apiFetch('/api/taxonomy')
    .then(data => {
      window.taxonomy = data.genres || {};
      populateGenreFilters();
    });

  filterGenre.addEventListener('change', renderTracks);
  filterStatus.addEventListener('change', renderTracks);
  // Search input — handled by initSearchFeature() to avoid duplicate listeners

  // Sortable headers
  document.querySelectorAll('.tracks-table th.sortable').forEach(header => {
    header.addEventListener('click', () => {
      const field = header.dataset.sort;
      if (window.currentSort.field === field) {
        window.currentSort.direction = window.currentSort.direction === 'asc' ? 'desc' : 'asc';
      } else {
        window.currentSort.field = field;
        window.currentSort.direction = 'asc';
      }

      // Update visual indicators
      document.querySelectorAll('.tracks-table th.sortable').forEach(h => {
        h.classList.remove('sort-asc', 'sort-desc');
      });
      header.classList.add(`sort-${window.currentSort.direction}`);

      renderTracks();
    });
  });
}

function populateGenreFilters() {
  const select = document.getElementById('filter-genre');
  select.innerHTML = '<option value="">All Genres</option>';
  Object.keys(window.taxonomy).forEach(genre => {
    const option = document.createElement('option');
    option.value = genre;
    option.textContent = genre;
    select.appendChild(option);
  });
}

function getFilteredTracks() {
  // Use server-side search results if a search is active
  let filtered = window.searchResults !== null
    ? [...window.searchResults]
    : [...(window.tracks || [])];

  // Genre filter
  const genreEl = document.getElementById('filter-genre');
  const genreFilter = genreEl ? genreEl.value : '';
  if (genreFilter) {
    filtered = filtered.filter(t => t.final_genre === genreFilter);
  }

  // Status filter
  const statusEl = document.getElementById('filter-status');
  const statusFilter = statusEl ? statusEl.value : '';
  if (statusFilter) {
    filtered = filtered.filter(t => t.review_status === statusFilter);
  }

  return filtered;
}

function sortTracks(tracks) {
  const sorted = [...tracks];
  sorted.sort((a, b) => {
    let aVal = a[window.currentSort.field] || '';
    let bVal = b[window.currentSort.field] || '';

    // Handle numeric fields
    if (window.currentSort.field === 'confidence' || window.currentSort.field === 'final_bpm' || window.currentSort.field === 'final_year') {
      aVal = parseFloat(aVal) || 0;
      bVal = parseFloat(bVal) || 0;
    } else {
      aVal = String(aVal).toLowerCase();
      bVal = String(bVal).toLowerCase();
    }

    if (aVal < bVal) return window.currentSort.direction === 'asc' ? -1 : 1;
    if (aVal > bVal) return window.currentSort.direction === 'asc' ? 1 : -1;
    return 0;
  });

  return sorted;
}

function drawWaveformThumb(canvas, data) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  const midY = h / 2;
  const barW = Math.max(1, w / data.length);

  ctx.clearRect(0, 0, w, h);

  // Subtle center line
  ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, midY);
  ctx.lineTo(w, midY);
  ctx.stroke();

  // Bars — teal gradient matching app accent colour
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, 'rgba(0,210,190,0.9)');
  grad.addColorStop(1, 'rgba(0,210,190,0.3)');
  ctx.fillStyle = grad;

  data.forEach((amp, i) => {
    const barH = Math.max(1, amp * midY);
    const x = i * barW;
    // Draw mirrored bar (top + bottom)
    ctx.fillRect(x, midY - barH, barW - 1, barH);
    ctx.fillRect(x, midY, barW - 1, barH);
  });
}

function getConfidenceBadgeClass(confidence) {
  if (confidence >= 80) return 'confidence-high';
  if (confidence >= 60) return 'confidence-mid';
  return 'confidence-low';
}

function getStatusBadge(status) {
  const badges = {
    pending: 'badge-pending',
    approved: 'badge-approved',
    skipped: 'badge-skipped',
    written: 'badge-written',
  };
  return badges[status] || 'badge-pending';
}

function renderTracks() {
  const tbody = document.getElementById('tracks-tbody');
  const filtered = getFilteredTracks();
  const sorted = sortTracks(filtered);

  tbody.innerHTML = '';

  // Reset to page 1 when filter/sort changes
  window.currentPage = 1;

  // Update pipeline stepper
  updatePipelineStepper();

  if (!sorted.length) {
    const row = document.createElement('tr');
    row.className = 'empty-state';
    const cell = document.createElement('td');
    cell.colSpan = '16';
    cell.textContent = 'No tracks match filters';
    row.appendChild(cell);
    tbody.appendChild(row);
    const countEl = document.getElementById('tracks-count');
    if (countEl) countEl.textContent = '0 tracks';
    updatePaginationControls(sorted.length);
    return;
  }

  // Pagination: slice to current page
  const start = (window.currentPage - 1) * TRACKS_PER_PAGE;
  const end = start + TRACKS_PER_PAGE;
  const pageData = sorted.slice(start, end);

  pageData.forEach(track => {
    const row = document.createElement('tr');
    row.style.cursor = 'pointer';

    const confidenceClass = getConfidenceBadgeClass(track.confidence || 0);
    const statusBadge = getStatusBadge(track.review_status);

    // Checkbox (new column for bulk select)
    const tdCheckbox = document.createElement('td');
    tdCheckbox.className = 'checkbox-col';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.dataset.filePath = track.file_path;
    checkbox.addEventListener('click', (e) => e.stopPropagation());
    tdCheckbox.appendChild(checkbox);
    row.appendChild(tdCheckbox);

    // Title
    const tdTitle = document.createElement('td');
    tdTitle.textContent = track.display_title || '—';
    row.appendChild(tdTitle);

    // Artist
    const tdArtist = document.createElement('td');
    tdArtist.textContent = track.display_artist || '—';
    row.appendChild(tdArtist);

    // Genre (with color chip)
    const tdGenre = document.createElement('td');
    tdGenre.innerHTML = genreChip(track.final_genre);
    row.appendChild(tdGenre);

    // Sub-genre (with color chip)
    const tdSubgenre = document.createElement('td');
    tdSubgenre.innerHTML = genreChip(track.final_subgenre);
    row.appendChild(tdSubgenre);

    // Confidence (with colored badge)
    const tdConfidence = document.createElement('td');
    tdConfidence.innerHTML = confidenceBadge(track.confidence);
    row.appendChild(tdConfidence);

    // BPM
    const tdBpm = document.createElement('td');
    tdBpm.textContent = track.final_bpm || '—';
    row.appendChild(tdBpm);

    // Key
    const tdKey = document.createElement('td');
    tdKey.textContent = track.final_key || '—';
    row.appendChild(tdKey);

    // Clave
    const tdClave = document.createElement('td');
    if (track.latin_analysis_done && track.clave_pattern) {
      const claveBadge = document.createElement('span');
      claveBadge.className = `clave-badge ${track.clave_pattern === '2-3' ? 'clave-badge-2-3' : 'clave-badge-3-2'}`;
      claveBadge.textContent = track.clave_pattern;
      tdClave.appendChild(claveBadge);
    } else {
      tdClave.textContent = '—';
      tdClave.style.color = 'var(--text-muted)';
    }
    row.appendChild(tdClave);

    // Vocal
    const tdVocal = document.createElement('td');
    if (track.vocal_flag) {
      const vClass = track.vocal_flag === 'vocal' ? 'vocal-badge-vocal'
                   : track.vocal_flag === 'instrumental' ? 'vocal-badge-instrumental'
                   : 'vocal-badge-mostly';
      const vLabel = track.vocal_flag === 'vocal' ? 'Vocal'
                   : track.vocal_flag === 'instrumental' ? 'Instr.'
                   : 'Mostly Instr.';
      tdVocal.innerHTML = `<span class="vocal-badge ${vClass}">${vLabel}</span>`;
    } else {
      tdVocal.textContent = '—';
      tdVocal.style.color = 'var(--text-muted)';
    }
    row.appendChild(tdVocal);

    // Tempo category
    const tdTempo = document.createElement('td');
    if (track.tempo_category) {
      const tClass = track.tempo_category === 'fast' ? 'tempo-fast'
                   : track.tempo_category === 'slow' ? 'tempo-slow'
                   : 'tempo-medium';
      tdTempo.innerHTML = `<span class="tempo-badge ${tClass}">${track.tempo_category}</span>`;
    } else {
      tdTempo.textContent = '—';
      tdTempo.style.color = 'var(--text-muted)';
    }
    row.appendChild(tdTempo);

    // LUFS
    const tdLufs = document.createElement('td');
    if (track.analyzed_lufs != null) {
      const lufsVal = track.analyzed_lufs;
      const lufsClass = (lufsVal >= -14 && lufsVal <= -8) ? 'lufs-good'
                        : (lufsVal >= -18 && lufsVal < -14) || (lufsVal > -8 && lufsVal <= -6) ? 'lufs-quiet'
                        : 'lufs-loud';
      tdLufs.innerHTML = `<span class="${lufsClass}">${lufsVal}</span>`;
    } else {
      tdLufs.textContent = '—';
      tdLufs.style.color = 'var(--text-muted)';
    }
    row.appendChild(tdLufs);

    // Year
    const tdYear = document.createElement('td');
    tdYear.textContent = track.final_year || '—';
    row.appendChild(tdYear);

    // Status
    const tdStatus = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = `badge ${statusBadge}`;
    badge.textContent = track.review_status;
    tdStatus.appendChild(badge);
    row.appendChild(tdStatus);

    // Approve cell
    const approveTd = document.createElement('td');
    approveTd.className = 'approve-col';
    if (track.proposed_genre) {
      const approveBtn = document.createElement('button');
      const st = track.review_status;
      approveBtn.className = 'approve-btn' + (st === 'approved' ? ' approved' : st === 'skipped' ? ' skipped' : '');
      approveBtn.textContent = st === 'approved' ? '✓' : st === 'skipped' ? '–' : '✓';
      approveBtn.title = st === 'approved' ? 'Approved — click to undo' : 'Click to approve';
      approveBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const newStatus = track.review_status === 'approved' ? 'pending' : 'approved';
        try {
          await apiFetch('/api/tracks/by-path?path=' + encodeURIComponent(track.file_path), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ review_status: newStatus })
          });
          const found = window.tracks.find(x => x.file_path === track.file_path);
          if (found) found.review_status = newStatus;
          renderTracks();
          updateStats();
          updateToolbarButtonStates();
        } catch (err) {
          showToast('Could not update status', 'error');
        }
      });
      approveTd.appendChild(approveBtn);
    } else {
      const dash = document.createElement('span');
      dash.style.cssText = 'color:var(--text-placeholder);font-size:11px;';
      dash.textContent = '—';
      approveTd.appendChild(dash);
    }
    row.appendChild(approveTd);

    // Action
    const tdAction = document.createElement('td');
    tdAction.style.textAlign = 'center';
    tdAction.style.display = 'flex';
    tdAction.style.gap = '4px';
    tdAction.style.justifyContent = 'center';

    const btnDetails = document.createElement('button');
    btnDetails.className = 'btn btn-secondary';
    btnDetails.style.padding = '4px 8px';
    btnDetails.style.fontSize = '12px';
    btnDetails.title = 'View details';
    btnDetails.textContent = '▼';
    btnDetails.addEventListener('click', (e) => {
      e.stopPropagation();
      openTrackDetail(track);
    });
    tdAction.appendChild(btnDetails);

    const btnPlay = document.createElement('button');
    btnPlay.className = 'btn btn-secondary';
    btnPlay.style.padding = '4px 8px';
    btnPlay.style.fontSize = '12px';
    btnPlay.title = 'Play preview';
    btnPlay.textContent = '▶';
    btnPlay.addEventListener('click', (e) => {
      e.stopPropagation();
      playTrack(track);
    });
    tdAction.appendChild(btnPlay);

    const btnSetlist = document.createElement('button');
    btnSetlist.className = 'btn btn-secondary';
    btnSetlist.style.padding = '4px 8px';
    btnSetlist.style.fontSize = '12px';
    btnSetlist.title = 'Add to setlist';
    btnSetlist.textContent = '+';
    btnSetlist.addEventListener('click', (e) => {
      e.stopPropagation();
      addTrackToSetlist(track.file_path);
    });
    tdAction.appendChild(btnSetlist);

    const btnEdit = document.createElement('button');
    btnEdit.className = 'btn btn-secondary';
    btnEdit.style.padding = '4px 8px';
    btnEdit.style.fontSize = '12px';
    btnEdit.title = 'Edit track';
    btnEdit.textContent = '✎';
    btnEdit.addEventListener('click', (e) => {
      e.stopPropagation();
      openEditModal(track.file_path);
    });
    tdAction.appendChild(btnEdit);
    row.appendChild(tdAction);

    tbody.appendChild(row);
  });

  const countEl = document.getElementById('tracks-count');
  if (countEl) {
    countEl.textContent = `${sorted.length} track${sorted.length !== 1 ? 's' : ''} (page ${window.currentPage})`;
  }
  updatePaginationControls(sorted.length);
}

// Pagination controls
function updatePaginationControls(totalTracks) {
  const totalPages = Math.ceil(totalTracks / TRACKS_PER_PAGE);
  let container = document.getElementById('tracks-pagination');

  if (!container) {
    // Fallback to pagination-info if tracks-pagination doesn't exist
    container = document.getElementById('pagination-info');
  }

  if (!container) return;
  container.innerHTML = '';
  container.style.display = 'flex';
  container.style.gap = '12px';
  container.style.justifyContent = 'center';
  container.style.padding = '12px 0';
  container.style.alignItems = 'center';

  if (totalPages <= 1) return;

  const prevBtn = document.createElement('button');
  prevBtn.className = 'btn btn-secondary';
  prevBtn.textContent = '← Prev';
  prevBtn.disabled = window.currentPage === 1;
  prevBtn.addEventListener('click', () => {
    if (window.currentPage > 1) {
      window.currentPage--;
      renderTracks();
    }
  });
  container.appendChild(prevBtn);

  const pageInfo = document.createElement('span');
  pageInfo.textContent = `Page ${window.currentPage} of ${totalPages}`;
  pageInfo.style.margin = '0 12px';
  pageInfo.style.alignSelf = 'center';
  container.appendChild(pageInfo);

  const nextBtn = document.createElement('button');
  nextBtn.className = 'btn btn-secondary';
  nextBtn.textContent = 'Next →';
  nextBtn.disabled = window.currentPage === totalPages;
  nextBtn.addEventListener('click', () => {
    if (window.currentPage < totalPages) {
      window.currentPage++;
      renderTracks();
    }
  });
  container.appendChild(nextBtn);
}

// Audio Player Control
function toggleAudioPlay(btn, filePath) {
  const audio = document.getElementById('audio-player');

  // If different file, stop current and play new
  const audioUrl = `/api/audio?path=${encodeURIComponent(filePath)}`;
  const isSameFile = audio.src.endsWith(audioUrl) || audio.src === audioUrl;
  if (currentAudioPlayer !== audio || !isSameFile) {
    // Stop any playing audio
    audio.pause();

    // Update all buttons
    document.querySelectorAll('.audio-play-btn').forEach(b => {
      b.classList.remove('playing');
      b.textContent = '▶';
    });

    // Set new source and play — wait for canplay before calling play()
    audio.src = audioUrl;
    currentAudioPlayer = audio;
    audio.load();

    btn.classList.add('playing');
    btn.textContent = '⏸';

    audio.addEventListener('canplay', function onCanPlay() {
      audio.removeEventListener('canplay', onCanPlay);
      audio.play().catch(err => {
        showToast('Could not play audio', 'error');
        console.error('Audio play error:', err);
        btn.classList.remove('playing');
        btn.textContent = '▶';
      });
    }, { once: true });

    audio.addEventListener('error', function onAudioError() {
      audio.removeEventListener('error', onAudioError);
      showToast('Could not load audio', 'error');
      btn.classList.remove('playing');
      btn.textContent = '▶';
    }, { once: true });

    // Update progress bar
    const updateProgress = () => {
      const allBtns = document.querySelectorAll('.audio-play-btn');
      allBtns.forEach(b => {
        if (b.dataset.filePath === filePath) {
          const progress = b.closest('.review-item-audio')?.querySelector('.audio-progress-fill');
          if (progress && audio.duration) {
            const percent = (audio.currentTime / audio.duration) * 100;
            progress.style.width = percent + '%';
          }
        }
      });
    };

    audio.ontimeupdate = updateProgress;

    audio.onended = () => {
      btn.classList.remove('playing');
      btn.textContent = '▶';
      const progress = btn.closest('.review-item-audio')?.querySelector('.audio-progress-fill');
      if (progress) progress.style.width = '0%';
    };
  } else if (audio.paused) {
    // Resume
    audio.play();
    btn.classList.add('playing');
    btn.textContent = '⏸';
  } else {
    // Pause
    audio.pause();
    btn.classList.remove('playing');
    btn.textContent = '▶';
  }
}

