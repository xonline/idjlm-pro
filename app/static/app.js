// DJ Library Manager — Frontend

const API_BASE = "/api";
let currentTab = "import";
let allTracks = [];
let currentFolder = "";
let importState = { tracks: [], folder: "" };
let taxonomy = {};
let stats = {};
let activeStream = null; // Track active SSE connection
let reviewIndex = 0; // Current review track index
let pendingReviewTracks = []; // Filtered pending tracks

// Filter state for tracks table
let trackFilters = {
  search: "",
  status: "all", // all, pending, approved, skipped
  genre: "all",
  sortBy: "title" // title, artist, bpm, confidence, genre, status
};

// === TAB NAVIGATION ===
document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    currentTab = btn.dataset.tab;
    document.querySelectorAll(".content-tab").forEach((t) => (t.style.display = "none"));
    document.getElementById(`tab-${currentTab}`).style.display = "block";
    if (currentTab === "stats") loadStats();
    if (currentTab === "review") {
      loadReview();
      reviewIndex = 0;
      focusReviewTrack(0);
    }
  });
});

// === PROGRESS BAR SETUP ===
function initProgressBar() {
  const container = document.getElementById("progress-bar-container");
  if (!container) {
    const html = `
      <div id="progress-bar-container" class="progress-container" style="display:none">
        <div class="progress-header">
          <span id="progress-text">Processing...</span>
          <button id="progress-cancel-btn" class="btn-small">Cancel</button>
        </div>
        <div class="progress-bar-outer">
          <div id="progress-bar" class="progress-bar-inner"></div>
        </div>
        <div id="progress-details" class="progress-details"></div>
      </div>
    `;
    document.querySelector(".container").insertAdjacentHTML("beforebegin", html);
  }
}

function showProgress(label) {
  initProgressBar();
  const container = document.getElementById("progress-bar-container");
  container.style.display = "block";
  document.getElementById("progress-text").innerText = label;
  document.getElementById("progress-bar").style.width = "0%";
  document.getElementById("progress-details").innerText = "";
}

function updateProgress(done, total, track, status, details) {
  const percent = Math.round((done / total) * 100);
  document.getElementById("progress-bar").style.width = percent + "%";
  document.getElementById("progress-text").innerText = `${done} / ${total} — ${track}`;
  
  const detailsEl = document.getElementById("progress-details");
  if (details) {
    detailsEl.innerText = details;
  }
}

function hideProgress() {
  const container = document.getElementById("progress-bar-container");
  if (container) container.style.display = "none";
  activeStream = null;
}

function cancelProgress() {
  if (activeStream) {
    activeStream.close();
    hideProgress();
  }
}

// Cancel button listener
document.addEventListener("DOMContentLoaded", () => {
  setTimeout(() => {
    const cancelBtn = document.getElementById("progress-cancel-btn");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", cancelProgress);
    }
  }, 100);
});

// === IMPORT WORKFLOW ===
document.getElementById("pick-folder-btn")?.addEventListener("click", async () => {
  const res = await fetch(`${API_BASE}/import/pick-folder`, { method: "POST", body: JSON.stringify({}) });
  const data = await res.json();
  currentFolder = data.folder;
  document.getElementById("folder-display").innerText = currentFolder;
});

document.getElementById("import-btn")?.addEventListener("click", async () => {
  const res = await fetch(`${API_BASE}/import/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder: currentFolder || process.env.HOME + "/Music" }),
  });
  const data = await res.json();
  importState.tracks = data.tracks || [];
  importState.folder = currentFolder;
  allTracks = importState.tracks;
  renderImportTracks();
});

document.getElementById("analyze-btn")?.addEventListener("click", async () => {
  const selected = Array.from(document.querySelectorAll(".import-track-check:checked")).map(
    (cb) => cb.value
  );
  if (selected.length === 0) {
    alert("Please select at least one track");
    return;
  }
  
  showProgress("Analyzing...");
  
  try {
    activeStream = new EventSource(
      `${API_BASE}/import/analyze/stream?track_ids=${encodeURIComponent(JSON.stringify(selected))}`
    );
    
    activeStream.addEventListener("message", (e) => {
      const data = JSON.parse(e.data);
      
      if (data.complete) {
        hideProgress();
        // Refresh track list
        const res = await fetch(`${API_BASE}/import`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ folder: currentFolder || process.env.HOME + "/Music" }),
        });
        const updated = await res.json();
        importState.tracks = updated.tracks || [];
        renderImportTracks();
        alert("Analysis complete!");
      } else {
        updateProgress(data.done, data.total, data.track, data.status, data.error ? `Error: ${data.error}` : "");
        // Update row in table
        updateTrackRow(data.track, { bpm: data.bpm });
      }
    });
    
    activeStream.addEventListener("error", () => {
      hideProgress();
      alert("Stream error");
    });
  } catch (err) {
    hideProgress();
    alert("Analysis failed: " + err.message);
  }
});

document.getElementById("classify-btn")?.addEventListener("click", async () => {
  const selected = Array.from(document.querySelectorAll(".import-track-check:checked")).map(
    (cb) => cb.value
  );
  if (selected.length === 0) {
    alert("Please select at least one track");
    return;
  }
  
  showProgress("Classifying...");
  
  try {
    activeStream = new EventSource(
      `${API_BASE}/import/classify/stream?track_ids=${encodeURIComponent(JSON.stringify(selected))}`
    );
    
    activeStream.addEventListener("message", (e) => {
      const data = JSON.parse(e.data);
      
      if (data.complete) {
        hideProgress();
        // Refresh track list
        const res = await fetch(`${API_BASE}/import`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ folder: currentFolder || process.env.HOME + "/Music" }),
        });
        const updated = await res.json();
        importState.tracks = updated.tracks || [];
        renderImportTracks();
        alert("Classification complete!");
      } else {
        const details = data.genre ? `Genre: ${data.genre} (${data.confidence * 100}%)` : "";
        updateProgress(data.done, data.total, data.track, data.status, details);
        // Update row in table
        updateTrackRow(data.track, { 
          classified_genre: data.genre,
          classification_confidence: data.confidence
        });
      }
    });
    
    activeStream.addEventListener("error", () => {
      hideProgress();
      alert("Stream error");
    });
  } catch (err) {
    hideProgress();
    alert("Classification failed: " + err.message);
  }
});

function updateTrackRow(trackName, updates) {
  const rows = document.querySelectorAll("#import-table tbody tr");
  for (const row of rows) {
    const titleCell = row.cells[1];
    if (titleCell && titleCell.innerText === trackName) {
      if (updates.bpm) row.cells[3].innerText = updates.bpm.toFixed(1);
      if (updates.classified_genre) row.cells[5].innerText = updates.classified_genre;
      if (updates.classification_confidence) row.cells[7].innerText = (updates.classification_confidence * 100).toFixed(0) + "%";
      break;
    }
  }
}

document.getElementById("finalize-btn")?.addEventListener("click", async () => {
  const res = await fetch(`${API_BASE}/import/finalize`, { method: "POST" });
  if ((await res.json()).success) {
    importState.tracks = [];
    renderImportTracks();
    loadTracks();
  }
});

function renderImportTracks() {
  const tbody = document.querySelector("#import-table tbody");
  tbody.innerHTML = "";
  importState.tracks.forEach((t) => {
    const row = `<tr>
      <td><input type="checkbox" class="import-track-check" value="${t.id}" /></td>
      <td>${t.existing_title || "—"}</td>
      <td>${t.existing_artist || "—"}</td>
      <td>${t.bpm ? t.bpm.toFixed(1) : "—"}</td>
      <td>${t.key || "—"}</td>
      <td>${t.classified_genre || "—"}</td>
      <td>${t.classified_subgenre || "—"}</td>
      <td>${(t.classification_confidence || 0).toFixed(2)}</td>
    </tr>`;
    tbody.innerHTML += row;
  });
}

// === TRACK LIST ===
async function loadTracks() {
  const res = await fetch(`${API_BASE}/tracks/?sort_by=genre`);
  const data = await res.json();
  allTracks = data.tracks || [];
  updateStatsSummary();
  renderTracks();
}

function getFilteredAndSortedTracks() {
  let filtered = allTracks.slice();
  
  // Status filter
  if (trackFilters.status === "pending") {
    filtered = filtered.filter(t => !t.approved && !t.skipped);
  } else if (trackFilters.status === "approved") {
    filtered = filtered.filter(t => t.approved);
  } else if (trackFilters.status === "skipped") {
    filtered = filtered.filter(t => t.skipped);
  }
  
  // Genre filter
  if (trackFilters.genre !== "all") {
    filtered = filtered.filter(t => (t.final_genre || t.classified_genre || "") === trackFilters.genre);
  }
  
  // Search filter
  if (trackFilters.search) {
    const q = trackFilters.search.toLowerCase();
    filtered = filtered.filter(t => 
      (t.existing_title || "").toLowerCase().includes(q) ||
      (t.existing_artist || "").toLowerCase().includes(q)
    );
  }
  
  // Sort
  filtered.sort((a, b) => {
    let aVal, bVal;
    switch (trackFilters.sortBy) {
      case "title":
        aVal = (a.existing_title || "").toLowerCase();
        bVal = (b.existing_title || "").toLowerCase();
        return aVal.localeCompare(bVal);
      case "artist":
        aVal = (a.existing_artist || "").toLowerCase();
        bVal = (b.existing_artist || "").toLowerCase();
        return aVal.localeCompare(bVal);
      case "bpm":
        return (a.final_bpm || a.bpm || 0) - (b.final_bpm || b.bpm || 0);
      case "confidence":
        return (b.classification_confidence || 0) - (a.classification_confidence || 0);
      case "genre":
        aVal = (a.final_genre || a.classified_genre || "").toLowerCase();
        bVal = (b.final_genre || b.classified_genre || "").toLowerCase();
        return aVal.localeCompare(bVal);
      case "status":
        const statusOrder = { approved: 0, skipped: 1, pending: 2 };
        const aStatus = a.approved ? "approved" : (a.skipped ? "skipped" : "pending");
        const bStatus = b.approved ? "approved" : (b.skipped ? "skipped" : "pending");
        return (statusOrder[aStatus] || 3) - (statusOrder[bStatus] || 3);
      default:
        return 0;
    }
  });
  
  return filtered;
}

function getAvailableGenres() {
  const genres = new Set();
  allTracks.forEach(t => {
    const g = t.final_genre || t.classified_genre;
    if (g) genres.add(g);
  });
  return Array.from(genres).sort();
}

function updateStatsSummary() {
  const total = allTracks.length;
  if (total === 0) {
    document.getElementById("stats-summary").innerHTML = "";
    return;
  }
  
  // Count by genre
  const genreCounts = {};
  let totalConfidence = 0;
  let confidentCount = 0;
  
  allTracks.forEach(t => {
    const genre = t.final_genre || t.classified_genre || "Other";
    genreCounts[genre] = (genreCounts[genre] || 0) + 1;
    if (t.classification_confidence) {
      totalConfidence += t.classification_confidence * 100;
      confidentCount++;
    }
  });
  
  const avgConfidence = confidentCount > 0 ? (totalConfidence / confidentCount).toFixed(0) : "—";
  const genreStats = Object.entries(genreCounts)
    .map(([g, c]) => `${g} ${c}`)
    .join(" · ");
  
  const html = `<div class="stats-summary" style="background: var(--color-surface-light); padding: 12px 16px; border-radius: var(--radius); margin-bottom: 12px; font-size: 13px; color: var(--color-text-muted);">
    <strong>${total} tracks</strong> · ${genreStats} · Avg confidence: ${avgConfidence}%
  </div>`;
  
  const container = document.getElementById("stats-summary");
  if (!container) {
    const panel = document.querySelector("#tab-tracks .panel:first-child");
    if (panel) {
      const div = document.createElement("div");
      div.id = "stats-summary";
      panel.parentNode.insertBefore(div, panel.nextSibling);
    }
  }
  document.getElementById("stats-summary").innerHTML = html;
}

function renderTracks() {
  const filtered = getFilteredAndSortedTracks();
  const tbody = document.querySelector("#track-table tbody");
  tbody.innerHTML = "";
  filtered.forEach((t) => {
    const confidence = (t.classification_confidence || 0) * 100;
    let confidenceColor = "color-text-muted";
    if (confidence >= 85) confidenceColor = "color-confidence-high";
    else if (confidence >= 60) confidenceColor = "color-confidence-medium";
    else confidenceColor = "color-confidence-low";
    
    const row = `<tr data-track-id="${t.id}" ondblclick="editTrack('${t.id}')" style="cursor: pointer;">
      <td>${t.existing_title || "—"}</td>
      <td>${t.existing_artist || "—"}</td>
      <td>${t.final_bpm ? t.final_bpm.toFixed(1) : (t.bpm ? t.bpm.toFixed(1) : "—")}</td>
      <td>${t.final_key || t.key || "—"}</td>
      <td>${t.final_genre || t.classified_genre || "—"}</td>
      <td>${t.final_subgenre || t.classified_subgenre || "—"}</td>
      <td><span style="font-weight: 600;" class="${confidenceColor}">${confidence.toFixed(0)}%</span></td>
      <td>${t.approved ? "✓" : ""}</td>
    </tr>`;
    tbody.innerHTML += row;
  });
}

function editTrack(trackId) {
  const track = allTracks.find((t) => t.id === trackId);
  if (!track) return;
  document.getElementById("edit-modal").style.display = "block";
  document.getElementById("edit-track-id").value = trackId;
  document.getElementById("edit-genre").value = track.override_genre || track.classified_genre || "";
  document.getElementById("edit-subgenre").value = track.override_subgenre || track.classified_subgenre || "";
  document.getElementById("edit-bpm").value = track.override_bpm || track.bpm || "";
  document.getElementById("edit-key").value = track.override_key || track.key || "";
  document.getElementById("edit-year").value = track.override_year || track.spotify_year || track.existing_year || "";
}

document.getElementById("save-edit-btn")?.addEventListener("click", async () => {
  const trackId = document.getElementById("edit-track-id").value;
  const res = await fetch(`${API_BASE}/tracks/${trackId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      override_genre: document.getElementById("edit-genre").value || null,
      override_subgenre: document.getElementById("edit-subgenre").value || null,
      override_bpm: parseFloat(document.getElementById("edit-bpm").value) || null,
      override_key: document.getElementById("edit-key").value || null,
      override_year: parseInt(document.getElementById("edit-year").value) || null,
    }),
  });
  if ((await res.json()).success) {
    document.getElementById("edit-modal").style.display = "none";
    loadTracks();
  }
});

// === TRACKS TABLE TOOLBAR ===
function initTracksToolbar() {
  const panel = document.querySelector("#tab-tracks .panel:first-child");
  if (!panel || document.getElementById("tracks-toolbar")) return;
  
  const toolbar = document.createElement("div");
  toolbar.id = "tracks-toolbar";
  toolbar.innerHTML = `
    <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; align-items: center;">
      <input type="text" id="track-search" placeholder="Search by title or artist..." 
        style="flex: 1; min-width: 200px; padding: 8px; border-radius: var(--radius); border: 1px solid var(--color-border); background: var(--color-surface); color: inherit;">
      <select id="track-sort" style="padding: 8px; border-radius: var(--radius); border: 1px solid var(--color-border); background: var(--color-surface); color: inherit;">
        <option value="title">Sort: Title</option>
        <option value="artist">Sort: Artist</option>
        <option value="bpm">Sort: BPM</option>
        <option value="confidence">Sort: Confidence</option>
        <option value="genre">Sort: Genre</option>
        <option value="status">Sort: Status</option>
      </select>
      <select id="track-status-filter" style="padding: 8px; border-radius: var(--radius); border: 1px solid var(--color-border); background: var(--color-surface); color: inherit;">
        <option value="all">All Status</option>
        <option value="pending">Pending</option>
        <option value="approved">Approved</option>
        <option value="skipped">Skipped</option>
      </select>
      <select id="track-genre-filter" style="padding: 8px; border-radius: var(--radius); border: 1px solid var(--color-border); background: var(--color-surface); color: inherit;">
        <option value="all">All Genres</option>
      </select>
    </div>
  `;
  
  panel.parentNode.insertBefore(toolbar, panel.nextSibling);
  
  // Add event listeners
  document.getElementById("track-search").addEventListener("input", (e) => {
    trackFilters.search = e.target.value;
    renderTracks();
  });
  
  document.getElementById("track-sort").addEventListener("change", (e) => {
    trackFilters.sortBy = e.target.value;
    renderTracks();
  });
  
  document.getElementById("track-status-filter").addEventListener("change", (e) => {
    trackFilters.status = e.target.value;
    renderTracks();
  });
  
  document.getElementById("track-genre-filter").addEventListener("change", (e) => {
    trackFilters.genre = e.target.value;
    renderTracks();
  });
}

function updateGenreFilterOptions() {
  const select = document.getElementById("track-genre-filter");
  if (!select) return;
  
  const genres = getAvailableGenres();
  const currentValue = select.value;
  
  select.innerHTML = `<option value="all">All Genres</option>`;
  genres.forEach(g => {
    select.innerHTML += `<option value="${g}">${g}</option>`;
  });
  
  select.value = currentValue === "all" ? "all" : (genres.includes(currentValue) ? currentValue : "all");
}

// === REVIEW QUEUE ===
async function loadReview() {
  await loadTracks();
  pendingReviewTracks = allTracks.filter((t) => !t.approved && !t.skipped);
  renderReviewTable();
  if (pendingReviewTracks.length > 0) {
    reviewIndex = 0;
    focusReviewTrack(0);
  }
}

function renderReviewTable() {
  const tbody = document.querySelector("#review-table tbody");
  tbody.innerHTML = "";
  pendingReviewTracks.forEach((t, idx) => {
    const confidence = (t.classification_confidence || 0) * 100;
    let confidenceColor = "color-text-muted";
    if (confidence >= 85) confidenceColor = "color-confidence-high";
    else if (confidence >= 60) confidenceColor = "color-confidence-medium";
    else confidenceColor = "color-confidence-low";
    
    const row = `<tr data-review-id="${t.id}" data-review-index="${idx}" style="cursor: pointer;">
      <td>${t.existing_title || "—"}</td>
      <td>${t.existing_artist || "—"}</td>
      <td>${t.classified_genre || "—"} / ${t.classified_subgenre || "—"}</td>
      <td><span class="${confidenceColor}" style="font-weight: 600;">${confidence.toFixed(0)}%</span></td>
      <td>${t.bpm ? t.bpm.toFixed(1) : "—"} BPM</td>
      <td>
        <button onclick="approveTrack('${t.id}')" class="btn-small">✓</button>
        <button onclick="skipTrack('${t.id}')" class="btn-small">✗</button>
      </td>
    </tr>`;
    tbody.innerHTML += row;
  });
}

function focusReviewTrack(idx) {
  if (idx < 0 || idx >= pendingReviewTracks.length) return;
  reviewIndex = idx;
  const rows = document.querySelectorAll("#review-table tbody tr");
  rows.forEach(r => r.style.backgroundColor = "transparent");
  if (rows[idx]) {
    rows[idx].style.backgroundColor = "var(--color-surface-light)";
    rows[idx].scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

async function approveTrack(trackId) {
  await fetch(`${API_BASE}/review/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ track_id: trackId }),
  });
  loadReview();
}

async function skipTrack(trackId) {
  await fetch(`${API_BASE}/review/skip`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ track_id: trackId }),
  });
  loadReview();
}

document.getElementById("write-tags-btn")?.addEventListener("click", async () => {
  const approved = allTracks.filter((t) => t.approved).map((t) => t.id);
  const res = await fetch(`${API_BASE}/review/write-tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ track_ids: approved }),
  });
  const data = await res.json();
  alert(`Wrote tags for ${data.written.length} tracks`);
  loadReview();
});

// === KEYBOARD SHORTCUTS (Review Tab) ===
document.addEventListener("keydown", (e) => {
  if (currentTab !== "review" || pendingReviewTracks.length === 0) return;
  
  const currentTrack = pendingReviewTracks[reviewIndex];
  
  switch (e.key.toLowerCase()) {
    case "a":
      e.preventDefault();
      approveTrack(currentTrack.id);
      break;
    case "s":
      e.preventDefault();
      skipTrack(currentTrack.id);
      break;
    case "e":
      e.preventDefault();
      editTrack(currentTrack.id);
      break;
    case "arrowleft":
      e.preventDefault();
      focusReviewTrack(reviewIndex - 1);
      break;
    case "arrowright":
      e.preventDefault();
      focusReviewTrack(reviewIndex + 1);
      break;
  }
});

// === TAXONOMY ===
async function loadTaxonomy() {
  const res = await fetch(`${API_BASE}/bulk/taxonomy`);
  taxonomy = (await res.json()).genres || [];
  renderTaxonomy();
}

function renderTaxonomy() {
  const container = document.getElementById("taxonomy-list");
  container.innerHTML = "";
  taxonomy.forEach((g) => {
    const html = `<div class="taxonomy-item">
      <strong>${g.name}</strong> [${g.bpm_range?.[0] || ""}-${g.bpm_range?.[1] || ""}]
      <div>${g.subgenres?.join(", ") || ""}</div>
      <button onclick="deleteGenre('${g.name}')">Delete</button>
    </div>`;
    container.innerHTML += html;
  });
}

document.getElementById("add-genre-btn")?.addEventListener("click", async () => {
  const genreName = prompt("Genre name:");
  const minBPM = prompt("Min BPM:");
  const maxBPM = prompt("Max BPM:");
  if (genreName) {
    await fetch(`${API_BASE}/bulk/taxonomy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: genreName,
        bpm_range: [parseInt(minBPM) || 0, parseInt(maxBPM) || 200],
        subgenres: [],
      }),
    });
    loadTaxonomy();
  }
});

async function deleteGenre(genreName) {
  if (confirm(`Delete "${genreName}"?`)) {
    await fetch(`${API_BASE}/bulk/taxonomy/${genreName}`, { method: "DELETE" });
    loadTaxonomy();
  }
}

// === STATS ===
async function loadStats() {
  const res = await fetch(`${API_BASE}/session/stats`);
  stats = await res.json();
  document.getElementById("stat-total").innerText = stats.total || 0;
  document.getElementById("stat-analyzed").innerText = stats.analyzed || 0;
  document.getElementById("stat-classified").innerText = stats.classified || 0;
  document.getElementById("stat-approved").innerText = stats.approved || 0;
}

// === SETTINGS ===
async function loadSettings() {
  const res = await fetch(`${API_BASE}/settings/`);
  const data = await res.json();
  document.getElementById("gemini-status").innerText = data.gemini_key;
  document.getElementById("spotify-status").innerText = data.spotify_id;
}

async function loadModelSettings() {
  const res = await fetch(`${API_BASE}/settings/models`);
  const data = await res.json();
  document.getElementById("gemini-model-select").value = data.current || "auto";
  document.getElementById("model-status").innerText = data.current || data.default;
}

document.getElementById("save-settings-btn")?.addEventListener("click", async () => {
  const res = await fetch(`${API_BASE}/settings/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      gemini_key: document.getElementById("gemini-key-input").value,
      spotify_id: document.getElementById("spotify-id-input").value,
      spotify_secret: document.getElementById("spotify-secret-input").value,
    }),
  });
  if ((await res.json()).success) {
    alert("Settings saved");
    loadSettings();
  }
});

document.getElementById("save-model-btn")?.addEventListener("click", async () => {
  const model = document.getElementById("gemini-model-select").value;
  const modelToSend = model === "auto" ? "" : model;
  const res = await fetch(`${API_BASE}/settings/model`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: modelToSend }),
  });
  if ((await res.json())) {
    alert("Model updated");
    loadModelSettings();
  }
});

// === WATCH ===
let watching = false;
async function startWatch() {
  const res = await fetch(`${API_BASE}/watch/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder: currentFolder }),
  });
  if ((await res.json()).success) {
    watching = true;
    document.getElementById("watch-status").innerText = "Watching...";
    pollWatch();
  }
}

async function stopWatch() {
  const res = await fetch(`${API_BASE}/watch/stop`, { method: "POST" });
  watching = false;
  document.getElementById("watch-status").innerText = "Stopped";
}

async function pollWatch() {
  if (!watching) return;
  const res = await fetch(`${API_BASE}/watch/poll`);
  const data = await res.json();
  if (data.new_files?.length > 0) {
    alert(`${data.new_files.length} new files detected`);
    loadTracks();
  }
  setTimeout(pollWatch, 5000);
}

// === SESSION ===
document.getElementById("save-session-btn")?.addEventListener("click", async () => {
  const res = await fetch(`${API_BASE}/session/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder: currentFolder }),
  });
  if ((await res.json()).success) alert("Session saved");
});

document.getElementById("load-session-btn")?.addEventListener("click", async () => {
  const res = await fetch(`${API_BASE}/session/load`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder: currentFolder }),
  });
  const data = await res.json();
  if (data.success) {
    alert(`Loaded ${data.count} tracks`);
    loadTracks();
  }
});

// === EXPORT ===
document.getElementById("export-m3u-btn")?.addEventListener("click", async () => {
  const genre = prompt("Filter by genre (optional):") || "";
  const subgenre = prompt("Filter by subgenre (optional):") || "";
  const url = `${API_BASE}/export/m3u?genre=${genre}&subgenre=${subgenre}`;
  window.location.href = url;
});

// === MODAL CLOSE ===
document.querySelectorAll(".modal .close").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.target.closest(".modal").style.display = "none";
  });
});

window.addEventListener("click", (e) => {
  if (e.target.classList.contains("modal")) e.target.style.display = "none";
});

// === INIT ===
initProgressBar();
loadTracks();
loadSettings();
loadModelSettings();
loadTaxonomy();
