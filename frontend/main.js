// Vite entry point (IDJLM 0.4). Imports every legacy module in the exact
// order the old <script> tags used, preserving execution/init order.
// Cross-module symbols are shared via explicit `window.*` bridges added to
// each module (see "ES module bridge" comment blocks) — see plan 0.4.
// store.js (0.5) loads first: it owns window.tracks/selectedTracks/setlist/
// taxonomy as reactive store.state, so every module below can use it.
import '../app/static/modules/store.js';
import '../app/static/modules/core.js';
import '../app/static/modules/loading.js';
import '../app/static/modules/navigation.js';
import '../app/static/modules/opsbar.js';
import '../app/static/modules/library.js';
import '../app/static/modules/stats.js';
import '../app/static/modules/player.js';
import '../app/static/modules/tracks.js';
import '../app/static/modules/review.js';
import '../app/static/modules/taxonomy.js';
import '../app/static/modules/camelot.js';
import '../app/static/modules/keygraph.js';
import '../app/static/modules/editor.js';
import '../app/static/modules/settings.js';
import '../app/static/modules/setplan.js';
import '../app/static/modules/search.js';
import '../app/static/modules/chips.js';
import '../app/static/modules/classify.js';
import '../app/static/modules/advisor.js';
import '../app/static/modules/shortcuts.js';
import '../app/static/modules/updater.js';
import '../app/static/modules/duplicates.js';
import '../app/static/modules/playlists-export.js';
import '../app/static/modules/pipeline.js';
import '../app/static/modules/detail-dock.js';
import '../app/static/modules/tags-sidebar.js';
import '../app/static/app.js';
