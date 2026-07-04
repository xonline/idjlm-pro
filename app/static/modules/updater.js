// ============================================================================
// updater.js — Self-update checker (GitHub release check + download + install)
// ============================================================================
// Extracted from pipeline.js (Phase 0.3). No behaviour change.
// Owns:
//   - checkForUpdates / formatReleaseNotes / downloadUpdate / pollDownloadProgress
//   - openDmg / runGitPull / closeUpdateModal / setUpdateBadge / clearUpdateBadge
//   - initUpdateChecker (called from app.js DOMContentLoaded)
// State (module-local let):
//   - updateCheckResult, downloadPollInterval
// Dependencies (window-globals): showToast, escapeHtml, apiFetch (core.js)
// ----------------------------------------------------------------------------

let updateCheckResult = null;
let downloadPollInterval = null;

async function checkForUpdates() {
  const modal = document.getElementById('update-modal');
  const titleEl = document.getElementById('update-modal-title');
  const bodyEl = document.getElementById('update-modal-body');
  const footerEl = document.getElementById('update-modal-footer');

  if (!modal || !bodyEl || !footerEl) return;

  // Show loading state
  if (titleEl) titleEl.textContent = 'Checking for Updates...';
  bodyEl.innerHTML = '<p style="text-align:center;color:var(--text-secondary);font-size:13px;">Contacting GitHub...</p>';
  footerEl.innerHTML = '<button class="btn btn-secondary" id="update-cancel-check">Cancel</button>';
  const cancelBtn = document.getElementById('update-cancel-check');
  if (cancelBtn) cancelBtn.addEventListener('click', closeUpdateModal);

  modal.style.display = 'flex';

  try {
    const data = await apiFetch('/api/version/check');
    if (!data) {
      bodyEl.innerHTML = '<p style="text-align:center;color:var(--red);font-size:13px;">Could not check for updates.</p>';
      footerEl.innerHTML = '<button class="btn btn-primary" onclick="closeUpdateModal()">Close</button>';
      return;
    }

    updateCheckResult = data;

    if (data.error) {
      // Error from API (rate limit, network, etc.)
      bodyEl.innerHTML = '<p style="text-align:center;color:var(--red);font-size:13px;">' + escapeHtml(data.error) + '</p>';
      footerEl.innerHTML = '<button class="btn btn-primary" onclick="closeUpdateModal()">Close</button>';
      return;
    }

    if (!data.has_update) {
      // Up to date
      bodyEl.innerHTML =
        '<div style="text-align:center;padding:20px 0;">' +
        '<div style="font-size:48px;margin-bottom:12px;">&#9989;</div>' +
        '<p style="font-size:15px;font-weight:600;color:var(--text-loud);margin-bottom:4px;">You\'re up to date!</p>' +
        '<p style="font-size:13px;color:var(--text-secondary);">Running <strong>' + escapeHtml(data.current) + '</strong> &mdash; the latest version.</p>' +
        '</div>';
      footerEl.innerHTML = '<button class="btn btn-primary" onclick="closeUpdateModal()">Done</button>';
      // Clear notification badge
      clearUpdateBadge();
      return;
    }

    // Update available
    const publishedStr = data.published_at
      ? '<p class="update-published-at">Published: ' + new Date(data.published_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) + '</p>'
      : '';

    const releaseNotesHtml = formatReleaseNotes(data.release_notes || 'No release notes available.');

    let bodyHtml = '';
    bodyHtml += '<div class="update-version-info">';
    bodyHtml += '<div class="update-version-current"><span class="update-version-label">Current</span><span class="update-version-number">' + escapeHtml(data.current) + '</span></div>';
    bodyHtml += '<span class="update-version-arrow">&#8594;</span>';
    bodyHtml += '<div class="update-version-latest"><span class="update-version-label">Latest</span><span class="update-version-number">' + escapeHtml(data.latest) + '</span></div>';
    bodyHtml += '</div>';

    bodyHtml += publishedStr;
    bodyHtml += '<h3 style="font-size:14px;font-weight:600;color:var(--text-loud);margin:0 0 4px;">What\'s New</h3>';
    bodyHtml += '<div class="release-notes">' + releaseNotesHtml + '</div>';

    // Git pull section for source installs
    if (!data.is_macos || !data.download_url || data.download_url.includes('/releases/')) {
      bodyHtml += '<div class="update-git-pull-section">';
      bodyHtml += '<h4>Source Install</h4>';
      bodyHtml += '<p style="font-size:12px;color:var(--text-secondary);margin:0 0 8px;">Update via git pull:</p>';
      bodyHtml += '<button class="btn btn-secondary btn-sm" id="btn-git-pull" style="font-size:12px;padding:5px 12px;">Run git pull</button>';
      bodyHtml += '<div id="git-pull-output" style="display:none;"></div>';
      bodyHtml += '</div>';
    }

    bodyEl.innerHTML = bodyHtml;

    // Footer buttons
    let footerHtml = '';
    footerHtml += '<button class="btn btn-secondary" onclick="closeUpdateModal()">Later</button>';
    if (data.is_macos && data.download_url && !data.download_url.includes('/releases/tag')) {
      footerHtml += '<button class="btn btn-primary" id="btn-download-update">Download Update</button>';
    } else {
      footerHtml += '<button class="btn btn-secondary" id="btn-open-release" style="font-size:12px;">View on GitHub</button>';
    }
    footerEl.innerHTML = footerHtml;

    // Event listeners
    const downloadBtn = document.getElementById('btn-download-update');
    if (downloadBtn) {
      downloadBtn.addEventListener('click', () => downloadUpdate(data.download_url));
    }

    const openReleaseBtn = document.getElementById('btn-open-release');
    if (openReleaseBtn) {
      openReleaseBtn.addEventListener('click', () => {
        window.open(data.download_url || 'https://github.com/xonline/idjlm-pro/releases/latest', '_blank');
        closeUpdateModal();
      });
    }

    const gitPullBtn = document.getElementById('btn-git-pull');
    if (gitPullBtn) {
      gitPullBtn.addEventListener('click', runGitPull);
    }

    // Set notification badge if update available
    setUpdateBadge();

  } catch (e) {
    bodyEl.innerHTML = '<p style="text-align:center;color:var(--red);font-size:13px;">Could not check for updates: ' + escapeHtml(e.message) + '</p>';
    footerEl.innerHTML = '<button class="btn btn-primary" onclick="closeUpdateModal()">Close</button>';
  }
}

function formatReleaseNotes(text) {
  // Basic markdown-like formatting
  let html = escapeHtml(text);
  // Bold: **text**
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Inline code: `text`
  html = html.replace(/`(.*?)`/g, '<code>$1</code>');
  // Links: [text](url)
  html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // Headings: ### text
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  // Unordered lists: - text or * text
  html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
  // Wrap consecutive <li> in <ul>
  html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul>$1</ul>');
  // Line breaks
  html = html.replace(/\n/g, '<br>');
  // Clean up extra <br> around block elements
  html = html.replace(/<br>\s*(<h[1-3]>)/g, '$1');
  html = html.replace(/(<\/h[1-3]>)\s*<br>/g, '$1');
  html = html.replace(/<br>\s*(<ul>)/g, '$1');
  html = html.replace(/(<\/ul>)\s*<br>/g, '$1');
  return html;
}

async function downloadUpdate(url) {
  const bodyEl = document.getElementById('update-modal-body');
  const footerEl = document.getElementById('update-modal-footer');
  const titleEl = document.getElementById('update-modal-title');

  if (!bodyEl || !footerEl) return;

  // Show download progress
  if (titleEl) titleEl.textContent = 'Downloading Update';
  bodyEl.innerHTML =
    '<div class="download-progress">' +
    '<div class="download-progress-label"><span>Downloading...</span><span id="download-pct">0%</span></div>' +
    '<div class="download-progress-track"><div class="download-progress-fill" id="download-fill" style="width:0%"></div></div>' +
    '<div class="download-progress-size" id="download-size">0 MB of &mdash;</div>' +
    '</div>' +
    '<p class="update-status-text" id="download-status">Starting download...</p>';
  footerEl.innerHTML = '<button class="btn btn-secondary" id="btn-cancel-download" disabled>Cancel</button>';

  try {
    const result = await apiFetch('/api/version/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    });

    if (result && result.downloading) {
      // Poll for progress
      pollDownloadProgress();
    }
  } catch (e) {
    const statusEl = document.getElementById('download-status');
    if (statusEl) {
      statusEl.textContent = 'Download failed: ' + e.message;
      statusEl.className = 'update-status-text error';
    }
    footerEl.innerHTML = '<button class="btn btn-primary" onclick="closeUpdateModal()">Close</button>';
  }
}

function pollDownloadProgress() {
  if (downloadPollInterval) clearInterval(downloadPollInterval);

  downloadPollInterval = setInterval(async () => {
    try {
      const data = await apiFetch('/api/version/download/status');

      const fillEl = document.getElementById('download-fill');
      const pctEl = document.getElementById('download-pct');
      const sizeEl = document.getElementById('download-size');
      const statusEl = document.getElementById('download-status');
      const footerEl = document.getElementById('update-modal-footer');

      if (data.error) {
        clearInterval(downloadPollInterval);
        downloadPollInterval = null;
        if (statusEl) {
          statusEl.textContent = 'Download failed: ' + data.error;
          statusEl.className = 'update-status-text error';
        }
        if (footerEl) {
          footerEl.innerHTML = '<button class="btn btn-primary" onclick="closeUpdateModal()">Close</button>';
        }
        return;
      }

      if (data.downloaded && data.size) {
        const pct = Math.round((data.downloaded / data.size) * 100);
        const downloadedMB = (data.downloaded / (1024 * 1024)).toFixed(1);
        const totalMB = (data.size / (1024 * 1024)).toFixed(1);

        if (fillEl) fillEl.style.width = pct + '%';
        if (pctEl) pctEl.textContent = pct + '%';
        if (sizeEl) sizeEl.textContent = downloadedMB + ' MB of ' + totalMB + ' MB';
      } else if (data.downloading) {
        if (statusEl) statusEl.textContent = 'Connecting...';
      }

      if (data.done && data.path) {
        clearInterval(downloadPollInterval);
        downloadPollInterval = null;

        const path = data.path;
        if (fillEl) fillEl.style.width = '100%';
        if (pctEl) pctEl.textContent = '100%';
        if (sizeEl) sizeEl.textContent = (data.size / (1024 * 1024)).toFixed(1) + ' MB';

        if (statusEl) {
          statusEl.textContent = 'Download complete!';
          statusEl.className = 'update-status-text success';
        }

        if (footerEl) {
          footerEl.innerHTML =
            '<button class="btn btn-secondary" onclick="closeUpdateModal()">Later</button>' +
            '<button class="btn btn-primary" id="btn-open-dmg">Open DMG</button>';
          const openBtn = document.getElementById('btn-open-dmg');
          if (openBtn) {
            openBtn.addEventListener('click', () => openDmg(path));
          }
        }
      }

      if (data.done && data.error) {
        clearInterval(downloadPollInterval);
        downloadPollInterval = null;
      }
    } catch (e) {
      // Poll error — just retry next interval
    }
  }, 500);
}

async function openDmg(path) {
  try {
    const data = await apiFetch('/api/version/open-dmg', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path })
    });

    if (data && data.opened) {
      showToast('DMG opened — drag IDJLM Pro to Applications folder', 'success');
      closeUpdateModal();
    } else {
      showToast('Failed to open DMG: ' + (data.error || 'unknown error'), 'error');
    }
  } catch (e) {
    showToast('Failed to open DMG: ' + e.message, 'error');
  }
}

async function runGitPull() {
  const outputEl = document.getElementById('git-pull-output');
  const btnEl = document.getElementById('btn-git-pull');

  if (!outputEl || !btnEl) return;

  btnEl.disabled = true;
  btnEl.textContent = 'Running...';
  outputEl.style.display = 'block';
  outputEl.innerHTML = '<p style="color:var(--text-secondary);font-size:12px;">Running git pull...</p>';

  try {
    const data = await apiFetch('/api/version/git-pull');

    if (data && data.success) {
      outputEl.innerHTML = '<div class="update-git-output">' + escapeHtml(data.output || 'Already up to date.') + '</div>';
    } else {
      outputEl.innerHTML = '<div class="update-git-output" style="color:var(--red);">' + escapeHtml(data.error || data.output || 'git pull failed') + '</div>';
    }
  } catch (e) {
    outputEl.innerHTML = '<div class="update-git-output" style="color:var(--red);">' + escapeHtml(e.message) + '</div>';
  }

  btnEl.disabled = false;
  btnEl.textContent = 'Run git pull';
}

function closeUpdateModal() {
  const modal = document.getElementById('update-modal');
  if (modal) modal.style.display = 'none';
  if (downloadPollInterval) {
    clearInterval(downloadPollInterval);
    downloadPollInterval = null;
  }
}

function setUpdateBadge() {
  const navBtn = document.getElementById('nav-btn-settings');
  if (navBtn) navBtn.classList.add('update-available-badge');
}

function clearUpdateBadge() {
  const navBtn = document.getElementById('nav-btn-settings');
  if (navBtn) navBtn.classList.remove('update-available-badge');
}

function initUpdateChecker() {
  // Header version badge click
  const headerBadge = document.getElementById('header-version-badge');
  if (headerBadge) {
    headerBadge.addEventListener('click', checkForUpdates);
  }

  // Check for Updates button in Settings
  const checkBtn = document.getElementById('btn-check-updates');
  if (checkBtn) {
    checkBtn.addEventListener('click', checkForUpdates);
  }

  // Update modal close
  const closeBtn = document.getElementById('update-modal-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', closeUpdateModal);
  }

  // Close on background click
  const modal = document.getElementById('update-modal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeUpdateModal();
    });
  }
}
