// ============================================================================
// Collection filter chips — one-click Genre/Year/Status/Key filters above table
// Rekordbox pattern: clickable pills, combinable, computed from library data
// ============================================================================

// Active chip filters: Set of "category:value" strings
// e.g. "genre:Salsa", "year:2023", "status:approved", "key:8B"
// Now lives in store.state.activeChips

function initFilterChips() {
}

function updateFilterChips() {
  const tracks = store.state.tracks || [];
  if (!tracks.length) {
    document.querySelectorAll('.chip-group-items').forEach(el => el.innerHTML = '');
    return;
  }

  const chips = {
    genre: computeChipValues(tracks, 'final_genre'),
    year: computeChipValues(tracks, 'final_year'),
    status: computeChipValues(tracks, 'review_status'),
    key: computeChipValues(tracks, 'final_key'),
  };

  // Status has a natural order
  const statusOrder = ['pending', 'approved', 'skipped', 'written'];
  chips.status.sort((a, b) => {
    const ai = statusOrder.indexOf(a.value);
    const bi = statusOrder.indexOf(b.value);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  // Years descending
  chips.year.sort((a, b) => {
    const an = parseInt(a.value) || 0;
    const bn = parseInt(b.value) || 0;
    return bn - an;
  });

  // Keys: sort by Camelot number then mode
  chips.key.sort((a, b) => {
    const am = a.value.match(/^(\d+)([AB])$/i);
    const bm = b.value.match(/^(\d+)([AB])$/i);
    if (am && bm) {
      const diff = parseInt(am[1]) - parseInt(bm[1]);
      if (diff !== 0) return diff;
      return am[2].localeCompare(bm[2]);
    }
    if (am) return -1;
    if (bm) return 1;
    return a.value.localeCompare(b.value);
  });

  renderChipGroup('genre', chips.genre);
  renderChipGroup('year', chips.year);
  renderChipGroup('status', chips.status);
  renderChipGroup('key', chips.key);

  const bar = document.getElementById('filter-chips-bar');
  if (bar) {
    bar.style.display = tracks.length > 0 ? 'flex' : 'none';
  }
}

function computeChipValues(tracks, field) {
  const countMap = new Map();
  tracks.forEach(t => {
    const val = t[field];
    if (val && String(val).trim()) {
      const key = String(val).trim();
      countMap.set(key, (countMap.get(key) || 0) + 1);
    }
  });
  return Array.from(countMap.entries()).map(([value, count]) => ({ value, count }));
}

function renderChipGroup(group, values) {
  const container = document.getElementById('chip-group-' + group);
  if (!container) return;
  container.innerHTML = '';

  values.forEach(({ value, count }) => {
    const chip = document.createElement('button');
    chip.className = 'filter-chip';
    chip.dataset.group = group;
    chip.dataset.value = value;

    const label = document.createElement('span');
    label.className = 'filter-chip-label';
    label.textContent = value;
    chip.appendChild(label);

    const badge = document.createElement('span');
    badge.className = 'filter-chip-count';
    badge.textContent = count;
    chip.appendChild(badge);

    if (store.state.activeChips.has(group + ':' + value)) {
      chip.classList.add('active');
    }

    chip.addEventListener('click', () => {
      toggleChip(chip, group, value);
    });

    container.appendChild(chip);
  });
}

function toggleChip(chip, group, value) {
  const key = group + ':' + value;
  if (store.state.activeChips.has(key)) {
    store.state.activeChips.delete(key);
    chip.classList.remove('active');
  } else {
    store.state.activeChips.add(key);
    chip.classList.add('active');
  }
  store.notify('activeChips');
}


// --- ES module bridge (0.4): expose to global scope for cross-module calls ---
window.initFilterChips = initFilterChips;
window.updateFilterChips = updateFilterChips;
