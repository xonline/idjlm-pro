// Bulk select with floating action bar
function initBulkSelectFeature() {
  const selectAllCheckbox = document.getElementById('select-all-checkbox');
  const trackTableBody = document.getElementById('tracks-tbody');

  if (!selectAllCheckbox || !trackTableBody) return;

  selectAllCheckbox.addEventListener('change', (e) => {
    const checkboxes = trackTableBody.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => {
      cb.checked = e.target.checked;
      if (e.target.checked) {
        window.selectedTracks.add(cb.dataset.filePath);
      } else {
        window.selectedTracks.delete(cb.dataset.filePath);
      }
    });
    updateBulkActionsBar();
  });

  trackTableBody.addEventListener('change', (e) => {
    if (e.target.type === 'checkbox') {
      if (e.target.checked) {
        window.selectedTracks.add(e.target.dataset.filePath);
      } else {
        window.selectedTracks.delete(e.target.dataset.filePath);
      }
      updateBulkActionsBar();
    }
  });

  document.addEventListener('click', (e) => {
    if (e.target.id === 'bulk-edit-btn') {
      showBulkEditModal();
    }
    if (e.target.id === 'bulk-add-setlist-btn') {
      window.selectedTracks.forEach(filePath => {
        addTrackToSetlist(filePath);
      });
      window.selectedTracks.clear();
      updateBulkActionsBar();
    }
    if (e.target.id === 'bulk-export-btn') {
      const modal = document.getElementById('export-format-modal');
      if (modal) modal.style.display = 'flex';
    }
  });

  // Wire bulk edit modal buttons
  const bulkEditModal = document.getElementById('bulk-edit-modal');
  const closeFn = () => { if (bulkEditModal) bulkEditModal.style.display = 'none'; };
  document.getElementById('bulk-edit-close')?.addEventListener('click', closeFn);
  document.getElementById('bulk-edit-cancel')?.addEventListener('click', closeFn);
  document.getElementById('bulk-edit-save')?.addEventListener('click', handleBulkEdit);
  bulkEditModal?.addEventListener('click', e => { if (e.target === bulkEditModal) closeFn(); });

  // Wire export format modal close + export buttons
  const exportModal = document.getElementById('export-format-modal');
  const closeExportFn = () => { if (exportModal) exportModal.style.display = 'none'; };
  document.getElementById('export-format-close')?.addEventListener('click', closeExportFn);
  exportModal?.addEventListener('click', e => { if (e.target === exportModal) closeExportFn(); });
  document.getElementById('btn-export-csv')?.addEventListener('click', () => { exportTracks('csv'); closeExportFn(); });
  document.getElementById('btn-export-json')?.addEventListener('click', () => { exportTracks('json'); closeExportFn(); });
  document.getElementById('btn-export-rekordbox')?.addEventListener('click', () => { exportTracks('rekordbox'); closeExportFn(); });

  // Wire change detail modal close button
  const changeDetailModal = document.getElementById('change-detail-modal');
  const closeChangeDetailFn = () => { if (changeDetailModal) changeDetailModal.style.display = 'none'; };
  document.getElementById('change-detail-close')?.addEventListener('click', closeChangeDetailFn);
  document.getElementById('change-detail-done')?.addEventListener('click', closeChangeDetailFn);
  changeDetailModal?.addEventListener('click', e => { if (e.target === changeDetailModal) closeChangeDetailFn(); });
}

function updateBulkActionsBar() {
  const bar = document.getElementById('bulk-actions-bar');
  if (!bar) return;

  if (window.selectedTracks.size > 0) {
    bar.style.display = 'flex';
    bar.innerHTML = `
      <span class="bulk-actions-count">${window.selectedTracks.size} selected</span>
      <button class="btn btn-accent btn-small" id="bulk-analyze-btn">Analyse</button>
      <button class="btn btn-primary btn-small" id="bulk-edit-btn">Bulk Edit</button>
      <button class="btn btn-secondary btn-small" id="bulk-export-btn">Export</button>
      <button class="btn btn-secondary btn-small" id="bulk-add-setlist-btn">Add to Setlist</button>
      <button class="btn btn-warning btn-small" id="bulk-reclassify-btn">Re-classify</button>
    `;

    const bulkAnalyzeBtn = document.getElementById('bulk-analyze-btn');
    if (bulkAnalyzeBtn) {
      bulkAnalyzeBtn.addEventListener('click', async () => {
        const paths = Array.from(window.selectedTracks);
        bulkAnalyzeBtn.disabled = true;
        showProgressInStatsBar(`Analysing ${paths.length} track${paths.length !== 1 ? 's' : ''}...`, 'analyze');
        try {
          const result = await apiFetch('/api/analyze', {
            method: 'POST',
            body: JSON.stringify({ track_paths: paths })
          });
          if (result && result.op_id) {
            connectToProgress(
              result.op_id,
              result.total,
              (current, total) => {
                const pct = Math.round((current / total) * 100);
                showProgressInStatsBar(`${current} / ${total} analysing...`, 'analyze');
                const fill = document.getElementById('stat-progress-fill');
                if (fill) fill.style.width = pct + '%';
              },
              (data) => {
                hideProgressInStatsBar();
                // Refetch fresh track data from server
                apiFetch('/api/tracks').then(d => {
                  window.tracks = d.tracks || [];
                  window.searchResults = null;
                  renderTracks();
                  updateStats();
                });
                updateToolbarButtonStates();
                showToast(`Analysed ${paths.length} track${paths.length !== 1 ? 's' : ''}`, 'success');
              },
              (err) => {
                hideProgressInStatsBar();
                showToast('Analyse error: ' + err.message, 'error');
              }
            );
          }
        } catch (e) {
          hideProgressInStatsBar();
          showToast('Analyse failed: ' + e.message, 'error');
        }
      });
    }

    const bulkReclassifyBtn = document.getElementById('bulk-reclassify-btn');
    if (bulkReclassifyBtn) {
      bulkReclassifyBtn.addEventListener('click', () => {
        showReclassifyModal();
      });
    }
  } else {
    bar.style.display = 'none';
  }
}

function showBulkEditModal() {
  const modal = document.getElementById('bulk-edit-modal');
  if (!modal) return;

  // Populate genre select from taxonomy
  const genreSelect = document.getElementById('bulk-genre');
  if (genreSelect && window.taxonomy) {
    while (genreSelect.firstChild) genreSelect.removeChild(genreSelect.firstChild);
    const defaultOpt = document.createElement('option');
    defaultOpt.value = '';
    defaultOpt.textContent = '— No change —';
    genreSelect.appendChild(defaultOpt);
    Object.keys(window.taxonomy).forEach(genre => {
      const opt = document.createElement('option');
      opt.value = genre;
      opt.textContent = genre;
      genreSelect.appendChild(opt);
    });
  }

  const countEl = document.getElementById('bulk-edit-count');
  if (countEl) countEl.textContent = `${window.selectedTracks.size} track${window.selectedTracks.size !== 1 ? 's' : ''} selected`;

  modal.style.display = 'flex';
}

// ============================================================================
// Reclassify Modal
// ============================================================================

function showReclassifyModal() {
  if (window.selectedTracks.size === 0) {
    showToast('Select tracks to re-classify', 'error');
    return;
  }

  const modal = document.getElementById('reclassify-modal');
  if (!modal) return;

  const countEl = document.getElementById('reclassify-count');
  if (countEl) countEl.textContent = `${window.selectedTracks.size} track${window.selectedTracks.size !== 1 ? 's' : ''} selected`;

  // Set default provider from settings
  const providerSelect = document.getElementById('reclassify-provider');
  if (providerSelect) {
    const currentProvider = document.getElementById('settings-provider');
    if (currentProvider && currentProvider.value) {
      providerSelect.value = currentProvider.value;
    }
  }

  modal.style.display = 'flex';
}

function initReclassifyModal() {
  const modal = document.getElementById('reclassify-modal');
  if (!modal) return;

  const closeBtn = document.getElementById('reclassify-close');
  const cancelBtn = document.getElementById('reclassify-cancel');
  const runBtn = document.getElementById('reclassify-run');

  const closeModal = () => { modal.style.display = 'none'; };

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

  // Close on background click
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      const provider = document.getElementById('reclassify-provider').value;
      const force = document.getElementById('reclassify-force').checked;
      const paths = Array.from(window.selectedTracks);

      if (!paths.length) {
        showToast('No tracks selected', 'error');
        return;
      }

      closeModal();
      runBtn.disabled = true;
      showProgressInStatsBar(`Re-classifying ${paths.length} tracks with ${provider}...`, 'classify');

      try {
        const result = await apiFetch('/api/classify', {
          method: 'POST',
          body: JSON.stringify({
            track_paths: paths,
            model_override: provider,
            reclassify: force
          })
        });

        if (result && result.op_id) {
          connectToProgress(
            result.op_id,
            result.total,
            (current, total) => {
              const pct = Math.round((current / total) * 100);
              showProgressInStatsBar(`${current} / ${total} re-classifying...`, 'classify');
              const fill = document.getElementById('stat-progress-fill');
              if (fill) fill.style.width = pct + '%';
            },
            (data) => {
              hideProgressInStatsBar();
              // Refetch fresh track data from server
              apiFetch('/api/tracks').then(d => {
                window.tracks = d.tracks || [];
                window.searchResults = null;
                renderTracks();
                updateStats();
              });
              updateToolbarButtonStates();
              showToast(`Re-classified ${paths.length} track${paths.length !== 1 ? 's' : ''} with ${provider}`, 'success');
              runBtn.disabled = false;
            },
            (err) => {
              hideProgressInStatsBar();
              showToast('Re-classify error: ' + err.message, 'error');
              runBtn.disabled = false;
            }
          );
        }
      } catch (e) {
        hideProgressInStatsBar();
        showToast('Re-classify failed: ' + e.message, 'error');
        runBtn.disabled = false;
      }
    });
  }

  // Close reclassify modal with Escape key (extend existing handler)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.style.display !== 'none') {
      closeModal();
    }
  });
}

// Apple Music sync button
function initAppleMusicSync() {
  const syncBtn = document.getElementById('apple-music-sync-btn');
  if (!syncBtn) return;

  syncBtn.addEventListener('click', async () => {
    showSpinner('Syncing with Apple Music...');
    try {
      const result = await apiFetch('/api/sync/apple-music', {
        method: 'POST',
        body: JSON.stringify({
          track_ids: Array.from(window.selectedTracks.size > 0 ? window.selectedTracks : window.tracks.map(t => t.file_path))
        })
      });
      showToast(result.message || 'Apple Music sync completed', 'success');
    } catch (error) {
      showToast('Apple Music sync failed', 'error');
    } finally {
      hideSpinner();
    }
  });
}

// Enhanced Settings tab with AI model selection
function updateSettingsSaveHandler() {
  const saveBtn = document.getElementById('settings-save-btn');
  if (!saveBtn) return;

  saveBtn.removeEventListener('click', saveSettings);
  saveBtn.addEventListener('click', saveSettingsRound2);
}

async function saveSettingsRound2() {
  try {
    const aiModel = document.getElementById('settings-provider')?.value || 'claude';
    const modelId = document.getElementById('settings-model')?.value || '';
    const anthropicKey = document.getElementById('settings-anthropic-key')?.value.trim() || '';
    const batchSize = parseInt(document.getElementById('settings-batch-size')?.value) || 5;
    const autoApproveThreshold = parseInt(document.getElementById('settings-auto-approve')?.value) || 80;
    const geminiKey = document.getElementById('settings-gemini-key')?.value.trim() || '';
    const openrouterKey = document.getElementById('settings-openrouter-key')?.value.trim() || '';
    const openaiKey = document.getElementById('settings-openai-key')?.value.trim() || '';
    const qwenKey = document.getElementById('settings-qwen-key')?.value.trim() || '';
    const deepseekKey = document.getElementById('settings-deepseek-key')?.value.trim() || '';
    const groqKey = document.getElementById('settings-groq-key')?.value.trim() || '';
    const spotifyId = document.getElementById('settings-spotify-id')?.value.trim() || '';
    const spotifySecret = document.getElementById('settings-spotify-secret')?.value.trim() || '';
    const lastfmKey = document.getElementById('settings-lastfm-key')?.value.trim() || '';
    const spotifyEnabled = document.getElementById('settings-spotify-enabled')?.checked ?? false;
    const deezerEnabled = document.getElementById('settings-deezer-enabled')?.checked ?? false;
    const beatportEnabled = document.getElementById('settings-beatport-enabled')?.checked ?? false;

    const payload = {
      ai_model: aiModel,
      model_id: modelId,
      classify_batch_size: batchSize,
      auto_approve_threshold: autoApproveThreshold,
      spotify_enrich_enabled: spotifyEnabled,
      deezer_enrich_enabled: deezerEnabled,
      beatport_enrich_enabled: beatportEnabled,
    };

    if (anthropicKey) payload.anthropic_api_key = anthropicKey;
    if (geminiKey) payload.gemini_api_key = geminiKey;
    if (openrouterKey) payload.openrouter_api_key = openrouterKey;
    if (openaiKey) payload.openai_api_key = openaiKey;
    if (qwenKey) payload.qwen_api_key = qwenKey;
    if (deepseekKey) payload.deepseek_api_key = deepseekKey;
    if (groqKey) payload.groq_api_key = groqKey;
    if (lastfmKey) payload.lastfm_api_key = lastfmKey;
    if (spotifyId) payload.spotify_client_id = spotifyId;
    if (spotifySecret) payload.spotify_client_secret = spotifySecret;

    if (Object.keys(payload).length === 0) {
      showToast('No settings to save', 'info');
      return;
    }

    showSpinner('Saving settings...');
    const result = await apiFetch('/api/settings', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (result.saved) {
      showToast('Settings saved successfully', 'success');
      // Flash the save button green to confirm
      const saveBtn = document.getElementById('settings-save-btn');
      if (saveBtn) {
        const orig = saveBtn.textContent;
        saveBtn.textContent = '✓ Saved';
        saveBtn.style.background = '#22c55e';
        setTimeout(() => {
          saveBtn.textContent = orig;
          saveBtn.style.background = '';
        }, 2000);
      }
      // Clear sensitive inputs — loadSettings will populate placeholders with masked values
      await loadSettings();
    }
  } catch (error) {
    // Error already shown in apiFetch
  } finally {
    hideSpinner();
  }
}

// Export functionality (CSV, JSON, Rekordbox)
function initExportFeature() {
  const exportBtn = document.getElementById('export-menu-item');
  if (!exportBtn) return;

  exportBtn.addEventListener('click', () => {
    const modal = document.getElementById('export-format-modal');
    if (modal) modal.style.display = 'flex';
  });

  document.addEventListener('click', (e) => {
    if (e.target.id === 'export-csv-btn') {
      exportTracks('csv');
    }
    if (e.target.id === 'export-json-btn') {
      exportTracks('json');
    }
    if (e.target.id === 'export-rekordbox-btn') {
      exportTracks('rekordbox');
    }
  });
}

function exportTracks(format) {
  const tracks = window.selectedTracks.size > 0
    ? Array.from(window.selectedTracks).map(fp => window.tracks.find(t => t.file_path === fp))
    : window.tracks;

  let data, filename, mime;

  if (format === 'csv') {
    const headers = ['Title', 'Artist', 'Genre', 'Comments', 'BPM', 'Key', 'Year', 'File Path'];
    const rows = tracks.map(t => [
      t.display_title || '',
      t.display_artist || '',
      t.final_genre || '',
      t.final_subgenre || '',
      t.final_bpm || '',
      t.final_key || '',
      t.final_year || '',
      t.file_path || '',
    ]);
    data = [headers, ...rows].map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
    filename = 'idlm-export.csv';
    mime = 'text/csv';
  } else if (format === 'json') {
    data = JSON.stringify(tracks.map(t => ({
      title: t.display_title,
      artist: t.display_artist,
      genre: t.final_genre,
      subGenre: t.final_subgenre,
      bpm: t.final_bpm,
      key: t.final_key,
      year: t.final_year,
      filePath: t.file_path,
    })), null, 2);
    filename = 'idlm-export.json';
    mime = 'application/json';
  } else if (format === 'rekordbox') {
    // Rekordbox XML format
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PLAYLIST Name="IDJLM Export" Type="1">
    <PLAYLIST_TRACKS>
      ${tracks.map((t, idx) => `
      <TRACK TrackID="${idx + 1}">
        <NAME>${escapeHtml(t.display_title || '')}</NAME>
        <ARTIST>${escapeHtml(t.display_artist || '')}</ARTIST>
        <ALBUM>${escapeHtml(t.album || '')}</ALBUM>
        <YEAR>${t.final_year || ''}</YEAR>
        <BPM>${t.final_bpm || ''}</BPM>
        <GENRE>${escapeHtml(t.final_genre || '')}</GENRE>
        <COMMENTS>${escapeHtml(t.final_subgenre || '')}</COMMENTS>
      </TRACK>
      `).join('')}
    </PLAYLIST_TRACKS>
  </PLAYLIST>
</DJ_PLAYLISTS>`;
    data = xml;
    filename = 'idlm-export.xml';
    mime = 'application/xml';
  }

  const blob = new Blob([data], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  showToast(`Exported ${tracks.length} tracks as ${format.toUpperCase()}`, 'success');
}

// ============================================================================
// Bulk Edit Handler
// ============================================================================

async function handleBulkEdit() {
  const genreInput = document.getElementById('bulk-genre')?.value.trim();
  const subgenreInput = document.getElementById('bulk-subgenre')?.value.trim();
  const bpmInput = document.getElementById('bulk-bpm')?.value.trim();
  const yearInput = document.getElementById('bulk-year')?.value.trim();

  if (!genreInput && !subgenreInput && !bpmInput && !yearInput) {
    showToast('Please enter at least one field to update', 'info');
    return;
  }

  const payload = {
    track_paths: Array.from(window.selectedTracks),
  };

  if (genreInput) payload.genre = genreInput;
  if (subgenreInput) payload.subgenre = subgenreInput;
  if (bpmInput) payload.bpm = parseInt(bpmInput);
  if (yearInput) payload.year = parseInt(yearInput);

  showSpinner('Updating tracks...');
  try {
    const result = await apiFetch('/api/review/bulk-edit', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (result.updated) {
      showToast(`Updated ${result.updated} tracks`, 'success');
      window.selectedTracks.clear();
      updateBulkActionsBar();
      document.getElementById('bulk-edit-modal').style.display = 'none';
      // Reload tracks to reflect changes
      apiFetch('/api/tracks').then(data => {
        window.tracks = data.tracks || [];
        window.searchResults = null;
        renderTracks();
      });
    }
  } catch (error) {
    showToast('Bulk edit failed', 'error');
  } finally {
    hideSpinner();
  }
}

