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

let desktopLibraryReadyReported = false;

function isHittable(element) {
  if (!element || !element.getClientRects().length || getComputedStyle(element).visibility === 'hidden') return false;
  const rect = element.getBoundingClientRect();
  const topElement = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
  return topElement === element || element.contains(topElement);
}

function reportDesktopLibraryReady(attempt) {
  if (desktopLibraryReadyReported) return true;
  const token = window.__IDJLM_DESKTOP_UI_READY_TOKEN__;
  const library = document.getElementById('latin-page-library');
  const shell = document.getElementById('latin-shell');
  const search = document.getElementById('latin-search');
  const rows = document.getElementById('latin-library-rows');
  const splash = document.getElementById('splash-screen');
  const renderedRow = rows?.querySelector('tr');
  if (!token || splash || !library?.classList.contains('active') || !isHittable(shell)
      || !isHittable(library) || !isHittable(search) || !isHittable(renderedRow)) return false;
  fetch('/__desktop/ui-ready', {
    method: 'POST',
    headers: {
      'X-IDJLM-UI-Ready': token,
      'X-IDJLM-Native-Picker': typeof window.__TAURI__?.core?.invoke === 'function' ? '1' : '0',
    },
    credentials: 'same-origin',
  }).then(response => {
    if (response.ok) {
      desktopLibraryReadyReported = true;
      window.__IDJLM_UI_READY__ = true;
    } else {
      waitForDesktopLibraryReady(attempt + 1);
    }
  }).catch(() => waitForDesktopLibraryReady(attempt + 1));
  return true;
}

function waitForDesktopLibraryReady(attempt = 0) {
  if (attempt >= 50 || reportDesktopLibraryReady(attempt)) return;
  setTimeout(() => waitForDesktopLibraryReady(attempt + 1), 100);
}

if (window.__IDJLM_DESKTOP_UI_READY_TOKEN__) {
  document.addEventListener('idjlm:latin-library-ready', () => waitForDesktopLibraryReady());
}

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
