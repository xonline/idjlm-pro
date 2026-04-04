// DJ Library Manager — Frontend

const API_BASE = "/api";
let currentTab = "import";
let allTracks = [];
let currentFolder = "";
let importState = { tracks: [], folder: "" };
let taxonomy = {};
let stats = {};
let activeStream = null; // Track active SSE connection
let currentAudioTrack = null; // Track currently playing in mini player
let appVersion = "unknown"; // Version from API

// === MINI PLAYER SETUP ===
function initMiniPlayer() {
  const container = document.getElementById("mini-player");
  if (!container) {
    const html = `
      <div id="mini-player" style="display:none; position:fixed; bottom:0; left:0; right:0; background:#1a1a2e; border-top:1px solid #333; padding:10px 20px; display:flex; align-items:center; gap:16px; z-index:1000;">
        <span id="player-title" style="flex:0 0 auto; font-size:13px; min-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"></span>
        <audio id="audio-player" controls style="flex:1; min-width:200px;"></audio>
        <button onclick="document.getElementById('mini-player').style.display='none'" style="background:none; border:none; color:#fff; cursor:pointer; font-size:18px; padding:0;">✕</button>
      </div>
    `;
    document.body.insertAdjacentHTML("beforeend", html);
  }
}

function playTrack(trackId, trackTitle, trackArtist) {
  currentAudioTrack = trackId;
  const audioPlayer = document.getElementById("audio-player");
  const playerTitle = document.getElementById("player-title");
  const miniPlayer = document.getElementById("mini-player");
  
  playerTitle.innerText = `${trackTitle} — ${trackArtist}`;
  audioPlayer.src = `${API_BASE}/audio/${encodeURIComponent(trackId)}`;
  miniPlayer.style.display = "flex";
  audioPlayer.play();
}

// === PAGE TITLE UPDATES ===
function updatePageTitle() {
  const totalTracks = allTracks.length;
  
  if (totalTracks === 0) {
    document.title = "XDJ Library Manager";
  } else if (currentTab === "import" && importState.tracks.length > 0) {
    document.title = `XDJ - Importing ${importState.tracks.length} tracks`;
  } else {
    document.title = `XDJ - ${totalTracks} tracks loaded`;
  }
}

function updatePageTitleDuringProgress(done, total) {
  document.title = `XDJ - Processing ${done}/${total}...`;
}

// === TAB NAVIGATION ===
document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    currentTab = btn.dataset.tab;
    document.querySelectorAll(".content-tab").forEach((t) => (t.style.display = "none"));
    document.getElementById(`tab-${currentTab}`).style.display = "block";
    if (currentTab === "stats") loadStats();
    if (currentTab === "review") loadReview();
    if (currentTab === "settings") loadConfidenceThreshold();
    updatePageTitle();
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

function updateProgress(done, total, track, status, details, eta, rate) {
  const percent = Math.round((done / total) * 100);
  document.getElementById("progress-bar").style.width = percent + "%";
  
  // Build progress text with ETA and rate
  let progressText = `Processing ${done} / ${total}`;
  if (rate) {
    progressText += ` · ${rate.toFixed(1)} tracks/sec`;
  }
  if (eta) {
    progressText += ` · ETA: ${eta}`;
  }
  document.getElementById("progress-text").innerText = progressText;
  updatePageTitleDuringProgress(done, total);
  
  const detailsEl = document.getElementById("progress-details");
  if (details) {
    detailsEl.innerText = details;
  }
}

function hideProgress() {
  const container = document.getElementById("progress-bar-container");
  if (container) container.style.display = "none";
  activeStream = null;
  updatePageTitle();
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

// === EMPTY STATE HANDLING ===
function updateTracksEmptyState() {
  const emptyState = document.getElementById("tracks-empty-state");
  const tablePanel = document.getElementById("tracks-table-panel");
  
  if (allTracks.length === 0) {
    emptyState.style.display = "flex";
    tablePanel.style.display = "none";
  } else {
    emptyState.style.display = "none";
    tablePanel.style.display = "block";
  }
}

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
  updatePageTitle();
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
        updateProgress(data.done, data.total, data.track, data.status, data.error ? `Error: ${data.error}` : "", data.eta, data.rate);
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
        updateProgress(data.done, data.total, data.track, data.status, details, data.eta, data.rate);
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
    updatePageTitle();
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
  renderTracks();
  updateTracksEmptyState();
  updatePageTitle();
}

function renderTracks() {
  const tbody = document.querySelector("#track-table tbody");
  tbody.innerHTML = "";
  allTracks.forEach((t) => {
    const row = `<tr data-track-id="${t.id}" ondblclick="editTrack('${t.id}')">
      <td>${t.existing_title || "—"}</td>
      <td>${t.existing_artist || "—"}</td>
      <td>${t.final_bpm ? t.final_bpm.toFixed(1) : "—"}</td>
      <td>${t.final_key || "—"}</td>
      <td>${t.final_genre || t.classified_genre || "—"}</td>
      <td>${t.final_subgenre || t.classified_subgenre || "—"}</td>
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

// === REVIEW QUEUE ===
async function loadReview() {
  await loadTracks();
  const pending = allTracks.filter((t) => !t.approved && !t.skipped);
  const tbody = document.querySelector("#review-table tbody");
  tbody.innerHTML = "";
  pending.forEach((t) => {
    const currentGenre = t.existing_genre || "none";
    const proposedGenre = t.classified_genre || "—";
    const hasChange = currentGenre !== proposedGenre && proposedGenre !== "—";
    const currentStyle = !t.existing_genre ? "color: var(--color-text-muted);" : "";
    const proposedStyle = hasChange ? "background-color: rgba(76, 175, 80, 0.15);" : "";
    const arrowStyle = hasChange ? "color: var(--color-success); font-weight: 600;" : "color: var(--color-text-muted);";
    
    const row = `<tr data-review-id="${t.id}">
      <td>${t.existing_title || "—"}</td>
      <td>
        <button class="btn-play-small" onclick="playTrack('${t.id}', '${(t.existing_title || "Track").replace(/'/g, "\\'")}', '${(t.existing_artist || "Unknown").replace(/'/g, "\\'")}')" title="Play preview">▶</button>
      </td>
      <td style="${currentStyle}">${currentGenre}</td>
      <td style="${arrowStyle}" title="${hasChange ? 'Change detected' : 'No change'}">${hasChange ? '→' : '—'}</td>
      <td style="${proposedStyle}">${proposedGenre}</td>
      <td>${t.classified_subgenre || "—"}</td>
      <td>${(t.classification_confidence || 0).toFixed(2)}</td>
      <td>${t.bpm ? t.bpm.toFixed(1) : "—"} BPM</td>
      <td>
        <button onclick="approveTrack('${t.id}')" class="btn-small">✓</button>
        <button onclick="skipTrack('${t.id}')" class="btn-small">✗</button>
      </td>
    </tr>`;
    tbody.innerHTML += row;
  });
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

async function loadConfidenceThreshold() {
  try {
    const res = await fetch(`${API_BASE}/settings`);
    const data = await res.json();
    const threshold = data.confidence_threshold || 70;
    document.getElementById("confidence-threshold-input").value = threshold;
  } catch (err) {
    console.error("Failed to load confidence threshold:", err);
  }
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

document.getElementById("save-confidence-btn")?.addEventListener("click", async () => {
  const threshold = parseInt(document.getElementById("confidence-threshold-input").value);
  if (isNaN(threshold) || threshold < 0 || threshold > 100) {
    alert("Please enter a valid number between 0 and 100");
    return;
  }
  
  try {
    const res = await fetch(`${API_BASE}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confidence_threshold: threshold }),
    });
    const data = await res.json();
    if (data.success) {
      alert("Confidence threshold saved");
    } else {
      alert("Failed to save threshold");
    }
  } catch (err) {
    alert("Error saving confidence threshold: " + err.message);
  }
});

// === EXPORT CSV ===
document.getElementById("export-csv-btn")?.addEventListener("click", async () => {
  window.location = `${API_BASE}/export/csv`;
});

// === RE-CLASSIFY LOW CONFIDENCE ===
document.getElementById("reclassify-low-confidence-btn")?.addEventListener("click", async () => {
  try {
    // Get the current confidence threshold (or default to 70%)
    let threshold = 0.7;
    try {
      const settingsRes = await fetch(`${API_BASE}/settings`);
      const settingsData = await settingsRes.json();
      threshold = (settingsData.confidence_threshold || 70) / 100;
    } catch (err) {
      console.log("Using default threshold of 70%");
    }
    
    // Get tracks with confidence below threshold
    const lowConfidenceTracks = allTracks.filter(
      (t) => (t.classification_confidence || 0) < threshold && t.classified_genre
    );
    
    if (lowConfidenceTracks.length === 0) {
      alert(`No tracks found with confidence below ${(threshold * 100).toFixed(0)}%`);
      return;
    }
    
    if (!confirm(`Found ${lowConfidenceTracks.length} tracks below ${(threshold * 100).toFixed(0)}% confidence. Re-classify them?`)) {
      return;
    }
    
    const trackIds = lowConfidenceTracks.map((t) => t.id);
    showProgress("Re-classifying low confidence tracks...");
    
    activeStream = new EventSource(
      `${API_BASE}/import/classify/stream?track_ids=${encodeURIComponent(JSON.stringify(trackIds))}`
    );
    
    activeStream.addEventListener("message", (e) => {
      const data = JSON.parse(e.data);
      
      if (data.complete) {
        hideProgress();
        loadTracks();
        alert("Re-classification complete!");
      } else {
        const details = data.genre ? `Genre: ${data.genre} (${(data.confidence * 100).toFixed(0)}%)` : "";
        updateProgress(data.done, data.total, data.track, data.status, details, data.eta, data.rate);
      }
    });
    
    activeStream.addEventListener("error", () => {
      hideProgress();
      alert("Re-classification stream error");
    });
  } catch (err) {
    alert("Re-classification failed: " + err.message);
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

// === VERSION ===
async function loadVersion() {
  try {
    const res = await fetch(`${API_BASE}/version`);
    const data = await res.json();
    appVersion = data.version || "unknown";
    document.getElementById("app-version-badge").innerText = `v${appVersion}`;
  } catch (err) {
    console.error("Failed to load version:", err);
  }
}

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
initMiniPlayer();
loadTracks();
loadSettings();
loadModelSettings();
loadTaxonomy();
loadVersion();
updatePageTitle();
