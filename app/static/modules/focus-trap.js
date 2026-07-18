// ============================================================================
// focus-trap.js — Modal focus trap + restore (Phase 6.4 a11y)
// ============================================================================
// Uses MutationObserver to detect modal open/close, auto-installs focus trap.
// Tab/Shift+Tab constrained to open modal. Focus restores to trigger element.
// Esc handling is centralised in shortcuts.js via the modal stack exposed here.
// Load order: after DOM content, before modules that open modals.
// ----------------------------------------------------------------------------

const _modalStack = [];
const FOCUSABLE_SEL = 'a[href], button:not([disabled]):not([tabindex="-1"]), input:not([disabled]):not([tabindex="-1"]), select:not([disabled]):not([tabindex="-1"]), textarea:not([disabled]):not([tabindex="-1"]), [tabindex]:not([tabindex="-1"])';

function _getFocusable(el) {
  return Array.from(el.querySelectorAll(FOCUSABLE_SEL));
}

function _topModal() {
  while (_modalStack.length > 0) {
    const top = _modalStack[_modalStack.length - 1];
    if (top.el.offsetParent !== null) return top;
    _modalStack.pop();
  }
  return null;
}

function _activateTrap(modalEl) {
  const triggerEl = document.activeElement;
  const existing = _modalStack.find(e => e.el === modalEl);
  if (existing) {
    existing.triggerEl = triggerEl;
    return;
  }
  _modalStack.push({ el: modalEl, triggerEl });
  const focusable = _getFocusable(modalEl);
  if (focusable.length > 0) {
    requestAnimationFrame(() => focusable[0].focus());
  }
}

function _deactivateTrap(modalEl) {
  const idx = _modalStack.findIndex(e => e.el === modalEl);
  if (idx === -1) return;
  const entry = _modalStack.splice(idx, 1)[0];
  if (entry.triggerEl && typeof entry.triggerEl.focus === 'function') {
    try { entry.triggerEl.focus(); } catch (_) {}
  }
}

function closeTopModal() {
  const top = _topModal();
  if (!top) return false;
  top.el.style.display = 'none';
  _deactivateTrap(top.el);
  return true;
}

function isModalOpen() {
  return _topModal() !== null;
}

// Tab trap — wrap focus inside open modal (called from shortcuts.js single registry)
function _trapTabKey(e) {
  const top = _topModal();
  if (!top) return;
  const focusable = _getFocusable(top.el);
  if (focusable.length === 0) {
    e.preventDefault();
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) {
      e.preventDefault();
      last.focus();
    }
  } else {
    if (document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
}

// MutationObserver — watch all .modal, .modal-overlay, .onboarding-overlay for display changes
function _initObserver() {
  const modals = document.querySelectorAll('.modal, .modal-overlay, .onboarding-overlay');
  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type !== 'attributes' || m.attributeName !== 'style') continue;
      const el = m.target;
      if (!el.matches('.modal, .modal-overlay, .onboarding-overlay')) continue;
      const display = el.style.display;
      if (display === 'flex' || display === 'block') {
        el.setAttribute('aria-hidden', 'false');
        _activateTrap(el);
      } else if (display === 'none') {
        el.setAttribute('aria-hidden', 'true');
        _deactivateTrap(el);
      }
    }
  });
  modals.forEach(m => {
    observer.observe(m, { attributes: true, attributeFilter: ['style'] });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', _initObserver);
} else {
  _initObserver();
}

window.focusTrap = { closeTopModal, isModalOpen, trapTabKey: _trapTabKey };
