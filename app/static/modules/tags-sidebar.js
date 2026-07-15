// ============================================================================
// tags-sidebar.js — MyTag-style custom tag browser (Phase 4.1)
// Sidebar checkbox groups per tag category. Filter library by tag combos
// (AND across tag keys, OR within a tag key's values).
// Backend: tag_routes.py (shipped in #208)
// ============================================================================

window.activeTagFilters = window.activeTagFilters || {};

function fetchTagsSidebar() {
  window.apiFetch('/api/tags')
    .then(function(data) {
      var keys = data.keys || [];
      var counts = data.counts || {};
      if (!keys.length) {
        renderEmptyTagsSidebar();
        return;
      }
      fetchTagValues(keys, counts);
    })
    .catch(function() {
      renderEmptyTagsSidebar();
    });
}

function fetchTagValues(keys, counts) {
  var tracks = store.state.tracks || [];
  var keyValues = {};

  keys.forEach(function(key) {
    keyValues[key] = { count: counts[key] || 0, values: {} };
  });

  tracks.forEach(function(t) {
    var tags = t.custom_tags || {};
    Object.keys(tags).forEach(function(key) {
      if (keyValues[key]) {
        var val = tags[key] || '(empty)';
        keyValues[key].values[val] = (keyValues[key].values[val] || 0) + 1;
      }
    });
  });

  renderTagsSidebar(keyValues);
}

function renderTagsSidebar(keyValues) {
  var container = document.getElementById('tags-sidebar-inner');
  if (!container) return;
  var html = '';

  Object.keys(keyValues).sort().forEach(function(key) {
    var info = keyValues[key];
    var values = Object.keys(info.values).sort();
    var isExpanded = window._tagsExpanded && window._tagsExpanded[key];
    var activeSet = window.activeTagFilters[key];

    html += '<div class="tag-group">';
    html += '<div class="tag-group-header" data-tag-key="' + window.escapeHtml(key) + '">';
    html += '<span class="tag-group-caret">' + (isExpanded ? '▼' : '▶') + '</span>';
    html += '<span class="tag-group-name">' + window.escapeHtml(key) + '</span>';
    html += '<span class="tag-group-count mono">' + info.count + '</span>';
    html += '</div>';

    if (isExpanded) {
      html += '<div class="tag-group-values">';
      values.forEach(function(val) {
        var checked = activeSet && activeSet.has(val);
        html += '<label class="tag-checkbox-label">';
        html += '<input type="checkbox" class="tag-checkbox" data-tag-key="' + window.escapeHtml(key) + '" data-tag-value="' + window.escapeHtml(val) + '"' + (checked ? ' checked' : '') + '>';
        html += '<span class="tag-checkbox-text">' + window.escapeHtml(val) + '</span>';
        html += '<span class="tag-checkbox-count mono">' + info.values[val] + '</span>';
        html += '</label>';
      });
      html += '</div>';
    }

    html += '</div>';
  });

  container.innerHTML = html;
  wireTagCheckboxEvents();
  wireTagGroupToggles();
}

function renderEmptyTagsSidebar() {
  var container = document.getElementById('tags-sidebar-inner');
  if (!container) return;
  container.innerHTML = '<div class="tag-sidebar-empty">No custom tags found</div>';
}

function wireTagCheckboxEvents() {
  var checkboxes = document.querySelectorAll('.tag-checkbox');
  checkboxes.forEach(function(cb) {
    cb.addEventListener('change', function() {
      var key = cb.dataset.tagKey;
      var value = cb.dataset.tagValue;
      if (!window.activeTagFilters[key]) {
        window.activeTagFilters[key] = new Set();
      }
      if (cb.checked) {
        window.activeTagFilters[key].add(value);
      } else {
        window.activeTagFilters[key].delete(value);
        if (window.activeTagFilters[key].size === 0) {
          delete window.activeTagFilters[key];
        }
      }
      if (typeof renderTracks === 'function') {
        renderTracks();
      }
      updateClearFiltersButton();
    });
  });
}

function wireTagGroupToggles() {
  var headers = document.querySelectorAll('.tag-group-header');
  headers.forEach(function(header) {
    header.addEventListener('click', function() {
      var key = header.dataset.tagKey;
      if (!window._tagsExpanded) window._tagsExpanded = {};
      window._tagsExpanded[key] = !window._tagsExpanded[key];
      refreshTagsSidebar();
    });
  });
}

function refreshTagsSidebar() {
  fetchTagsSidebar();
}

function clearTagFilters() {
  window.activeTagFilters = {};
  if (typeof renderTracks === 'function') {
    renderTracks();
  }
  refreshTagsSidebar();
  var btn = document.getElementById('btn-clear-tag-filters');
  if (btn) btn.style.display = 'none';
}

function updateClearFiltersButton() {
  var btn = document.getElementById('btn-clear-tag-filters');
  if (btn) {
    btn.style.display = hasActiveTagFilters() ? 'block' : 'none';
  }
}

function hasActiveTagFilters() {
  return Object.keys(window.activeTagFilters).length > 0;
}

function initTagsSidebar() {
  var container = document.getElementById('tags-sidebar-inner');
  if (!container) return;
  fetchTagsSidebar();

  // Auto-refresh when tracks change (import, analyse, etc.)
  store.subscribe('tracks', function() {
    refreshTagsSidebar();
  });

  var clearBtn = document.getElementById('btn-clear-tag-filters');
  if (clearBtn) {
    clearBtn.addEventListener('click', clearTagFilters);
  }

  if (typeof window.registerGlobalShortcut === 'function') {
    window.registerGlobalShortcut('quicktag', function() {
      openQuickTagPanel();
    });
  }
}

// ---- Quick-tag panel (OneTagger pattern) ----

function openQuickTagPanel() {
  var sel = store.state.selectedTracks;
  if (!sel || sel.size === 0) {
    window.showToast && window.showToast('Select tracks first', 'info');
    return;
  }

  var existing = document.getElementById('quick-tag-panel');
  if (existing) { existing.remove(); return; }

  var panel = document.createElement('div');
  panel.id = 'quick-tag-panel';
  panel.className = 'quick-tag-panel';

  window.apiFetch('/api/tags')
    .then(function(data) {
      var keys = data.keys || [];
      if (!keys.length) {
        window.showToast && window.showToast('No tags defined yet', 'info');
        panel.remove();
        return;
      }

      var html = '<div class="quick-tag-header">Tag ' + sel.size + ' track' + (sel.size > 1 ? 's' : '') + ' <button class="quick-tag-close" id="quick-tag-close">&times;</button></div>';
      html += '<div class="quick-tag-body">';

      keys.sort().forEach(function(key, idx) {
        var num = idx + 1;
        html += '<div class="quick-tag-row"><span class="quick-tag-key">' + (num <= 9 ? '<kbd>' + num + '</kbd> ' : '') + window.escapeHtml(key) + '</span>';
        html += '<input type="text" class="quick-tag-input" data-tag-key="' + window.escapeHtml(key) + '" placeholder="value (or empty to remove)">';
        html += '</div>';
      });

      html += '</div>';
      html += '<div class="quick-tag-footer"><button class="btn btn-primary btn-sm" id="quick-tag-apply">Apply</button><button class="btn btn-secondary btn-sm" id="quick-tag-cancel">Cancel</button></div>';

      panel.innerHTML = html;
      document.body.appendChild(panel);

      document.getElementById('quick-tag-close').addEventListener('click', function() { panel.remove(); });
      document.getElementById('quick-tag-cancel').addEventListener('click', function() { panel.remove(); });
      document.getElementById('quick-tag-apply').addEventListener('click', function() { applyQuickTags(sel, panel); panel.remove(); });

      var firstInput = panel.querySelector('.quick-tag-input');
      if (firstInput) firstInput.focus();

      // Keyboard nav: number keys focus inputs, Enter to apply, Esc to cancel
      panel.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') { panel.remove(); return; }
        if (e.key === 'Enter') { applyQuickTags(sel, panel); panel.remove(); return; }
        var num = parseInt(e.key);
        if (num >= 1 && num <= Math.min(keys.length, 9) && !e.ctrlKey && !e.metaKey) {
          var inputs = panel.querySelectorAll('.quick-tag-input');
          if (inputs[num - 1]) inputs[num - 1].focus();
        }
      });
    })
    .catch(function() {
      window.showToast && window.showToast('Could not load tags', 'error');
      panel.remove();
    });
}

function applyQuickTags(selection, panel) {
  var inputs = panel.querySelectorAll('.quick-tag-input');
  var tags = {};
  inputs.forEach(function(inp) {
    var key = inp.dataset.tagKey;
    var val = inp.value.trim();
    if (val) {
      tags[key] = val;
    } else {
      tags[key] = null;
    }
  });

  var filePaths = Array.from(selection);
  var promises = filePaths.map(function(fp) {
    return window.apiFetch('/api/tracks/' + encodeURIComponent(fp) + '/tags', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tags: tags })
    });
  });

  Promise.all(promises)
    .then(function() {
      window.showToast && window.showToast('Tags applied to ' + filePaths.length + ' track' + (filePaths.length > 1 ? 's' : ''), 'success');
      var filePathSet = new Set(filePaths);
      var tracks = store.state.tracks || [];
      for (var i = 0; i < tracks.length; i++) {
        if (filePathSet.has(tracks[i].file_path)) {
          if (!tracks[i].custom_tags) tracks[i].custom_tags = {};
          Object.keys(tags).forEach(function(k) {
            if (tags[k] === null) {
              delete tracks[i].custom_tags[k];
            } else {
              tracks[i].custom_tags[k] = tags[k];
            }
          });
        }
      }
      refreshTagsSidebar();
      if (typeof renderTracks === 'function') renderTracks();
      if (typeof updateFilterChips === 'function') updateFilterChips();
    })
    .catch(function(err) {
      window.showToast && window.showToast('Failed to apply tags', 'error');
    });
}

window.initTagsSidebar = initTagsSidebar;
window.refreshTagsSidebar = refreshTagsSidebar;
window.hasActiveTagFilters = hasActiveTagFilters;
