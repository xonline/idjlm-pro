# IDJLM Pro — Vision Document
**Date:** 2026-06-12  
**Author:** Fable (strategic analysis)  
**Purpose:** Honest assessment, architectural direction, and highest-impact improvements for IDJLM Pro

---

## 1. What's Already Strong — Honest Assessment

This app is genuinely impressive for its age. It went from zero to a real, shippable product in roughly 10 weeks. That pace is only possible because the decisions made along the way were mostly correct.

**The domain knowledge is exceptional.** Most DJ tools treat "Latin" as a single genre. IDJLM Pro understands that Salsa Romántica and Salsa Dura are as different as country and death metal. The clave detection (2-3 vs 3-2 correlation over 2-bar windows), the genre-aware BPM correction (salsa 4/3, bachata half-speed, cha cha disambiguation), and the auto cue point logic (Beat 1, Montuno/Drop, Main Hook, Outro) all reflect real musical knowledge. Competitors cannot touch this for Latin-focused libraries.

**The audio analysis pipeline is solid.** Reading existing BPM/key from mutagen tags first (skipping librosa when data already exists) is the right call — it is fast and respects the user's prior work. The hand-rolled K-weighted LUFS (EBU R128 approximation without pyloudnorm) is technically sound. Two waveform resolutions (60pt thumbnail, 600pt detail) show architectural forethought.

**The AI fallback chain is production-quality.** Six providers with automatic failover, backoff retries (30s/60s/120s), correction hints injected from the learning system, and batched 10-track API calls — this is better architecture than most commercial tools that rely on a single API.

**The harmonic mixing model is correct.** The Camelot wheel distance calculation, separate scoring weights for the mix scorer (BPM 25%, Key 35%, Energy 20%, Genre 20%) versus the advisor (Key 40%, BPM 30%, Energy 20%, Genre 10%), and the BPM transition ratings in the Set Planner are all the right design choices.

**The UX decisions are DJ-first.** Undo after write, shift-click range select, keyboard shortcuts, the real-time BPM/key filter, confidence scores shown during review — these are features that show the builder understands the workflow.

---

## 2. Current Weaknesses and Gaps

### Critical

**The in-memory store will collapse at scale.** The track store is a Python dict in process memory, serialised to `session.json`. At 500 tracks it is fine. At 5,000 tracks, load time becomes painful. At 20,000 tracks (a professional DJ's actual library), the whole model breaks — JSON serialisation of 50-field dataclasses times 20K tracks is 50-100MB of file I/O on every save. There is no indexing, no query optimisation, and no way to work with a subset of a large library without loading everything.

**macOS-only folder picker.** `/api/pick-folder` uses `osascript` — it literally does not work on Windows. The Windows installer exists (README says so) but this route silently fails or requires a workaround. This is not a minor bug; it blocks the core import flow on half the target platform.

**Key detection accuracy is inadequate for professional use.** Chroma CQT to major/minor template correlation is the simplest possible key detection algorithm. It achieves roughly 60-65% accuracy on pop/rock. On Latin music (complex polyrhythmic percussion, lots of chromatic passing tones, clave rhythms that confuse spectral analysis), accuracy is likely 50-55%. Mixed In Key's STEM analysis achieves 85%+. DJs who rely on this for harmonic mixing will hit wrong transitions and blame the tool.

**Vocal detection is unreliable for Latin percussion.** The code acknowledges this directly — "biased toward vocal for Latin percussion." HPSS + spectral flatness + MFCC variance + ZCR cannot reliably separate vocals from congas, timbales, and brass sections in a dense Salsa Dura arrangement. The flag is noise, not signal.

**OpenRouter has no backoff.** Every other provider has 30s/60s/120s backoff retries on failure. OpenRouter silently fails without retry. This is a bug that will cause silent classification failures for users on OpenRouter.

**No cross-session learning.** The approval logging captures corrections, but the learning system's correction hints are only injected per-session. There is no aggregation, trending, or model improvement over time. The README's claim that "it learns from your corrections — the more you use it, the better it gets" is only partially true.

### Significant

**Energy detection is empirically calibrated to one person's library.** The `0.35` empirical normalisation constant in the energy calculation is a magic number with no scientific basis. It will be wrong for libraries with different average loudness profiles (mastered-for-streaming vs pre-2010 loudness-war tracks vs live recordings).

**The Set Planner assumes 4-minute average track length.** This constant is hardcoded. A Salsa Romántica set might have 7-minute tracks. A peak-hour Timba set might have 10-minute tracks. The time estimates will be wrong by 40-100%.

**No persistent track identity across imports.** If a user moves a file, renames it, or re-imports, the track is treated as new. All analysis, classification, and review decisions are lost. This is a data integrity problem that causes real frustration in professional use.

**The Rekordbox integration is read-only and path-dependent.** Reading from `master.db` is correct but brittle — Pioneer has changed this schema multiple times. There is no write-back to Rekordbox. A professional using both tools has to maintain two databases.

---

## 3. Ideal Architecture — Even If Starting Over

The current stack (Flask + Vanilla JS) is not wrong, but it has hit its ceiling faster than expected. Here is what the ideal architecture looks like, with an honest assessment of migration cost.

### What to Keep

**Flask as the backend** — Python is the right language for audio analysis (librosa, numpy, scipy). The backend is well-structured and the routes are clean. Keep it.

**The Track dataclass** — It is a clean data model. The fallback chain properties (`final_genre`, `final_bpm`, etc.) are the right abstraction. Keep it.

**The AI fallback chain** — The multi-provider architecture is a genuine competitive advantage. Keep it and fix the OpenRouter backoff gap.

**The CSS token system** — The `--bg0/bg1/bg2/bg3` depth layers and `--t1/t2/t3/t4` contrast hierarchy are correct. The three themes are a professional feature. Keep it.

### What to Replace

**SQLite instead of JSON session file.** This is the single most impactful structural change. SQLite gives you: indexed queries (filter 20K tracks by genre/BPM/key in milliseconds), incremental writes (update one track, not re-serialise everything), persistent track identity via file hash (not path), and WAL mode for safe concurrent reads during analysis. Migration effort: one sprint. Impact: enables professional-scale libraries.

**React or Svelte for the frontend.** The 15-module vanilla JS architecture is clean but has hit complexity limits. The library table, detail panel, set planner, and advisor all need reactive state management — right now this is manual DOM manipulation scattered across 15 files. Svelte is the recommendation: smaller bundle than React, simpler mental model, compiles away at build time (no runtime overhead), and the learning curve from vanilla JS is lower than React. Migration effort: 3-4 sprints. Impact: faster feature velocity, better performance, eliminates the class of bug where UI and data state diverge.

**Chromaprint for key detection.** The AcoustID/Chromaprint fingerprinting library achieves 80%+ key detection accuracy versus chroma CQT's 55-65%. It is open source, runs locally, and has Python bindings. This directly addresses the most professionally-damaging accuracy gap. Migration effort: 3-5 days. Impact: makes harmonic mixing actually reliable.

### Ideal Data Architecture

```
tracks
  - id (hash of file content)
  - file_path
  - file_mtime (for change detection)

analysis
  - track_id (FK)
  - bpm, key, energy, lufs, waveform_data

classification
  - track_id (FK)
  - genre, subgenre, confidence, provider, timestamp

enrichment
  - track_id (FK)
  - source (spotify|deezer|lastfm|beatport)
  - data (JSON blob)

corrections
  - track_id (FK)
  - field, old_value, new_value, timestamp

sessions
  - session state, setlists, etc.
```

Content-hash track IDs solve the rename/move problem. Separate tables for analysis, classification, and enrichment allow re-running any phase independently without losing other data.

---

## 4. Feature Gap Analysis vs Competitors

### Mixed In Key 10
**Their edge:** STEM separation (vocals/drums/bass/melody isolated before key detection) achieves 85%+ key accuracy. Cue point placement trained on 10 million tracks.  
**IDJLM's edge:** AI genre classification, Latin domain knowledge, enrichment chain, full write-back to tags.  
**Verdict:** IDJLM beats MIK on genre intelligence; MIK beats IDJLM on audio accuracy. The gap to close is key detection.

### Rekordbox 7
**Their edge:** Pioneer ecosystem lock-in, CDJ hardware sync, full performance mode, cloud library sync.  
**IDJLM's edge:** AI classification, Latin sub-genres, multi-source enrichment, AI provider choice.  
**Verdict:** Do not compete with Rekordbox on ecosystem. Compete on intelligence. IDJLM should be "what Rekordbox sends your tracks to before you play them."

### Lexicon
**Their edge:** Imports from and exports to every major DJ platform (Rekordbox, Serato, Traktor, djay Pro, VirtualDJ). It is a universal DJ library translator.  
**IDJLM's edge:** AI classification, genre depth, Latin analysis.  
**Gap:** IDJLM needs two-way Rekordbox sync and Serato support to stop losing users who "just need to get their library into [X]."

### Serato and Traktor
Performance tools, not library tools. Not the right comparison category.

### Key Missing Features vs All Competitors

1. Two-way Rekordbox sync (read + write, not just read)
2. Serato crate/smart crate export
3. STEM-based or Chromaprint-based key detection
4. Streaming service integration (add from Spotify/Beatport directly to queue)
5. Conflict resolution UI when reimporting a modified file

---

## 5. Ten Highest-Impact Improvements (Ranked by Impact/Effort)

### Tier 1 — Do Now (days of effort, major impact)

**1. Fix OpenRouter backoff (1 day)**  
Add the same 30s/60s/120s retry logic to OpenRouter that every other provider has. This is a one-function change in `classifier.py`. Currently, OpenRouter failures are silent — the track stays unclassified with no error message. This is a reliability bug, not a feature request.

**2. Replace Chroma CQT key detection with Chromaprint (3-5 days)**  
Install `acoustid` Python library, fingerprint each track, look up via AcoustID API (free, returns key data from community submissions), fall back to local chroma if not found. This brings key detection from roughly 60% to 80%+ accuracy without changing any other part of the pipeline. This is the single change most likely to make professionals trust the tool for harmonic mixing.

**3. Content-hash track identity (1 week)**  
Store tracks by SHA-256 hash of first 1MB of audio content. On re-import, match by hash first, then fall back to path. This preserves all analysis/classification data when users reorganise their library folders — a workflow that every serious DJ does regularly.

### Tier 2 — Next Sprint (1-2 weeks, high impact)

**4. SQLite persistence (1-2 weeks)**  
Replace `session.json` with a SQLite database. The migration path: write a one-time `session.json` to SQLite migration script, update all routes to query SQLite instead of the dict store, keep the dict as a write-through cache for performance. This unblocks every professional DJ with a serious library.

**5. Windows folder picker (2 days)**  
Replace the `osascript` call in `/api/pick-folder` with a cross-platform solution. Options: `tkinter.filedialog.askdirectory()` (stdlib, works everywhere), or a Tauri frontend invocation that calls the native OS dialog. The Tauri path is cleanest — the frontend already handles the UI; the backend just needs to receive a path.

**6. Aggregated correction learning (1 week)**  
The corrections table accumulates every override the user makes. Build a weekly aggregation job: which AI-classified genres did this user most often override, and to what? Inject these as weighted hints into the classification prompt. After 50-100 corrections, the AI's accuracy on this user's library should measurably improve. This is the feature that creates lock-in.

### Tier 3 — Quarter Work (2-4 weeks, unlocks new users)

**7. Two-way Rekordbox sync (2-3 weeks)**  
Write back to `master.db` using the documented Rekordbox SQLite schema. Write to a separate Rekordbox crate/playlist (`IDJLM Tagged`) rather than overwriting existing data — this is safe to adopt alongside an existing Rekordbox workflow. This is the main reason professionals will not fully commit to IDJLM.

**8. Serato crate export (1 week)**  
Serato stores library data in `_Serato_/database V2` — a binary format that has been reverse-engineered and documented. Libraries like `pyserato` exist. Exporting to Serato crates opens the entire Serato user base.

**9. Energy calibration per library (3-5 days)**  
On first import, analyse a sample of 50 tracks to establish the library's loudness baseline. Use this to set a library-specific normalisation constant instead of the hardcoded `0.35`. Users with loud modern masters and users with dynamic 1970s vinyl recordings will both get accurate 1-10 energy scores.

**10. Live BPM tap override (2-3 days)**  
Add a tap-BPM button in the track detail panel. When a user taps tempo, store it as `override_bpm` with a `source: "tap"` flag, and recalculate all mix scores against the tapped value in real time. DJs frequently know the correct BPM but the analyser is wrong — giving them a fast correction path is table stakes.

---

## 6. UI/UX Vision — World-Class Professional DJ Tool

The current UI is functional and clean but it feels like a web app pretending to be a desktop app. A world-class professional tool looks and feels like Rekordbox 7 or Traktor Pro — dense information, high contrast, every pixel earns its place.

### Visual Design Direction

**Dark-first, always.** DJs work in dark rooms. The light theme can exist for library-organising-at-home sessions, but the default must be the dark theme, and it must be refined until it looks expensive. The current purple-tinted dark (`--bg0: #0d0d11`) is the right instinct — deepen it. Rekordbox uses near-black with subtle blue-grey tints. Traktor uses pure black with electric blue accents. Pick a lane and commit.

**Three-panel layout as the permanent home screen.** Left panel: library/filters (always visible). Centre panel: track table (primary workspace). Right panel: waveform + detail (collapses to icon bar when not in use). This is the standard for professional DJ software because it matches the mental model of "browse, select, inspect." The current tab-based navigation that hides the library when you open the Set Planner is the wrong pattern — professionals need to see their library while building sets.

**Waveform as a first-class citizen.** The current waveform is good (real amplitude peaks, purple-to-cyan gradient, playhead scrubbing) but it is buried in a detail panel. The waveform should be visible in the track table as a mini-waveform column — like Rekordbox's beatgrid overview. DJs navigate by waveform shape, not by filename.

**BPM and Key displayed prominently.** In the track table, BPM and Key should be displayed in a larger font than the artist/title, not smaller. DJs search by BPM and Key first, title second.

**Colour-coded genre taxonomy.** Each primary genre gets a colour: Salsa = red, Bachata = blue, Kizomba = gold, Cha Cha = green. These colours appear as a left-border stripe on every row, not just in the Genre column. At a glance, a DJ should see the genre balance of any filter result before reading a single word.

### Interaction Design

**Keyboard-first, click-second.** Add: `J/K` for up/down navigation (Vim-style), `A` to instantly approve current track and advance, `R` to re-classify current track, `E` to open edit panel inline.

**Inline editing everywhere.** Clicking a cell in the review table should make it directly editable inline — like Airtable. Press Enter to confirm, Escape to cancel. Opening a modal for every tag edit breaks bulk review flow.

**Drag-and-drop set building.** Allow dragging tracks from the library directly into the set planner list. Show BPM transition rating in real time as you drag.

**Background analysis with persistent status bar.** Analysis and classification should run in the background with a persistent status bar at the bottom — like a browser download indicator. The user should be able to browse and review tracks while analysis runs on the rest. The current blocking UI is acceptable at 100 tracks; it is unusable at 5,000.

### Feature Surface Reduction

The Stats dashboard is impressive but it is a feature that gets used once per library, not per session. Move it behind a "Library Health" button, not a permanent tab. The five permanent tabs should be: Library, Review, Set Planner, Advisor, Settings. Everything else is secondary.

---

## 7. Monetisation Angle

**Recommendation: $79 one-time purchase, $9/month Pro tier.**

### Why One-Time Alone Is the Wrong Primary Model

DJ tools are distributed through community word-of-mouth — gigs, Facebook groups, Reddit. A $79 one-time price looks expensive to a bedroom DJ and cheap to a working professional. A freemium model removes friction at the top of the funnel and captures value from heavy users.

### Tiered Model

**Free (forever, no card required)**
- Import up to 500 tracks
- Analysis: BPM, key, energy, waveform
- Basic genre classification (Gemini free tier, 3 genres: Salsa/Bachata/Kizomba)
- Read from existing Rekordbox library
- Export to M3U

**Pro — $9/month or $79/year**
- Unlimited tracks
- Full genre taxonomy (all sub-genres, custom taxonomies)
- All 6 AI providers + fallback chain
- Next Track Advisor + Set Planner
- Rekordbox write-back
- Serato export
- Latin analysis (clave detection, auto-cues)
- LUFS analysis
- Multi-source enrichment (Spotify, Deezer, Last.fm, Beatport)

**Agency/Studio — $29/month**
- Everything in Pro
- Multiple library management (venue library + personal library)
- Shareable taxonomy exports
- Team seat sharing (2 seats)

### Acquisition Strategy

**Targeted Reddit seeding.** r/DJs, r/latinos, r/salsadancing, r/bachata. Not ads — genuine posts showing the Latin sub-genre detection working on real tracks. This is the niche where IDJLM has no competition.

**YouTube demo with real DJ workflow.** A 10-minute video showing a DJ going from "I have 2,000 untagged tracks" to "my djay Pro smart playlists work and I built a set in 20 minutes."

**Rekordbox users frustrated with Latin genre support.** There are hundreds of posts on DJ forums about Rekordbox's terrible Latin genre tagging. A landing page specifically targeting "Rekordbox Latin music organiser" as a search term will capture this intent for free.

**Free tier as the primary distribution vehicle.** The free tier should be genuinely useful. A free user who organises 500 tracks and then has 501 is already sold.

---

## 8. North Star

IDJLM Pro should become the tool that serious DJs run every track through before it touches their performance software. Not a replacement for Rekordbox or Serato — a mandatory step upstream of them. The vision is a DJ receiving new tracks, dropping them into IDJLM, and having everything analysed, classified, enriched, and tagged correctly within 10 minutes, ready to sync to their CDJs or controller. The Latin domain knowledge is the right beachhead — it is an underserved niche with passionate, word-of-mouth-driven users who have been failed by every generic tool that calls "salsa" a genre. Nail the Latin niche first, nail it so completely that every salsa/bachata DJ tells two other DJs, and then expand. The architecture decisions that matter most right now are the ones that prevent scale from becoming a ceiling: content-hash track identity, SQLite persistence, and accurate key detection. Everything else is refinement. The ceiling for this product, executed well, is the DJ equivalent of what Lightroom is for photographers — not optional infrastructure, but the tool that defines the professional standard for how you manage your music.
