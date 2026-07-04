// ============================================================================
// IDJLM Pro — OpsBar (persistent status bar for background operations)
// ============================================================================
//
// Replaces the previous single-slot progress UI in the stats bar with a
// multi-chip layout: each cancellable streaming operation owns its own chip
// rendered in #opsbar (inside the library stats bar). Per-op chips mean
// concurrent background work no longer clobbers each other.
//
// Public API:
//   registerOp({ id, label, kind, onCancel })  -> returns a handle
//     kind: 'analyze' | 'classify' | 'write' | 'cue' | 'generic'
//     onCancel(): optional async () => void — called when user clicks ✕
//   opsbar.progress(handle, current, total, message?)
//   opsbar.complete(handle, summary?)
//   opsbar.error(handle, message)
//   opsbar.listCancellable() -> handle[]  (callers can re-issue cancel on reload)
//
// Backwards-compatible shims (kept so old call sites continue to work during
// the migration window):
//   showProgressInStatsBar(text, kind)   -> starts/updates an op named 'legacy'
//   hideProgressInStatsBar()             -> completes 'legacy' if it exists
//
// All ops persist across tab switches (chips live in the stats bar; not
// attached to a tab). Cancel buttons POST to /api/progress/<op_id>/cancel
// if the handle still holds an op_id, otherwise onCancel() fires.
// ============================================================================

(function () {
  const ROOT_ID = 'opsbar';
  const KIND_DEFAULT = 'generic';

  // handle -> { id, label, kind, el, opId, onCancel, current, total, queue, status, summary }
  const ops = new Map();

  // ---------- DOM helpers ----------

  function getRoot() {
    let root = document.getElementById(ROOT_ID);
    if (!root) {
      // Lazy-create inside the stats bar so the shell works even before
      // the stats bar has been rendered (defensive — should already exist)
      const statsBar = document.getElementById('library-stats-bar');
      if (!statsBar) return null;
      root = document.createElement('div');
      root.id = ROOT_ID;
      root.className = 'opsbar';
      statsBar.appendChild(root);
    }
    return root;
  }

  function buildChipEl(handle) {
    const chip = document.createElement('div');
    chip.className = `opsbar-chip opsbar-kind-${handle.kind || KIND_DEFAULT}`;
    chip.dataset.opId = handle.id;

    const label = document.createElement('span');
    label.className = 'opsbar-chip-label';
    label.textContent = handle.label;

    const track = document.createElement('div');
    track.className = 'opsbar-chip-track';
    const fill = document.createElement('div');
    fill.className = 'opsbar-chip-fill';
    track.appendChild(fill);

    const count = document.createElement('span');
    count.className = 'opsbar-chip-count';
    count.textContent = '';

    const cancel = document.createElement('button');
    cancel.className = 'opsbar-chip-cancel';
    cancel.type = 'button';
    cancel.textContent = '✕';
    cancel.title = 'Cancel';
    cancel.addEventListener('click', async () => {
      cancel.disabled = true;
      try {
        if (handle.onCancel) await handle.onCancel();
      } catch (e) {
        console.error('opsbar cancel failed:', e);
      }
      // The owning module is expected to either complete() or error() the op
      // from inside its cancel handler. If neither fires within ~1.2s we
      // fall back to error('cancelled') so the chip doesn't dangle.
      setTimeout(() => {
        if (ops.has(handle.id) && ops.get(handle.id).status === 'running') {
          opsbar.error(handle, 'cancelled');
          showToast(handle.label + ' cancelled', 'info');
        }
      }, 1200);
    });

    chip.appendChild(label);
    chip.appendChild(track);
    chip.appendChild(count);
    chip.appendChild(cancel);

    handle.el = chip;
    handle._fill = fill;
    handle._count = count;
    handle._cancel = cancel;
    return chip;
  }

  // ---------- Public API ----------

  function makeId() {
    return 'op_' + Math.random().toString(36).slice(2, 10);
  }

  function registerOp(opts) {
    const handle = {
      id: opts.id || makeId(),
      label: opts.label || 'Working…',
      kind: opts.kind || KIND_DEFAULT,
      opId: opts.opId || null,
      onCancel: opts.onCancel || null,
      current: 0,
      total: 0,
      status: 'running',  // running | success | error
      summary: null,
    };
    const root = getRoot();
    if (!root) {
      console.warn('opsbar: root #opsbar not found, op will be tracked in-memory only');
      ops.set(handle.id, handle);
      return handle;
    }
    const chip = buildChipEl(handle);
    root.appendChild(chip);
    ops.set(handle.id, handle);
    return handle;
  }

  function progress(handle, current, total, message) {
    const op = ops.get(handle && handle.id);
    if (!op) return;
    op.current = current;
    op.total = total;
    if (op._fill) {
      const pct = total > 0 ? Math.min(100, Math.max(0, Math.round((current / total) * 100))) : 0;
      op._fill.style.width = pct + '%';
    }
    if (op._count) {
      op._count.textContent = total > 0 ? `${current} / ${total}` : '';
    }
    if (message && op.el) {
      const lbl = op.el.querySelector('.opsbar-chip-label');
      if (lbl) lbl.textContent = `${handle.label} — ${message}`;
    } else if (op.el) {
      const lbl = op.el.querySelector('.opsbar-chip-label');
      if (lbl) lbl.textContent = handle.label;
    }
  }

  function complete(handle, summary) {
    const op = ops.get(handle && handle.id);
    if (!op) return;
    op.status = 'success';
    op.summary = summary || null;
    if (op._fill) op._fill.style.width = '100%';
    // Briefly flash so the user sees completion, then auto-remove
    if (op.el) op.el.classList.add('opsbar-chip-done');
    setTimeout(() => removeOp(op.id), 900);
  }

  function error(handle, message) {
    const op = ops.get(handle && handle.id);
    if (!op) return;
    op.status = 'error';
    if (op.el) {
      op.el.classList.add('opsbar-chip-error');
      const lbl = op.el.querySelector('.opsbar-chip-label');
      if (lbl) lbl.textContent = `${handle.label} — ${message || 'failed'}`;
    }
    if (op._fill) op._fill.style.width = '0%';
    setTimeout(() => removeOp(op.id), 2200);
  }

  function removeOp(id) {
    const op = ops.get(id);
    if (!op) return;
    if (op.el && op.el.parentNode) op.el.parentNode.removeChild(op.el);
    ops.delete(id);
  }

  function listCancellable() {
    return Array.from(ops.values()).filter(op => op.status === 'running');
  }

  // ---------- Legacy shims (drop after Phase 1 migrates every caller) ----------

  let _legacyHandle = null;
  function showProgressInStatsBar(text, kind) {
    if (!_legacyHandle) {
      _legacyHandle = registerOp({ id: 'legacy-spinner', label: text || 'Working…', kind: kind || KIND_DEFAULT });
    } else {
      _legacyHandle.label = text;
      if (_legacyHandle.el) {
        const lbl = _legacyHandle.el.querySelector('.opsbar-chip-label');
        if (lbl) lbl.textContent = text || 'Working…';
      }
    }
    return _legacyHandle;
  }
  function hideProgressInStatsBar() {
    if (_legacyHandle) {
      complete(_legacyHandle);
      _legacyHandle = null;
    }
  }

  // Assign on window so legacy callers can keep calling global functions and
  // so other modules can use the new API without explicit import in the
  // script-tag era (will move to ESM import when Vite lands in 0.4).
  window.opsbar = {
    registerOp,
    progress,
    complete,
    error,
    listCancellable,
  };
  // Keep the legacy globals working during migration.
  window.showProgressInStatsBar = showProgressInStatsBar;
  window.hideProgressInStatsBar = hideProgressInStatsBar;
})();
