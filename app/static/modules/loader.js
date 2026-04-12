/**
 * IDJLM Pro Module Loader
 * 
 * This file registers the module loading infrastructure.
 * Modules register themselves on window.modules[name] and are initialized on DOMContentLoaded.
 * 
 * Usage:
 *   // In a feature file:
 *   registerModule('myFeature', function init() { ... });
 * 
 * Future: app.js will be split into individual module files that register here.
 */

window.modules = window.modules || {};

function registerModule(name, initFn) {
  window.modules[name] = { init: initFn };
}

// Initialize all registered modules after DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  for (const [name, mod] of Object.entries(window.modules)) {
    try {
      mod.init();
    } catch (e) {
      console.error(`Module "${name}" init failed:`, e);
    }
  }
});
