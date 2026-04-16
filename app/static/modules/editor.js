// ============================================================================
// Edit Modal
// ============================================================================

function initEditModal() {
  const modal = document.getElementById('edit-modal');
  const addGenreModal = document.getElementById('add-genre-modal');
  const closeBtn = document.getElementById('modal-close');
  const addGenreCloseBtn = document.getElementById('add-genre-close');
  const cancelBtn = document.getElementById('modal-cancel');
  const addGenreCancelBtn = document.getElementById('add-genre-cancel');
  const saveBtn = document.getElementById('modal-save');
  const addGenreSaveBtn = document.getElementById('add-genre-save');

  closeBtn.addEventListener('click', () => {
    modal.style.display = 'none';
  });

  addGenreCloseBtn.addEventListener('click', () => {
    addGenreModal.style.display = 'none';
  });

  cancelBtn.addEventListener('click', () => {
    modal.style.display = 'none';
  });

  addGenreCancelBtn.addEventListener('click', () => {
    addGenreModal.style.display = 'none';
  });

  saveBtn.addEventListener('click', saveTrackEdits);
  addGenreSaveBtn.addEventListener('click', addNewGenre);

  // Close on background click
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.style.display = 'none';
    }
  });

  addGenreModal.addEventListener('click', (e) => {
    if (e.target === addGenreModal) {
      addGenreModal.style.display = 'none';
    }
  });

  // Close modals with Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (modal.style.display !== 'none') modal.style.display = 'none';
      if (addGenreModal.style.display !== 'none') addGenreModal.style.display = 'none';
    }
  });
}

function openEditModal(filePath) {
  const track = window.tracks.find(t => t.file_path === filePath);
  if (!track) return;

  currentEditPath = filePath;

  // Populate current info
  document.getElementById('modal-title').textContent = track.display_title || track.filename;
  document.getElementById('modal-artist').textContent = track.display_artist || 'Unknown';
  document.getElementById('modal-filename').textContent = track.filename;

  // Populate editable fields
  document.getElementById('modal-genre').value = track.final_genre || '';
  document.getElementById('modal-bpm').value = track.final_bpm || '';
  document.getElementById('modal-key').value = track.final_key || '';
  document.getElementById('modal-year').value = track.final_year || '';
  document.getElementById('modal-comment').value = track.final_comment || '';

  // Populate genre options
  const genreSelect = document.getElementById('modal-genre');
  genreSelect.innerHTML = '';
  const optionDefault = document.createElement('option');
  optionDefault.value = '';
  optionDefault.textContent = 'Select Genre';
  genreSelect.appendChild(optionDefault);

  Object.keys(window.taxonomy).forEach(genre => {
    const option = document.createElement('option');
    option.value = genre;
    option.textContent = genre;
    genreSelect.appendChild(option);
  });
  genreSelect.value = track.final_genre || '';

  // Populate subgenre options based on selected genre
  updateSubgenreOptions();
  // Replace the select element to remove any previously attached listeners (prevent leak)
  const oldGenreSelect = document.getElementById('modal-genre');
  const newGenreSelect = oldGenreSelect.cloneNode(true);
  oldGenreSelect.parentNode.replaceChild(newGenreSelect, oldGenreSelect);
  newGenreSelect.addEventListener('change', updateSubgenreOptions);

  // Populate analysis results
  document.getElementById('modal-analyzed-bpm').textContent = track.analyzed_bpm
    ? Math.round(track.analyzed_bpm)
    : '—';
  document.getElementById('modal-energy').textContent = track.analyzed_energy
    ? `${track.analyzed_energy}/10`
    : '—';
  document.getElementById('modal-confidence').textContent = track.confidence
    ? `${Math.round(track.confidence)}%`
    : '—';
  document.getElementById('modal-reasoning').textContent = track.reasoning || 'N/A';

  // Render Camelot wheel
  createCamelotWheel(track.final_key || '');

  document.getElementById('edit-modal').style.display = 'flex';
}

function updateSubgenreOptions() {
  const genreSelect = document.getElementById('modal-genre');
  const subgenreSelect = document.getElementById('modal-subgenre');
  const selectedGenre = genreSelect.value;

  subgenreSelect.innerHTML = '';
  const optionDefault = document.createElement('option');
  optionDefault.value = '';
  optionDefault.textContent = 'Select Comment';
  subgenreSelect.appendChild(optionDefault);

  if (selectedGenre && window.taxonomy[selectedGenre]) {
    const subgenres = window.taxonomy[selectedGenre].subgenres || [];
    subgenres.forEach(sub => {
      const option = document.createElement('option');
      option.value = sub;
      option.textContent = sub;
      subgenreSelect.appendChild(option);
    });
  }

  // Restore current value if available
  const track = window.tracks.find(t => t.file_path === currentEditPath);
  if (track && track.final_subgenre) {
    subgenreSelect.value = track.final_subgenre;
  }
}

async function saveTrackEdits() {
  if (!currentEditPath) return;

  const override = {
    override_genre: document.getElementById('modal-genre').value || undefined,
    override_subgenre: document.getElementById('modal-subgenre').value || undefined,
    override_bpm: document.getElementById('modal-bpm').value || undefined,
    override_key: document.getElementById('modal-key').value || undefined,
    override_year: document.getElementById('modal-year').value || undefined,
    override_comment: document.getElementById('modal-comment').value || undefined,
  };

  showSpinner('Saving changes...');
  try {
    const result = await apiFetch(`/api/tracks/by-path?path=${encodeURIComponent(currentEditPath)}`, {
      method: 'PUT',
      body: JSON.stringify(override),
    });

    const track = window.tracks.find(t => t.file_path === currentEditPath);
    if (track) {
      Object.assign(track, result);
    }

    showToast('Track updated', 'success');
    renderTracks();
    renderReview();

    document.getElementById('edit-modal').style.display = 'none';
  } catch (error) {
    // Error shown
  } finally {
    hideSpinner();
  }
}

function addNewGenre() {
  const name = document.getElementById('new-genre-name').value.trim();
  const description = document.getElementById('new-genre-description').value.trim();

  if (!name) {
    showToast('Genre name required', 'error');
    return;
  }

  window.taxonomy[name] = {
    description: description,
    subgenres: [],
  };

  showToast(`Added genre: ${name}`, 'success');
  renderTaxonomy();

  document.getElementById('add-genre-modal').style.display = 'none';
  document.getElementById('new-genre-name').value = '';
  document.getElementById('new-genre-description').value = '';
}

