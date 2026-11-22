// ============================================================================
// IDJLM Pro — Entry Point
// ============================================================================
// This file is the application bootstrap. All application logic lives in the
// module files under /static/modules/ and is loaded via <script> tags in
// index.html before this file. Everything in those modules is global-scoped,
// so all init functions are accessible here.

let legacyApplicationInitialized = false;
let legacyAudioInitialized = false;

function initializeLegacyApplication() {
  if (legacyApplicationInitialized) return;
  legacyApplicationInitialized = true;

  initLibraryToolbar();
  initTheme();
  initThemeSwatches();
  initNavigation();
  initLoadingStates();
  initEditModal();
  initReclassifyModal();
  if (!legacyAudioInitialized) {
    initAudioPlayer();
    legacyAudioInitialized = true;
  }
  initColumnToggle();
  initBulkSelectFeature();
  initSearchFeature();
  initFilterChips();
  initSettingsTab();
  initKeyboardShortcuts();
  initGlobalSearch();
  initUpdateChecker();
  initKeyGraph();
  initAdvisorModal();
  startStatsPolling();
  loadTaxonomy();
  loadSetlistFromStorage();
  initSetlistTab();
  renderTracks();
  updateFilterChips();
  renderSetlist();
  checkResumeSession();
  initThresholdPersistence();
  // First-run setup belongs to the local-first shell. The legacy wizard asks
  // for an API key and is intentionally not started from the Advanced view.
  initWorkflowGuide();
  initDetailDock();
  initSyncCenter();
  initInbox();
  initTagsSidebar();
  if (typeof initDragDrop === 'function') initDragDrop();
  initPreparePanel();
  initKeyPreview();
  initSetlistTimeline();
  initTracksTab();
}

window.initializeLegacyApplication = initializeLegacyApplication;

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

  if (window.__latinRedesignActive) {
    // The redesigned first-run flow is local-first. Hide legacy onboarding
    // overlays that still advertise API keys and remote classification.
    ['onboarding-overlay', 'onboarding-modal'].forEach(id => {
      const overlay = document.getElementById(id);
      if (overlay) { overlay.style.display = 'none'; overlay.style.pointerEvents = 'none'; overlay.setAttribute('aria-hidden', 'true'); }
    });
    initTheme();
    if (!legacyAudioInitialized) {
      initAudioPlayer();
      legacyAudioInitialized = true;
    }
    window.initLatinRedesign?.();
    return;
  }

  initializeLegacyApplication();
});
