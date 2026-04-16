// ============================================================================
// Library Toolbar & Session Management
// ============================================================================

function initLibraryToolbar() {
  const folderDisplay  = document.getElementById('folder-display');
  const folderInput    = document.getElementById('folder-input');
  const btnChange      = document.getElementById('btn-change-folder');
  const btnImport      = document.getElementById('btn-import');
  const btnAnalyze     = document.getElementById('btn-analyze');
  const btnClassify    = document.getElementById('btn-classify');
  const btnWriteTags   = document.getElementById('btn-write-tags');
  const btnBulkApprove = document.getElementById('btn-bulk-approve-toolbar');
  const btnGetStarted  = document.getElementById('btn-get-started');

  async function openFolderPicker() {
    if (window.pywebview && window.pywebview.api) {
      // Native OS folder picker via pywebview
      const path = await window.pywebview.api.choose_folder();
      if (path) doImport(path);
    } else {
      // Dev-mode fallback: show text input
      if (folderInput)  folderInput.style.display  = 'inline-block';
      if (btnImport)    btnImport.style.display    = 'inline-block';
      if (folderInput)  folderInput.focus();
    }
  }

  if (btnGetStarted) btnGetStarted.addEventListener('click', openFolderPicker);
  if (btnChange)     btnChange.addEventListener('click', openFolderPicker);

  if (folderInput) {
    folderInput.addEventListener('keydown', e => { if (e.key === 'Enter') doImport(folderInput.value.trim()); });
  }
  if (btnImport) btnImport.addEventListener('click', () => doImport(folderInput ? folderInput.value.trim() : ''));

  async function doImport(folder) {
    if (!folder) return;
    if (folderInput)  folderInput.style.display  = 'none';
    if (btnImport)    btnImport.style.display    = 'none';
    if (folderDisplay) folderDisplay.textContent = folder;
    showSpinner();
    try {
      const result = await apiFetch('/api/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: folder })
      });
      if (result && result.tracks) {
        window.tracks = result.tracks;
        window.searchResults = null;
        renderTracks();
        updateStats();
        showToast((result.count || result.tracks.length) + ' tracks imported — click Analyse All to extract BPM & key', 'success');
        apiFetch('/api/session/save', { method: 'POST' }).catch(() => {});
      }
    } catch (e) {
      showToast('Import failed: ' + e.message, 'error');
    } finally {
      hideSpinner();
    }
  }

  if (btnAnalyze) {
    let currentAnalyzeOpId = null;
    btnAnalyze.addEventListener('click', async () => {
      btnAnalyze.disabled = true;
      try {
        const result = await apiFetch('/api/analyze', { method: 'POST' });
        if (result && result.op_id) {
          currentAnalyzeOpId = result.op_id;
          const total = result.total || 0;
          // Show started toast
          showToast('Analysis started — ' + total + ' tracks to go', 'info');
          showProgressInStatsBar('Analysing audio...', 'analyze');
          // Show cancel button
          const cancelBtn = document.getElementById('stat-cancel-btn');
          if (cancelBtn) cancelBtn.style.display = 'inline-block';
          cancelBtn.onclick = async () => {
            await apiFetch('/api/progress/' + currentAnalyzeOpId + '/cancel', { method: 'POST' });
            hideProgressInStatsBar();
            showToast('Analysis cancelled', 'info');
            btnAnalyze.disabled = false;
            if (cancelBtn) cancelBtn.style.display = 'none';
          };
          // Stream progress via SSE
          connectToProgress(
            result.op_id,
            result.total,
            (current, total, message) => {
              const pct = Math.round((current / total) * 100);
              showProgressInStatsBar(current + ' / ' + total + ' analysing...', 'analyze');
              const fill = document.getElementById('stat-progress-fill');
              if (fill) fill.style.width = pct + '%';
            },
            (data) => {
              // SSE complete event
              hideProgressInStatsBar();
              if (cancelBtn) cancelBtn.style.display = 'none';
              if (data.cancelled) {
                showToast('Analysis cancelled', 'info');
                btnAnalyze.disabled = false;
                return;
              }
              // Refetch fresh track data from server
              apiFetch('/api/tracks').then(d => {
                window.tracks = d.tracks || [];
                window.searchResults = null;
                renderTracks();
                updateStats();
              });
              updateToolbarButtonStates();
              showToast('Analysis complete', 'success');
              btnAnalyze.disabled = false;
              currentAnalyzeOpId = null;
            },
            (err) => {
              hideProgressInStatsBar();
              if (cancelBtn) cancelBtn.style.display = 'none';
              showToast('Analysis stream error: ' + err.message, 'error');
              btnAnalyze.disabled = false;
              currentAnalyzeOpId = null;
            }
          );
        }
      } catch (e) {
        hideProgressInStatsBar();
        const cancelBtn = document.getElementById('stat-cancel-btn');
        if (cancelBtn) cancelBtn.style.display = 'none';
        showToast('Analysis failed: ' + e.message, 'error');
        btnAnalyze.disabled = false;
      }
    });
  }

  if (btnClassify) {
    let currentClassifyOpId = null;
    btnClassify.addEventListener('click', async () => {
      btnClassify.disabled = true;
      try {
        const result = await apiFetch('/api/classify', { method: 'POST' });
        if (result && result.op_id) {
          currentClassifyOpId = result.op_id;
          showToast('Classification started — this may take a few minutes', 'info');
          showProgressInStatsBar('Classifying genres...', 'classify');
          const cancelBtn = document.getElementById('stat-cancel-btn');
          if (cancelBtn) cancelBtn.style.display = 'inline-block';
          cancelBtn.onclick = async () => {
            await apiFetch('/api/progress/' + currentClassifyOpId + '/cancel', { method: 'POST' });
            hideProgressInStatsBar();
            showToast('Classification cancelled', 'info');
            btnClassify.disabled = false;
            if (cancelBtn) cancelBtn.style.display = 'none';
          };
          // Stream progress via SSE
          connectToProgress(
            result.op_id,
            result.total,
            (current, total, message) => {
              const pct = Math.round((current / total) * 100);
              showProgressInStatsBar(current + ' / ' + total + ' classifying...', 'classify');
              const fill = document.getElementById('stat-progress-fill');
              if (fill) fill.style.width = pct + '%';
            },
            (data) => {
              hideProgressInStatsBar();
              if (cancelBtn) cancelBtn.style.display = 'none';
              if (data.cancelled) {
                showToast('Classification cancelled', 'info');
                btnClassify.disabled = false;
                return;
              }
              apiFetch('/api/tracks').then(d => {
                window.tracks = d.tracks || [];
                window.searchResults = null;
                renderTracks();
                updateStats();
              });
              updateToolbarButtonStates();
              showToast('Classification complete', 'success');
              btnClassify.disabled = false;
              currentClassifyOpId = null;
            },
            (err) => {
              hideProgressInStatsBar();
              if (cancelBtn) cancelBtn.style.display = 'none';
              showToast('Classification stream error: ' + err.message, 'error');
              btnClassify.disabled = false;
              currentClassifyOpId = null;
            }
          );
        }
      } catch (e) {
        hideProgressInStatsBar();
        const cancelBtn = document.getElementById('stat-cancel-btn');
        if (cancelBtn) cancelBtn.style.display = 'none';
        showToast('Classification failed: ' + e.message, 'error');
        btnClassify.disabled = false;
      }
    });
  }

  if (btnBulkApprove) {
    btnBulkApprove.addEventListener('click', async () => {
      const thresholdEl = document.getElementById('toolbar-threshold');
      const threshold = parseInt(thresholdEl ? (thresholdEl.value || thresholdEl.textContent) : '80') || 80;
      try {
        const result = await apiFetch('/api/review/bulk-approve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ min_confidence: threshold })
        });
        if (result) {
          // Refetch fresh track data from server
          apiFetch('/api/tracks').then(d => {
            window.tracks = d.tracks || [];
            renderTracks();
            updateStats();
          });
          showToast((result.approved_count ?? 0) + ' tracks approved', 'success');
        }
      } catch (e) {
        showToast('Bulk approve failed: ' + e.message, 'error');
      }
    });
  }

  if (btnWriteTags) {
    let currentWriteOpId = null;
    btnWriteTags.addEventListener('click', async () => {
      btnWriteTags.disabled = true;
      try {
        const result = await apiFetch('/api/review/write', { method: 'POST' });
        if (result && result.op_id) {
          currentWriteOpId = result.op_id;
          const total = result.total || 0;
          showToast('Writing tags to ' + total + ' files — do not close the app', 'info');
          showProgressInStatsBar('Writing tags...', 'write');
          const cancelBtn = document.getElementById('stat-cancel-btn');
          if (cancelBtn) cancelBtn.style.display = 'inline-block';
          cancelBtn.onclick = async () => {
            await apiFetch('/api/progress/' + currentWriteOpId + '/cancel', { method: 'POST' });
            hideProgressInStatsBar();
            showToast('Write cancelled', 'info');
            btnWriteTags.disabled = false;
            if (cancelBtn) cancelBtn.style.display = 'none';
          };
          // Stream progress via SSE
          connectToProgress(
            result.op_id,
            result.total,
            (current, total, message) => {
              const pct = Math.round((current / total) * 100);
              showProgressInStatsBar(current + ' / ' + total + ' writing...', 'write');
              const fill = document.getElementById('stat-progress-fill');
              if (fill) fill.style.width = pct + '%';
            },
            (data) => {
              hideProgressInStatsBar();
              if (cancelBtn) cancelBtn.style.display = 'none';
              if (data.cancelled) {
                showToast('Write cancelled', 'info');
                btnWriteTags.disabled = false;
                return;
              }
              // Refetch fresh track data from server
              apiFetch('/api/tracks').then(d => {
                window.tracks = d.tracks || [];
                window.searchResults = null;
                renderTracks();
                updateStats();
              });
              updateToolbarButtonStates();

              const written = data.written || 0;
              const changes = data.change_summary || [];
              const changedCount = changes.length;

              // Save state for undo
              window._lastWrittenState = JSON.parse(JSON.stringify(window.tracks || []));

              if (changedCount > 0) {
                showToast(written + ' tracks written, ' + changedCount + ' changed', 'success', {
                  action: 'Undo',
                  onAction: undoLastWrite
                });
                // Show first 3 changes in detail
                let detailHtml = '<div style="max-height:300px;overflow-y:auto;font-size:13px;line-height:1.5;">';
                changes.slice(0, 3).forEach(entry => {
                  detailHtml += '<div style="margin-bottom:8px;padding:6px 8px;border-left:3px solid #8b5cf6;background:rgba(139,92,246,0.08);border-radius:4px;">';
                  detailHtml += '<strong style="color:#c4b5fd;">' + escapeHtml(entry.filename) + '</strong><br>';
                  entry.changes.forEach(ch => {
                    detailHtml += '<span style="color:#a5b4fc;">' + escapeHtml(ch) + '</span><br>';
                  });
                  detailHtml += '</div>';
                });
                if (changes.length > 3) {
                  detailHtml += '<div style="color:#888;font-size:12px;text-align:center;">+' + (changes.length - 3) + ' more changes</div>';
                }
                detailHtml += '</div>';

                const modal = document.getElementById('change-detail-modal');
                const modalBody = document.getElementById('change-detail-body');
                if (modal && modalBody) {
                  modalBody.innerHTML = detailHtml;
                  modal.style.display = 'block';
                }
              } else {
                showToast(written + ' tracks written', 'success', {
                  action: 'Undo',
                  onAction: undoLastWrite
                });
              }

              btnWriteTags.disabled = false;
              currentWriteOpId = null;
            },
            (err) => {
              hideProgressInStatsBar();
              if (cancelBtn) cancelBtn.style.display = 'none';
              showToast('Write stream error: ' + err.message, 'error');
              btnWriteTags.disabled = false;
              currentWriteOpId = null;
            }
          );
        }
      } catch (e) {
        hideProgressInStatsBar();
        const cancelBtn = document.getElementById('stat-cancel-btn');
        if (cancelBtn) cancelBtn.style.display = 'none';
        showToast('Write failed: ' + e.message, 'error');
        btnWriteTags.disabled = false;
      }
    });
  }

  const btnShortcuts = document.getElementById('btn-shortcuts');
  if (btnShortcuts) btnShortcuts.addEventListener('click', showKeyboardShortcuts);
}

function updateToolbarButtonStates(stats) {
  const s = stats || {};
  const total      = s.total      ?? (window.tracks ? window.tracks.length : 0);
  const analyzed   = s.analyzed   ?? (window.tracks ? window.tracks.filter(t => t.final_bpm).length : 0);
  const classified = s.classified ?? (window.tracks ? window.tracks.filter(t => t.final_genre && t.final_genre !== 'Unknown').length : 0);
  const approved   = s.approved   ?? (window.tracks ? window.tracks.filter(t => t.review_status === 'approved').length : 0);

  const btnAnalyze     = document.getElementById('btn-analyze');
  const btnClassify    = document.getElementById('btn-classify');
  const btnBulkApprove = document.getElementById('btn-bulk-approve-toolbar');
  const btnWriteTags   = document.getElementById('btn-write-tags');

  if (btnAnalyze)     btnAnalyze.disabled     = total      === 0;
  if (btnClassify)    btnClassify.disabled     = analyzed   === 0;
  if (btnBulkApprove) btnBulkApprove.disabled  = classified === 0;
  if (btnWriteTags)   btnWriteTags.disabled     = approved   === 0;
}

function showProgressInStatsBar(text, opType) {
  const sep  = document.getElementById('stat-progress-sep');
  const wrap = document.getElementById('stat-progress-wrap');
  const txt  = document.getElementById('stat-progress-text');
  const fill = document.getElementById('stat-progress-fill');
  if (sep)  sep.style.display  = 'inline';
  if (wrap) wrap.style.display = 'flex';
  if (txt)  txt.textContent    = text;
  // Apply color class based on operation type
  if (fill) {
    fill.classList.remove('progress-analyze', 'progress-classify', 'progress-write');
    if (opType === 'analyze')      fill.classList.add('progress-analyze');
    else if (opType === 'classify') fill.classList.add('progress-classify');
    else if (opType === 'write')    fill.classList.add('progress-write');
  }
}

function hideProgressInStatsBar() {
  const sep  = document.getElementById('stat-progress-sep');
  const wrap = document.getElementById('stat-progress-wrap');
  const fill = document.getElementById('stat-progress-fill');
  if (sep)  sep.style.display  = 'none';
  if (wrap) wrap.style.display = 'none';
  if (fill) {
    fill.style.width = '0%';
    fill.classList.remove('progress-analyze', 'progress-classify', 'progress-write');
  }
}

function checkResumeSession() {
  apiFetch('/api/session/exists').then(data => {
    if (!data || !data.exists) return;
    const banner = document.getElementById('resume-banner');
    const info   = document.getElementById('resume-info');
    if (banner && info) {
      info.textContent = 'Session: ' + (data.track_count || 0) + ' tracks from ' + (data.folder_path || 'previous session');
      banner.style.display = 'flex';
    }
    const btnResume  = document.getElementById('btn-resume-session');
    const btnDismiss = document.getElementById('btn-dismiss-session');
    if (btnResume) {
      btnResume.addEventListener('click', async () => {
        showSpinner('Loading session...');
        try {
          const result = await apiFetch('/api/session/load', { method: 'POST' });
          if (result) {
            window.tracks = result.tracks || [];
            window.searchResults = null;
            renderTracks();
            updateStats();
            if (banner) banner.style.display = 'none';
            showToast('Session resumed', 'success');
          }
        } catch (e) {
          showToast('Failed to resume session: ' + e.message, 'error');
        } finally {
          hideSpinner();
        }
      });
    }
    if (btnDismiss) {
      btnDismiss.addEventListener('click', () => { if (banner) banner.style.display = 'none'; });
    }
  }).catch(() => {});
}

// ============================================================================
// Import Tab
// ============================================================================

// initImportTab — replaced by initLibraryToolbar() in v2.4.0
function initImportTab() {}

// Session & Watcher Helpers
async function checkPreviousSession() {
  try {
    const result = await apiFetch('/api/session/exists');
    if (result.exists) {
      const banner = document.getElementById('resume-session-banner');
      const text = document.getElementById('resume-banner-text');
      text.textContent = `Previous session found — ${result.track_count} tracks from ${result.folder_path}. Last saved: ${new Date(result.saved_at).toLocaleString()}`;
      banner.style.display = 'block';
    }
  } catch (error) {
    // Silently fail if no session exists
  }
}

async function pollFolderWatch() {
  try {
    const result = await apiFetch('/api/watch/poll');
    if (result.tracks && result.tracks.length > 0) {
      // Add new tracks to window.tracks
      window.tracks = window.tracks.concat(result.tracks);
      window.searchResults = null;
      renderTracks();
      renderReview();
      updateStats();
      showToast(`${result.tracks.length} new track${result.tracks.length !== 1 ? 's' : ''} detected`, 'success');
    }
  } catch (error) {
    // Silently fail on poll errors
  }
}

