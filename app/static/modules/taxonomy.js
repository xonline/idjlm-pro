// ============================================================================
// Taxonomy Tab
// ============================================================================

function initTaxonomyTab() {
  const btnAddGenre = document.getElementById('btn-add-genre');
  const btnSaveTaxonomy = document.getElementById('btn-save-taxonomy');

  btnAddGenre.addEventListener('click', () => {
    showAddGenreModal();
  });

  if (btnSaveTaxonomy) {
    btnSaveTaxonomy.addEventListener('click', async () => {
      showSpinner('Saving taxonomy...');
      try {
        await apiFetch('/api/taxonomy', {
          method: 'PUT',
          body: JSON.stringify({ genres: window.taxonomy }),
        });
        showToast('Taxonomy saved', 'success');
      } catch (error) {
        // Error shown
      } finally {
        hideSpinner();
      }
    });
  }

  // Taxonomy export
  const btnExportTaxonomy = document.getElementById('btn-export-taxonomy');
  if (btnExportTaxonomy) {
    btnExportTaxonomy.addEventListener('click', () => {
      window.open('/api/taxonomy/export', '_blank');
      showToast('Downloading taxonomy...', 'info');
    });
  }

  // Taxonomy import
  const btnImportTaxonomy = document.getElementById('btn-import-taxonomy');
  const fileInput = document.getElementById('taxonomy-file-input');
  if (btnImportTaxonomy && fileInput) {
    btnImportTaxonomy.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const text = await file.text();
        const json = JSON.parse(text);
        // Validate
        if (typeof json !== 'object' || Array.isArray(json)) {
          showToast('Invalid taxonomy file: must be a JSON object', 'error');
          fileInput.value = '';
          return;
        }
        const genreCount = Object.keys(json).length;
        let subCount = 0;
        Object.values(json).forEach(v => {
          if (v && typeof v === 'object') {
            const subs = v.subgenres || [];
            subCount += Array.isArray(subs) ? subs.length : Object.keys(subs).length;
          }
        });
        if (confirm('This will add ' + genreCount + ' genres and ' + subCount + ' subgenres to your current taxonomy (merge mode). Continue?')) {
          showSpinner('Importing taxonomy...');
          try {
            const result = await apiFetch('/api/taxonomy/import', {
              method: 'POST',
              body: JSON.stringify({ taxonomy: json, merge: true })
            });
            if (result && result.ok) {
              window.taxonomy = result.taxonomy || {};
              renderTaxonomy();
              showToast('Imported ' + (result.added_genres || []).length + ' genres and ' + (result.added_subgenres || 0) + ' subgenres', 'success');
            }
          } catch (err) {
            showToast('Import failed: ' + err.message, 'error');
          } finally {
            hideSpinner();
          }
        }
      } catch (err) {
        showToast('Invalid JSON file: ' + err.message, 'error');
      }
      fileInput.value = '';
    });
  }

  // OneTagger import
  const btnImportOneTagger = document.getElementById('btn-import-onetagger');
  const onetaggerFileInput = document.getElementById('onetagger-file-input');
  if (btnImportOneTagger && onetaggerFileInput) {
    btnImportOneTagger.addEventListener('click', () => onetaggerFileInput.click());
    onetaggerFileInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const text = await file.text();
        const json = JSON.parse(text);
        // OneTagger settings.json is a large object — check it has genre mappings
        const hasGenreMappings = json.genre || json.subgenre;
        if (!hasGenreMappings) {
          showToast('No genre mappings found in this OneTagger settings file', 'error');
          onetaggerFileInput.value = '';
          return;
        }
        // Count mappings for preview
        let genreCount = 0, subCount = 0;
        if (json.genre) genreCount = Object.keys(json.genre).length;
        if (json.subgenre) subCount = Object.keys(json.subgenre).length;
        const totalMappings = genreCount + subCount;
        if (confirm('This will import ' + totalMappings + ' genre mappings from OneTagger into your taxonomy (merge mode). Continue?')) {
          showSpinner('Importing OneTagger mappings...');
          try {
            const result = await apiFetch('/api/taxonomy/import-onetagger', {
              method: 'POST',
              body: JSON.stringify({ settings: json, merge: true })
            });
            if (result && result.ok) {
              window.taxonomy = result.taxonomy.genres || {};
              renderTaxonomy();
              showToast('Imported ' + result.genres_added + ' genres and ' + result.subgenres_added + ' subgenres from OneTagger', 'success');
            }
          } catch (err) {
            showToast('Import failed: ' + err.message, 'error');
          } finally {
            hideSpinner();
          }
        }
      } catch (err) {
        showToast('Invalid JSON file: ' + err.message, 'error');
      }
      onetaggerFileInput.value = '';
    });
  }

  // Taxonomy templates
  loadTaxonomyTemplates();

  const btnApplyTemplate = document.getElementById('btn-apply-template');
  if (btnApplyTemplate) {
    btnApplyTemplate.addEventListener('click', applySelectedTemplate);
  }

  loadTaxonomy();
}

async function loadTaxonomy() {
  try {
    const data = await apiFetch('/api/taxonomy');
    window.taxonomy = data.genres || {};
    renderTaxonomy();
  } catch (error) {
    // Error shown
  }
}

function renderTaxonomy() {
  const list = document.getElementById('taxonomy-list');
  list.innerHTML = '';

  if (!Object.keys(window.taxonomy).length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'No genres defined. Add one to get started.';
    list.appendChild(empty);
    return;
  }

  Object.entries(window.taxonomy).forEach(([genre, data]) => {
    const genreEl = document.createElement('div');
    genreEl.className = 'taxonomy-genre';

    // Header
    const header = document.createElement('div');
    header.className = 'taxonomy-genre-header';
    header.addEventListener('click', () => toggleGenre(header));

    const textDiv = document.createElement('div');
    const titleDiv = document.createElement('div');
    titleDiv.className = 'taxonomy-genre-title';
    titleDiv.textContent = genre;
    textDiv.appendChild(titleDiv);

    const descDiv = document.createElement('div');
    descDiv.className = 'taxonomy-genre-desc';
    descDiv.textContent = data.description || '';
    textDiv.appendChild(descDiv);
    header.appendChild(textDiv);

    const rightDiv = document.createElement('div');
    rightDiv.style.display = 'flex';
    rightDiv.style.gap = '12px';
    rightDiv.style.alignItems = 'center';

    const countDiv = document.createElement('span');
    countDiv.style.color = '#888';
    countDiv.style.fontSize = '12px';
    const subgenres = data.subgenres || [];
    countDiv.textContent = `${subgenres.length} comment${subgenres.length !== 1 ? 's' : ''}`;
    rightDiv.appendChild(countDiv);

    const toggleDiv = document.createElement('span');
    toggleDiv.className = 'taxonomy-toggle';
    toggleDiv.textContent = '▼';
    rightDiv.appendChild(toggleDiv);

    header.appendChild(rightDiv);
    genreEl.appendChild(header);

    // Subgenres container
    const subgenresDiv = document.createElement('div');
    subgenresDiv.className = 'taxonomy-subgenres';

    subgenres.forEach((sub, idx) => {
      const subEl = document.createElement('div');
      subEl.className = 'taxonomy-subgenre';

      const span = document.createElement('span');
      span.textContent = sub;
      subEl.appendChild(span);

      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'taxonomy-actions';

      const btnDel = document.createElement('button');
      btnDel.className = 'btn btn-secondary';
      btnDel.textContent = 'Delete';
      btnDel.addEventListener('click', () => removeSubgenre(genre, idx));
      actionsDiv.appendChild(btnDel);

      subEl.appendChild(actionsDiv);
      subgenresDiv.appendChild(subEl);
    });

    const addBtn = document.createElement('button');
    addBtn.className = 'btn btn-primary';
    addBtn.style.width = '100%';
    addBtn.style.marginTop = '10px';
    addBtn.textContent = '+ Add Comment';
    addBtn.addEventListener('click', () => addSubgenreForm(genre));
    subgenresDiv.appendChild(addBtn);

    genreEl.appendChild(subgenresDiv);
    list.appendChild(genreEl);
  });
}

function toggleGenre(header) {
  const subgenres = header.nextElementSibling;
  const toggle = header.querySelector('.taxonomy-toggle');

  subgenres.classList.toggle('open');
  toggle.classList.toggle('open');
}

function addSubgenreForm(genre) {
  const name = prompt(`Add comment to ${genre}:`);
  if (name) {
    if (!window.taxonomy[genre].subgenres) {
      window.taxonomy[genre].subgenres = [];
    }
    window.taxonomy[genre].subgenres.push(name);
    renderTaxonomy();
  }
}

function removeSubgenre(genre, idx) {
  if (confirm('Remove this comment?')) {
    window.taxonomy[genre].subgenres.splice(idx, 1);
    renderTaxonomy();
  }
}

function showAddGenreModal() {
  document.getElementById('add-genre-modal').style.display = 'flex';
  document.getElementById('new-genre-name').focus();
}

// ============================================================================
// Taxonomy Templates
// ============================================================================

async function loadTaxonomyTemplates() {
  try {
    const data = await apiFetch('/api/taxonomy/templates');
    const select = document.getElementById('taxonomy-template-select');
    if (!select) return;

    // Clear existing options except first
    select.innerHTML = '<option value="">Apply Template...</option>';

    Object.entries(data).forEach(([name, info]) => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name + ' (' + info.genre_count + ' genres, ' + info.subgenre_count + ' subgenres)';
      select.appendChild(opt);
    });

    select.addEventListener('change', () => {
      const btn = document.getElementById('btn-apply-template');
      if (btn) btn.disabled = !select.value;
      showTemplatePreview(select.value);
    });
  } catch (e) {
    // Templates unavailable
  }
}

async function showTemplatePreview(templateName) {
  const preview = document.getElementById('template-preview');
  if (!preview) return;

  if (!templateName) {
    preview.style.display = 'none';
    preview.innerHTML = '';
    return;
  }

  try {
    const templates = await apiFetch('/api/taxonomy/templates');
    const info = templates[templateName];
    if (!info) {
      preview.style.display = 'none';
      return;
    }

    let genreTags = '';
    (info.genres || []).forEach(g => {
      genreTags += '<span class="template-genre-tag">' + escapeHtml(g) + '</span>';
    });

    preview.innerHTML =
      '<h5>' + escapeHtml(templateName) + '</h5>' +
      '<p>This will add ' + info.genre_count + ' genre' + (info.genre_count !== 1 ? 's' : '') +
      ' and ' + info.subgenre_count + ' subgenre' + (info.subgenre_count !== 1 ? 's' : '') +
      ' to your current taxonomy (merge mode). Existing items will not be removed.</p>' +
      '<div class="template-preview-genres">' + genreTags + '</div>' +
      '<div class="template-preview-actions">' +
      '<button class="btn btn-primary btn-sm" id="btn-confirm-template">Apply Template</button>' +
      '<button class="btn btn-secondary btn-sm" id="btn-cancel-template">Cancel</button>' +
      '</div>';

    preview.style.display = 'block';

    // Bind confirm
    const confirmBtn = document.getElementById('btn-confirm-template');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', () => applyTemplate(templateName));
    }

    // Bind cancel
    const cancelBtn = document.getElementById('btn-cancel-template');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        document.getElementById('taxonomy-template-select').value = '';
        preview.style.display = 'none';
        preview.innerHTML = '';
        const btn = document.getElementById('btn-apply-template');
        if (btn) btn.disabled = true;
      });
    }
  } catch (e) {
    preview.style.display = 'none';
  }
}

async function applyTemplate(templateName) {
  if (!templateName) return;

  showSpinner('Applying template...');
  try {
    const result = await apiFetch('/api/taxonomy/templates/' + encodeURIComponent(templateName) + '/apply', {
      method: 'POST',
      body: JSON.stringify({ merge: true })
    });
    if (result && result.ok) {
      window.taxonomy = result.taxonomy || {};
      renderTaxonomy();
      showToast('Applied template: ' + (result.added_genres || []).length + ' genres and ' + (result.added_subgenres || 0) + ' subgenres added', 'success');
      // Reset preview
      const preview = document.getElementById('template-preview');
      if (preview) {
        preview.style.display = 'none';
        preview.innerHTML = '';
      }
      document.getElementById('taxonomy-template-select').value = '';
      const btn = document.getElementById('btn-apply-template');
      if (btn) btn.disabled = true;
    }
  } catch (e) {
    showToast('Failed to apply template: ' + e.message, 'error');
  } finally {
    hideSpinner();
  }
}

async function applySelectedTemplate() {
  const select = document.getElementById('taxonomy-template-select');
  if (select && select.value) {
    await applyTemplate(select.value);
  }
}

