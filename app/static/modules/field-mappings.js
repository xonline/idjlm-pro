// ============================================================================
// Field Mappings (IDJLM 5.2) — Lexicon visual mapping pattern
// ============================================================================

const IDJLM_FIELD_CATEGORIES = [
  {
    category: 'ID3 Tag Frames',
    desc: 'Core audio metadata written to standard ID3v2 text frames',
    fields: [
      { id: 'final_genre',     label: 'Genre',           note: 'ID3 TCON' },
      { id: 'final_subgenre',  label: 'Sub-genre',       note: 'COMM subgenre frame' },
      { id: 'final_bpm',       label: 'BPM',             note: 'ID3 TBPM' },
      { id: 'final_key',       label: 'Key (Camelot)',   note: 'ID3 TKEY + INITIALKEY' },
      { id: 'initial_key',     label: 'Initial Key',     note: 'TXXX:INITIALKEY for Rekordbox/Serato' },
      { id: 'final_year',      label: 'Year',            note: 'ID3 TDRC' },
    ],
  },
  {
    category: 'Latin Analysis',
    desc: 'Latin-music specific metadata from AI analysis pipeline',
    fields: [
      { id: 'analyzed_energy', label: 'Energy (1-10)',   note: 'AI-computed energy level' },
      { id: 'clave_pattern',   label: 'Clave Pattern',   note: '2-3 or 3-2' },
      { id: 'vocal_flag',      label: 'Vocal / Instr.',  note: 'vocal or instrumental' },
      { id: 'tempo_category',  label: 'Tempo Category',  note: 'slow / medium / fast' },
    ],
  },
  {
    category: 'Custom Tags & Assets',
    desc: 'User-defined metadata and embedded media',
    fields: [
      { id: 'custom_tags',     label: 'Custom Tags',     note: 'User-defined TXXX frames' },
      { id: 'album_art',       label: 'Album Art',       note: 'APIC embedded image' },
    ],
  },
  {
    category: 'Display Metadata',
    desc: 'Track identification fields for M3U/CSV export',
    fields: [
      { id: 'display_title',   label: 'Title' },
      { id: 'display_artist',  label: 'Artist' },
      { id: 'album',           label: 'Album' },
      { id: 'comment',         label: 'Comment' },
      { id: 'confidence',      label: 'AI Confidence' },
      { id: 'filename',        label: 'File Path' },
    ],
  },
];

var TARGET_FIELD_SETS = {
  rekordbox: [
    { value: 'TCON',  label: 'TCON (Genre)' },
    { value: 'TIT2',  label: 'TIT2 (Title)' },
    { value: 'TPE1',  label: 'TPE1 (Artist)' },
    { value: 'TALB',  label: 'TALB (Album)' },
    { value: 'TBPM',  label: 'TBPM (BPM)' },
    { value: 'TKEY',  label: 'TKEY (Key)' },
    { value: 'TDRC',  label: 'TDRC (Year)' },
    { value: 'TCOM',  label: 'TCOM (Composer)' },
    { value: 'TLAN',  label: 'TLAN (Language)' },
    { value: 'TPUB',  label: 'TPUB (Publisher)' },
    { value: 'WOAR',  label: 'WOAR (Artist URL)' },
    { value: 'COMM:subgenre:eng',           label: 'COMM:subgenre' },
    { value: 'COMM:energy:eng',             label: 'COMM:energy' },
    { value: 'COMM:clave:eng',              label: 'COMM:clave' },
    { value: 'COMM:vocal_flag:eng',         label: 'COMM:vocal' },
    { value: 'COMM:tempo_category:eng',     label: 'COMM:tempo' },
    { value: 'TXXX:INITIALKEY',             label: 'TXXX:INITIALKEY' },
    { value: 'TXXX',           label: 'TXXX (Custom)' },
    { value: 'APIC',           label: 'APIC (Art)' },
  ],
  serato: [
    { value: 'TCON',  label: 'TCON (Genre)' },
    { value: 'TIT2',  label: 'TIT2 (Title)' },
    { value: 'TPE1',  label: 'TPE1 (Artist)' },
    { value: 'TALB',  label: 'TALB (Album)' },
    { value: 'TBPM',  label: 'TBPM (BPM)' },
    { value: 'TKEY',  label: 'TKEY (Key)' },
    { value: 'TDRC',  label: 'TDRC (Year)' },
    { value: 'TCOM',  label: 'TCOM (Composer)' },
    { value: 'COMM:subgenre:eng',           label: 'COMM:subgenre' },
    { value: 'COMM:energy:eng',             label: 'COMM:energy' },
    { value: 'COMM:clave:eng',              label: 'COMM:clave' },
    { value: 'COMM:vocal_flag:eng',         label: 'COMM:vocal' },
    { value: 'COMM:tempo_category:eng',     label: 'COMM:tempo' },
    { value: 'TXXX:INITIALKEY',             label: 'TXXX:INITIALKEY' },
    { value: 'TXXX',           label: 'TXXX (Custom)' },
    { value: 'APIC',           label: 'APIC (Art)' },
  ],
  m3u: [
    { value: 'title',    label: 'EXTINF title' },
    { value: 'artist',   label: 'EXTINF artist' },
    { value: 'genre',    label: 'EXTINF genre' },
    { value: 'key',      label: 'EXTINF key' },
    { value: 'bpm',      label: 'EXTINF bpm' },
    { value: 'year',     label: 'EXTINF year' },
    { value: 'energy',   label: 'EXTINF energy' },
    { value: 'comment',  label: 'EXTINF comment' },
    { value: 'path',     label: 'File Path' },
  ],
  csv: [
    { value: 'Genre',         label: 'Genre' },
    { value: 'Sub-genre',     label: 'Sub-genre' },
    { value: 'BPM',           label: 'BPM' },
    { value: 'Key',           label: 'Key' },
    { value: 'Year',          label: 'Year' },
    { value: 'Energy',        label: 'Energy' },
    { value: 'Clave',         label: 'Clave' },
    { value: 'Vocal',         label: 'Vocal' },
    { value: 'Tempo_Category', label: 'Tempo Category' },
    { value: 'Title',         label: 'Title' },
    { value: 'Artist',        label: 'Artist' },
    { value: 'Album',         label: 'Album' },
    { value: 'Comment',       label: 'Comment' },
    { value: 'Confidence',    label: 'Confidence' },
    { value: 'File_Path',     label: 'File Path' },
    { value: 'Duration',      label: 'Duration' },
  ],
};

var TARGET_LABELS = {
  rekordbox: 'Rekordbox',
  serato: 'Serato',
  m3u: 'M3U Playlist',
  csv: 'CSV Export',
};

var currentTarget = null;
var loadedMappings = {};

var CATEGORY_COLORS = {
  'ID3 Tag Frames':          'var(--accent)',
  'Latin Analysis':          '#e879f9',
  'Custom Tags & Assets':    '#facc15',
  'Display Metadata':        'var(--text-secondary)',
};

function renderCategorySection(cat, targetMappings, targetFields) {
  var color = CATEGORY_COLORS[cat.category] || 'var(--text-secondary)';

  var rows = cat.fields.map(function (field) {
    var mappedTo = targetMappings[field.id] !== undefined ? targetMappings[field.id] : null;
    return renderMappingRow(field, mappedTo, targetFields, color);
  }).join('');

  return [
    '<tr class="fm-category-header" style="--fm-cat-color:' + color + '">',
    '<td colspan="3">',
    '<div class="fm-cat-bar">',
    '<span class="fm-cat-dot" style="background:' + color + '"></span>',
    '<span class="fm-cat-name">' + escapeHtml(cat.category) + '</span>',
    '<span class="fm-cat-desc">' + escapeHtml(cat.desc) + '</span>',
    '</div>',
    '</td>',
    '</tr>',
    rows,
  ].join('');
}

function renderMappingRow(field, mappedTo, targetFields, color) {
  var currentValue = mappedTo || '';

  var options = ['<option value="">-- Skip --</option>']
    .concat(targetFields.map(function (tf) {
      var sel = tf.value === currentValue ? ' selected' : '';
      return '<option value="' + escapeHtml(tf.value) + '"' + sel + '>' + escapeHtml(tf.label) + '</option>';
    }))
    .join('');

  return [
    '<tr class="fm-row" data-field="' + escapeHtml(field.id) + '" style="--fm-cat-color:' + color + '">',
    '<td class="fm-source">',
    '<span class="fm-source-badge" style="border-color:' + color + '">' + escapeHtml(field.label) + '</span>',
    field.note ? '<span class="fm-note">' + escapeHtml(field.note) + '</span>' : '',
    '</td>',
    '<td class="fm-arrow">',
    '<svg class="fm-arrow-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="' + color + '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>',
    '</td>',
    '<td class="fm-target">',
    '<select class="fm-select" data-field-id="' + escapeHtml(field.id) + '">' + options + '</select>',
    '</td>',
    '</tr>',
  ].join('');
}

function renderMappings(target, mappings) {
  var container = document.getElementById('fm-table-body');
  if (!container) return;

  var targetFields = TARGET_FIELD_SETS[target] || [];
  var targetMappings = mappings[target] || {};

  var html = IDJLM_FIELD_CATEGORIES.map(function (cat) {
    return renderCategorySection(cat, targetMappings, targetFields);
  }).join('');

  container.innerHTML = html;
}

function updateTargetHeader(target) {
  var label = TARGET_LABELS[target] || target;
  var el = document.getElementById('fm-target-name');
  if (el) el.textContent = label;

  var desc = document.getElementById('fm-target-desc');
  if (desc) {
    var descriptions = {
      rekordbox: 'Define how IDJLM fields map to ID3 frames for Rekordbox XML export.',
      serato: 'Define how IDJLM fields map to ID3 frames for Serato .crate export.',
      m3u: 'Define which IDJLM fields appear in M3U playlist EXTINF tags.',
      csv: 'Define which IDJLM fields become CSV columns and their header names.',
    };
    desc.textContent = descriptions[target] || '';
  }

  var targetEl = document.getElementById('field-mappings-tab');
  if (targetEl) targetEl.dataset.mappingsTarget = target;
}

function collectMappings() {
  var result = {};
  var rows = document.querySelectorAll('.fm-row');
  rows.forEach(function (row) {
    var field = row.dataset.field;
    var select = row.querySelector('.fm-select');
    if (field && select && select.value) {
      result[field] = select.value;
    }
  });
  return result;
}

async function saveCurrentMappings() {
  if (!currentTarget) return;

  var mappings = collectMappings();

  try {
    var data = await apiFetch('/api/field-mappings', {
      method: 'POST',
      body: JSON.stringify({ target: currentTarget, mappings: mappings }),
    });
    if (data.saved) {
      showToast('Field mappings saved for ' + (TARGET_LABELS[currentTarget] || currentTarget), 'success');
    }
  } catch (err) {
    showToast('Failed to save field mappings', 'error');
  }
}

async function resetCurrentMappings() {
  if (!currentTarget) return;

  try {
    var data = await apiFetch('/api/field-mappings/reset', {
      method: 'POST',
      body: JSON.stringify({ target: currentTarget }),
    });
    if (data.reset) {
      await loadAndRender(currentTarget);
      showToast('Reset to ' + (TARGET_LABELS[currentTarget] || currentTarget) + ' defaults', 'info');
    }
  } catch (err) {
    showToast('Failed to reset mappings', 'error');
  }
}

async function loadAndRender(target) {
  currentTarget = target;
  updateTargetHeader(target);

  try {
    loadedMappings = await apiFetch('/api/field-mappings');
  } catch (err) {
    loadedMappings = {};
  }

  renderMappings(target, loadedMappings);

  var saveBtn = document.getElementById('btn-save-field-mappings');
  var resetBtn = document.getElementById('btn-reset-field-mappings');

  if (saveBtn) saveBtn.onclick = saveCurrentMappings;
  if (resetBtn) resetBtn.onclick = resetCurrentMappings;
}

function initFieldMappings(target) {
  target = target || 'rekordbox';
  loadAndRender(target);
}

window.initFieldMappings = initFieldMappings;
