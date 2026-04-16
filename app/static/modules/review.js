// ============================================================================
// Review Tab
// ============================================================================

function initReviewTab() {
  const slider = document.getElementById('confidence-slider');
  const valueSpan = document.getElementById('confidence-value');
  const thresholdPct = document.getElementById('threshold-pct');
  const btnBulkApprove = document.getElementById('btn-bulk-approve');
  const btnWriteTags = document.getElementById('btn-write-tags');
  const btnExportPlaylist = document.getElementById('btn-export-playlist');
  const exportMenu = document.getElementById('export-menu');
  const btnExportAll = document.getElementById('btn-export-all-approved');
  const btnExportByGenre = document.getElementById('btn-export-by-genre');

  // Export dropdown toggle
  btnExportPlaylist.addEventListener('click', (e) => {
    e.stopPropagation();
    exportMenu.style.display = exportMenu.style.display === 'none' ? 'block' : 'none';
  });

  // Close dropdown when clicking elsewhere
  document.addEventListener('click', () => {
    exportMenu.style.display = 'none';
  });

  // Export all approved
  btnExportAll.addEventListener('click', () => {
    const split = document.getElementById('checkbox-split-m3u').checked;
    const chunkSize = document.getElementById('select-chunk-size')?.value || '500';
    let url = '/api/export/m3u?status=approved';
    if (split) {
      url += `&split=true&chunk_size=${chunkSize}`;
    }
    window.location = url;
    exportMenu.style.display = 'none';
    showToast('Downloading playlist...', 'info');
  });

  // Export by genre
  btnExportByGenre.addEventListener('click', () => {
    showGenreSelector();
    exportMenu.style.display = 'none';
  });

  // Split M3U checkbox
  const checkboxSplitM3u = document.getElementById('checkbox-split-m3u');
  if (checkboxSplitM3u) {
    checkboxSplitM3u.addEventListener('change', () => {
      // Store checkbox state in session storage
      sessionStorage.setItem('splitM3u', checkboxSplitM3u.checked);
    });
  }

  // Export cue sheet
  const btnExportCueSheet = document.getElementById('btn-export-cue-sheet');
  if (btnExportCueSheet) {
    btnExportCueSheet.addEventListener('click', async () => {
      try {
        // Fetch cue sheet data
        const result = await apiFetch('/api/export/cue-sheet', {
          method: 'GET',
        });

        // Convert to JSON and trigger download
        const dataStr = JSON.stringify(result, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `cue-sheet-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        exportMenu.style.display = 'none';
        showToast('Cue sheet exported', 'success');
      } catch (error) {
        // Error already shown in apiFetch
      }
    });
  }

  slider.addEventListener('input', () => {
    const value = slider.value;
    valueSpan.textContent = value + '%';
    thresholdPct.textContent = value;
  });

  btnBulkApprove.addEventListener('click', async () => {
    const threshold = parseInt(slider.value);
    showSpinner(`Bulk approving tracks ≥ ${threshold}%...`);
    try {
      const result = await apiFetch('/api/review/bulk-approve', {
        method: 'POST',
        body: JSON.stringify({ min_confidence: threshold }),
      });

      // Update tracks
      result.forEach(trackPath => {
        const track = window.tracks.find(t => t.file_path === trackPath);
        if (track) {
          track.review_status = 'approved';
        }
      });

      showToast(`Approved ${result.length} tracks`, 'success');
      renderReview();
      updateStats();
    } catch (error) {
      // Error shown in apiFetch
    } finally {
      hideSpinner();
    }
  });

  btnWriteTags.addEventListener('click', async () => {
    showSpinner('Writing tags to files...');
    try {
      const result = await apiFetch('/api/review/write', {
        method: 'POST',
        body: JSON.stringify({ track_paths: [] }), // Empty = all approved
      });

      // Update tracks
      result.forEach(trackPath => {
        const track = window.tracks.find(t => t.file_path === trackPath);
        if (track) {
          track.tags_written = true;
          track.review_status = 'written';
        }
      });

      showToast(`Tags written to ${result.length} files`, 'success');
      renderReview();
      renderTracks();
      updateStats();
    } catch (error) {
      // Error shown
    } finally {
      hideSpinner();
    }
  });
}

function getPendingTracks() {
  return window.tracks.filter(t => t.review_status === 'pending');
}

function renderReview() {
  const list = document.getElementById('review-list');
  const pending = getPendingTracks();
  const approvedCount = window.tracks.filter(t => t.review_status === 'approved').length;

  document.getElementById('approved-count').textContent = approvedCount;
  document.getElementById('btn-write-tags').disabled = approvedCount === 0;

  list.innerHTML = '';

  if (!pending.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'No pending tracks to review';
    list.appendChild(empty);
    return;
  }

  pending.forEach(track => {
    const item = document.createElement('div');
    item.className = 'review-item';

    const confidenceValue = track.confidence || 0;
    let confidenceClass = 'low';
    if (confidenceValue >= 80) confidenceClass = 'high';
    else if (confidenceValue >= 60) confidenceClass = 'medium';

    const existingChanged = track.existing_genre !== track.final_genre;

    // Header
    const header = document.createElement('div');
    header.className = 'review-item-header';

    const titleDiv = document.createElement('div');
    const titleStrong = document.createElement('div');
    titleStrong.className = 'review-item-title';
    titleStrong.textContent = track.display_title || track.filename;
    titleDiv.appendChild(titleStrong);

    const artistDiv = document.createElement('div');
    artistDiv.style.fontSize = '12px';
    artistDiv.style.color = '#888';
    artistDiv.style.marginTop = '4px';
    artistDiv.textContent = track.display_artist || 'Unknown Artist';
    titleDiv.appendChild(artistDiv);

    // Audio player
    const audioContainer = document.createElement('div');
    audioContainer.className = 'review-item-audio';
    const playBtn = document.createElement('button');
    playBtn.className = 'audio-play-btn';
    playBtn.textContent = '▶';
    playBtn.dataset.filePath = track.file_path;
    playBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleAudioPlay(playBtn, track.file_path);
    });
    audioContainer.appendChild(playBtn);

    const progressContainer = document.createElement('div');
    progressContainer.className = 'audio-progress';
    const progressFill = document.createElement('div');
    progressFill.className = 'audio-progress-fill';
    progressContainer.appendChild(progressFill);
    progressContainer.addEventListener('click', (e) => {
      if (currentAudioPlayer) {
        const percent = e.offsetX / progressContainer.offsetWidth;
        currentAudioPlayer.currentTime = percent * currentAudioPlayer.duration;
      }
    });
    audioContainer.appendChild(progressContainer);

    titleDiv.appendChild(audioContainer);
    header.appendChild(titleDiv);

    const confBadge = document.createElement('div');
    confBadge.className = `review-item-confidence ${confidenceClass}`;
    confBadge.textContent = `${Math.round(confidenceValue)}% confident`;
    header.appendChild(confBadge);

    item.appendChild(header);

    // Diff view
    const diff = document.createElement('div');
    diff.className = 'review-diff';

    // Left column - current
    const leftCol = document.createElement('div');
    leftCol.className = 'review-column';

    const leftTitle = document.createElement('div');
    leftTitle.className = 'review-column-title';
    leftTitle.textContent = 'Current Tags';
    leftCol.appendChild(leftTitle);

    const createField = (label, value) => {
      const field = document.createElement('div');
      field.className = 'review-field';
      const labelEl = document.createElement('div');
      labelEl.className = 'review-field-label';
      labelEl.textContent = label;
      const valueEl = document.createElement('div');
      valueEl.className = 'review-field-value';
      valueEl.textContent = value || '—';
      field.appendChild(labelEl);
      field.appendChild(valueEl);
      return field;
    };

    leftCol.appendChild(createField('Genre', track.existing_genre));
    leftCol.appendChild(createField('BPM', track.existing_bpm));
    leftCol.appendChild(createField('Key', track.existing_key));
    leftCol.appendChild(createField('Year', track.existing_year));

    diff.appendChild(leftCol);

    // Right column - proposed
    const rightCol = document.createElement('div');
    rightCol.className = 'review-column';

    const rightTitle = document.createElement('div');
    rightTitle.className = 'review-column-title';
    rightTitle.textContent = 'Proposed Tags';
    rightCol.appendChild(rightTitle);

    const genreField = document.createElement('div');
    genreField.className = `review-field ${existingChanged ? 'changed' : ''}`;
    const genreLabel = document.createElement('div');
    genreLabel.className = 'review-field-label';
    genreLabel.textContent = 'Genre';
    const genreValue = document.createElement('div');
    genreValue.className = 'review-field-value';
    const genreText = track.proposed_genre || '—';
    const subText = track.proposed_subgenre ? ` → ${track.proposed_subgenre}` : '';
    genreValue.textContent = genreText + subText;
    genreField.appendChild(genreLabel);
    genreField.appendChild(genreValue);
    rightCol.appendChild(genreField);

    rightCol.appendChild(createField('BPM (analysed)', track.analyzed_bpm ? Math.round(track.analyzed_bpm) : ''));
    rightCol.appendChild(createField('Key (analysed)', track.analyzed_key));
    rightCol.appendChild(createField('Energy Level', track.analyzed_energy ? `${track.analyzed_energy}/10` : ''));

    diff.appendChild(rightCol);
    item.appendChild(diff);

    // Reasoning
    if (track.reasoning) {
      const reasoningDiv = document.createElement('div');
      reasoningDiv.style.fontSize = '12px';
      reasoningDiv.style.color = '#888';
      reasoningDiv.style.marginBottom = '15px';
      reasoningDiv.style.padding = '10px';
      reasoningDiv.style.backgroundColor = '#2a2a3a';
      reasoningDiv.style.borderRadius = '4px';
      const reasoningStrong = document.createElement('strong');
      reasoningStrong.textContent = 'AI Reasoning: ';
      reasoningDiv.appendChild(reasoningStrong);
      const reasoningText = document.createTextNode(track.reasoning);
      reasoningDiv.appendChild(reasoningText);
      item.appendChild(reasoningDiv);
    }

    // Actions
    const actions = document.createElement('div');
    actions.className = 'review-actions';

    const btnSkip = document.createElement('button');
    btnSkip.className = 'btn btn-secondary';
    btnSkip.textContent = '✗ Skip';
    btnSkip.setAttribute('data-skip-btn', '');
    btnSkip.addEventListener('click', () => skipTrack(track.file_path));
    actions.appendChild(btnSkip);

    const btnEditReview = document.createElement('button');
    btnEditReview.className = 'btn btn-secondary';
    btnEditReview.textContent = '✎ Edit';
    btnEditReview.addEventListener('click', () => openEditModal(track.file_path));
    actions.appendChild(btnEditReview);

    const btnApprove = document.createElement('button');
    btnApprove.className = 'btn btn-primary';
    btnApprove.textContent = '✓ Approve';
    btnApprove.setAttribute('data-approve-btn', '');
    btnApprove.addEventListener('click', () => approveTrack(track.file_path));
    actions.appendChild(btnApprove);

    item.appendChild(actions);
    list.appendChild(item);
  });
}

async function approveTrack(filePath) {
  try {
    await apiFetch('/api/review/approve', {
      method: 'POST',
      body: JSON.stringify({ track_paths: [filePath] }),
    });

    const track = window.tracks.find(t => t.file_path === filePath);
    if (track) {
      track.review_status = 'approved';
    }

    renderReview();
    renderTracks();
    updateStats();
  } catch (error) {
    // Error shown in apiFetch
  }
}

async function skipTrack(filePath) {
  try {
    await apiFetch('/api/review/skip', {
      method: 'POST',
      body: JSON.stringify({ track_paths: [filePath] }),
    });

    const track = window.tracks.find(t => t.file_path === filePath);
    if (track) {
      track.review_status = 'skipped';
    }

    renderReview();
    renderTracks();
    updateStats();
  } catch (error) {
    // Error shown
  }
}

// Genre Selector for Export
function showGenreSelector() {
  // Get unique approved genres
  const genres = new Set();
  window.tracks.forEach(track => {
    if (track.review_status === 'approved' && track.final_genre) {
      genres.add(track.final_genre);
    }
  });

  if (!genres.size) {
    showToast('No approved tracks with genres found', 'error');
    return;
  }

  const modal = document.createElement('div');
  modal.className = 'genre-selector-modal';
  modal.id = 'genre-selector-modal';

  const content = document.createElement('div');
  content.className = 'genre-selector-content';

  const title = document.createElement('h3');
  title.textContent = 'Select Genre to Export';
  content.appendChild(title);

  const select = document.createElement('select');
  select.className = 'input-select';

  const option = document.createElement('option');
  option.value = '';
  option.textContent = 'All Genres';
  select.appendChild(option);

  Array.from(genres).sort().forEach(genre => {
    const opt = document.createElement('option');
    opt.value = genre;
    opt.textContent = genre;
    select.appendChild(opt);
  });

  content.appendChild(select);

  const buttons = document.createElement('div');
  buttons.className = 'genre-selector-buttons';

  const btnCancel = document.createElement('button');
  btnCancel.className = 'btn btn-secondary';
  btnCancel.textContent = 'Cancel';
  btnCancel.addEventListener('click', () => {
    modal.remove();
  });

  const btnExport = document.createElement('button');
  btnExport.className = 'btn btn-primary';
  btnExport.textContent = 'Export';
  btnExport.addEventListener('click', () => {
    const genre = select.value;
    const url = genre
      ? `/api/export/m3u?genre=${encodeURIComponent(genre)}&status=approved`
      : '/api/export/m3u?status=approved';
    window.location = url;
    showToast('Downloading playlist...', 'info');
    modal.remove();
  });

  buttons.appendChild(btnCancel);
  buttons.appendChild(btnExport);
  content.appendChild(buttons);

  modal.appendChild(content);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.remove();
    }
  });

  document.body.appendChild(modal);
  select.focus();
}

