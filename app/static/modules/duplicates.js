// ============================================================================
// duplicates.js — Duplicates tab (scan / render / merge / remove)
// ============================================================================
// Extracted from pipeline.js (Phase 0.3). No behaviour change.
// Owns:
//   - initDuplicatesTab: wires scan button
//   - scanForDuplicates / renderDuplicates / mergeDuplicateGroup / removeDuplicate
// Dependencies (window-globals, resolved by load order):
//   - showSpinner / hideSpinner / apiFetch / showToast / escapeHtml: core.js
//   - renderTracks: tracks.js
//   - window.tracks / window.searchResults: core.js
//   - scanForDuplicates is also re-invoked by removeDuplicate for rescan (recursive).
// ----------------------------------------------------------------------------

function initDuplicatesTab() {
  const scanBtn = document.getElementById('btn-scan-duplicates');
  if (scanBtn) {
    scanBtn.addEventListener('click', scanForDuplicates);
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
