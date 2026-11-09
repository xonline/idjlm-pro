// Primary local-first interface for the Latin classifier redesign.
window.__latinRedesignActive = true;

const latinFamilyPalette = ['Salsa', 'Bachata', 'Kizomba', 'Cha-cha', 'Boogaloo'];
const latinPages = ['library', 'review', 'categories', 'export', 'activity', 'settings'];
const latinAxisNames = { music_family: 'Genre', style: 'Style', dance_use: 'Dance use', production: 'Version', vocal_presence: 'Vocals', vocal_language: 'Language', instrument_cue: 'Instruments', my_tags: 'My tags' };
const latinState = {
  page: 'library', reviewState: 'needs_review', items: [], total: 0, nextCursor: null,
  cursors: [null], cursorIndex: 0, revision: null, filters: { query: '', family_ids: [], style_ids: [], comment_tokens: [], review_states: [] },
  sort: 'title:asc', selected: new Set(), allFiltered: false, activeItem: null, taxonomy: null,
  capabilities: {}, settings: {}, taxonomyRevision: 0, savedViews: [], jobs: [], exports: [], migrationStatus: null, pageBusy: false, initialized: false,
  lastFocus: null, selectedRoute: 'direct_cable', destination: '', exportScope: null,
};

const latin$ = id => document.getElementById(id);
const latinEscape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
const latinLabel = value => value || 'Unknown';

async function latinRequest(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail || data.error || `Request failed (${response.status})`);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

function latinAnnounce(message, kind = 'info') {
  const el = latin$('latin-announcer');
  if (!el) return;
  el.textContent = message;
  el.dataset.kind = kind;
  if (kind === 'error') window.showToast?.(message, 'error');
}

function latinQuery() {
  return new URLSearchParams({
    cursor: latinState.cursors[latinState.cursorIndex] ?? '',
    limit: '100', sort: latinState.sort, filters: JSON.stringify(latinState.filters),
  });
}

async function latinLoadLibrary({ reset = false } = {}) {
  // An import can finish while a previous read is still rendering the empty
  // inventory. Remember that refresh instead of dropping the completed job's
  // view update.
  if (latinState.pageBusy) {
    latinState.libraryReloadQueued = Boolean(latinState.libraryReloadQueued || reset);
    return;
  }
  latinState.pageBusy = true;
  const rows = latin$('latin-library-rows');
  if (rows) rows.innerHTML = '<tr><td colspan="7" class="latin-table-message">Loading tracks…</td></tr>';
  try {
    if (reset) {
      latinState.cursors = [null];
      latinState.cursorIndex = 0;
    }
    const query = latinQuery();
    const data = await latinRequest(`/api/v2/library/items?${query}`);
    latinState.items = data.items || [];
    latinState.total = Number(data.total || 0);
    latinState.nextCursor = data.next_cursor ?? null;
    latinState.revision = data.revision ?? null;
    latinRenderLibrary();
  } catch (error) {
    if (rows) rows.innerHTML = `<tr><td colspan="7" class="latin-table-message error">${latinEscape(error.message)} <button class="latin-text-button" data-retry="library">Retry</button></td></tr>`;
    latinAnnounce(`Could not load the library. ${error.message}`, 'error');
  } finally {
    latinState.pageBusy = false;
    if (latinState.libraryReloadQueued) {
      const queuedReset = latinState.libraryReloadQueued;
      latinState.libraryReloadQueued = false;
      latinLoadLibrary({ reset: queuedReset });
    }
  }
}

function latinRenderLibrary() {
  const rows = latin$('latin-library-rows');
  if (!rows) return;
  if (!latinState.items.length) {
    const migration = latinState.migrationStatus?.migration_required
      ? `<button class="latin-button quiet" data-action="bootstrap-library">Bring ${latinState.migrationStatus.legacy_track_count.toLocaleString()} existing library tracks into this view</button>`
      : '';
    rows.innerHTML = `<tr><td colspan="7" class="latin-table-message"><div class="latin-empty"><strong>${latinState.total ? 'No tracks match these filters' : 'Your library is ready for music'}</strong><span>${latinState.total ? 'Clear one or more filters to see tracks.' : 'Add a music folder to inventory it. IDJLM leaves the source files where they are.'}</span>${latinState.total ? '<button class="latin-button quiet" data-action="clear-filters">Clear filters</button>' : `<button class="latin-button primary" data-action="add-folder">＋ Add folder</button>${migration}`}</div></td></tr>`;
  } else {
    rows.innerHTML = latinState.items.map((item, index) => {
      const existing = item.existing || {};
      const proposed = item.proposed || {};
      const id = latinEscape(item.id);
      const checked = latinState.selected.has(item.id) || latinState.allFiltered;
      const selectedRow = latinState.activeItem?.id === item.id ? ' selected' : '';
      const family = latinLabelsFor(proposed.music_family || proposed.family, 'music_family').map(latinDisplayLabel).filter(Boolean).join(' · ');
      const style = latinLabelsFor(proposed.style, 'style').map(latinDisplayLabel).filter(Boolean).join(' · ');
      const proposal = [family, style].filter(Boolean).join(' · ');
      const analysis = item.analysis || {};
      const proposalMeta = proposal
        ? (item.confidence_label || 'Experimental audio proposal · review required')
        : (analysis.state && analysis.state !== 'not_analyzed'
          ? `${latinStatusText(analysis.state)}${analysis.reason ? ` · ${analysis.reason}` : ''}`
          : 'Not analyzed');
      const status = item.review_state || 'unreviewed';
      const conflict = item.conflict ? '<span class="latin-status-tag danger">Conflict</span>' : '';
      return `<tr class="latin-track-row${selectedRow}" data-item-id="${id}" tabindex="0" aria-rowindex="${index + 2}">
        <td><input type="checkbox" class="latin-row-check" aria-label="Select ${latinEscape(item.title || 'track')}" data-item-id="${id}" ${checked ? 'checked' : ''}></td>
        <td><button class="latin-track-open" data-open-item="${id}"><span class="latin-track-title">${latinEscape(item.title || 'Untitled')}</span><span class="latin-track-artist">${latinEscape(item.artist || 'Unknown artist')}</span></button></td>
        <td><span class="latin-existing-genre">${latinEscape(existing.genre || '—')}</span><span class="latin-existing-comment">${latinEscape(existing.comment || 'No comment')}</span></td>
        <td><span class="latin-proposal">${latinEscape(proposal || 'No proposal')}</span><span class="latin-proposal-meta">${latinEscape(proposalMeta)}</span></td>
        <td><span class="latin-status-tag ${latinStatusClass(status)}">${latinEscape(latinStatusText(status))}</span>${conflict}</td>
        <td class="latin-number">${latinEscape(item.bpm ?? '—')} <span>·</span> ${latinEscape(item.key ?? '—')}</td>
        <td><button class="latin-icon-button" data-open-item="${id}" aria-label="Inspect ${latinEscape(item.title || 'track')}">›</button></td>
      </tr>`;
    }).join('');
  }
  const start = latinState.total ? latinState.cursorIndex * 100 + 1 : 0;
  const end = Math.min(latinState.cursorIndex * 100 + latinState.items.length, latinState.total);
  latin$('latin-result-count').textContent = `${start.toLocaleString()}–${end.toLocaleString()} of ${latinState.total.toLocaleString()} tracks`;
  latin$('latin-nav-library-count').textContent = latinState.total.toLocaleString();
  latin$('latin-page-prev').disabled = latinState.cursorIndex === 0;
  latin$('latin-page-next').disabled = !latinState.nextCursor;
  latinRenderSelection();
  latinRenderSummary();
}

async function latinLoadMigrationStatus() {
  try {
    latinState.migrationStatus = await latinRequest('/api/v2/library/migration-status');
    if (!latinState.total && !latinState.items.length) latinRenderLibrary();
  } catch (_) { /* The primary library remains usable when no legacy store exists. */ }
}

function latinBootstrapLibrary() {
  const count = Number(latinState.migrationStatus?.legacy_track_count || 0);
  if (!count) return;
  latinOpenModal({ kicker: 'EXISTING LIBRARY', title: `Bring ${count.toLocaleString()} tracks into this view`, body: '<p>This adds the existing local library to the redesigned inventory. It does not scan folders, change files, alter raw Genre or Comment values, or replace redesign decisions.</p><p>Only legacy tracks previously approved or edited by a person are carried forward as locked human decisions. Pending suggestions remain evidence only.</p>', buttons: [
    { label: 'Cancel', kind: 'quiet', close: true },
    { label: 'Bring existing library in', kind: 'primary', action: async () => {
      const result = await latinRequest('/api/v2/library/bootstrap', { method: 'POST', body: JSON.stringify({}) });
      latinCloseModal();
      await latinLoadMigrationStatus();
      await latinLoadTaxonomy();
      await latinLoadLibrary({ reset: true });
      latinAnnounce(`${Number(result.count || 0).toLocaleString()} existing tracks are available in Library.`);
    } },
  ] });
}

function latinStatusClass(value) {
  const status = String(value || '').toLowerCase();
  if (status.includes('ready') || status.includes('accepted') || status.includes('verified')) return 'success';
  if (status.includes('fail') || status.includes('conflict')) return 'danger';
  if (status.includes('review') || status.includes('pending') || status.includes('unknown')) return 'warning';
  return 'neutral';
}

function latinStatusText(value) {
  const names = { needs_review: 'Needs review', ready: 'Ready', auto_ready: 'Ready', preserved: 'Preserved', corrected: 'Corrected', write_failed: 'Write failed', not_analyzed: 'Not analyzed', proposed: 'Proposal available', abstained: 'No reliable proposal', unsupported: 'Not supported', vocabulary_only: 'Vocabulary only', completed_with_errors: 'Completed with errors', missing_media: 'Missing media', unsupported_format: 'Unsupported format', queued: 'Queued', running: 'Running', paused: 'Paused', interrupted: 'Interrupted', failed: 'Failed', cancelled: 'Cancelled', completed: 'Completed' };
  return names[value] || String(value ?? 'Unknown').replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());
}

function latinRenderSummary() {
  const el = latin$('latin-library-summary');
  if (!el) return;
  el.innerHTML = `<div class="latin-summary-card"><span>IN THIS LIBRARY</span><strong>${latinState.total.toLocaleString()}</strong><small>Tracks indexed</small></div><div class="latin-summary-card"><span>VISIBLE PAGE</span><strong>${latinState.items.length.toLocaleString()}</strong><small>Tracks loaded now</small></div><div class="latin-summary-card"><span>SELECTION</span><strong>${latinState.allFiltered ? latinState.total.toLocaleString() : latinState.selected.size.toLocaleString()}</strong><small>${latinState.allFiltered ? 'All matching filters' : 'Tracks selected'}</small></div>`;
}

function latinRenderSelection() {
  const bar = latin$('latin-selection-bar');
  const count = latinState.allFiltered ? latinState.total : latinState.selected.size;
  bar.hidden = false;
  latin$('latin-selected-count').textContent = latinState.allFiltered ? `All ${count.toLocaleString()} filtered tracks selected` : `${count.toLocaleString()} selected`;
  latin$('latin-select-all-filtered').hidden = latinState.allFiltered || !latinState.total;
  latin$('latin-select-visible').hidden = !latinState.items.length;
  latin$('latin-batch-edit').disabled = !(latinState.selected.size || latinState.allFiltered);
  latin$('latin-batch-catalogue').disabled = !(latinState.selected.size || latinState.allFiltered);
  latin$('latin-batch-review').disabled = !latinState.selected.size || latinState.allFiltered;
  latin$('latin-batch-classify').disabled = !count || latinState.model?.state !== 'installed';
  latin$('latin-batch-export').disabled = !count;
  const rbar = latin$('latin-review-selection-bar');
  if (rbar) {
    rbar.hidden = !latinState.selected.size;
    latin$('latin-review-selected-count').textContent = `${latinState.selected.size} tracks selected`;
  }
}

function latinFiltersChanged() {
  latinState.filters.query = latin$('latin-search').value.trim();
  latinState.cursors = [null];
  latinState.cursorIndex = 0;
  latinState.allFiltered = false;
  latinRenderChips();
  latinPersistView();
  latinLoadLibrary({ reset: true });
}

function latinAdaptFiltersToViewport() {
  const area = latin$('latin-filter-area');
  const toggle = latin$('latin-filter-toggle');
  if (!area || !toggle || window.innerWidth > 1100 || latinState.filtersExpandedByUser) return;
  area.hidden = true;
  toggle.setAttribute('aria-expanded', 'false');
}

function latinRenderChips() {
  const families = latin$('latin-family-chips');
  const styles = latin$('latin-style-chips');
  const comments = latin$('latin-comment-chips');
  if (!families || !styles || !comments) return;
  const familiesSelected = latinState.filters.family_ids || [];
  const stylesSelected = latinState.filters.style_ids || [];
  const commentsSelected = latinState.filters.comment_tokens || [];
  families.innerHTML = latinFamilyPalette.map(label => `<button class="latin-chip ${familiesSelected.includes(label.toLowerCase()) ? 'active' : ''}" aria-pressed="${familiesSelected.includes(label.toLowerCase())}" data-family="${latinEscape(label.toLowerCase())}">${latinEscape(label)}</button>`).join('');
  const availableStyles = (latinState.taxonomy?.labels || []).filter(label => label.axis === 'style' && (!familiesSelected.length || familiesSelected.some(family => label.id.startsWith(`${family}_`) || (family === 'salsa' && label.id === 'timba'))));
  styles.innerHTML = availableStyles.length ? availableStyles.map(label => `<button class="latin-chip ${stylesSelected.includes(label.id) ? 'active' : ''}" aria-pressed="${stylesSelected.includes(label.id)}" data-style="${latinEscape(label.id)}">${latinEscape(label.display_name)}</button>`).join('') : '<span class="latin-chip-hint">Load Categories to show available style labels. Vocabulary does not prove model support.</span>';
  const palette = latinState.taxonomy?.palette?.raw_comment_tokens || [];
  comments.innerHTML = palette.map(label => `<button class="latin-chip ${commentsSelected.includes(label) ? 'active' : ''}" aria-pressed="${commentsSelected.includes(label)}" data-comment="${latinEscape(label)}">${latinEscape(label)}</button>`).join('');
  if (!palette.length) comments.innerHTML = '<span class="latin-chip-hint">Choose Salsa or import literal tag vocabulary. Values filter comments; they do not label audio.</span>';
  const active = [];
  familiesSelected.forEach(label => active.push({ type: 'family', value: label }));
  stylesSelected.forEach(label => active.push({ type: 'style', value: label }));
  commentsSelected.forEach(label => active.push({ type: 'comment', value: label }));
  latin$('latin-active-filters').innerHTML = active.map(chip => `<button class="latin-active-chip" data-clear-${chip.type}="${latinEscape(chip.value)}">${latinEscape(chip.value)} <span aria-hidden="true">×</span></button>`).join('');
}

function latinPersistView() {
  localStorage.setItem('idjlm-latin-view-v1', JSON.stringify({ filters: latinState.filters, sort: latinState.sort, page: latinState.cursorIndex }));
}

function latinLoadSavedViewState() {
  try {
    const saved = JSON.parse(localStorage.getItem('idjlm-latin-view-v1') || '{}');
    if (saved.filters) latinState.filters = { ...latinState.filters, ...saved.filters };
    if (saved.sort) latinState.sort = saved.sort;
  } catch (_) { /* Ignore an invalid local view and keep defaults. */ }
}

function latinRenderSavedViews() {
  const select = latin$('latin-saved-view-select');
  const saved = latinState.savedViews;
  select.innerHTML = '<option value="">Saved views</option>' + saved.map((view, index) => `<option value="${index}">${latinEscape(view.name)}</option>`).join('');
}

async function latinLoadSavedViews() {
  try {
    const data = await latinRequest('/api/v2/views');
    latinState.savedViews = data.views || [];
  } catch (_) {
    try { latinState.savedViews = JSON.parse(localStorage.getItem('idjlm-latin-saved-views-v1') || '[]'); }
    catch (_) { latinState.savedViews = []; }
  }
  latinRenderSavedViews();
}

async function latinSaveViewRecord(name) {
  const definition = { filters: structuredClone(latinState.filters), sort: latinState.sort, columns: ['title', 'existing', 'proposed', 'status', 'bpm_key'] };
  try {
    const result = await latinRequest('/api/v2/views', { method: 'PUT', body: JSON.stringify({ name, definition }) });
    latinState.savedViews.push(result.view || result);
  } catch (error) {
    if (error.status !== 404 && error.status !== 405) throw error;
    const views = JSON.parse(localStorage.getItem('idjlm-latin-saved-views-v1') || '[]');
    views.push({ name, definition });
    localStorage.setItem('idjlm-latin-saved-views-v1', JSON.stringify(views));
    latinState.savedViews = views;
  }
}

function latinSaveView() {
  return latinOpenModal({
    kicker: 'SAVE VIEW', title: 'Name this filtered view',
    body: '<label class="latin-field-label" for="latin-new-view-name">View name</label><input id="latin-new-view-name" class="latin-input" maxlength="60" placeholder="e.g. Salsa romantica, high energy">',
    buttons: [{ label: 'Cancel', kind: 'quiet', close: true }, { label: 'Save view', kind: 'primary', action: async () => {
      const name = latin$('latin-new-view-name').value.trim();
      if (!name) throw new Error('Enter a view name.');
      await latinSaveViewRecord(name);
      latinRenderSavedViews(); latinCloseModal(); latinAnnounce(`Saved view ${name}.`);
    } }],
  });
}

function latinRenderReview() {
  const body = latin$('latin-review-rows');
  if (!body) return;
  const requestId = (latinState.reviewRequestId || 0) + 1;
  latinState.reviewRequestId = requestId;
  const reviewFilters = { ...latinState.filters, review_states: [latinState.reviewState] };
  if (latinState.reviewState === 'conflict') reviewFilters.has_conflict = true;
  else delete reviewFilters.has_conflict;
  const query = new URLSearchParams({ cursor: latinState.cursors[latinState.cursorIndex] ?? '', limit: '100', sort: latinState.sort, filters: JSON.stringify(reviewFilters) });
  body.innerHTML = '<tr><td colspan="8" class="latin-table-message">Loading review queue…</td></tr>';
  latinRequest(`/api/v2/library/items?${query}`).then(data => {
    if (requestId !== latinState.reviewRequestId) return;
    latinState.items = data.items || []; latinState.total = Number(data.total || 0); latinState.nextCursor = data.next_cursor ?? null; latinState.revision = data.revision ?? null;
    if (!latinState.items.length) {
      body.innerHTML = `<tr><td colspan="8" class="latin-table-message"><div class="latin-empty"><strong>${latinState.total ? 'No tracks on this page' : 'Nothing in this review group'}</strong><span>${latinState.total ? 'Use the page controls to continue.' : 'Preserved existing tags and unsupported styles are counted separately.'}</span></div></td></tr>`;
    } else {
      body.innerHTML = latinState.items.map(item => { const family = latinLabelsFor(item.axes?.music_family?.proposal || item.proposed?.music_family, 'music_family').map(latinDisplayLabel); const style = latinLabelsFor(item.axes?.style?.proposal || item.proposed?.style, 'style').map(latinDisplayLabel); const hasProposal = family.length || style.length; return `<tr data-item-id="${latinEscape(item.id)}"><td><input type="checkbox" class="latin-review-check" data-item-id="${latinEscape(item.id)}" ${latinState.selected.has(item.id) ? 'checked' : ''} aria-label="Select ${latinEscape(item.title)}"></td><td><button class="latin-track-open" data-open-item="${latinEscape(item.id)}"><span class="latin-track-title">${latinEscape(item.title)}</span><span class="latin-track-artist">${latinEscape(item.artist)}</span></button></td><td>${latinEscape(item.existing?.genre || '—')}<small class="latin-existing-comment">${latinEscape(item.existing?.comment || '—')}</small></td><td>${latinEscape(family.join(' · ') || '—')}</td><td>${latinEscape(style.join(' · ') || '—')}</td><td>${latinEscape(latinStatusText(item.review_state || 'needs_review'))}</td><td><button class="latin-text-button" data-decision="accept" data-item-id="${latinEscape(item.id)}" ${hasProposal ? '' : 'disabled'}>Accept</button><button class="latin-text-button" data-decision="correct" data-item-id="${latinEscape(item.id)}">Correct</button></td><td><button class="latin-icon-button" data-open-item="${latinEscape(item.id)}" aria-label="Inspect ${latinEscape(item.title)}">›</button></td></tr>`; }).join('');
    }
    latin$('latin-review-result-count').textContent = `${latinState.total.toLocaleString()} tracks`;
    latin$('latin-review-prev').disabled = latinState.cursorIndex === 0;
    latin$('latin-review-next').disabled = !latinState.nextCursor;
    latin$('latin-nav-review-count').textContent = latinState.reviewState === 'needs_review' ? latinState.total.toLocaleString() : '•';
    latinRenderSelection();
  }).catch(error => {
    if (requestId !== latinState.reviewRequestId) return;
    body.innerHTML = `<tr><td colspan="8" class="latin-table-message error">${latinEscape(error.message)} <button class="latin-text-button" data-retry="review">Retry</button></td></tr>`;
    latinAnnounce(`Could not load the review queue. ${error.message}`, 'error');
  });
}

async function latinOpenReviewPreview(itemIds, action = 'accept', corrections = {}) {
  if (!itemIds.length) return latinAnnounce('Select one or more visible tracks first.', 'error');
  try {
    const preview = await latinRequest('/api/v2/reviews/previews', { method: 'POST', body: JSON.stringify({ scope: { item_ids: itemIds, selection: 'explicit' }, fields: ['music_family', 'style'] }) });
    const allItems = preview.items || [];
    const rows = allItems.slice(0, 100).map(item => {
      const axes = item.axes || {};
      const value = axis => {
        const values = corrections[item.item_id]?.[axis] || latinLabelsFor(axes[axis]?.proposal || axes[axis]?.decision || axes[axis], axis);
        return values.map(latinDisplayLabel).join(' · ') || 'No proposal';
      };
      return `<tr><td>${latinEscape(latinState.items.find(row => row.id === item.item_id)?.title || 'Track')}</td><td>${latinEscape(latinFormatValue(item.before))}</td><td>Genre: ${latinEscape(value('music_family'))}<br>Style: ${latinEscape(value('style'))}</td><td>${['music_family','style'].filter(axis => axes[axis]?.decision?.locked).map(latinAxisLabel).join(', ') || 'None'}</td></tr>`;
    }).join('');
    const acceptable = action === 'correct' || allItems.some(item => ['music_family','style'].some(axis => (corrections[item.item_id]?.[axis] || latinLabelsFor(item.axes?.[axis]?.proposal, axis)).length));
    latinOpenModal({ kicker: 'REVIEW FIELD CHANGES', title: `Review ${allItems.length || itemIds.length} tracks`, body: `<p>Acceptance records your decision. It does not train the model or write tags.</p>${allItems.length > 100 ? `<p>Showing 100 of ${allItems.length.toLocaleString()} tracks. The decision applies to the complete frozen selection.</p>` : ''}<div class="latin-diff-wrap"><table class="latin-diff"><thead><tr><th>TRACK</th><th>EXISTING</th><th>PROPOSED</th><th>LOCKED FIELDS</th></tr></thead><tbody>${rows}</tbody></table></div>`, buttons: [
      { label: 'Cancel', kind: 'quiet', close: true },
      { label: action === 'correct' ? 'Save correction' : 'Accept proposals', kind: 'primary', disabled: !acceptable, action: async () => {
        const decisions = allItems.flatMap(item => ['music_family', 'style'].filter(axis => action === 'correct' || (corrections[item.item_id]?.[axis] || latinLabelsFor(item.axes?.[axis]?.proposal, axis)).length).map(axis => ({
          item_id: item.item_id, axis, action,
          label_ids: corrections[item.item_id]?.[axis] || latinLabelsFor(item.axes?.[axis]?.proposal || item.axes?.[axis]?.decision || item.axes?.[axis], axis),
        })));
        await latinRequest('/api/v2/reviews/decisions', { method: 'POST', body: JSON.stringify({ preview_id: preview.preview_id, decisions }) });
        latinCloseModal(); latinState.selected.clear(); latinRenderSelection(); latinAnnounce('Review decisions saved. No files were written.'); latinLoadLibrary({ reset: true }); latinRenderReview();
      } },
    ] });
  } catch (error) { latinAnnounce(`Could not prepare the review diff. ${error.message}`, 'error'); }
}

function latinLabelsFor(proposed, axis) {
  if (proposed?.label_ids) return proposed.label_ids;
  if (proposed?.labels) return proposed.labels.map(item => typeof item === 'string' ? item : item.id || item.label_id).filter(Boolean);
  const value = proposed?.[axis];
  if (Array.isArray(value)) return value.map(item => typeof item === 'string' ? item : item.id || item.label_id).filter(Boolean);
  if (value && typeof value === 'object') return value.label_ids || (value.label_id ? [value.label_id] : []);
  return value ? [value] : [];
}

function latinDisplayLabel(id) {
  return latinState.taxonomy?.labels?.find(label => label.id === id)?.display_name || String(id || '').replaceAll('_', ' ');
}

async function latinOpenCorrection(itemId) {
  try {
    if (!latinState.taxonomy) await latinLoadTaxonomy();
    const item = latinState.items.find(row => row.id === itemId) || await latinRequest(`/api/v2/items/${encodeURIComponent(itemId)}`);
    const familyOptions = (latinState.taxonomy?.labels || []).filter(label => label.axis === 'music_family');
    const styleOptions = (latinState.taxonomy?.labels || []).filter(label => label.axis === 'style');
    const selected = axis => latinLabelsFor(item.proposed?.[axis] || latinEffectiveAxis(item, axis), axis);
    const checks = (id, axis, options) => options.map(label => `<label class="latin-check-option"><input type="checkbox" name="${id}" value="${latinEscape(label.id)}" ${selected(axis).includes(label.id) ? 'checked' : ''}><span>${latinEscape(label.display_name)}</span></label>`).join('') || '<p class="latin-muted">No vocabulary has been added for this field.</p>';
    latinOpenModal({ kicker: 'HUMAN CORRECTION', title: `Correct ${item.title || 'track'}`, body: `<fieldset class="latin-choice-group"><legend>Genre</legend>${checks('latin-correct-family','music_family',familyOptions)}</fieldset><fieldset class="latin-choice-group"><legend>Style</legend>${checks('latin-correct-style','style',styleOptions)}</fieldset><p>A correction records your explicit choice and locks only the fields you save. It does not write audio tags.</p>`, buttons: [
      { label: 'Cancel', kind: 'quiet', close: true },
      { label: 'Preview correction', kind: 'primary', action: async () => {
        const familyLabels = [...document.querySelectorAll('input[name="latin-correct-family"]:checked')].map(input => input.value);
        const styleLabels = [...document.querySelectorAll('input[name="latin-correct-style"]:checked')].map(input => input.value);
        const corrections = { [itemId]: { music_family: familyLabels, style: styleLabels } };
        latinCloseModal();
        await latinOpenReviewPreview([itemId], 'correct', corrections);
      } },
    ] });
  } catch (error) { latinAnnounce(`Could not open correction form. ${error.message}`, 'error'); }
}

async function latinChangeLock(item, axis, action) {
  try {
    const preview = await latinRequest('/api/v2/reviews/previews', { method: 'POST', body: JSON.stringify({ scope: { item_ids: [item.id], selection: 'explicit' }, fields: [axis] }) });
    const axisData = preview.items?.[0]?.axes?.[axis] || {};
    await latinRequest('/api/v2/reviews/decisions', { method: 'POST', body: JSON.stringify({ preview_id: preview.preview_id, decisions: [{ item_id: item.id, axis, action, label_ids: latinLabelsFor(axisData.decision || axisData.proposal, axis) }] }) });
    latinAnnounce(action === 'lock' ? `${latinAxisLabel(axis)} locked.` : `${latinAxisLabel(axis)} unlocked.`);
    await latinOpenItem(item.id);
  } catch (error) { latinAnnounce(`Could not update field lock. ${error.message}`, 'error'); }
}

function latinFormatValue(value) {
  if (value == null || value === '') return '—';
  if (typeof value === 'object') return Object.values(value).flat().filter(Boolean).join(' · ') || '—';
  return String(value);
}

async function latinOpenItem(id) {
  latinState.lastFocus = document.activeElement;
  const requestId = (latinState.drawerRequestId || 0) + 1;
  latinState.drawerRequestId = requestId;
  try {
    const details = await latinRequest(`/api/v2/items/${encodeURIComponent(id)}`);
    if (requestId !== latinState.drawerRequestId) return;
    const item = { ...latinState.items.find(row => row.id === id), ...details };
    latinState.activeItem = item;
    latinRenderLibrary();
    latinRenderDrawer(item);
    latin$('latin-drawer-overlay').hidden = false;
    latin$('latin-track-drawer').hidden = false;
    document.body.classList.add('latin-drawer-open');
    latin$('latin-drawer-close').focus();
  } catch (error) { if (requestId === latinState.drawerRequestId) latinAnnounce(`Could not load track details. ${error.message}`, 'error'); }
}

function latinRenderDrawer(item) {
  const original = item.original || item.existing || {};
  const proposed = item.proposed || {};
  const axes = item.axes || {};
  const decisions = item.decisions || Object.entries(axes).flatMap(([axis, value]) => value.decision ? [{ axis, ...value.decision }] : []);
  const evidence = item.evidence || item.predictions || [];
  const audioUrl = item.audio_url || '';
  latin$('latin-drawer-title').textContent = item.title || 'Track details';
  const lockedAxes = new Set(item.locked_axes || [...Object.entries(item.axes || {}).filter(([, value]) => value.decision?.locked).map(([axis]) => axis), ...decisions.filter(decision => decision.locked).map(decision => decision.axis)]);
  const originalGenre = original.genre || original.existing_genre;
  const originalComment = original.comment || original.existing_comment || original.raw_comment;
  const catalogueDecision = axes.custom_tag?.decision;
  const currentCatalogueIds = latinLabelsFor(catalogueDecision, 'custom_tag');
  const labels = latinState.taxonomy?.labels || [];
  const displayForId = id => labels.find(label => label.id === id)?.display_name || id;
  const catalogueValues = [...new Set([...(latinState.taxonomy?.palette?.raw_comment_tokens || []), ...currentCatalogueIds.map(displayForId)])];
  const catalogueChoices = catalogueValues.map(value => {
    const id = labels.find(label => label.axis === 'custom_tag' && label.display_name === value)?.id || '';
    return `<label class="latin-check-option"><input type="checkbox" name="latin-drawer-catalogue-tag" value="${latinEscape(value)}" data-current-tag-id="${latinEscape(currentCatalogueIds.includes(id) ? id : '')}" ${currentCatalogueIds.includes(id) ? 'checked' : ''}><span>${latinEscape(value)}</span></label>`;
  }).join('');
  latin$('latin-drawer-body').innerHTML = `
    <div class="latin-drawer-track"><strong>${latinEscape(item.title || 'Untitled')}</strong><span>${latinEscape(item.artist || 'Unknown artist')}</span><small>${latinEscape(item.album || '')}</small></div>
    <div class="latin-drawer-section"><h3>Original tags</h3><label class="latin-field-label">Genre</label><div class="latin-source-value">${latinEscape(originalGenre || '—')}</div><label class="latin-field-label">Comment · kept literally</label><div class="latin-source-value">${latinEscape(originalComment || '—')}</div></div>
    <div class="latin-drawer-section"><h3>Proposed labels</h3>${['music_family','style','dance_use','production','vocal_presence','vocal_language','instrument_cue'].map(axis => { const result = axes[axis] || {}; const proposal = result.proposal || proposed[axis]; const ids = latinLabelsFor(proposal, axis); return `<div class="latin-axis-row"><span>${latinEscape(latinAxisLabel(axis))}</span><strong>${latinEscape(ids.map(latinDisplayLabel).join(' · ') || 'No proposal')}</strong><small>${latinEscape(latinEvidenceForAxis(result, evidence, axis))}</small>${latinEvidenceButtons(result)}</div>`; }).join('')}</div>
    <div class="latin-drawer-section"><h3>Human decisions</h3>${decisions.length ? decisions.map(d => `<div class="latin-axis-row"><span>${latinEscape(latinAxisLabel(d.axis))}</span><strong>${latinEscape(latinLabelsFor(d, d.axis).map(latinDisplayLabel).join(' · ') || 'Cleared / unknown')}</strong><small>${d.locked ? 'Locked field' : latinEscape(d.source || d.action || 'Saved decision')}</small></div>`).join('') : '<p class="latin-muted">No human decisions yet.</p>'}</div>
    <div class="latin-drawer-section"><h3>Catalogue tags</h3><p class="latin-muted">Literal tags are separate from source metadata and can be exported or written later from a checked preview.</p><div class="latin-chips latin-edit-token-list">${catalogueChoices || '<span class="latin-muted">No literal palette is available yet.</span>'}</div><label class="latin-field-label" for="latin-drawer-catalogue-custom">Exact custom tag</label><input id="latin-drawer-catalogue-custom" class="latin-input full" maxlength="80" placeholder="Commas stay part of this one tag"><div class="latin-drawer-actions"><button class="latin-button quiet" data-drawer-save-tags="${latinEscape(item.id)}">Save tags</button><button class="latin-button primary" data-drawer-save-tags-next="${latinEscape(item.id)}">Save & next <kbd>Ctrl↵</kbd></button></div></div>
    <div class="latin-drawer-section"><h3>Evidence & diagnostics</h3><p>${latinEscape(Object.values(axes).map(value => value.proposal?.model_id || value.proposal?.model_version).find(Boolean) || item.model_version || 'No model evidence')}</p><p>${latinEscape(item.taxonomy_version ? `Categories ${item.taxonomy_version}` : 'Category version unavailable')}</p><p>${latinEscape(item.analysis?.state ? `${latinStatusText(item.analysis.state)}${item.analysis.reason ? ` · ${item.analysis.reason}` : ''}` : 'No audio analysis has run')}</p><p>${latinEscape(latinStatusText(item.review_state || 'Not reviewed'))} · ${latinEscape(latinStatusText(item.write_state || 'Not written'))}</p><p>${item.audio_available ? 'Audio available on this Mac' : 'Audio unavailable'}</p></div>
    <div class="latin-drawer-actions"><button class="latin-button primary" data-drawer-play="${latinEscape(audioUrl)}" ${audioUrl ? '' : 'disabled'}>▶ Play track</button><button class="latin-button quiet" data-drawer-review="${latinEscape(item.id)}">Review changes</button></div>`;
}

async function latinSaveDrawerCatalogueTags(itemId, next = false) {
  const currentIds = [...document.querySelectorAll('input[name="latin-drawer-catalogue-tag"][data-current-tag-id]')].map(input => input.dataset.currentTagId).filter(Boolean);
  const selected = [...document.querySelectorAll('input[name="latin-drawer-catalogue-tag"]:checked')].map(input => input.value);
  const custom = latin$('latin-drawer-catalogue-custom')?.value.trim();
  if (custom) selected.push(custom);
  const currentValueIds = await latinRegisterPersonalTags(selected);
  const selectedIds = new Set(currentValueIds.values());
  const additions = selected.filter(value => !currentIds.includes(currentValueIds.get(value)));
  const removed = currentIds.filter(id => !selectedIds.has(id));
  const changed = additions.length || removed.length ? await latinSaveCatalogueTags({ item_ids: [itemId], selection: 'explicit' }, { addValues: additions, removeIds: removed }) : 0;
  latinAnnounce(changed ? `Saved catalogue tags for ${changed} track. No files were changed.` : 'Catalogue tags are already saved.');
  const currentIndex = latinState.items.findIndex(item => item.id === itemId);
  const targetId = next ? latinState.items[currentIndex + 1]?.id || latinState.items[0]?.id : itemId;
  await latinLoadLibrary();
  if (targetId) await latinOpenItem(targetId);
}

function latinEvidenceForAxis(result, evidence, axis) {
  const proposal = result?.proposal || {};
  const found = evidence.find(entry => entry.axis === axis) || proposal;
  if (!found.model_id && !found.model_version && found.raw_score == null && !found.reason && !found.details) return 'No measured evidence';
  const score = found.calibrated_band ? `Calibrated ${found.calibrated_band}` : found.raw_score != null ? `Raw model score ${Number(found.raw_score).toFixed(3)}` : 'Score not calibrated';
  return [score, found.reason || found.uncertainty_reason, found.model_id || found.model_version].filter(Boolean).join(' · ');
}

function latinEvidenceButtons(result) {
  const candidates = result?.proposal?.details?.candidates || result?.proposal?.candidates || [];
  if (!candidates.length) return '';
  const rows = candidates.slice(0, 3).map(candidate => {
    const start = Number(candidate.start_seconds ?? candidate.start_s ?? candidate.offset_seconds ?? (candidate.start_ms != null ? Number(candidate.start_ms) / 1000 : NaN));
    const hasTime = Number.isFinite(start);
    return `<span class="latin-evidence-candidate">${latinEscape(candidate.display_name || candidate.label || candidate.label_id || 'Candidate')}${candidate.score != null ? ` · ${latinEscape(Number(candidate.score).toFixed(3))}` : ''}${hasTime ? ` <button class="latin-text-button" data-audition-at="${start}" aria-label="Play evidence at ${start} seconds">Play section</button>` : ''}</span>`;
  }).join('');
  return `<div class="latin-evidence-candidates" aria-label="Top candidates">${rows}</div>`;
}

function latinAxisLabel(axis) {
  return latinAxisNames[axis] || axis.replaceAll('_', ' ');
}

function latinEffectiveAxis(item, axis) {
  const value = item.axes?.[axis];
  return value?.decision || value?.proposal || value || null;
}

function latinPlayItem(item) {
  const url = item.audio_url;
  if (!url) return latinAnnounce('Audio playback is unavailable for this track.', 'error');
  const audio = latin$('audio-player');
  const parsedUrl = new URL(url, window.location.origin);
  if (parsedUrl.origin !== window.location.origin) return latinAnnounce('The audio source was rejected because it is not local.', 'error');
  audio.src = parsedUrl.pathname + parsedUrl.search;
  latin$('audio-track-title').textContent = item.title || 'Untitled';
  latin$('audio-track-artist').textContent = item.artist || 'Unknown artist';
  latin$('audio-player-bar').classList.remove('hidden');
  audio.load();
  audio.play().then(() => { latin$('icon-play').style.display = 'none'; latin$('icon-pause').style.display = 'block'; })
    .catch(() => latinAnnounce('Could not play this track. Check that the file is still available.', 'error'));
}

function latinPlayAt(seconds) {
  const item = latinState.activeItem;
  if (!item?.audio_url || !Number.isFinite(seconds) || seconds < 0) return;
  latinPlayItem(item);
  const audio = latin$('audio-player');
  const seek = () => { audio.currentTime = Math.min(seconds, Number.isFinite(audio.duration) ? audio.duration : seconds); audio.removeEventListener('loadedmetadata', seek); };
  if (audio.readyState >= 1) seek(); else audio.addEventListener('loadedmetadata', seek, { once: true });
}

function latinCloseDrawer() {
  latinState.drawerRequestId = (latinState.drawerRequestId || 0) + 1;
  latin$('latin-track-drawer').hidden = true;
  latin$('latin-drawer-overlay').hidden = true;
  document.body.classList.remove('latin-drawer-open');
  latinState.activeItem = null;
  latinState.lastFocus?.focus?.();
  latinRenderLibrary();
}

async function latinStartJob(kind, scope = undefined) {
  if (kind === 'classify' && latinState.model?.state !== 'installed') {
    return latinAnnounce(latinState.model?.state === 'runtime_unavailable' ? 'Local audio analysis is unavailable because this installation does not include the audio runtime.' : 'Set up the local model before starting audio analysis.', 'error');
  }
  const jobScope = scope || (latinState.allFiltered ? { filter: structuredClone(latinState.filters), selection: 'all_filtered' } : { item_ids: [...latinState.selected], selection: 'explicit' });
  const result = await latinRequest('/api/v2/jobs', { method: 'POST', body: JSON.stringify({ kind, scope: jobScope, axes: kind === 'classify' ? ['music_family'] : undefined }) });
  latinAnnounce(`${kind === 'classify' ? 'Experimental audio classification' : latinStatusText(kind)} job queued. Review every result; this model has not met the release accuracy gate.`);
  latinState.jobs.unshift({ job_id: result.job_id, state: result.state, kind, counts: {} });
  if (kind === 'classify') latinState.jobs[0].experimental = true;
  if (latinState.page === 'activity') latinRenderJobs();
  latinPollJob(result.job_id);
  return result;
}

async function latinPollJob(jobId) {
  latinState.eventSources ||= {};
  latinState.eventSources[jobId]?.close();
  const source = new EventSource(`/api/v2/jobs/${encodeURIComponent(jobId)}/events`);
  latinState.eventSources[jobId] = source;
  const onEvent = event => {
    try {
      const data = JSON.parse(event.data);
      latinUpdateJob(data);
    // Every replayed event is stamped with the job's current state by the
    // server. Only a state_changed event represents the transition itself;
    // otherwise a completed import would close after its first old item event.
    if (latinEventTerminal(data)) {
        source.close(); delete latinState.eventSources[jobId];
      }
    } catch (_) { latinAnnounce('Received an unreadable job event. Activity will retry on refresh.', 'error'); }
  };
  source.onmessage = onEvent;
  source.addEventListener('progress', onEvent);
  source.onerror = () => latinAnnounce(`Connection to job ${jobId} paused. Activity reconnects automatically.`);
}

function latinTerminalJobState(state) {
  return ['completed', 'completed_with_errors', 'failed', 'cancelled', 'interrupted'].includes(state);
}

function latinEventTerminal(event) {
  return event?.type === 'state_changed' && latinTerminalJobState(event.state);
}

function latinJobAnnouncement(job) {
  const counts = job?.counts || {};
  const total = Number(counts.total || 0);
  const completed = Number(counts.completed || 0);
  const failed = Number(counts.failed || 0);
  const processed = completed + failed;
  const terminal = latinTerminalJobState(job?.state);
  const name = latinStatusText(job?.kind || 'Job');
  const state = latinStatusText(job?.state || 'updated');
  if (terminal && (!total || !processed)) return `${name} ${state}. Check Activity for per-file results.`;
  return `${name} ${state}: ${processed}/${total || '—'}`;
}

async function latinConfirmTerminalJob(jobId) {
  try {
    const durable = await latinRequest(`/api/v2/jobs/${encodeURIComponent(jobId)}`);
    const job = latinState.jobs.find(item => item.job_id === jobId);
    if (job) Object.assign(job, durable);
    else latinState.jobs.unshift(durable);
    latinAnnounce(latinJobAnnouncement(durable));
    if (latinState.page === 'activity') latinRenderJobs();
  } catch (_) {
    const job = latinState.jobs.find(item => item.job_id === jobId);
    latinAnnounce(`${latinStatusText(job?.kind || 'Job')} finished. Check Activity for per-file results.`);
  }
}

function latinUpdateJob(event) {
  if (!event?.job_id) return;
  latinState.jobSequences ||= {};
  const sequence = Number(event.sequence || 0);
  if (sequence && sequence <= Number(latinState.jobSequences[event.job_id] || 0)) return;
  if (sequence) latinState.jobSequences[event.job_id] = sequence;
  let job = latinState.jobs.find(item => item.job_id === event.job_id);
  if (!job) {
    job = { job_id: event.job_id, counts: {} };
    latinState.jobs.unshift(job);
  }
  const terminal = latinEventTerminal(event);
  // Event replays include a current-state snapshot on every historical item
  // update. Keep the known running state until the matching state_changed
  // event arrives, while still accepting each event's real count snapshot.
  const update = { ...event };
  if (event.type !== 'state_changed') delete update.state;
  // SSE can replay historic queued/running events after a reconnect. A durable
  // terminal state must never be replaced by one of those older events.
  if (latinTerminalJobState(job.state) && !terminal) return;
  Object.assign(job, update);
  const now = Date.now();
  if (!terminal && (!latinState.lastAnnounceAt || now - latinState.lastAnnounceAt > 5000)) {
    latinState.lastAnnounceAt = now;
    latinAnnounce(latinJobAnnouncement(job));
  }
  if (latinState.page === 'activity') latinRenderJobs();
  if (terminal) {
    if (!latinState.terminalJobs?.has(event.job_id)) {
      latinState.terminalJobs ||= new Set();
      latinState.terminalJobs.add(event.job_id);
      latinConfirmTerminalJob(event.job_id);
    }
    if (event.state === 'completed' && latinState.followupJobs?.[event.job_id]) {
      const followup = latinState.followupJobs[event.job_id];
      delete latinState.followupJobs[event.job_id];
      latinStartJob('classify', followup.scope).catch(error => latinAnnounce(`Import finished, but classification could not start. ${error.message}`, 'error'));
    }
    latinLoadLibrary({ reset: true });
    if (job?.kind === 'model_download') latinLoadCapabilities();
    if (job?.kind === 'export') latinLoadExportHistory();
    if (job?.kind === 'write') latinLoadBackups();
  }
}

function latinRenderJobs() {
  const jobs = latinState.jobs;
  const rows = latin$('latin-job-rows');
  if (!rows) return;
  if (!jobs.length) {
    rows.innerHTML = '<tr><td colspan="6" class="latin-table-message">No jobs yet.</td></tr>';
    return;
  }
  rows.innerHTML = jobs.map(job => `<tr><td><button class="latin-text-button" data-job-details="${latinEscape(job.job_id)}">${latinEscape(job.job_id?.slice(0, 8) || 'Job')}</button>${job.experimental ? '<small>Experimental audio model</small>' : ''}</td><td>${latinEscape(latinStatusText(job.kind))}</td><td><span class="latin-status-tag ${latinStatusClass(job.state)}">${latinEscape(latinStatusText(job.state))}</span></td><td>${latinEscape(job.counts?.completed ?? 0)} / ${latinEscape(job.counts?.total ?? '—')}<progress max="${latinEscape(job.counts?.total || 1)}" value="${latinEscape(job.counts?.completed || 0)}"></progress></td><td>${latinEscape(job.updated_at || 'Just started')}</td><td><button class="latin-text-button" data-job-details="${latinEscape(job.job_id)}">View results</button>${latinJobActions(job)}</td></tr>`).join('');
}

async function latinLoadJobs() {
  const rows = latin$('latin-job-rows');
  rows.innerHTML = '<tr><td colspan="6" class="latin-table-message">Loading durable job history…</td></tr>';
  try {
    const data = await latinRequest('/api/v2/jobs?limit=50');
    const remoteJobs = data.jobs || data.items || [];
    const merged = new Map(latinState.jobs.map(job => [job.job_id, job]));
    remoteJobs.forEach(job => merged.set(job.job_id, { ...merged.get(job.job_id), ...job, experimental: merged.get(job.job_id)?.experimental }));
    latinState.jobs = [...merged.values()];
    latinRenderJobs();
  } catch (error) {
    rows.innerHTML = `<tr><td colspan="6" class="latin-table-message">Job history unavailable: ${latinEscape(error.message)}. Jobs created in this session remain visible here.</td></tr>`;
    if (latinState.jobs.length) latinRenderJobs();
  }
}

async function latinActOnJob(jobId, action) {
  try {
    const updated = await latinRequest(`/api/v2/jobs/${encodeURIComponent(jobId)}/${action}`, { method: 'POST', body: JSON.stringify({}) });
    const existing = latinState.jobs.find(job => job.job_id === jobId);
    if (existing) Object.assign(existing, updated);
    latinRenderJobs();
    if (['running', 'queued'].includes(updated.state)) latinPollJob(jobId);
    latinAnnounce(`${latinStatusText(action)} requested for job ${jobId}.`);
  } catch (error) { latinAnnounce(`Could not ${action} this job. ${error.message}`, 'error'); }
}

async function latinStartModelAction(action) {
  if (latinState.model?.state === 'runtime_unavailable') {
    return latinAnnounce('Local model setup is unavailable because this installation does not include the audio runtime.', 'error');
  }
  try {
    const result = await latinRequest('/api/v2/models/jobs', { method: 'POST', body: JSON.stringify({ action }) });
    latinState.jobs.unshift(result);
    latinRenderJobs();
    latinPollJob(result.job_id);
    latinAnnounce(`${action === 'install' ? 'Local model setup' : latinStatusText(action)} started. Progress is in Activity.`);
  } catch (error) { latinAnnounce(`Could not ${action} the local model. ${error.message}`, 'error'); }
}

function latinJobActions(job) {
  const actions = [];
  const canPause = job.kind !== 'model_download';
  if ((job.state === 'running' || job.state === 'queued') && canPause) actions.push(`<button class="latin-text-button" data-job-action="pause" data-job-id="${latinEscape(job.job_id)}">Pause</button>`, `<button class="latin-text-button" data-job-action="cancel" data-job-id="${latinEscape(job.job_id)}">Cancel</button>`);
  if ((job.state === 'paused' || job.state === 'interrupted') && canPause) actions.push(`<button class="latin-text-button" data-job-action="resume" data-job-id="${latinEscape(job.job_id)}">Resume</button>`);
  return actions.join('');
}

async function latinOpenJobDetails(jobId, cursor = null) {
  const requestId = (latinState.jobDetailsRequestId || 0) + 1;
  latinState.jobDetailsRequestId = requestId;
  try {
    const [job, page] = await Promise.all([
      latinRequest(`/api/v2/jobs/${encodeURIComponent(jobId)}`),
      latinRequest(`/api/v2/jobs/${encodeURIComponent(jobId)}/items?limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`),
    ]);
    if (requestId !== latinState.jobDetailsRequestId) return;
    const items = page.items || [];
    const rows = items.map(item => `<tr><td><button class="latin-text-button" data-job-item-open="${latinEscape(item.item_id)}">${latinEscape(item.item_id)}</button></td><td>${latinEscape(latinStatusText(item.state))}</td><td>${latinEscape(item.error_code || '—')}</td><td>${latinEscape(item.attempt || 0)}</td></tr>`).join('') || '<tr><td colspan="4">No item outcomes yet.</td></tr>';
    const failed = Number(job.counts?.failed || 0);
    latinOpenModal({ kicker: 'JOB RESULTS', title: `${latinStatusText(job.kind)} · ${Number(page.total || 0).toLocaleString()} tracks`, body: `<p>${latinEscape(latinStatusText(job.state))}. Each track links to its inspector; error codes are kept with the durable job history.</p><div class="latin-diff-wrap"><table class="latin-diff"><thead><tr><th>TRACK</th><th>OUTCOME</th><th>DETAIL</th><th>ATTEMPT</th></tr></thead><tbody>${rows}</tbody></table></div><div class="latin-pager"><button class="latin-button quiet" data-job-page="${latinEscape(jobId)}" data-job-cursor="${latinEscape(cursor || '')}" ${cursor ? '' : 'disabled'}>Previous</button><button class="latin-button quiet" data-job-page="${latinEscape(jobId)}" data-job-cursor="${latinEscape(page.next_cursor || '')}" ${page.next_cursor ? '' : 'disabled'}>Next</button></div>`, buttons: [
      { label: 'Close', kind: 'quiet', close: true },
      ...(job.kind === 'classify' && failed ? [{ label: `Retry ${failed.toLocaleString()} failed analysis tracks`, kind: 'primary', action: async () => latinRetryFailedClassification(jobId), close: true }] : []),
    ] });
  } catch (error) { if (requestId === latinState.jobDetailsRequestId) latinAnnounce(`Could not load job results. ${error.message}`, 'error'); }
}

async function latinRetryFailedClassification(jobId) {
  let cursor = null;
  const itemIds = [];
  do {
    const page = await latinRequest(`/api/v2/jobs/${encodeURIComponent(jobId)}/items?limit=250${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`);
    itemIds.push(...(page.items || []).filter(item => item.state === 'failed').map(item => item.item_id));
    cursor = page.next_cursor || null;
  } while (cursor);
  if (!itemIds.length) throw new Error('This job has no failed analysis tracks to retry.');
  await latinStartJob('classify', { item_ids: itemIds, selection: 'explicit' });
  latinAnnounce(`Retrying ${itemIds.length.toLocaleString()} failed analysis tracks with the current local model.`);
}

async function latinLoadCapabilities() {
  const requestId = (latinState.capabilitiesRequestId || 0) + 1;
  latinState.capabilitiesRequestId = requestId;
  try {
    const data = await latinRequest('/api/v2/settings');
    const settings = data.values || {};
    const capabilities = data.capabilities || {};
    let model = null;
    try { model = (await latinRequest('/api/v2/models')).model || null; } catch (_) { /* Settings still work without the status endpoint. */ }
    if (requestId !== latinState.capabilitiesRequestId) return;
    latinState.settings = settings;
    latinState.capabilities = capabilities;
    latinState.model = model;
    if (latin$('latin-theme') && latinState.settings.theme) {
      latin$('latin-theme').value = latinState.settings.theme;
      document.body.classList.toggle('light', latinState.settings.theme === 'light');
      document.documentElement.dataset.theme = latinState.settings.theme;
    }
    if (latin$('latin-text-scale') && latinState.settings.text_scale) {
      latin$('latin-text-scale').value = String(latinState.settings.text_scale);
      document.documentElement.style.setProperty('--latin-scale', latinState.settings.text_scale);
    }
    if (latin$('latin-reduced-motion')) {
      latin$('latin-reduced-motion').checked = Boolean(latinState.settings.reduced_motion);
      document.body.classList.toggle('latin-reduced-motion', Boolean(latinState.settings.reduced_motion));
    }
    latinRenderSettings();
  } catch (error) {
    if (requestId !== latinState.capabilitiesRequestId) return;
    latin$('latin-model-state').textContent = `Local model status unavailable: ${error.message}`;
    latin$('latin-model-actions').innerHTML = '<span class="latin-muted">The v2 capability service is not available yet.</span>';
  }
}

async function latinSaveSettings(values) {
  try {
    const result = await latinRequest('/api/v2/settings', { method: 'PUT', body: JSON.stringify({ values: { ...latinState.settings, ...values } }) });
    latinState.settings = result.values || { ...latinState.settings, ...values };
    latinAnnounce('Settings saved on this machine.');
  } catch (error) { latinAnnounce(`Settings were not saved. ${error.message}`, 'error'); }
}

function latinRenderSettings() {
  const model = latinState.model || latinState.capabilities.model || latinState.settings.model || {};
  const installed = model.state === 'installed' || Boolean(model.installed);
  const runtimeUnavailable = model.state === 'runtime_unavailable';
  latin$('latin-model-state').innerHTML = `<div><strong>${latinEscape(model.model_id ? 'Local audio model' : 'No local model reported')}</strong><span>${latinEscape(latinStatusText(model.state || model.status || 'unknown'))}</span></div><p>${latinEscape(model.reason || model.note || (installed ? 'Classification is an experimental local feature. Review all results.' : 'Set up the optional model to enable local audio classification. No API key is needed.'))}</p>`;
  const actions = [];
  if (!installed && !runtimeUnavailable) actions.push('<button class="latin-button primary" data-model-action="install">Set up local model</button>');
  if (installed) actions.push('<button class="latin-button quiet" data-model-action="verify">Verify model</button><button class="latin-button quiet" data-model-action="repair">Repair model</button>');
  if (runtimeUnavailable) actions.push('<span class="latin-muted">Local analysis is unavailable because this installation does not include the audio runtime.</span>');
  if (!actions.length) actions.push('<span class="latin-muted">Model controls will appear when this installation exposes them.</span>');
  latin$('latin-model-actions').innerHTML = actions.join('');
  latin$('latin-library-settings').innerHTML = `<div class="latin-setting-row"><span>Classification</span><strong>${installed ? 'Experimental local model' : 'Unavailable until setup'}</strong></div><div class="latin-setting-row"><span>Model installed</span><strong>${latinEscape(latinStatusText(model.state || 'unknown'))}</strong></div><div class="latin-setting-row"><span>Network required</span><strong>${installed ? 'No for local analysis' : 'Only for optional model setup'}</strong></div>`;
}

async function latinLoadTaxonomy() {
  const requestId = (latinState.taxonomyRequestId || 0) + 1;
  latinState.taxonomyRequestId = requestId;
  try {
    const result = await latinRequest('/api/v2/taxonomy');
    if (requestId !== latinState.taxonomyRequestId) return;
    latinState.taxonomy = result.document || result;
    latinState.taxonomyRevision = Number(result.revision || 0);
    latinRenderTaxonomy();
    latinRenderChips();
  } catch (error) {
    if (requestId !== latinState.taxonomyRequestId) return;
    latin$('latin-taxonomy-content').innerHTML = `<div class="latin-error-card">Categories could not load: ${latinEscape(error.message)}<button class="latin-text-button" data-retry="taxonomy">Retry</button></div>`;
  }
}

function latinRenderTaxonomy() {
  const taxonomy = latinState.taxonomy;
  if (!taxonomy) return;
  const labels = Array.isArray(taxonomy.labels) ? taxonomy.labels : Object.entries(taxonomy.axes || taxonomy.taxonomy?.axes || {}).flatMap(([axis, values]) => (values || []).map(label => ({ ...label, axis })));
  const axes = [...new Set(labels.map(label => label.axis))];
  const rawTags = taxonomy.palette?.raw_comment_tokens || [];
  if (!labels.length) {
    latin$('latin-taxonomy-content').innerHTML = rawTags.length ? `<div class="latin-taxonomy-list">${rawTags.map(tag => `<div class="latin-taxonomy-row"><div><strong>${latinEscape(tag)}</strong><small>Literal Comment token</small></div><span class="latin-status-tag neutral">Personal tag</span><span>My tags</span></div>`).join('')}</div>` : '<div class="latin-empty"><strong>Taxonomy loaded, but no labels were returned.</strong><span>No example labels are inserted by the interface.</span></div>';
  } else {
    latin$('latin-taxonomy-content').innerHTML = `<div class="latin-axis-tabs">${axes.map(axis => `<span class="latin-axis-tab">${latinEscape(latinAxisLabel(axis))}</span>`).join('')}</div><div class="latin-taxonomy-list">${labels.map(label => `<div class="latin-taxonomy-row"><div><strong>${latinEscape(label.display_name || label.name || label.id)}</strong><small>${latinEscape(label.aliases?.length ? `Also known as: ${label.aliases.join(' · ')}` : '')}</small></div><span class="latin-status-tag ${latinStatusClass(label.status)}">${latinEscape(latinStatusText(label.status || 'vocabulary_only'))}</span><span>${latinEscape(latinAxisLabel(label.axis))}</span></div>`).join('')}${rawTags.map(tag => `<div class="latin-taxonomy-row"><div><strong>${latinEscape(tag)}</strong><small>Literal Comment token</small></div><span class="latin-status-tag neutral">Personal tag</span><span>My tags</span></div>`).join('')}</div>`;
  }
}

function latinRenderPriority() {
  latin$('latin-priority-chips').innerHTML = latinFamilyPalette.map((name, i) => `<span class="latin-priority-chip"><b>${i + 1}</b>${latinEscape(name)}</span>`).join('');
}

function latinRenderRoutes() {
  const routes = [
    ['direct_cable', 'Direct cable · first bulk test', 'Finder file sharing only when the receiving app supports it.'],
    ['wireless_smb', 'Wireless local copy', 'Copy from a registered Mac share into stable On My iPad storage.'],
    ['music_sync', 'Apple Music and Finder Music sync', 'Existing route. Cable first; Wi-Fi sync may be slower.'],
    ['onelibrary', 'OneLibrary · optional', 'Only if already available with a supported USB workflow.'],
  ];
  latin$('latin-export-routes').innerHTML = routes.map(([id, title, detail]) => `<label class="latin-route-option"><input type="radio" name="latin-export-route" value="${id}" ${latinState.selectedRoute === id ? 'checked' : ''}><span><strong>${latinEscape(title)}</strong><small>${latinEscape(detail)}</small></span><em>Test required</em></label>`).join('');
}

async function latinPersonalTagId(value) {
  const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)));
  return `personal:${[...bytes].map(byte => byte.toString(16).padStart(2, '0')).join('').slice(0, 24)}`;
}

async function latinRegisterPersonalTags(values) {
  if (!latinState.taxonomy) await latinLoadTaxonomy();
  const unique = [...new Set(values.map(value => value.trim()).filter(Boolean))];
  const normalize = value => String(value || '').toLocaleLowerCase();
  const existing = new Map((latinState.taxonomy?.labels || []).filter(label => label.axis === 'custom_tag').map(label => [normalize(label.display_name), label]));
  const missing = unique.filter(value => !existing.has(normalize(value)));
  if (missing.length) {
    const document = structuredClone(latinState.taxonomy);
    document.labels ||= [];
    for (const value of missing) {
      const label = { id: await latinPersonalTagId(value), display_name: value, axis: 'custom_tag', status: 'manual', aliases: [] };
      document.labels.push(label);
      existing.set(normalize(value), label);
    }
    const saved = await latinRequest('/api/v2/taxonomy', { method: 'PUT', body: JSON.stringify({ document, expected_revision: latinState.taxonomyRevision }) });
    latinState.taxonomy = saved.document;
    latinState.taxonomyRevision = Number(saved.revision || latinState.taxonomyRevision);
  }
  return new Map(unique.map(value => [value, existing.get(normalize(value)).id]));
}

async function latinSaveCatalogueTags(scope, { addValues = [], removeIds = [] } = {}) {
  const labelIds = await latinRegisterPersonalTags(addValues);
  const additions = [...new Set([...labelIds.values()])];
  const removals = [...new Set(removeIds.filter(Boolean))];
  if (!additions.length && !removals.length) throw new Error('Choose one or more catalogue tags to change.');
  const preview = await latinRequest('/api/v2/reviews/previews', { method: 'POST', body: JSON.stringify({ scope, fields: ['custom_tag'] }) });
  const decisions = (preview.items || []).flatMap(item => [
    ...(additions.length ? [{ item_id: item.item_id, axis: 'custom_tag', action: 'add', label_ids: additions }] : []),
    ...(removals.length ? [{ item_id: item.item_id, axis: 'custom_tag', action: 'remove', label_ids: removals }] : []),
  ]);
  if (!decisions.length) throw new Error('No tracks were available in this saved scope.');
  await latinRequest('/api/v2/reviews/decisions', { method: 'POST', body: JSON.stringify({ preview_id: preview.preview_id, decisions }) });
  return preview.items?.length || 0;
}

function latinCatalogueScope() {
  return latinState.allFiltered ? { filter: structuredClone(latinState.filters), selection: 'all_filtered' } : { item_ids: [...latinState.selected], selection: 'explicit' };
}

function latinOpenCatalogueTags(scope = latinCatalogueScope()) {
  const palette = latinState.taxonomy?.palette?.raw_comment_tokens || [];
  const count = scope.selection === 'all_filtered' ? `${latinState.total.toLocaleString()} filtered` : `${scope.item_ids.length} selected`;
  const choices = palette.map(value => `<label class="latin-check-option"><input type="checkbox" name="latin-catalogue-tag" value="${latinEscape(value)}"><span>${latinEscape(value)}</span></label>`).join('');
  latinOpenModal({ kicker: 'CATALOGUE TAGS', title: `Tag ${count} tracks`, body: `<p>These literal tags are catalogue decisions only. They work for every imported format and do not change source files. Export or write metadata later from its own preview.</p><label class="latin-field-label" for="latin-catalogue-action">Change</label><select id="latin-catalogue-action" class="latin-select full"><option value="add">Add selected literal tags</option><option value="remove">Remove selected literal tags</option></select><div class="latin-chips latin-edit-token-list">${choices || '<span class="latin-muted">Import or add category vocabulary first.</span>'}</div><label class="latin-field-label" for="latin-catalogue-custom">Add an exact custom tag</label><input id="latin-catalogue-custom" class="latin-input full" maxlength="80" placeholder="Commas stay part of this one tag">`, buttons: [
    { label: 'Cancel', kind: 'quiet', close: true },
    { label: 'Save catalogue tags', kind: 'primary', action: async () => {
      const action = latin$('latin-catalogue-action').value;
      const values = [...document.querySelectorAll('input[name="latin-catalogue-tag"]:checked')].map(input => input.value);
      const custom = latin$('latin-catalogue-custom').value.trim();
      if (custom && action === 'add') values.push(custom);
      if (!values.length) throw new Error('Choose at least one literal tag.');
      const ids = action === 'remove' ? [...(await latinRegisterPersonalTags(values)).values()] : [];
      const changed = await latinSaveCatalogueTags(scope, action === 'add' ? { addValues: values } : { removeIds: ids });
      latinCloseModal(); latinAnnounce(`Saved catalogue tags for ${changed.toLocaleString()} tracks. No files were changed.`); latinLoadLibrary({ reset: true });
    } },
  ] });
}

function latinOpenBatchEdit(itemIdsOrScope) {
  const scope = Array.isArray(itemIdsOrScope) ? { item_ids: itemIdsOrScope, selection: 'explicit' } : itemIdsOrScope;
  if (!scope.item_ids?.length && scope.selection !== 'all_filtered') return latinAnnounce('Select tracks first.', 'error');
  const countLabel = scope.selection === 'all_filtered' ? `${latinState.total.toLocaleString()} filtered` : `${scope.item_ids.length} selected`;
  const tokenPalette = latinState.taxonomy?.palette?.raw_comment_tokens || [];
  const tokenChoices = tokenPalette.map(token => `<label class="latin-check-option"><input type="checkbox" name="latin-edit-token" value="${latinEscape(token)}"><span>${latinEscape(token)}</span></label>`).join('');
  latinOpenModal({ kicker: 'BATCH FIELD EDIT', title: `Edit ${countLabel} tracks`, body: `<p>One preview covers the frozen selection. Original Comment text stays intact; these tags are stored separately as IDJLM-managed tokens.</p><label class="latin-field-label" for="latin-edit-genre-mode">Genre</label><select id="latin-edit-genre-mode" class="latin-select full"><option value="keep">Keep each current Genre</option><option value="set">Set Genre to…</option><option value="clear">Clear Genre</option></select><input id="latin-edit-genre" class="latin-input full" placeholder="Enter Genre" hidden><label class="latin-field-label" for="latin-edit-token-mode">My tags</label><select id="latin-edit-token-mode" class="latin-select full"><option value="none">Leave unchanged</option><option value="add">Add selected tags</option><option value="remove">Remove selected managed tags</option><option value="replace">Replace managed tags</option></select><div class="latin-chips latin-edit-token-list">${tokenChoices}</div><label class="latin-field-label" for="latin-edit-custom-token">Add an exact custom tag</label><input id="latin-edit-custom-token" class="latin-input full" maxlength="80" placeholder="Commas stay part of this one tag"><p>Unsupported files and conflicts will be excluded and shown in the preview.</p>`, buttons: [
    { label: 'Cancel', kind: 'quiet', close: true },
    { label: 'Preview changes', kind: 'primary', action: async () => {
      const genreMode = latin$('latin-edit-genre-mode').value;
      const genre = latin$('latin-edit-genre').value.trim();
      const mode = latin$('latin-edit-token-mode').value;
      const tokens = [...document.querySelectorAll('input[name="latin-edit-token"]:checked')].map(input => input.value);
      const custom = latin$('latin-edit-custom-token').value.trim();
      if (custom) tokens.push(custom);
      if (genreMode === 'set' && !genre) throw new Error('Enter a Genre or choose Keep current Genre.');
      if (genreMode === 'keep' && mode === 'none') throw new Error('Choose a field to edit.');
      if (mode !== 'none' && !tokens.length && mode !== 'replace') throw new Error('Choose at least one tag for this action.');
      const override = { ...(genreMode === 'set' ? { genre } : genreMode === 'clear' ? { genre: null } : {}), ...(mode !== 'none' ? { comment_tokens: { action: mode, values: tokens } } : {}) };
      const fields = [...(genreMode !== 'keep' ? ['genre'] : []), ...(mode !== 'none' ? ['comment'] : [])];
      latinCloseModal();
      await latinPreviewWrite(scope, override, fields);
    } },
  ] });
  latin$('latin-edit-genre-mode').addEventListener('change', event => { latin$('latin-edit-genre').hidden = event.target.value !== 'set'; });
}

async function latinPreviewWrite(scope, override = {}, fields = ['genre','comment']) {
  try {
    const field_overrides = scope.selection === 'all_filtered' ? {} : Object.fromEntries(scope.item_ids.map(id => [id, override]));
    const body = { scope, fields, field_overrides, ...(scope.selection === 'all_filtered' ? { default_override: override } : {}) };
    const preview = await latinRequest('/api/v2/writes/previews', { method: 'POST', body: JSON.stringify(body) });
    latinRenderWritePreview(preview);
  } catch (error) { latinAnnounce(`Could not prepare a write preview. ${error.message}`, 'error'); }
}

function latinRenderWritePreview(preview) {
  const rows = preview.items || [];
  const safeCount = rows.filter(item => item.status === 'ready').length;
  const changes = rows.flatMap(item => Object.entries(item.fields || {}).map(([field, value]) => ({ item: { ...item, title: latinState.items.find(row => row.id === item.item_id)?.title || 'Track' }, field, ...value })));
  latinOpenModal({ kicker: 'WRITE PREVIEW · NO FILES CHANGED', title: `Review ${safeCount.toLocaleString()} proposed file changes`, body: `<p>Only the selected fields will be written. Conflicts, unsupported formats, and backup failures are excluded. Existing unowned Comment frames are preserved.</p>${changes.length > 100 ? `<p>Showing 100 of ${changes.length.toLocaleString()} field changes.</p>` : ''}<div class="latin-diff-wrap"><table class="latin-diff"><thead><tr><th>FILE</th><th>FIELD</th><th>BEFORE</th><th>AFTER</th><th>STATUS</th></tr></thead><tbody>${changes.slice(0,100).map(change => `<tr><td>${latinEscape(change.item.title)}</td><td>${latinEscape(change.field === 'genre' ? 'Genre' : 'My tags')}</td><td>${latinEscape(change.field === 'comment' ? latinManagedCommentText(change.before) : change.before || '—')}</td><td>${latinEscape(change.field === 'comment' ? latinManagedCommentText(change.after) : change.after || '—')}</td><td>${latinEscape(latinStatusText(change.item.status))}</td></tr>`).join('')}</tbody></table></div><p class="latin-warning">Writing changes audio-file metadata. This action uses the verified backup and read-back service.</p>`, buttons: [
      { label: 'Cancel', kind: 'quiet', close: true },
      { label: `Write ${safeCount} files`, kind: 'primary', disabled: !safeCount, action: async () => {
        const result = await latinRequest('/api/v2/writes/commit', { method: 'POST', body: JSON.stringify({ preview_id: preview.preview_id, confirm: true }) });
        latinCloseModal(); latinAnnounce(`Write job ${result.job_id} queued. Check Activity for per-file verification.`); latinState.jobs.unshift({ job_id: result.job_id, state: result.state || 'queued', kind: 'write', counts: {} }); latinPollJob(result.job_id);
      } },
    ] });
}

function latinManagedCommentText(value) {
  if (!value) return 'No managed tags';
  const prefix = 'IDJLMv1:';
  if (!String(value).startsWith(prefix)) return String(value);
  try { return JSON.parse(String(value).slice(prefix.length)).tokens.join(' · ') || 'No managed tags'; }
  catch (_) { return 'Managed tag value (could not be decoded)'; }
}

async function latinPreviewExport() {
  const itemIds = latinState.exportScope?.item_ids || (latinState.allFiltered ? undefined : [...latinState.selected]);
  const filters = latinState.exportScope?.filter || (latinState.allFiltered ? structuredClone(latinState.filters) : undefined);
  if (!itemIds?.length && !filters) return latinAnnounce('Select tracks in Library or choose a saved view first.', 'error');
  if (!latinState.destination) return latinAnnounce('Choose a destination folder before previewing.', 'error');
  const requestId = (latinState.exportPreviewRequestId || 0) + 1;
  latinState.exportPreviewRequestId = requestId;
  const previewCard = latin$('latin-export-preview-card');
  // A prior preview describes an earlier frozen scope. Replace it while the
  // next request is pending so it cannot be mistaken for current fields.
  previewCard.hidden = false;
  previewCard.innerHTML = '<div class="latin-empty"><strong>Preparing current export preview…</strong><span>No files are copied until you confirm the returned preview.</span></div>';
  try {
    const profile = latin$('latin-export-profile').value;
    const scope = itemIds ? { item_ids: itemIds, selection: 'explicit' } : { filter: filters, selection: 'all_filtered' };
    const profileNames = { broad_genre_raw_comment: 'Broad Genre + existing Comments', djay_extended_genre: 'Extended Genre · Genre and Style labels' };
    const preview = await latinRequest('/api/v2/exports/previews', { method: 'POST', body: JSON.stringify({ scope, profile: { id: profile, name: profile }, route: latinState.selectedRoute, destination: latinState.destination }) });
    if (requestId !== latinState.exportPreviewRequestId) return;
    latinState.exportProfileName = profileNames[profile] || profile;
    latinState.exportScope = { item_ids: itemIds, filter: filters };
    latinRenderExportPreview(preview);
  } catch (error) {
    if (requestId !== latinState.exportPreviewRequestId) return;
    previewCard.hidden = true;
    latinAnnounce(`Could not preview export. ${error.message}`, 'error');
  }
}

function latinRenderExportPreview(preview) {
  const el = latin$('latin-export-preview-card');
  el.hidden = false;
  const report = preview.report || {};
  const manifest = report.manifest || [];
  const ready = Number(report.copy_count || 0) + manifest.filter(row => row.status === 'unchanged').length;
  const changed = manifest.filter(row => row.status === 'changed');
  const enoughSpace = report.enough_space === true;
  const routeHelp = {
    direct_cable: 'After preparation, use Finder with the iPad connected by cable. Copy into a location offered by an installed receiving app, then add those local files to djay My Collection. Confirm Genre filtering and find a detailed style before marking verified.',
    wireless_smb: 'After preparation, connect from iPad Files to the Mac SMB share and copy into a stable On My iPad folder. Add local files to djay My Collection; confirm Genre filtering and detailed-style discovery.',
    music_sync: 'After preparation, add the staged files to the Music library and sync using Finder Music. Import or add them to djay, then confirm Genre filtering and detailed-style discovery.',
    onelibrary: 'After preparation, use djay OneLibrary through its supported USB workflow. Check that the expected Genre and style remain findable in djay before recording verification.',
  }[latinState.selectedRoute];
  el.innerHTML = `<div class="latin-card-heading"><div><span class="latin-eyebrow">EXPORT PREVIEW · NO FILES COPIED</span><h2>${latinEscape((report.source_count || manifest.length).toLocaleString())} tracks · ${latinEscape((report.bytes_to_copy || 0).toLocaleString())} bytes to copy</h2><p>${latinEscape(report.destination || latinState.destination)} · ${latinEscape(latinState.selectedRoute)}</p></div><button class="latin-button quiet" data-close-export-preview>Close preview</button></div><div class="latin-export-preflight"><span>${latinEscape(report.copy_count ?? 0)} to copy</span><span>${latinEscape(manifest.filter(row => row.status === 'unchanged').length)} already staged</span><span>${latinEscape(report.missing_count ?? 0)} missing</span><span>${latinEscape(report.conflict_count ?? 0)} conflicts</span></div><p>${enoughSpace ? `Free space: ${latinEscape((report.free_bytes || 0).toLocaleString())} bytes.` : 'Not enough free space for this copy.'} Staged copies use <strong>${latinEscape(latinState.exportProfileName || 'the selected profile')}</strong>; source files stay unchanged. Transfer is manual and not reported until you confirm it.</p><div class="latin-note-card"><strong>Next in djay</strong><span>${latinEscape(routeHelp)}</span></div><div class="latin-diff-wrap"><table class="latin-diff"><thead><tr><th>TRACK</th><th>STATUS</th><th>COPY GENRE</th><th>COPY COMMENTS</th><th>STAGED NAME</th><th>SIZE</th></tr></thead><tbody>${manifest.slice(0, 100).map(row => `<tr><td>${latinEscape(latinState.items.find(item => item.id === row.item_id)?.title || 'Track')}</td><td>${latinEscape(latinStatusText(row.status))}</td><td>${latinEscape(row.tag_fields?.genre || '—')}</td><td>${latinEscape(row.tag_fields?.comment || '—')}</td><td>${latinEscape(row.relative_path || '—')}</td><td>${latinEscape(row.bytes ?? '—')}</td></tr>`).join('')}</tbody></table></div>${manifest.length > 100 ? `<p>Showing first 100 of ${manifest.length.toLocaleString()} files.</p>` : ''}${changed.length ? `<button class="latin-button primary" data-commit-export="${latinEscape(preview.preview_id)}" data-replace-known="true" ${!enoughSpace ? 'disabled' : ''}>Review replacement of ${changed.length.toLocaleString()} known staged copies</button><p>Only previously managed staged files can be replaced. The next confirmation shows this scope.</p>` : `<button class="latin-button primary" data-commit-export="${latinEscape(preview.preview_id)}" ${!enoughSpace || ready === 0 ? 'disabled' : ''}>Prepare ${ready.toLocaleString()} files</button>`}`;
}

async function latinCommitExport(previewId, replaceKnown = false) {
  try {
    if (replaceKnown) {
      const confirmed = await new Promise(resolve => latinOpenModal({ kicker: 'REPLACE STAGED COPIES', title: 'Review before replacing', body: '<p>This replaces only files already recorded in IDJLM’s staging manifest. A backup of each prior staged copy is retained. Source files are not changed.</p>', buttons: [{ label: 'Cancel', kind: 'quiet', action: () => { latinCloseModal(); resolve(false); } }, { label: 'Replace known copies', kind: 'primary', action: () => { latinCloseModal(); resolve(true); } }] }));
      if (!confirmed) return;
    }
    const result = await latinRequest('/api/v2/exports/commit', { method: 'POST', body: JSON.stringify({ preview_id: previewId, confirm: true, replace_known: replaceKnown }) });
    const job = result.job || result;
    latin$('latin-export-preview-card').hidden = true;
    if (result.export) latinState.exports.unshift(result.export);
    latinState.jobs.unshift(job);
    latinRenderExportHistory();
    latinPollJob(job.job_id); latinAnnounce(`Export preparation ${job.job_id} queued. No device transfer is claimed.`);
  } catch (error) { latinAnnounce(`Export was not prepared. ${error.message}`, 'error'); }
}

async function latinRecordExportTransfer(exportId, state) {
  const verify = state === 'Verified in djay';
  latinOpenModal({ kicker: verify ? 'VERIFY IN DJAY' : 'CONFIRM TRANSFER', title: verify ? 'Record what you checked' : 'Confirm the files were transferred', body: `<p>${verify ? 'Verification is a user-recorded check. The app cannot inspect djay or the iPad.' : 'Only mark this after copying the prepared files with Finder, Files, Music sync, or another route.'}</p><label class="latin-field-label" for="latin-transfer-evidence">${verify ? 'What did you confirm in djay?' : 'Transfer note (optional)'}</label><textarea class="latin-input full" id="latin-transfer-evidence" rows="3" maxlength="500" placeholder="For example: searched Salsa Romántica in My Collection and played a track"></textarea>`, buttons: [
    { label: 'Cancel', kind: 'quiet', close: true },
    { label: verify ? 'Record verification' : 'Record transfer', kind: 'primary', action: async () => {
      const evidence = latin$('latin-transfer-evidence').value.trim();
      if (verify && !evidence) throw new Error('Describe what you checked in djay.');
      const result = await latinRequest(`/api/v2/exports/${encodeURIComponent(exportId)}/transfer`, { method: 'POST', body: JSON.stringify({ state, evidence }) });
      const index = latinState.exports.findIndex(item => item.export_id === exportId);
      if (index >= 0) latinState.exports[index] = result;
      latinCloseModal(); latinRenderExportHistory();
      latinAnnounce(verify ? 'Verification recorded from your report. The app did not inspect djay.' : 'Transfer recorded from your confirmation.');
    } },
  ] });
}

function latinOpenModal({ kicker = '', title, body, buttons = [] }) {
  const backdrop = latin$('latin-modal-backdrop');
  latinState.lastFocus = document.activeElement;
  latin$('latin-modal-kicker').textContent = kicker;
  latin$('latin-modal-title').textContent = title;
  latin$('latin-modal-body').innerHTML = body;
  latin$('latin-modal-footer').innerHTML = buttons.map((button, index) => `<button class="latin-button ${button.kind || 'quiet'}" data-modal-action="${index}" ${button.disabled ? 'disabled' : ''}>${latinEscape(button.label)}</button>`).join('');
  backdrop.hidden = false;
  backdrop.querySelector('.latin-modal').focus();
  latinState.modalButtons = buttons;
}

function latinCloseModal() {
  latinState.jobDetailsRequestId = (latinState.jobDetailsRequestId || 0) + 1;
  latin$('latin-modal-backdrop').hidden = true;
  latinState.lastFocus?.focus?.();
}

async function latinHandleModalAction(index) {
  const button = latinState.modalButtons?.[index];
  if (!button) return;
  try {
    await button.action?.();
    if (button.close) latinCloseModal();
  } catch (error) { latinAnnounce(error.message, 'error'); }
}

async function latinImportFolder() {
  try {
    const picker = await latinRequest('/api/pick-folder');
    if (picker.cancelled || picker.unavailable) return;
    const root = picker.path || picker.folder || picker.directory;
    if (!root) return;
    latinOpenModal({ kicker: 'ADD MUSIC FOLDER', title: 'Add music from this folder', body: `<p>Files stay where they are. Unchanged tracks are reused during future scans.</p><p><strong>${latinEscape(root.split(/[\\/]/).filter(Boolean).at(-1) || 'Selected folder')}</strong></p><p>After import, select the imported tracks in Library and start audio analysis for that selection.</p>`, buttons: [
      { label: 'Cancel', kind: 'quiet', close: true },
      { label: 'Import folder', kind: 'primary', action: async () => {
        latin$('latin-modal-footer').querySelectorAll('button').forEach(button => button.disabled = true);
        latinAnnounce('Additive folder import queued. Existing folders and reviewed labels are preserved.');
        const result = await latinRequest('/api/v2/library/import-jobs', { method: 'POST', body: JSON.stringify({ folder_path: root }) });
        latinCloseModal();
        latinState.jobs.unshift(result);
        latinPollJob(result.job_id);
        if (latinState.page === 'activity') latinRenderJobs();
      } },
    ] });
  } catch (error) { latinAnnounce(`Folder import could not start. ${error.message}`, 'error'); }
}

function latinSwitchPage(page) {
  if (!latinPages.includes(page)) return;
  latinState.page = page;
  document.querySelectorAll('.latin-nav-item').forEach(button => button.classList.toggle('active', button.dataset.page === page));
  document.querySelectorAll('.latin-page').forEach(section => section.classList.toggle('active', section.id === `latin-page-${page}`));
  const title = page[0].toUpperCase() + page.slice(1);
  latin$('latin-page-title').textContent = title;
  latin$('latin-breadcrumb').textContent = page === 'library' ? 'YOUR MUSIC' : `YOUR MUSIC  /  ${title.toUpperCase()}`;
  if (page === 'review') latinRenderReview();
  if (page === 'categories') latinLoadTaxonomy();
  if (page === 'export') { latinRenderRoutes(); latinRenderExportHistory(); latinLoadExportHistory(); }
  if (page === 'activity') { latinRenderJobs(); latinLoadJobs(); latinLoadBackups(); }
  if (page === 'settings') latinLoadCapabilities();
  if (page === 'library') latinLoadLibrary({ reset: true });
}

function latinRenderExportHistory() {
  const exports = latinState.exports;
  latin$('latin-export-history').innerHTML = exports.length ? exports.map(item => `<div class="latin-export-history-row"><div><strong>${latinEscape(item.export_id || 'Export')}</strong><small>${latinEscape(item.destination || '')}</small></div><span class="latin-status-tag ${latinStatusClass(item.state)}">${latinEscape(item.state || 'Draft')}</span><div>${latinExportActions(item)}</div></div>`).join('') : 'No export jobs yet. Prepared files are not reported as transferred or verified.';
}

function latinExportActions(item) {
  if (item.state === 'Prepared') return `<button class="latin-text-button" data-export-transfer="${latinEscape(item.export_id)}" data-transfer-state="Transferred (user-confirmed)">Mark transferred</button><button class="latin-text-button" data-export-transfer="${latinEscape(item.export_id)}" data-transfer-state="Verified in djay">Verify in djay</button>`;
  if (item.state === 'Transferred (user-confirmed)' || item.state === 'Transfer unverified') return `<button class="latin-text-button" data-export-transfer="${latinEscape(item.export_id)}" data-transfer-state="Verified in djay">Verify in djay</button>`;
  return '';
}

async function latinLoadExportHistory() {
  try {
    const jobs = await latinRequest('/api/v2/jobs?limit=100');
    const exportJobs = (jobs.jobs || jobs.items || []).filter(job => job.kind === 'export' && job.config?.export_id);
    const loaded = await Promise.all(exportJobs.map(job => latinRequest(`/api/v2/exports/${encodeURIComponent(job.config.export_id)}`).catch(() => null)));
    const byId = new Map(latinState.exports.map(item => [item.export_id, item]));
    loaded.filter(Boolean).forEach(item => byId.set(item.export_id, item));
    latinState.exports = [...byId.values()];
    latinRenderExportHistory();
  } catch (error) {
    if (!latinState.exports.length) latin$('latin-export-history').textContent = `Export history unavailable: ${error.message}`;
  }
}

async function latinLoadBackups() {
  try {
    const data = await latinRequest('/api/v2/writes?limit=100');
    const records = data.writes || data.items || [];
    latin$('latin-restore-list').innerHTML = records.length ? records.map(item => `<div class="latin-restore-row"><div><strong>${latinEscape(latinState.items.find(row => row.id === item.item_id)?.title || 'Track')}</strong><small>${latinEscape(latinStatusText(item.status))} · ${latinEscape(item.created_at || '')}</small></div><button class="latin-button quiet" data-restore-preview="${latinEscape(item.write_id)}" ${item.status !== 'written' ? 'disabled' : ''}>Preview restore</button></div>`).join('') : '<div class="latin-empty"><strong>No completed writes with verified backups yet.</strong><span>Restore appears here after a successful metadata write.</span></div>';
  } catch (error) { latin$('latin-restore-list').textContent = `Verified write history unavailable: ${error.message}`; }
}

async function latinPreviewRestore(writeId) {
  try {
    const preview = await latinRequest('/api/v2/restores/previews', { method: 'POST', body: JSON.stringify({ write_id: writeId }) });
    const row = preview.items?.[0];
    latinOpenModal({ kicker: 'RESTORE PREVIEW · NO FILES CHANGED', title: 'Restore the original file', body: `<p>This restores the original complete file backup. It proceeds only if the current file still matches the verified post-write checksum.</p><p>Track: ${latinEscape(latinState.items.find(item => item.id === row?.item_id)?.title || 'Track')}</p><p>Current and original checksums are pinned to this preview.</p>`, buttons: [
      { label: 'Cancel', kind: 'quiet', close: true },
      { label: 'Restore original file', kind: 'primary', action: async () => {
        const result = await latinRequest('/api/v2/restores/commit', { method: 'POST', body: JSON.stringify({ preview_id: preview.preview_id, confirm: true }) });
        latinCloseModal(); latinAnnounce(result.outcomes?.every(outcome => outcome.status === 'restored') ? 'Original file restored and verified.' : 'Restore finished with an error; check Activity.', result.outcomes?.every(outcome => outcome.status === 'restored') ? 'info' : 'error');
        await latinLoadLibrary({ reset: true }); await latinLoadBackups();
      } },
    ] });
  } catch (error) { latinAnnounce(`Could not prepare restore. ${error.message}`, 'error'); }
}

function latinOpenAdvanced() {
  document.getElementById('latin-shell').hidden = true;
  latin$('app-content').classList.add('latin-advanced-mode');
  latin$('latin-advanced-banner').hidden = false;
  document.querySelector('.app-body').classList.add('latin-legacy-active');
  window.initializeLegacyApplication?.();
  window.switchTab?.('library');
}

function latinReturnPrimary() {
  latin$('app-content').classList.remove('latin-advanced-mode');
  document.querySelector('.app-body').classList.remove('latin-legacy-active');
  latin$('latin-advanced-banner').hidden = true;
  document.getElementById('latin-shell').hidden = false;
  ['onboarding-overlay', 'onboarding-modal'].forEach(id => { const overlay = document.getElementById(id); if (overlay) { overlay.hidden = true; overlay.style.display = 'none'; overlay.style.pointerEvents = 'none'; overlay.setAttribute('aria-hidden', 'true'); } });
  const workflowGuide = document.getElementById('workflow-guide');
  if (workflowGuide) { workflowGuide.hidden = true; workflowGuide.style.display = 'none'; workflowGuide.style.pointerEvents = 'none'; }
  latinCloseDrawer();
  latinSwitchPage('library');
  latinLoadLibrary({ reset: true });
}

function latinAddCommentChip() {
  latinOpenModal({ kicker: 'PERSONAL COMMENT FILTER', title: 'Add a literal tag filter', body: '<label class="latin-field-label" for="latin-custom-comment">Exact label text</label><input class="latin-input" id="latin-custom-comment" maxlength="80" placeholder="Keep punctuation and commas as typed"><p>Filters existing Comment values. It does not rename, split, or write them.</p>', buttons: [{ label: 'Cancel', kind: 'quiet', close: true }, { label: 'Add filter', kind: 'primary', action: () => {
    const value = latin$('latin-custom-comment').value.trim();
    if (!value) throw new Error('Enter the exact text to filter.');
    if (!latinState.filters.comment_tokens.includes(value)) latinState.filters.comment_tokens.push(value);
    latinCloseModal(); latinFiltersChanged();
  } }] });
}

function latinInit() {
  if (latinState.initialized) return;
  latinState.initialized = true;
  latinLoadSavedViewState();
  latinRenderChips(); latinRenderPriority(); latinRenderRoutes(); latinRenderSavedViews();
  latin$('latin-add-folder').addEventListener('click', latinImportFolder);
  latin$('latin-refresh').addEventListener('click', () => latinLoadLibrary({ reset: true }));
  latin$('latin-search').addEventListener('input', () => {
    clearTimeout(latinState.searchTimer);
    latinState.searchTimer = setTimeout(latinFiltersChanged, 250);
  });
  latin$('latin-family-chips').addEventListener('click', event => {
    const chip = event.target.closest('[data-family]'); if (!chip) return;
    const value = chip.dataset.family; const list = latinState.filters.family_ids;
    latinState.filters.family_ids = list.includes(value) ? list.filter(item => item !== value) : [...list, value];
    latinFiltersChanged();
  });
  latin$('latin-style-chips').addEventListener('click', event => {
    const chip = event.target.closest('[data-style]'); if (!chip) return;
    const value = chip.dataset.style; const list = latinState.filters.style_ids;
    latinState.filters.style_ids = list.includes(value) ? list.filter(item => item !== value) : [...list, value];
    latinFiltersChanged();
  });
  latin$('latin-comment-chips').addEventListener('click', event => {
    const chip = event.target.closest('[data-comment]'); if (!chip) return;
    const value = chip.dataset.comment; const list = latinState.filters.comment_tokens;
    latinState.filters.comment_tokens = list.includes(value) ? list.filter(item => item !== value) : [...list, value];
    latinFiltersChanged();
  });
  latin$('latin-active-filters').addEventListener('click', event => {
    const family = event.target.closest('[data-clear-family]'); const style = event.target.closest('[data-clear-style]'); const comment = event.target.closest('[data-clear-comment]');
    if (family) latinState.filters.family_ids = latinState.filters.family_ids.filter(value => value !== family.dataset.clearFamily);
    if (style) latinState.filters.style_ids = latinState.filters.style_ids.filter(value => value !== style.dataset.clearStyle);
    if (comment) latinState.filters.comment_tokens = latinState.filters.comment_tokens.filter(value => value !== comment.dataset.clearComment);
    latinFiltersChanged();
  });
  latin$('latin-add-comment-chip').addEventListener('click', latinAddCommentChip);
  latin$('latin-save-view').addEventListener('click', latinSaveView);
  latin$('latin-saved-view-select').addEventListener('change', event => {
    const view = latinState.savedViews[Number(event.target.value)]; if (!view) return;
    const definition = view.definition || view;
    latinState.filters = { ...definition.filters }; latinState.sort = definition.sort || 'title:asc';
    latin$('latin-search').value = latinState.filters.query || ''; latinRenderChips(); latinLoadLibrary({ reset: true });
  });
  latin$('latin-filter-toggle').addEventListener('click', () => {
    const area = latin$('latin-filter-area'); area.hidden = !area.hidden;
    latinState.filtersExpandedByUser = !area.hidden;
    latin$('latin-filter-toggle').setAttribute('aria-expanded', String(!area.hidden));
  });
  latin$('latin-library-rows').addEventListener('change', event => {
    const check = event.target.closest('.latin-row-check'); if (!check) return;
    check.checked ? latinState.selected.add(check.dataset.itemId) : latinState.selected.delete(check.dataset.itemId);
    latinRenderSelection();
  });
  latin$('latin-library-rows').addEventListener('click', event => {
    const open = event.target.closest('[data-open-item]'); if (open) latinOpenItem(open.dataset.openItem);
    if (event.target.closest('[data-action="add-folder"]')) latinImportFolder();
    if (event.target.closest('[data-action="bootstrap-library"]')) latinBootstrapLibrary();
    if (event.target.closest('[data-action="clear-filters"]')) { latinState.filters = { query: '', family_ids: [], style_ids: [], comment_tokens: [], review_states: [] }; latin$('latin-search').value = ''; latinFiltersChanged(); }
  });
  latin$('latin-select-visible').addEventListener('click', () => { latinState.items.forEach(item => latinState.selected.add(item.id)); latinRenderLibrary(); });
  latin$('latin-select-all-filtered').addEventListener('click', () => { latinState.allFiltered = true; latinState.selected.clear(); latinRenderLibrary(); latinAnnounce(`${latinState.total} filtered tracks selected. Actions use this frozen filter scope.`); });
  latin$('latin-clear-selection').addEventListener('click', () => { latinState.selected.clear(); latinState.allFiltered = false; latinRenderLibrary(); });
  latin$('latin-page-prev').addEventListener('click', () => { if (!latinState.cursorIndex) return; latinState.cursorIndex--; latinLoadLibrary(); });
  latin$('latin-page-next').addEventListener('click', () => { if (!latinState.nextCursor) return; latinState.cursors[++latinState.cursorIndex] = latinState.nextCursor; latinLoadLibrary(); });
  document.querySelectorAll('.latin-nav-item').forEach(button => button.addEventListener('click', () => latinSwitchPage(button.dataset.page)));
  latin$('latin-review-tabs').addEventListener('click', event => { const tab = event.target.closest('[data-review-state]'); if (!tab) return; latinState.reviewState = tab.dataset.reviewState; latinState.cursorIndex = 0; latinState.cursors = [null]; latin$('latin-review-tabs').querySelectorAll('button').forEach(btn => btn.classList.toggle('active', btn === tab)); latinState.selected.clear(); latinRenderReview(); });
  latin$('latin-review-rows').addEventListener('click', event => {
    const open = event.target.closest('[data-open-item]'); if (open) latinOpenItem(open.dataset.openItem);
    const action = event.target.closest('[data-decision]');
    if (action?.dataset.decision === 'accept') latinOpenReviewPreview([action.dataset.itemId]);
    if (action?.dataset.decision === 'correct') latinOpenCorrection(action.dataset.itemId);
  });
  latin$('latin-review-rows').addEventListener('change', event => { const check = event.target.closest('.latin-review-check'); if (!check) return; check.checked ? latinState.selected.add(check.dataset.itemId) : latinState.selected.delete(check.dataset.itemId); latinRenderSelection(); });
  latin$('latin-review-approve').addEventListener('click', () => latinOpenReviewPreview([...latinState.selected]));
  latin$('latin-review-clear').addEventListener('click', () => { latinState.selected.clear(); latinRenderReview(); });
  latin$('latin-review-prev').addEventListener('click', () => { if (latinState.cursorIndex) latinState.cursorIndex--; latinRenderReview(); });
  latin$('latin-review-next').addEventListener('click', () => { if (latinState.nextCursor) { latinState.cursors[++latinState.cursorIndex] = latinState.nextCursor; latinRenderReview(); } });
  latin$('latin-job-rows').addEventListener('click', event => { const detail = event.target.closest('[data-job-details]'); if (detail) latinOpenJobDetails(detail.dataset.jobDetails); const button = event.target.closest('[data-job-action]'); if (button) latinActOnJob(button.dataset.jobId, button.dataset.jobAction); });
  latin$('latin-model-actions').addEventListener('click', event => { const button = event.target.closest('[data-model-action]'); if (button) latinStartModelAction(button.dataset.modelAction); });
  latin$('latin-restore-list').addEventListener('click', event => { const button = event.target.closest('[data-restore-preview]'); if (button) latinPreviewRestore(button.dataset.restorePreview); });
  latin$('latin-batch-review').addEventListener('click', () => latinOpenReviewPreview([...latinState.selected]));
  latin$('latin-batch-classify').addEventListener('click', async () => {
    const scope = latinState.allFiltered ? { filter: structuredClone(latinState.filters), selection: 'all_filtered' } : { item_ids: [...latinState.selected], selection: 'explicit' };
    if (!scope.item_ids?.length && !scope.filter) return latinAnnounce('Select tracks or choose all filtered tracks first.', 'error');
    try { await latinStartJob('classify', scope); }
    catch (error) { latinAnnounce(`Audio classification did not start. ${error.message}`, 'error'); }
  });
  latin$('latin-batch-edit').addEventListener('click', () => latinOpenBatchEdit(latinState.allFiltered ? { filter: structuredClone(latinState.filters), selection: 'all_filtered' } : [...latinState.selected]));
  latin$('latin-batch-catalogue').addEventListener('click', () => latinOpenCatalogueTags());
  latin$('latin-batch-export').addEventListener('click', () => { latinState.exportScope = latinState.allFiltered ? { filter: structuredClone(latinState.filters) } : { item_ids: [...latinState.selected] }; latinSwitchPage('export'); });
  latin$('latin-export-change-scope').addEventListener('click', () => latinSwitchPage('library'));
  latin$('latin-export-routes').addEventListener('change', event => { if (event.target.name === 'latin-export-route') latinState.selectedRoute = event.target.value; });
  latin$('latin-export-pick-destination').addEventListener('click', async () => {
    try { const result = await latinRequest('/api/pick-folder'); latinState.destination = result.path || result.folder || ''; latin$('latin-export-destination').value = latinState.destination; }
    catch (error) { latinAnnounce(`Destination picker unavailable. ${error.message}`, 'error'); }
  });
  latin$('latin-export-preview').addEventListener('click', latinPreviewExport);
  latin$('latin-export-preview-card').addEventListener('click', event => { const commit = event.target.closest('[data-commit-export]'); if (commit) latinCommitExport(commit.dataset.commitExport, commit.dataset.replaceKnown === 'true'); if (event.target.closest('[data-close-export-preview]')) latin$('latin-export-preview-card').hidden = true; });
  latin$('latin-export-history').addEventListener('click', event => { const control = event.target.closest('[data-export-transfer]'); if (control) latinRecordExportTransfer(control.dataset.exportTransfer, control.dataset.transferState); });
  latin$('latin-category-add').addEventListener('click', () => latinOpenModal({ kicker: 'PERSONAL VOCABULARY', title: 'Add a label', body: '<label class="latin-field-label" for="latin-label-name">Exact label text</label><input class="latin-input" id="latin-label-name" maxlength="80"><label class="latin-field-label" for="latin-label-axis">Axis</label><select id="latin-label-axis" class="latin-select full"><option value="music_family">Genre</option><option value="style">Style</option><option value="dance_use">Dance use</option><option value="production">Version</option><option value="vocal_presence">Vocals</option><option value="vocal_language">Language</option><option value="instrument_cue">Instruments</option></select><p>This adds vocabulary. It does not enable audio recognition.</p>', buttons: [{ label: 'Cancel', kind: 'quiet', close: true }, { label: 'Save vocabulary', kind: 'primary', action: async () => {
    const label = latin$('latin-label-name').value.trim(); const axis = latin$('latin-label-axis').value;
    if (!label) throw new Error('Enter a label.');
    const updated = structuredClone(latinState.taxonomy || { version: 1, labels: [], palette: { raw_comment_tokens: [] }, auto_approval: { enabled: false } });
    updated.labels ||= [];
    if (updated.labels.some(entry => entry.axis === axis && entry.display_name.toLocaleLowerCase() === label.toLocaleLowerCase())) throw new Error('That label already exists on this axis.');
    const slug = label.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
    updated.labels.push({ id: `${axis}_${slug || crypto.randomUUID()}`, display_name: label, axis, status: 'vocabulary_only', aliases: [] });
    await latinRequest('/api/v2/taxonomy', { method: 'PUT', body: JSON.stringify({ document: updated, expected_revision: latinState.taxonomyRevision }) });
    latinCloseModal(); latinAnnounce('Vocabulary saved. Model recognition remains unenabled.'); await latinLoadTaxonomy();
  } }] }));
  latin$('latin-category-import').addEventListener('click', () => latin$('latin-taxonomy-file').click());
  latin$('latin-taxonomy-file').addEventListener('change', async event => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    try {
      const imported = JSON.parse(await file.text());
      const tokens = Array.isArray(imported) ? imported : imported?.raw_comment_tokens;
      if (!Array.isArray(tokens) || tokens.some(token => typeof token !== 'string' || !token.trim())) throw new Error('Choose a JSON array of exact tag strings or an object with a raw_comment_tokens array. Commas and punctuation are kept literal.');
      const updated = structuredClone(latinState.taxonomy || { version: 1, labels: [], palette: {}, auto_approval: { enabled: false } });
      updated.palette ||= {};
      updated.palette.raw_comment_tokens = [...new Set([...(updated.palette.raw_comment_tokens || []), ...tokens])];
      await latinRequest('/api/v2/taxonomy', { method: 'PUT', body: JSON.stringify({ document: updated, expected_revision: latinState.taxonomyRevision }) });
      latinAnnounce(`Imported ${tokens.length} literal comment labels.`);
      await latinLoadTaxonomy();
    } catch (error) { latinAnnounce(`Labels were not imported. ${error.message}`, 'error'); }
  });
  latin$('latin-open-advanced').addEventListener('click', latinOpenAdvanced); latin$('latin-footer-advanced').addEventListener('click', latinOpenAdvanced); latin$('latin-open-legacy-settings').addEventListener('click', () => { latinOpenAdvanced(); window.switchTab?.('settings'); });
  latin$('latin-return-primary').addEventListener('click', latinReturnPrimary);
  latin$('latin-drawer-close').addEventListener('click', latinCloseDrawer); latin$('latin-drawer-overlay').addEventListener('click', latinCloseDrawer);
  latin$('latin-drawer-body').addEventListener('click', event => {
    const play = event.target.closest('[data-drawer-play]');
    if (play && play.dataset.drawerPlay) {
      latinPlayItem(latinState.activeItem);
    }
    const review = event.target.closest('[data-drawer-review]'); if (review) latinOpenReviewPreview([review.dataset.drawerReview]);
    const lock = event.target.closest('[data-lock-axis]');
    if (lock) latinChangeLock(latinState.activeItem, lock.dataset.lockAxis, lock.dataset.lockAction);
    const saveTags = event.target.closest('[data-drawer-save-tags]');
    if (saveTags) latinSaveDrawerCatalogueTags(saveTags.dataset.drawerSaveTags).catch(error => latinAnnounce(`Could not save catalogue tags. ${error.message}`, 'error'));
    const saveTagsNext = event.target.closest('[data-drawer-save-tags-next]');
    if (saveTagsNext) latinSaveDrawerCatalogueTags(saveTagsNext.dataset.drawerSaveTagsNext, true).catch(error => latinAnnounce(`Could not save catalogue tags. ${error.message}`, 'error'));
    const evidence = event.target.closest('[data-audition-at]');
    if (evidence) latinPlayAt(Number(evidence.dataset.auditionAt));
  });
  latin$('latin-modal-close').addEventListener('click', latinCloseModal);
  latin$('latin-modal-backdrop').addEventListener('click', event => { if (event.target.id === 'latin-modal-backdrop') latinCloseModal(); const button = event.target.closest('[data-modal-action]'); if (button) latinHandleModalAction(Number(button.dataset.modalAction)); });
  latin$('latin-modal-body').addEventListener('click', event => {
    const item = event.target.closest('[data-job-item-open]');
    if (item) { latinCloseModal(); latinOpenItem(item.dataset.jobItemOpen); return; }
    const page = event.target.closest('[data-job-page]');
    if (page && !page.disabled) latinOpenJobDetails(page.dataset.jobPage, page.dataset.jobCursor || null);
  });
  document.addEventListener('keydown', event => {
    const modalOpen = !latin$('latin-modal-backdrop').hidden;
    if (event.key === 'Escape') { if (modalOpen) latinCloseModal(); else if (!latin$('latin-track-drawer').hidden) latinCloseDrawer(); return; }
    const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName) || document.activeElement?.isContentEditable;
    if (!typing && !modalOpen && event.key === '?') { event.preventDefault(); latinShowShortcuts(); }
    if (!typing && !modalOpen && event.key === '/') { event.preventDefault(); latin$('latin-search').focus(); }
    if (!typing && !modalOpen && event.key === 'j') latinMoveSelection(1);
    if (!typing && !modalOpen && event.key === 'k') latinMoveSelection(-1);
    if (!typing && !modalOpen && event.ctrlKey && event.key === 'Enter' && latinState.activeItem && !latin$('latin-track-drawer').hidden) { event.preventDefault(); latinSaveDrawerCatalogueTags(latinState.activeItem.id, true).catch(error => latinAnnounce(`Could not save catalogue tags. ${error.message}`, 'error')); }
    if (!typing && !modalOpen && event.code === 'Space' && latinState.activeItem) { event.preventDefault(); latin$('audio-play-pause').click(); }
  });
  latin$('latin-help-shortcuts').addEventListener('click', latinShowShortcuts);
  document.addEventListener('click', event => {
    const retry = event.target.closest('[data-retry]');
    if (!retry) return;
    if (retry.dataset.retry === 'library') latinLoadLibrary({ reset: true });
    if (retry.dataset.retry === 'review') latinRenderReview();
    if (retry.dataset.retry === 'taxonomy') latinLoadTaxonomy();
  });
  latinLoadSavedViews();
  latin$('latin-text-scale').addEventListener('change', event => { document.documentElement.style.setProperty('--latin-scale', event.target.value); localStorage.setItem('latin-scale', event.target.value); latinSaveSettings({ text_scale: Number(event.target.value) }); });
  latin$('latin-reduced-motion').addEventListener('change', event => { document.body.classList.toggle('latin-reduced-motion', event.target.checked); latinSaveSettings({ reduced_motion: event.target.checked }); });
  latin$('latin-theme').addEventListener('change', event => { document.body.classList.toggle('light', event.target.value === 'light'); document.documentElement.dataset.theme = event.target.value; latinSaveSettings({ theme: event.target.value }); });
  latinRenderRoutes();
  latinLoadTaxonomy();
  latinLoadMigrationStatus();
  latinLoadLibrary({ reset: true });
  latinLoadCapabilities();
  latinAdaptFiltersToViewport();
  window.addEventListener('resize', latinAdaptFiltersToViewport);
  const savedScale = localStorage.getItem('latin-scale');
  if (savedScale) { latin$('latin-text-scale').value = savedScale; document.documentElement.style.setProperty('--latin-scale', savedScale); }
  document.addEventListener('click', event => {
    const control = event.target.closest('#audio-prev, #audio-next');
    if (!control || !latin$('app-content').classList.contains('latin-shell-active') || latin$('app-content').classList.contains('latin-advanced-mode')) return;
    event.preventDefault(); event.stopImmediatePropagation();
    const index = latinState.items.findIndex(item => item.id === latinState.activeItem?.id);
    const delta = control.id === 'audio-next' ? 1 : -1;
    const next = latinState.items[Math.max(0, Math.min(latinState.items.length - 1, (index < 0 ? 0 : index) + delta))];
    if (next) latinOpenItem(next.id).then(() => latinPlayItem(latinState.activeItem));
  }, true);
}

function latinMoveSelection(offset) {
  const current = latinState.items.findIndex(item => item.id === latinState.activeItem?.id);
  const next = latinState.items[Math.max(0, Math.min(latinState.items.length - 1, (current < 0 ? 0 : current) + offset))];
  if (next) latinOpenItem(next.id);
}

function latinShowShortcuts() {
  latinOpenModal({ kicker: 'KEYBOARD HELP', title: 'Move through your library', body: '<div class="latin-shortcut-grid"><span><kbd>/</kbd> Focus search</span><span><kbd>J</kbd> Next track</span><span><kbd>K</kbd> Previous track</span><span><kbd>Space</kbd> Play or pause selected track</span><span><kbd>Enter</kbd> Open focused track</span><span><kbd>Esc</kbd> Close dialog or inspector</span><span><kbd>?</kbd> Open this guide</span></div><p>Shortcuts are ignored while typing or editing a modal.</p>', buttons: [{ label: 'Done', kind: 'primary', close: true }] });
}

window.initLatinRedesign = latinInit;
