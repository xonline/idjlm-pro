// ============================================================================
// Loading States — Skeleton Rows & Empty States
// ============================================================================

/**
 * Show skeleton loading rows in the tracks table.
 * Call before API requests; pair with hideSkeletonRows() after data arrives.
 */
function showSkeletonRows() {
  const emptyRow = document.getElementById('empty-state-row');
  const skeletonRows = [1, 2, 3, 4].map(i => document.getElementById(`skeleton-row-${i}`));

  if (emptyRow) emptyRow.style.display = 'none';
  skeletonRows.forEach(row => {
    if (row) row.style.display = '';
  });
}

/**
 * Hide skeleton loading rows and show content or empty state.
 * Call after API requests complete.
 */
function hideSkeletonRows() {
  const skeletonRows = [1, 2, 3, 4].map(i => document.getElementById(`skeleton-row-${i}`));
  skeletonRows.forEach(row => {
    if (row) row.style.display = 'none';
  });

  // Show empty state if no tracks
  if (!store.state.tracks || store.state.tracks.length === 0) {
    const emptyRow = document.getElementById('empty-state-row');
    if (emptyRow) emptyRow.style.display = '';
  }
}

/**
 * Initialize loading state handlers.
 * Call on DOM ready to wire up the folder picker and track loading.
 */
function initLoadingStates() {
  // Ensure empty state is visible on first load
  if (store.state.tracks && store.state.tracks.length > 0) {
    hideSkeletonRows();
  } else {
    // Show empty state for first-run
    const emptyRow = document.getElementById('empty-state-row');
    const skeletonRows = [1, 2, 3, 4].map(i => document.getElementById(`skeleton-row-${i}`));
    if (emptyRow) emptyRow.style.display = '';
    skeletonRows.forEach(row => {
      if (row) row.style.display = 'none';
    });
  }
}

// Wire up to renderTracks so skeleton disappears when data arrives
if (typeof window !== 'undefined') {
  const originalRenderTracks = window.renderTracks;
  if (originalRenderTracks && typeof originalRenderTracks === 'function') {
    window.renderTracks = function(...args) {
      hideSkeletonRows();
      return originalRenderTracks.apply(this, args);
    };
  }
}

// --- ES module bridge (0.4): expose to global scope for cross-module calls ---
// Pre-existing gap found while smoke-testing 0.5 (app.js's DOMContentLoaded
// handler calls initLoadingStates(); library.js calls showSkeletonRows() —
// neither was ever bridged, so both threw ReferenceError and silently aborted
// init/import before this fix).
window.showSkeletonRows = showSkeletonRows;
window.hideSkeletonRows = hideSkeletonRows;
window.initLoadingStates = initLoadingStates;
