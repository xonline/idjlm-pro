// ============================================================================
// responsive.js — Responsive layout handling (Phase 6.3)
// ============================================================================
// Handles:
//   - Sidebar hamburger toggle on narrow windows (<1100px)
//   - Detail-dock overlay positioning
//   - Overlay backdrop dismiss
//   - Keyboard shortcut: Ctrl+M to toggle sidebar, Shift+D to toggle detail-dock
// Load order: late, after DOM is ready
// -----------

(function initResponsiveLayout() {
  const sidebar = document.querySelector('.sidebar');
  const detailDock = document.getElementById('detail-dock');
  const sidebarOverlay = document.getElementById('sidebar-overlay');
  const sidebarToggleBtn = document.getElementById('btn-toggle-sidebar');
  const detailToggleBtn = document.getElementById('btn-toggle-detail-dock');

  if (!sidebar) return; // Defensive

  // Check if we're in narrow mode (max-width: 1100px) using media query
  function isNarrowMode() {
    return window.matchMedia('(max-width: 1100px)').matches;
  }

  // Toggle sidebar visibility
  function toggleSidebar() {
    sidebar.classList.toggle('sidebar-open');
    sidebarOverlay.classList.toggle('show');
  }

  // Close sidebar
  function closeSidebar() {
    sidebar.classList.remove('sidebar-open');
    sidebarOverlay.classList.remove('show');
  }

  // Toggle detail-dock visibility
  function toggleDetailDock() {
    if (detailDock) {
      const isHidden = detailDock.hasAttribute('hidden');
      if (isHidden) {
        detailDock.removeAttribute('hidden');
        detailToggleBtn?.setAttribute('aria-pressed', 'true');
      } else {
        detailDock.setAttribute('hidden', '');
        detailToggleBtn?.setAttribute('aria-pressed', 'false');
      }
    }
  }

  // Event listeners
  if (sidebarToggleBtn) {
    sidebarToggleBtn.addEventListener('click', toggleSidebar);
  }

  if (detailToggleBtn) {
    detailToggleBtn.addEventListener('click', toggleDetailDock);
  }

  // Sidebar overlay backdrop — click to close
  if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', closeSidebar);
  }

  // Close sidebar when clicking a nav item
  sidebar.addEventListener('click', (e) => {
    const navBtn = e.target.closest('.nav-btn');
    if (navBtn && isNarrowMode()) {
      closeSidebar();
    }
  });

  // Register global shortcuts
  document.addEventListener('keydown', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) return;

    // Ctrl+M to toggle sidebar
    if (e.ctrlKey && (e.key === 'm' || e.key === 'M')) {
      e.preventDefault();
      if (isNarrowMode()) {
        toggleSidebar();
      }
    }

    // Shift+D to toggle detail-dock (already exists, but ensure it works at all widths)
    if (e.shiftKey && (e.key === 'd' || e.key === 'D')) {
      e.preventDefault();
      toggleDetailDock();
    }
  });

  // Handle window resize to show/hide hamburger button and reset layout
  function handleResize() {
    const narrow = isNarrowMode();
    if (narrow) {
      if (sidebarToggleBtn) sidebarToggleBtn.style.display = 'flex';
    } else {
      // Desktop: show sidebar normally, close overlay, reset positioning
      sidebar.classList.remove('sidebar-open');
      sidebarOverlay?.classList.remove('show');
      if (sidebarToggleBtn) sidebarToggleBtn.style.display = 'none';
      sidebar.style.position = '';
      sidebar.style.transform = '';
    }
  }

  // Watch for media query changes
  const mediaQuery = window.matchMedia('(max-width: 1100px)');
  if (mediaQuery.addListener) {
    mediaQuery.addListener(handleResize);
  } else {
    mediaQuery.addEventListener('change', handleResize);
  }

  window.addEventListener('resize', handleResize);
  handleResize(); // Initial call

  // Expose functions globally for other modules
  window.toggleSidebar = toggleSidebar;
  window.closeSidebar = closeSidebar;
  window.toggleDetailDock = toggleDetailDock;
})();
