// Text search with debounce — server-side
function initSearchFeature() {
  const searchInput = document.getElementById('search-tracks');
  const searchClearBtn = document.getElementById('search-clear');

  if (!searchInput) return;

  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchDebounceTimer);
    const query = e.target.value;

    // Show/hide clear button
    if (searchClearBtn) {
      searchClearBtn.style.display = query ? 'block' : 'none';
    }

    searchDebounceTimer = setTimeout(async () => {
      const trimmed = query.trim();
      if (!trimmed) {
        // Empty query: clear search results, fall back to all tracks
        window.searchResults = null;
        renderTracks();
        return;
      }

      // Show searching indicator
      const searchLabel = searchInput.placeholder;
      searchInput.placeholder = 'Searching...';

      try {
        const data = await apiFetch('/api/tracks/search?q=' + encodeURIComponent(trimmed));
        window.searchResults = data.tracks || [];
        renderTracks();
      } catch (err) {
        // On error, fall back to all tracks
        window.searchResults = null;
        renderTracks();
      } finally {
        searchInput.placeholder = searchLabel || 'Search tracks...';
      }
    }, 300);
  });

  if (searchClearBtn) {
    searchClearBtn.addEventListener('click', () => {
      searchInput.value = '';
      window.searchResults = null;
      renderTracks();
      if (searchClearBtn) searchClearBtn.style.display = 'none';
    });
  }
}

