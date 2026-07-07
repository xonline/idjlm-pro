// ============================================================================
// Initialization
// ============================================================================

// ─── Threshold localStorage persistence ───────────────────────────────────────
function initThresholdPersistence() {
  const input = document.getElementById('toolbar-threshold');
  if (!input) return;
  const saved = localStorage.getItem('idjlm-threshold');
  if (saved) input.value = saved;
  input.addEventListener('change', () => {
    localStorage.setItem('idjlm-threshold', input.value);
  });
  // Stop click on input from firing the parent button
  input.addEventListener('click', e => e.stopPropagation());
}


function initWorkflowGuide() {
  // Show workflow guide on first run (if no tracks imported yet)
  var guide = document.getElementById('workflow-guide');
  if (!guide) return;

  if (!localStorage.getItem('idjlm-workflow-seen')) {
    var store = window.tracks || [];
    if (store.length === 0) {
      guide.style.display = 'block';
    }
  }

  var closeBtn = document.getElementById('close-workflow-guide');
  if (closeBtn) {
    closeBtn.addEventListener('click', function() {
      guide.style.display = 'none';
      localStorage.setItem('idjlm-workflow-seen', '1');
    });
  }
}

function saveSetlistToStorage() {
  localStorage.setItem('idjlm-setlist', JSON.stringify(window.setlist || []));
}

function loadSetlistFromStorage() {
  try {
    const saved = localStorage.getItem('idjlm-setlist');
    if (saved) window.setlist = JSON.parse(saved);
  } catch(e) {
    window.setlist = [];
  }
}


// ============================================================================

let organiseTabInited = false;
function initOrganiseTab() {
  if (organiseTabInited) return;
  organiseTabInited = true;

  document.getElementById('btn-refresh-health')?.addEventListener('click', loadLibraryHealth);
  document.getElementById('btn-parse-filenames')?.addEventListener('click', parseFilenames);
  document.getElementById('btn-organise-preview')?.addEventListener('click', previewOrganise);
  document.getElementById('btn-organise-run')?.addEventListener('click', runOrganise);
  document.getElementById('btn-validate-keys')?.addEventListener('click', validateKeys);
  initDuplicatesTab();
  loadLibraryHealth();
}

// ============================================================================
// Set Planner Tab Init (called lazily from switchTab on first visit)
// ============================================================================

let setplanTabInited = false;
function initSetPlanTab() {
  if (setplanTabInited) return;
  setplanTabInited = true;

  document.getElementById('btn-generate-set')?.addEventListener('click', generateSet);

  // Populate genre filter from taxonomy
  const genreSelect = document.getElementById('setplan-genre');
  if (genreSelect && window.taxonomy) {
    Object.keys(window.taxonomy).forEach(genre => {
      const opt = document.createElement('option');
      opt.value = genre;
      opt.textContent = genre;
      genreSelect.appendChild(opt);
    });
  }

  loadSetplanArcs();
}


async function loadLibraryHealth() {
  try {
    const res = await apiFetch('/api/library/health');
    document.getElementById('health-total').textContent = res.total;
    document.getElementById('health-analysed').textContent = res.analyzed;
    document.getElementById('health-classified').textContent = res.classified;
    document.getElementById('health-approved').textContent = res.approved;
    document.getElementById('health-written').textContent = res.tags_written;
    document.getElementById('health-duplicates').textContent = res.duplicates;

    // Coverage bars
    const covEl = document.getElementById('health-coverage');
    const fields = [
      ['BPM', res.coverage.bpm],
      ['Key', res.coverage.key],
      ['Energy', res.coverage.energy],
      ['Artwork', res.coverage.artwork],
    ];
    covEl.innerHTML = fields.map(([label, val]) => {
      const pct = Math.round((val || 0) * 100);
      const color = pct >= 80 ? 'var(--accent)' : pct >= 50 ? '#f0a500' : 'var(--danger)';
      return `<div style="margin-bottom:0.5rem;">
        <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
          <span style="font-size:0.8rem;color:var(--text-muted)">${label}</span>
          <span style="font-size:0.8rem;color:var(--text-muted)">${pct}%</span>
        </div>
        <div style="height:6px;background:var(--border);border-radius:3px;">
          <div style="height:100%;width:${pct}%;background:${color};border-radius:3px;transition:width 0.3s;"></div>
        </div>
      </div>`;
    }).join('');

    // Genre breakdown
    const genreEl = document.getElementById('health-by-genre');
    if (res.by_genre && Object.keys(res.by_genre).length) {
      const sorted = Object.entries(res.by_genre).sort((a,b) => b[1]-a[1]);
      genreEl.innerHTML = `<div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.5rem;">By Genre</div>`
        + sorted.map(([g, n]) => `<span class="badge" style="margin:2px;">${g} <strong>${n}</strong></span>`).join('');
    }
  } catch(e) {
    console.error('Health load failed', e);
  }
}

async function parseFilenames() {
  const btn = document.getElementById('btn-parse-filenames');
  btn.disabled = true; btn.textContent = 'Scanning...';
  try {
    const res = await apiFetch('/api/organise/parse-filenames', {
      method: 'POST',
      body: JSON.stringify({all: true})
    });
    const data = res;
    const el = document.getElementById('filename-parse-results');
    if (!data.length) {
      el.innerHTML = '<p style="color:var(--text-muted)">No parseable filenames found (all tracks already have tags, or filenames don\'t match "Artist - Title" pattern).</p>';
      return;
    }
    const conflicting = data.filter(t => t.has_conflict);
    const noTag = data.filter(t => !t.has_conflict);
    let html = `<p style="margin-bottom:0.5rem;">${data.length} tracks with parseable filenames (${conflicting.length} conflicts, ${noTag.length} no existing tags).</p>`;
    html += `<table class="data-table" style="font-size:0.8rem;">
      <thead><tr><th>File</th><th>Parsed Artist</th><th>Parsed Title</th><th>Current Artist</th><th>Current Title</th><th></th></tr></thead>
      <tbody>`;
    data.forEach(t => {
      const rowStyle = t.has_conflict ? 'background:rgba(240,80,80,0.05);' : '';
      html += `<tr style="${rowStyle}">
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${t.filename}">${t.filename}</td>
        <td>${t.parsed_artist || '—'}</td>
        <td>${t.parsed_title || '—'}</td>
        <td>${t.current_artist || '—'}</td>
        <td>${t.current_title || '—'}</td>
        <td><button class="btn btn-sm btn-primary" onclick="applyFilenameTag('${encodeURIComponent(t.file_path)}','${encodeURIComponent(t.parsed_artist||'')}','${encodeURIComponent(t.parsed_title||'')}', this)">Apply</button></td>
      </tr>`;
    });
    html += `</tbody></table>`;
    html += `<div style="margin-top:0.75rem;"><button class="btn btn-primary" onclick="applyAllFilenameTags(${JSON.stringify(data)})">Apply All</button></div>`;
    el.innerHTML = html;
  } finally {
    btn.disabled = false; btn.textContent = 'Scan All Tracks';
  }
}

async function applyFilenameTag(encodedPath, encodedArtist, encodedTitle, btn) {
  btn.disabled = true;
  const path = decodeURIComponent(encodedPath);
  const artist = decodeURIComponent(encodedArtist);
  const title = decodeURIComponent(encodedTitle);
  await apiFetch('/api/organise/apply-filename-tags', {
    method: 'POST',
    body: JSON.stringify({updates: [{file_path: path, artist, title}]})
  });
  btn.textContent = '✓'; btn.style.background = 'var(--accent)';
}

async function applyAllFilenameTags(tracks) {
  const updates = tracks.filter(t => t.parsed_artist || t.parsed_title).map(t => ({
    file_path: t.file_path, artist: t.parsed_artist || t.current_artist, title: t.parsed_title || t.current_title
  }));
  const res = await apiFetch('/api/organise/apply-filename-tags', {
    method: 'POST',
    body: JSON.stringify({updates})
  });
  const d = res;
  alert(`Applied tags to ${d.updated} tracks. They are now set to "pending" for review.`);
}

async function previewOrganise() {
  const dest = document.getElementById('organise-dest').value.trim();
  if (!dest) { alert('Enter a destination folder first.'); return; }
  const pattern = document.getElementById('organise-pattern').value;
  const res = await apiFetch('/api/organise/folders', {
    method: 'POST',
    body: JSON.stringify({destination: dest, pattern, dry_run: true})
  });
  const d = res;
  const el = document.getElementById('organise-preview-results');
  if (d.error) { el.innerHTML = `<p style="color:var(--danger)">${d.error}</p>`; return; }
  const moves = d.moves || [];
  if (!moves.length) { el.innerHTML = '<p style="color:var(--text-muted)">No approved tracks to move.</p>'; return; }
  const overwrite = moves.filter(m => m.would_overwrite).length;
  el.innerHTML = `<p style="margin-bottom:0.5rem;">${moves.length} files to move${overwrite ? ` (${overwrite} would overwrite)` : ''}.</p>
    <div style="max-height:200px;overflow-y:auto;font-size:0.75rem;background:var(--bg-secondary);padding:0.75rem;border-radius:6px;">
      ${moves.slice(0, 50).map(m => `<div>${m.from.split('/').pop()} → <strong>${m.to.split('/').slice(-3).join('/')}</strong>${m.would_overwrite ? ' ⚠️' : ''}</div>`).join('')}
      ${moves.length > 50 ? `<div style="color:var(--text-muted)">... and ${moves.length - 50} more</div>` : ''}
    </div>`;
  document.getElementById('btn-organise-run').disabled = false;
  document.getElementById('btn-organise-run')._previewData = {dest, pattern};
}

async function runOrganise() {
  const previewData = document.getElementById('btn-organise-run')._previewData;
  if (!previewData) { showToast('Run a preview first', 'warning'); return; }
  if (!confirm(`This will physically move files. Continue?`)) return;
  const {dest, pattern} = previewData;
  const btn = document.getElementById('btn-organise-run');
  btn.disabled = true; btn.textContent = 'Moving...';
  const res = await apiFetch('/api/organise/folders', {
    method: 'POST',
    body: JSON.stringify({destination: dest, pattern, dry_run: false})
  });
  const d = res;
  if (d.error) { alert(d.error); }
  else { alert(`Moved ${d.moved} files successfully${d.errors?.length ? ` (${d.errors.length} errors)` : ''}.`); }
  btn.textContent = 'Move Files';
}

async function validateKeys() {
  const btn = document.getElementById('btn-validate-keys');
  btn.disabled = true; btn.textContent = 'Checking...';
  try {
    const res = await apiFetch('/api/validate/keys');
    const d = res;
    const el = document.getElementById('key-validation-results');
    if (d.error) { el.innerHTML = `<p style="color:var(--danger)">${d.error}</p>`; return; }
    if (!d.mismatches?.length) {
      el.innerHTML = `<p style="color:var(--accent)">✓ All ${d.total_checked} keys match (within 1 Camelot step). No corrections needed.</p>`;
      return;
    }
    let html = `<p style="margin-bottom:0.5rem;">${d.mismatch_count} mismatches out of ${d.total_checked} tracks checked.</p>
      <table class="data-table" style="font-size:0.8rem;">
        <thead><tr><th>Title</th><th>Artist</th><th>Stored Key</th><th>Detected Key</th><th>Distance</th><th></th></tr></thead>
        <tbody>`;
    d.mismatches.forEach(m => {
      html += `<tr>
        <td>${m.title || '—'}</td><td>${m.artist || '—'}</td>
        <td><span class="badge">${m.stored_key}</span></td>
        <td><span class="badge" style="background:var(--accent);">${m.analyzed_key}</span></td>
        <td>${m.distance}</td>
        <td><button class="btn btn-sm btn-primary" onclick="fixKey('${encodeURIComponent(m.file_path)}', this)">Use Detected</button></td>
      </tr>`;
    });
    html += `</tbody></table>
      <div style="margin-top:0.75rem;">
        <button class="btn btn-primary" onclick="fixAllKeys(${JSON.stringify(d.mismatches.map(m=>m.file_path))})">Fix All (${d.mismatch_count})</button>
      </div>`;
    el.innerHTML = html;
  } finally {
    btn.disabled = false; btn.textContent = 'Check Keys';
  }
}

async function fixKey(encodedPath, btn) {
  btn.disabled = true;
  await apiFetch('/api/validate/keys/fix', {
    method: 'POST',
    body: JSON.stringify({paths: [decodeURIComponent(encodedPath)], use_analyzed: true})
  });
  btn.textContent = '✓'; btn.style.background = 'var(--accent)';
}

async function fixAllKeys(paths) {
  const res = await apiFetch('/api/validate/keys/fix', {
    method: 'POST',
    body: JSON.stringify({paths, use_analyzed: true})
  });
  const d = res;
  alert(`Fixed ${d.fixed} key mismatches.`);
  validateKeys();
}


/* ============================================================
   Pipeline Stepper & Onboarding Wizard
   ============================================================ */

/** Update the pipeline stepper based on current track states */
function updatePipelineStepper() {
  var allTracks = window.tracks || [];
  if (!allTracks.length) return;

  var total = allTracks.length;
  var imported = total;
  var analyzed = allTracks.filter(function(t) { return t.analysis_done; }).length;
  var classified = allTracks.filter(function(t) { return t.classification_done; }).length;
  var approved = allTracks.filter(function(t) { return t.review_status === 'approved' || t.review_status === 'edited'; }).length;
  var written = allTracks.filter(function(t) { return t.tags_written; }).length;

  setStepStatus('import', imported, imported, total, imported > 0 ? 'completed' : '');
  setStepStatus('analyse', analyzed, total, analyzed > 0 ? (analyzed === total ? 'completed' : 'active') : '');
  setStepStatus('classify', classified, total, classified > 0 ? (classified === total ? 'completed' : 'active') : '');
  setStepStatus('review', approved, total, approved > 0 ? (approved === total ? 'completed' : 'active') : '');
  setStepStatus('write', written, total, written > 0 ? (written === total ? 'completed' : 'active') : '');
}

function setStepStatus(step, done, total, status) {
  var el = document.getElementById('step-' + step);
  var countEl = document.getElementById('count-' + step);
  if (!el || !countEl) return;
  el.classList.toggle('active', status === 'active');
  el.classList.toggle('completed', status === 'completed');
  countEl.textContent = done + '/' + total;
}

/** Show onboarding wizard if first run */
function showOnboardingIfNeeded() {
  if (localStorage.getItem('idjlm-onboarding-done')) return;
  var store = window.tracks || [];
  if (store.length > 0) return;
  var overlay = document.getElementById('onboarding-overlay');
  if (overlay) { overlay.style.display = 'flex'; updateOnboardingStep(1); }
}

function updateOnboardingStep(step) {
  for (var i = 1; i <= 3; i++) {
    var el = document.getElementById('onboard-step-' + i);
    if (el) el.style.display = i === step ? '' : 'none';
  }
  var fill = document.getElementById('onboard-progress-fill');
  var text = document.getElementById('onboard-progress-text');
  if (fill) fill.style.width = (step / 3 * 100) + '%';
  if (text) text.textContent = 'Step ' + step + ' of 3';
}

function completeOnboarding() {
  localStorage.setItem('idjlm-onboarding-done', 'true');
  var overlay = document.getElementById('onboarding-overlay');
  if (overlay) {
    overlay.style.display = 'none';
    overlay.style.pointerEvents = 'none';
  }
}


/** Auto-resume previous session on startup; show onboarding only on true first launch */
async function autoResumeOrOnboard() {
  try {
    const sessionInfo = await apiFetch('/api/session/exists');
    if (sessionInfo && sessionInfo.exists && sessionInfo.track_count > 0) {
      // Auto-resume: load without prompting
      const result = await apiFetch('/api/session/load', { method: 'POST' });
      if (result && result.tracks) {
        window.tracks = result.tracks;
        window.searchResults = null;
        renderTracks();
        updateStats();
        updatePipelineStepper();
        updateToolbarButtonStates();
        const count = result.count || result.tracks.length;
        const folder = result.metadata && result.metadata.folder_path ? ' from ' + (result.metadata.folder_path.split('/').pop() || result.metadata.folder_path) : '';
        showToast('Resumed: ' + count + ' tracks' + folder, 'success');
        // Update folder display if metadata has it
        if (result.metadata && result.metadata.folder_path) {
          const folderDisplay = document.getElementById('folder-display');
          if (folderDisplay) folderDisplay.textContent = result.metadata.folder_path;
        }
      }
      return; // Don't show onboarding
    }
  } catch (e) {
    // session/exists failed (network error etc.) — fall through to onboarding check
  }
  // No session or failed to load — show onboarding if first launch
  showOnboardingIfNeeded();
}

function initOnboarding() {
  // Bind ALL close buttons (there are two elements with id="onboarding-close")
  document.querySelectorAll('#onboarding-close, .onboarding-close').forEach(function(btn) {
    btn.addEventListener('click', completeOnboarding);
  });

  var chooseBtn = document.getElementById('onboard-choose-folder');
  if (chooseBtn) {
    chooseBtn.addEventListener('click', async function() {
      if (window.pywebview && window.pywebview.api) {
        var path = await window.pywebview.api.choose_folder();
        if (path) {
          document.getElementById('onboard-folder-path').textContent = path;
          // Actually import the folder — not just show the path
          try {
            var result = await apiFetch('/api/import', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ folder_path: path })
            });
            if (result && result.tracks) {
              window.tracks = result.tracks;
              window.searchResults = null;
              renderTracks();
              updateStats();
              updatePipelineStepper();
              updateToolbarButtonStates();
              showToast((result.count || result.tracks.length) + ' tracks imported', 'success');
            }
          } catch (e) {
            showToast('Import failed: ' + e.message, 'error');
          }
          updateOnboardingStep(2);
        }
      } else {
        document.getElementById('btn-get-started')?.click();
        updateOnboardingStep(2);
      }
    });
  }

  var continueBtn = document.getElementById('onboard-continue');
  if (continueBtn) {
    continueBtn.addEventListener('click', function() {
      var sel = document.querySelector('.onboarding-provider.selected');
      var provider = sel ? sel.dataset.provider : 'gemini';
      var ps = document.getElementById('settings-provider');
      if (ps) { ps.value = provider; ps.dispatchEvent(new Event('change')); }
      updateOnboardingStep(3);
    });
  }

  document.querySelectorAll('.onboarding-provider').forEach(function(el) {
    el.addEventListener('click', function() {
      document.querySelectorAll('.onboarding-provider').forEach(function(e) { e.classList.remove('selected'); });
      el.classList.add('selected');
    });
  });

  var startBtn = document.getElementById('onboard-start-import');
  if (startBtn) {
    startBtn.addEventListener('click', function() { completeOnboarding(); });
  }

  // Skip API key setup
  var skipBtn = document.getElementById('onboard-skip-api');
  if (skipBtn) {
    skipBtn.addEventListener('click', function() { updateOnboardingStep(3); });
  }

  // Go to Settings from onboarding
  var settingsBtn = document.getElementById('onboard-go-settings');
  if (settingsBtn) {
    settingsBtn.addEventListener('click', function() {
      completeOnboarding();
      switchTab('settings');
    });
  }

  autoResumeOrOnboard();
}

/* ============================================================
   API Key Test Button
   ============================================================ */
async function testApiKey(provider) {
  // Clear all status elements first
  document.querySelectorAll('[id^="key-test-status-"]').forEach(function(el) {
    el.innerHTML = '';
  });
  const statusEl = document.getElementById('key-test-status-' + provider);
  if (!statusEl) return;
  statusEl.innerHTML = '<span style="color:var(--text-muted);font-size:12px;">Testing ' + provider + '...</span>';

  // Read the key the user has typed (or left blank to use the saved key).
  const keyInputMap = {
    claude: 'settings-anthropic-key',
    openai: 'settings-openai-key',
    openrouter: 'settings-openrouter-key',
    gemini: 'settings-gemini-key',
    qwen: 'settings-qwen-key',
    deepseek: 'settings-deepseek-key',
    groq: 'settings-groq-key',
  };
  const keyInputEl = keyInputMap[provider] ? document.getElementById(keyInputMap[provider]) : null;
  const typedKey = keyInputEl ? keyInputEl.value.trim() : '';
  const payload = { provider: provider };
  if (typedKey) payload.api_key = typedKey;

  try {
    const res = await apiFetch('/api/test_key', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      statusEl.innerHTML = '<span style="color:#22c55e;font-size:12px;">✓ Connected (' + res.latency_ms + 'ms)</span>';
      setTimeout(() => { statusEl.innerHTML = ''; }, 5000);
    } else {
      statusEl.innerHTML = '<span style="color:var(--danger);font-size:12px;">✗ ' + escapeHtml(res.error || 'Test failed') + '</span>';
    }
  } catch (e) {
    statusEl.innerHTML = '<span style="color:var(--danger);font-size:12px;">✗ ' + escapeHtml(e.message) + '</span>';
  }
}


// --- ES module bridge (0.4): expose to global scope for cross-module calls ---
window.initOnboarding = initOnboarding;
window.initOrganiseTab = initOrganiseTab;
window.initSetPlanTab = initSetPlanTab;
window.initThresholdPersistence = initThresholdPersistence;
window.initWorkflowGuide = initWorkflowGuide;
window.loadSetlistFromStorage = loadSetlistFromStorage;
window.saveSetlistToStorage = saveSetlistToStorage;
window.testApiKey = testApiKey;
window.updatePipelineStepper = updatePipelineStepper;
