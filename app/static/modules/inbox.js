// ============================================================================
// IDJLM Pro — Inbox (Phase 5.5)
// ============================================================================
// Watch-folder inbox view: polls /api/watch/poll from a single owner, fans
// out to store.state.inboxTracks + store.state.tracks. Owns auto-analyse
// toggle and one-key file-away (hotkey 'f', registered in shortcuts.js).
// ============================================================================

(function () {
  let pollInterval = null;
  let autoAnalyseEnabled = false;
  let polling = false;

  function initInbox() {
    if (!store.state.inboxTracks) store.state.inboxTracks = [];

    store.subscribe('inboxTracks', () => renderInbox());

    var toggle = document.getElementById('inbox-auto-analyse');
    if (toggle) {
      autoAnalyseEnabled = localStorage.getItem('idjlm-inbox-auto-analyse') === '1';
      toggle.checked = autoAnalyseEnabled;
      toggle.addEventListener('change', function () {
        autoAnalyseEnabled = toggle.checked;
        localStorage.setItem('idjlm-inbox-auto-analyse', autoAnalyseEnabled ? '1' : '0');
      });
    }

    var destInput = document.getElementById('inbox-destination');
    if (destInput) {
      var saved = localStorage.getItem('idjlm-inbox-destination') || '';
      destInput.value = saved;
      destInput.addEventListener('input', function () {
        localStorage.setItem('idjlm-inbox-destination', destInput.value);
      });
    }

    var pollBtn = document.getElementById('btn-inbox-poll');
    if (pollBtn) pollBtn.addEventListener('click', function () { doPoll(); });

    // Delegated click on file-away buttons + row select
    var inboxTbody = document.getElementById('inbox-tbody');
    if (inboxTbody) {
      inboxTbody.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-file-away]');
        if (btn) {
          e.stopPropagation();
          fileAwayTrack(btn.dataset.fileAway);
          return;
        }
        var row = e.target.closest('tr[data-file-path]');
        if (row) selectInboxRow(row);
      });
    }

    // Register hotkey via shortcuts registry
    if (window.registerGlobalShortcut) {
      window.registerGlobalShortcut('inbox-file-away', handleFileAway);
    }

    // Hook switchTab to start/stop polling
    var origSwitchTab = window.switchTab;
    window.switchTab = function (tabName) {
      origSwitchTab(tabName);
      if (tabName === 'inbox') { startPolling(); checkWatchStatus(); }
      else stopPolling();
    };

    window.addEventListener('beforeunload', stopPolling);
  }

  // --- Watch status ----------------------------------------------------------

  function checkWatchStatus() {
    apiFetch('/api/watch/status').then(function (data) {
      var el = document.getElementById('inbox-watch-status');
      if (!el) return;
      if (data.watching) {
        el.textContent = 'Watching: ' + (data.folder || '--') + ' (' + (data.new_count || 0) + ' pending)';
        el.className = 'inbox-watch-status active';
      } else {
        el.textContent = 'Not watching — start watch in Settings';
        el.className = 'inbox-watch-status';
      }
    }).catch(function () {});
  }

  // --- Polling ---------------------------------------------------------------

  function startPolling() {
    if (pollInterval) return;
    doPoll();
    pollInterval = setInterval(doPoll, 5000);
  }

  function stopPolling() {
    if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
  }

  function doPoll() {
    if (polling) return;
    polling = true;
    apiFetch('/api/watch/poll').then(function (result) {
      if (result.tracks && result.tracks.length) {
        ingestPolledTracks(result.tracks);
      }
    }).catch(function () {}).finally(function () {
      polling = false;
    });
  }

  function ingestPolledTracks(newTracks) {
    // Add to main track store
    var currentTracks = store.state.tracks || [];
    var existingPaths = new Set(currentTracks.map(function (t) { return t.file_path; }));
    var novel = newTracks.filter(function (t) { return !existingPaths.has(t.file_path); });
    if (novel.length) store.set('tracks', currentTracks.concat(novel));

    // Add to inbox
    var currentInbox = store.state.inboxTracks || [];
    var inboxPaths = new Set(currentInbox.map(function (t) { return t.file_path; }));
    var newInbox = newTracks.filter(function (t) { return !inboxPaths.has(t.file_path); });
    if (newInbox.length) {
      store.set('inboxTracks', currentInbox.concat(newInbox));
      showToast(newInbox.length + ' new track' + (newInbox.length !== 1 ? 's' : '') + ' detected', 'success');
    }

    // Auto-analyse
    if (autoAnalyseEnabled && novel.length) {
      autoAnalyseTracks(novel.map(function (t) { return t.file_path; }));
    }

    updateBadge();
  }

  // --- Auto-analyse ----------------------------------------------------------

  function autoAnalyseTracks(paths) {
    apiFetch('/api/analyze', {
      method: 'POST',
      body: JSON.stringify({ track_paths: paths }),
    }).then(function (result) {
      if (!result || !result.op_id) return;
      var opHandle = window.opsbar.registerOp({
        id: 'inbox-analyze:' + result.op_id,
        label: 'Auto-analysing inbox',
        kind: 'analyze',
        onCancel: function () {
          return apiFetch('/api/progress/' + result.op_id + '/cancel', { method: 'POST' });
        },
      });
      window.connectToProgress(
        result.op_id,
        result.total || paths.length,
        function (current, total, msg) { window.opsbar.progress(opHandle, current, total, msg); },
        function (data) {
          if (data.cancelled) { window.opsbar.error(opHandle, 'cancelled'); return; }
          window.opsbar.complete(opHandle, (result.total || paths.length) + ' analysed');
          apiFetch('/api/tracks').then(function (d) {
            if (d && d.tracks) store.set('tracks', d.tracks);
            window.searchResults = null;
            renderInbox();
          });
          if (typeof updateStats === 'function') updateStats();
        },
        function (err) { window.opsbar.error(opHandle, err.message || 'analysis failed'); }
      );
    }).catch(function (e) {
      showToast('Auto-analyse failed: ' + e.message, 'error');
    });
  }

  // --- File-away -------------------------------------------------------------

  function handleFileAway() {
    var rows = document.querySelectorAll('#inbox-tbody tr:not(.empty-state)');
    if (!rows.length) return;
    var selected = document.querySelector('#inbox-tbody tr.row-selected');
    var fp = selected ? selected.dataset.filePath : rows[0].dataset.filePath;
    if (fp) fileAwayTrack(fp);
  }

  function fileAwayTrack(filePath) {
    var destination = localStorage.getItem('idjlm-inbox-destination');
    if (!destination) {
      showToast('Set a destination folder for file-away first', 'warning');
      return;
    }
    apiFetch('/api/organise/file-away', {
      method: 'POST',
      body: JSON.stringify({ file_path: filePath, destination: destination }),
    }).then(function () {
      var tracks = (store.state.inboxTracks || []).filter(function (t) { return t.file_path !== filePath; });
      store.set('inboxTracks', tracks);
      showToast('Track filed away', 'success');
    }).catch(function (e) {
      showToast('File-away failed: ' + (e.message || 'unknown'), 'error');
    });
  }

  // --- Rendering -------------------------------------------------------------

  function selectInboxRow(row) {
    var rows = document.querySelectorAll('#inbox-tbody tr[data-file-path]');
    rows.forEach(function (r) { r.classList.remove('row-selected'); });
    row.classList.add('row-selected');
  }

  function renderInbox() {
    var tbody = document.getElementById('inbox-tbody');
    if (!tbody) return;
    var tracks = store.state.inboxTracks || [];

    if (!tracks.length) {
      tbody.innerHTML = '<tr class="empty-state"><td colspan="6"><div class="empty-state-content"><div class="empty-icon">&#x1F4e5;</div><div class="empty-msg">No tracks in inbox</div><div class="empty-submsg">Start watching a folder to see new tracks here</div></div></td></tr>';
      updateBadge();
      return;
    }

    tbody.innerHTML = tracks.map(function (t) {
      var artist = t.artist || t.existing_artist || '\u2014';
      var title = t.title || t.existing_title || t.filename || '\u2014';
      var bpm = t.final_bpm || t.existing_bpm || '\u2014';
      var key = t.final_key || t.existing_key || '\u2014';
      return '<tr data-file-path="' + escapeHtml(t.file_path) + '">' +
        '<td class="col-title">' + escapeHtml(title) + '</td>' +
        '<td class="col-artist">' + escapeHtml(artist) + '</td>' +
        '<td class="col-bpm mono">' + escapeHtml(String(bpm)) + '</td>' +
        '<td class="col-key mono">' + escapeHtml(String(key)) + '</td>' +
        '<td class="col-status">' + (t.analysis_done
          ? '<span class="badge" style="background:var(--green-dim)">analysed</span>'
          : '<span class="badge" style="background:var(--amber-dim)">pending</span>') + '</td>' +
        '<td class="col-actions"><button class="btn btn-secondary btn-sm" data-file-away="' + escapeHtml(t.file_path) + '">File Away</button></td>' +
        '</tr>';
    }).join('');

    updateBadge();
  }

  function updateBadge() {
    var count = (store.state.inboxTracks || []).length;
    var badge = document.getElementById('sidebar-count-inbox');
    if (badge) badge.textContent = count;
  }

  // --- Export ----------------------------------------------------------------

  window.initInbox = initInbox;
  window.handleFileAway = handleFileAway;
})();
