// ============================================================================
// IDJLM Pro — Entry Point
// ============================================================================
// This file is the application bootstrap. All application logic lives in the
// module files under /static/modules/ and is loaded via <script> tags in
// index.html before this file. Everything in those modules is global-scoped,
// so all init functions are accessible here.

document.addEventListener('DOMContentLoaded', () => {
  // Splash screen fade-out after 1.5s animation
  const splash = document.getElementById('splash-screen');
  if (splash) {
    setTimeout(() => {
      splash.classList.add('fade-out');
      // Remove from DOM after transition
      setTimeout(() => splash.remove(), 600);
    }, 1500);
  }
  // Fade in main app content
  const appContent = document.getElementById('app-content');
  if (appContent) {
    setTimeout(() => {
      appContent.style.opacity = '1';
    }, 200);
  }

  initLibraryToolbar();
  initTheme();
  initThemeSwatches();
  initNavigation();
  initEditModal();
  initReclassifyModal();
  initAudioPlayer();
  initColumnToggle();
  initBulkSelectFeature();
  initSearchFeature();
  initSettingsTab();
  initKeyboardShortcuts();
  initUpdateChecker();
  initKeyGraph();
  initAdvisorModal();
  startStatsPolling();
  loadTaxonomy();
  loadSetlistFromStorage();
  initSetlistTab();
  renderTracks();
  renderSetlist();
  checkResumeSession();
  initThresholdPersistence();
  initOnboarding();
  initWorkflowGuide();
});
