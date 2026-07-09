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
    // Tauri v2 — invoke the pick_folder Rust command directly (most reliable path)
    if (window.__TAURI__ && window.__TAURI__.core) {
      try {
        const selected = await window.__TAURI__.core.invoke('pick_folder');
        if (selected) doImport(selected);
      } catch (e) {
        console.warn('[idjlm] Tauri pick_folder invoke failed, trying dialog plugin:', e);
        // Fallback: dialog plugin JS API
        try {
          const selected2 = await window.__TAURI__.dialog.open({
            directory: true,
            multiple: false,
            title: 'Select Music Folder'
          });
          if (selected2) doImport(selected2);
        } catch (e2) {
          console.warn('[idjlm] Tauri dialog.open also failed, using text input:', e2);
          _showTextInput();
        }
      }
      return;
    }

    // pywebview native dialog (legacy PyInstaller build — kept for rollback)
    if (window.pywebview && window.pywebview.api) {
      const path = await window.pywebview.api.choose_folder();
      if (path) doImport(path);
      return;
    }

    // Dev-mode / plain browser fallback: show text input
    _showTextInput();
  }

  function _showTextInput() {
    if (folderInput)  folderInput.style.display  = 'inline-block';
    if (btnImport)    btnImport.style.display    = 'inline-block';
    if (folderInput)  folderInput.focus();
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
    showSkeletonRows();
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
    btnAnalyze.addEventListener('click', async () => {
      btnAnalyze.disabled = true;
      try {
        const result = await apiFetch('/api/analyze', { method: 'POST' });
        if (result && result.op_id) {
          const total = result.total || 0;
          showToast('Analysis started — ' + total + ' tracks to go', 'info');
          const opHandle = window.opsbar.registerOp({
            id: 'analyze:' + result.op_id,
            label: 'Analysing audio',
            kind: 'analyze',
            onCancel: async () => {
              await apiFetch('/api/progress/' + result.op_id + '/cancel', { method: 'POST' });
            },
          });
          // Stream progress via SSE
          connectToProgress(
            result.op_id,
            result.total,
            (current, total, message) => {
              window.opsbar.progress(opHandle, current, total, message);
            },
            (data) => {
              if (data.cancelled) {
                window.opsbar.error(opHandle, 'cancelled');
                showToast('Analysis cancelled', 'info');
                btnAnalyze.disabled = false;
                return;
              }
              window.opsbar.complete(opHandle, data);
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
            },
            (err) => {
              window.opsbar.error(opHandle, err.message || 'stream error');
              showToast('Analysis stream error: ' + err.message, 'error');
              btnAnalyze.disabled = false;
            }
          );
        }
      } catch (e) {
        showToast('Analysis failed: ' + e.message, 'error');
        btnAnalyze.disabled = false;
      }
    });
  }

  if (btnClassify) {
    btnClassify.addEventListener('click', async () => {
      btnClassify.disabled = true;
      try {
        const result = await apiFetch('/api/classify', { method: 'POST' });
        if (result && result.op_id) {
          showToast('Classification started — this may take a few minutes', 'info');
          const opHandle = window.opsbar.registerOp({
            id: 'classify:' + result.op_id,
            label: 'Classifying genres',
            kind: 'classify',
            onCancel: async () => {
              await apiFetch('/api/progress/' + result.op_id + '/cancel', { method: 'POST' });
            },
          });
          // Stream progress via SSE
          connectToProgress(
            result.op_id,
            result.total,
            (current, total, message) => {
              window.opsbar.progress(opHandle, current, total, message);
            },
            (data) => {
              if (data.cancelled) {
                window.opsbar.error(opHandle, 'cancelled');
                showToast('Classification cancelled', 'info');
                btnClassify.disabled = false;
                return;
              }
              window.opsbar.complete(opHandle, data);
              apiFetch('/api/tracks').then(d => {
                window.tracks = d.tracks || [];
                window.searchResults = null;
                renderTracks();
                updateStats();
              });
              updateToolbarButtonStates();
              showToast('Classification complete', 'success');
              btnClassify.disabled = false;
            },
            (err) => {
              window.opsbar.error(opHandle, err.message || 'stream error');
              showToast('Classification stream error: ' + err.message, 'error');
              btnClassify.disabled = false;
            }
          );
        }
      } catch (e) {
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
    btnWriteTags.addEventListener('click', async () => {
      btnWriteTags.disabled = true;
      try {
        const result = await apiFetch('/api/review/write', { method: 'POST' });
        if (result && result.op_id) {
          const total = result.total || 0;
          showToast('Writing tags to ' + total + ' files — do not close the app', 'info');
          const opHandle = window.opsbar.registerOp({
            id: 'write:' + result.op_id,
            label: 'Writing tags',
            kind: 'write',
            onCancel: async () => {
              await apiFetch('/api/progress/' + result.op_id + '/cancel', { method: 'POST' });
            },
          });
          // Stream progress via SSE
          connectToProgress(
            result.op_id,
            result.total,
            (current, total, message) => {
              window.opsbar.progress(opHandle, current, total, message);
            },
            (data) => {
              if (data.cancelled) {
                window.opsbar.error(opHandle, 'cancelled');
                showToast('Write cancelled', 'info');
                btnWriteTags.disabled = false;
                return;
              }
              window.opsbar.complete(opHandle, data);
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
            },
            (err) => {
              window.opsbar.error(opHandle, err.message || 'stream error');
              showToast('Write stream error: ' + err.message, 'error');
              btnWriteTags.disabled = false;
            }
          );
        } else {
          btnWriteTags.disabled = false;
        }
      } catch (e) {
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

// showProgressInStatsBar / hideProgressInStatsBar shims live in opsbar.js
// (loaded before this file). Local definitions removed in v4.2.0 phase1.2.


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


// --- ES module bridge (0.4): expose to global scope for cross-module calls ---
window.checkResumeSession = checkResumeSession;
window.initLibraryToolbar = initLibraryToolbar;
window.updateToolbarButtonStates = updateToolbarButtonStates;
