const SYNC_TS_KEY = 'idjlm_sync_timestamps';

const TARGETS = [
  {
    id: 'rekordbox',
    name: 'Rekordbox',
    icon: 'rekordbox',
    description: 'Pioneer DJ Rekordbox XML export, library read, and database write-back',
    statusEndpoint: '/api/rekordbox/status',
    statusTransform: (data) => {
      if (data && data.found) {
        const fn = data.path ? data.path.split(/[/\\]/).pop() : '';
        return { text: fn ? 'Connected \u2014 ' + fn : 'Connected', ok: true };
      }
      return { text: 'Rekordbox not found', ok: false, warn: true };
    },
    capabilities: [
      { id: 'export-xml', label: 'XML Export', available: true },
      { id: 'read', label: 'Library Read', available: true },
      { id: 'write-back', label: 'Write Back', available: false, note: '#210 E.2' },
    ],
    exportLabel: 'Export XML',
    exportUri: '/api/export/rekordbox',
    fieldMappings: true,
  },
  {
    id: 'serato',
    name: 'Serato',
    icon: 'serato',
    description: 'Serato DJ .crate read + write \u2014 backend in progress (#210)',
    statusEndpoint: null,
    capabilities: [
      { id: 'crate-read', label: 'Crate Read', available: false, note: '#210 E.1' },
      { id: 'crate-write', label: 'Crate Write', available: false, note: '#210 E.1' },
    ],
    exportLabel: null,
    exportUri: null,
    fieldMappings: false,
  },
  {
    id: 'm3u',
    name: 'M3U Playlist',
    icon: 'm3u',
    description: 'Standard M3U playlist export for universal DJ software',
    statusEndpoint: null,
    capabilities: [
      { id: 'export-m3u', label: 'M3U Export', available: true },
    ],
    exportLabel: 'Export M3U',
    exportUri: '/api/export/m3u',
    fieldMappings: true,
  },
  {
    id: 'csv',
    name: 'CSV Export',
    icon: 'csv',
    description: 'Spreadsheet export for analysis, migration, and backup',
    statusEndpoint: null,
    capabilities: [
      { id: 'export-csv', label: 'CSV Export', available: true },
    ],
    exportLabel: 'Export CSV',
    exportUri: '/api/export/csv',
    fieldMappings: true,
  },
];

const ICON_SVG = {
  rekordbox: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="14" rx="2"/><circle cx="12" cy="11" r="3"/><path d="M12 8v1.5M12 12.5v1.5M14.5 11H13M11 11H9.5"/><path d="M7 20h10"/></svg>',
  serato: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
  m3u: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/><path d="M12 8h5M12 11h4M12 14h3"/></svg>',
  csv: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 8h10M7 12h10M7 16h7"/></svg>',
};

function loadLastSyncTimes() {
  try {
    return JSON.parse(localStorage.getItem(SYNC_TS_KEY) || '{}');
  } catch { return {}; }
}

function saveLastSyncTime(targetId) {
  const times = loadLastSyncTimes();
  times[targetId] = new Date().toISOString();
  try { localStorage.setItem(SYNC_TS_KEY, JSON.stringify(times)); } catch {}
  const el = document.getElementById('sync-value-' + targetId + '-last-sync');
  if (el) el.textContent = formatTimestamp(times[targetId]);
}

function formatTimestamp(iso) {
  if (!iso) return '\u2014\u2014';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '\u2014\u2014';
  const pad = function (n) { return String(n).padStart(2, '0'); };
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
}

function statusBadgeClass(available) {
  return available ? 'sync-status-ok' : 'sync-status-unavailable';
}

function statusBadgeLabel(available) {
  return available ? 'Ready' : 'Not yet available';
}

function renderCapTag(cap) {
  if (cap.available) {
    return '<span class="sync-cap-tag sync-cap-avail">' + cap.label + '</span>';
  }
  var note = cap.note ? ' \u2014 ' + cap.note : '';
  return '<span class="sync-cap-tag sync-cap-empty">' + cap.label + note + '</span>';
}

function renderCard(target, lastSyncTimes) {
  var id = target.id;
  var name = target.name;
  var icon = target.icon;
  var description = target.description;
  var capabilities = target.capabilities;
  var exportLabel = target.exportLabel;
  var exportUri = target.exportUri;
  var fieldMappings = target.fieldMappings;
  var lastSync = lastSyncTimes[id] || null;
  var anyAvailable = capabilities.some(function (c) { return c.available; });

  var capTags = capabilities.map(renderCapTag).join('');

  var exportHtml = exportLabel && exportUri
    ? '<a class="sync-card-export btn btn-secondary btn-sm" href="' + exportUri + '" target="_blank" rel="noopener">' + exportLabel + '</a>'
    : '';

  var mappingsHtml = fieldMappings
    ? '<div class="sync-card-action"><span class="sync-card-mappings" data-target="' + id + '">Field mappings</span></div>'
    : '';

  var statusValue = anyAvailable
    ? (target.statusEndpoint ? 'Checking...' : 'Available')
    : 'No backend';

  var statusBadgeClassVal = statusBadgeClass(anyAvailable);
  var statusBadgeLabelVal = statusBadgeLabel(anyAvailable);

  return '' +
    '<div class="sync-card" data-target="' + id + '">' +
      '<div class="sync-card-header">' +
        '<div class="sync-card-icon">' + (ICON_SVG[icon] || '') + '</div>' +
        '<div class="sync-card-title">' +
          '<span class="sync-card-name">' + name + '</span>' +
          '<span class="sync-status-badge ' + statusBadgeClassVal + '">' + statusBadgeLabelVal + '</span>' +
        '</div>' +
      '</div>' +
      '<p class="sync-card-desc">' + description + '</p>' +
      '<div class="sync-card-body">' +
        '<div class="sync-card-row" id="sync-row-' + id + '-status">' +
          '<span class="sync-card-label">Status</span>' +
          '<span class="sync-card-value" id="sync-value-' + id + '-status">' + statusValue + '</span>' +
        '</div>' +
        '<div class="sync-card-row" id="sync-row-' + id + '-last-sync">' +
          '<span class="sync-card-label">Last sync</span>' +
          '<span class="sync-card-value" id="sync-value-' + id + '-last-sync">' + formatTimestamp(lastSync) + '</span>' +
        '</div>' +
        '<div class="sync-card-caps">' + capTags + '</div>' +
      '</div>' +
      '<div class="sync-card-footer">' +
        exportHtml +
        mappingsHtml +
      '</div>' +
    '</div>';
}

function pollStatus(target) {
  var statusEl = document.getElementById('sync-value-' + target.id + '-status');
  if (!statusEl) return;

  if (!target.statusEndpoint) {
    return;
  }

  var transform = target.statusTransform || function (data) {
    return { text: 'Connected', ok: true };
  };

  apiFetch(target.statusEndpoint)
    .then(function (data) {
      var result = transform(data);
      statusEl.textContent = result.text;
      statusEl.style.color = result.ok ? 'var(--green)' : 'var(--amber)';
    })
    .catch(function () {
      statusEl.textContent = 'Unreachable';
      statusEl.style.color = 'var(--red)';
    });
}

function initSyncCenter() {
  var grid = document.getElementById('sync-center-grid');
  if (!grid) return;

  var lastSyncTimes = loadLastSyncTimes();

  grid.innerHTML = TARGETS.map(function (t) { return renderCard(t, lastSyncTimes); }).join('');

  TARGETS.forEach(pollStatus);

  grid.querySelectorAll('.sync-card-mappings').forEach(function (el) {
    el.addEventListener('click', function () {
      var target = el.dataset.target;
      initFieldMappings(target);
      switchTab('field-mappings');
    });
  });

  grid.querySelectorAll('a.sync-card-export').forEach(function (el) {
    el.addEventListener('click', function (e) {
      e.preventDefault();
      var uri = el.getAttribute('href');
      var targetId = el.closest('.sync-card')?.dataset.target;
      var win = window.open(uri, '_blank', 'noopener');
      if (!win) {
        showToast('Pop-up blocked \u2014 check your browser settings', 'warn');
      } else {
        if (targetId) saveLastSyncTime(targetId);
      }
    });
  });
}

window.initSyncCenter = initSyncCenter;
