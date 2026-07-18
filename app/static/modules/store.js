// ============================================================================
// Reactive Store (IDJLM 0.5)
// ============================================================================
// Tiny pub/sub store — single source of truth for state that used to live as
// scattered global-on-window fields: tracks, selectedTracks, setlist,
// taxonomy, searchResults, currentSort, activeChips.
//
// This kills the "mutate state, then remember to call renderTracks()" bug
// class: callers that replace a whole value use store.set(key, value) and
// any subscriber (e.g. tracks.js's renderTracks, subscribed to the 'tracks'
// key) fires automatically — no separate manual re-render call needed.
//
// In-place mutations (Set.add/delete, Array.push, object property writes)
// still work directly against store.state, exactly like the old window.*
// globals did — call store.notify(key) afterward only if a subscriber needs
// to react to that specific in-place change.
//
// --- ES module bridge (0.4 convention): loaded first, before core.js, so
// every other module can read/write store.state from the moment it runs. ---

const state = {
  tracks: [],
  selectedTracks: new Set(),
  setlist: [],
  taxonomy: {},
  searchResults: null,
  currentSort: { field: 'display_title', direction: 'asc' },
  activeChips: new Set(),
  activeTagFilters: {},
  _tagsExpanded: {},
  chartInstances: {
    genres: null, bpm: null, years: null, keyDist: null,
    energyDist: null, decadeDist: null, genreEra: null, energyTimeline: null,
  },
};

const listeners = Object.create(null); // key -> Set<fn>

function subscribe(key, fn) {
  if (!listeners[key]) listeners[key] = new Set();
  listeners[key].add(fn);
  return () => {
    if (listeners[key]) listeners[key].delete(fn);
  };
}

function notify(key) {
  if (!listeners[key]) return;
  listeners[key].forEach(fn => {
    try {
      fn(state[key], key);
    } catch (err) {
      console.error(`[store] subscriber for "${key}" threw:`, err);
    }
  });
}

function set(key, value) {
  state[key] = value;
  notify(key);
}

function get(key) {
  return state[key];
}

const store = { state, get, set, notify, subscribe };
window.store = store;
