# Engineering specification

This is a reference for JB’s implementation of the Latin classifier redesign. It describes the current source where confirmed and marks future components and endpoints as proposed. The existing audit, [Latin music classifier redesign](../latin-classifier-redesign-2026-10-18.md), remains the evidence record for current defects and cited model, licensing, and workflow claims. [djay transfer design and device verification](djay-transfer.md) owns route order, device states, and external transfer capability evidence.

## 1. Product boundary and architecture

Keep the desktop architecture: Tauri starts and stops the Python Flask sidecar; Flask serves the JavaScript UI and local API; SQLite persists library state in the user data directory. `app/__init__.py` creates the Flask app, initializes `TrackStore`, loads taxonomy, and registers route blueprints. `src-tauri/src/main.rs` launches the sidecar and exposes the native folder picker. The current API listens on loopback port 5050. Preserve this lifecycle and verify that long-running analysis does not break clean shutdown or startup recovery.

Replace the classifier’s evidence path, not the desktop shell. `app/services/classifier.py` currently constructs text prompts and calls configured providers. It is a metadata classifier, not an audio classifier. The proposed local audio runtime becomes the source of audio evidence. Existing metadata and optional enrichment can be secondary evidence, with source and reliability recorded. The default path must be local and must not call a paid or cloud API. Do not add a second web service, LAN server, native iOS app, or a private djay integration.

One local worker owns model loading, decode/feature queues, and bounded inference. Keep request handling and the UI responsive while the worker processes resumable jobs. Limit resident audio payloads to a small queue; do not hold a library-wide waveform or embedding matrix in Python memory. Target a proposed 4 GB worker ceiling, but report it as unmeasured until the M3 benchmark. SQLite writes happen in short transactions. A failed file records an item error and does not abort unrelated items. Pause, cancel, and shutdown stop at a safe file boundary and persist the current cursor.

Model choice remains an evidence gate. Benchmark CLAP and MAEST519, with the metadata-only baseline. MAEST519’s labels do not include all target fine styles and it lacks Kizomba, Salsa Romántica, and Salsa Dura. CLAP embeddings can rank candidate labels but do not supply calibrated probabilities. The audit links the model cards and licensing evidence. Review the exact weight artifact and use rights before shipping it. Do not download weights as part of the plan. Select the smallest candidate that meets held-out accuracy, licensing, M3 resource, offline operation, and packaging requirements. Do not train from scratch by default.

## 2. Current source map and proposed ownership

The table maps real files inspected in the current checkout. Proposed file names are implementation suggestions, not present APIs. Keep existing boundaries unless a focused prototype shows a simpler fit.

| Concern | Current source and callers | Proposed responsibility |
|---|---|---|
| Desktop lifecycle and permissions | `src-tauri/src/main.rs`; `src-tauri/tauri.conf.json`; `run_app.py`; `idjlm.spec` | Keep sidecar startup, health wait, window, picker, and kill-on-exit behavior. Add only the minimum local model resource and permission wiring after packaging proof. Keep user data outside the bundle. |
| Flask wiring and process state | `app/__init__.py`; registered blueprints include import, track, review, bulk, audio, session, export, progress, settings, and backup | Keep app composition. Move durable jobs and model worker ownership out of module globals. Keep only lightweight process handles and wake signals in memory. |
| Track identity and model | `app/models/track.py`; `scanner.py`; `fingerprint.py`; `analysis_cache.py` | Keep `Track` as the legacy library view during migration. Add separate identity, prediction, decision, and evidence records. Do not expand the `Track` JSON payload into the source of truth for every new subsystem. |
| SQLite | `app/services/track_store.py` | Preserve the existing `tracks(file_path, content_hash, payload_json, updated_at, created_at)` and `store_meta` data. Add versioned, non-destructive tables for jobs, identities/features, predictions, decisions, write previews, write ledger, export profiles, and export manifest. Keep path as a current location, not permanent audio identity. |
| Import and discovery | `app/routes/import_routes.py`; `app/services/scanner.py`; UI `inbox.js`, `dragdrop.js`, `pipeline.js` | Keep initial folder selection and incremental scan behavior. Add stable paginated discovery jobs, supported-format decode checks, and item-level errors. Never clear the library to replace it during a scan. |
| Audio analysis and classifier | `app/services/analyzer.py`, `latin_analyzer.py`, `classifier.py`; callers include `/api/analyze`, `/api/classify`, `/api/analyze/latin` | Keep general BPM/key analysis distinct from genre inference. Replace genre use of metadata prompts with local audio embeddings and frozen/calibrated heads. Preserve raw tempo candidates and mark clave/rhythm uncertain unless separately benchmarked. |
| Taxonomy | root `taxonomy.json`; `app/data/taxonomy_templates.json`; `app/routes/bulk_routes.py`; UI `taxonomy.js`, `editor.js` | Define one versioned schema and validate it before import, persistence, or prediction. Migrate legacy genre/subgenre mappings through an explicit reviewed mapping. Do not infer target values from a taxonomy palette. |
| Review and correction | `app/routes/review_routes.py`; `app/services/learning.py`; UI `review.js`, `classify.js`, `detail-dock.js` | Replace confidence-only bulk approval with selected prediction revision and class/axis gate. Keep acceptance separate from correction; only curated corrections may become training evidence. Keep human locks across reanalysis. |
| Audio playback | `app/routes/audio_routes.py`; `player.js`, `waveform.js`, `key-preview.js` | Reuse audio route and player where supported. Add optional section markers from model evidence. Playback failure must not prevent review or write safety. |
| Tag writing and backup | `app/services/tag_writer.py`, `tag_backup.py`; `review_routes.py`, `backup_routes.py` | Replace blind direct write with preview, conflict check, full tag backup, format-specific writer, atomic replacement where supported, read-back, and append-preserving comment mapping. Existing writer supports only a subset of formats safely; gate each format independently. |
| Export and destination | `app/routes/export_routes.py`; playlist export routes; `playlists-export.js`, `field-mappings.js` | Add explicit profile mapping, destination choice, dry-run manifest, incremental copy/export, and outcome ledger. Treat all djay transport paths as testable candidates. Never write private djay files. |
| UI bootstrap and shared modules | `templates/index.html`, `app/static/app.js`, `app/static/modules/*.js`, `app/static/style.css` | Keep the existing globals and initialization convention until migration is chosen. `app.js` calls many `initX()` functions explicitly; any new page or module must be added to the startup path and verified. UX page details are in `ux-ui-spec.md`. |
| Jobs and progress | `app/routes/progress_routes.py`; `app/__init__.py` progress queues; `pipeline.js`, `sync-center.js` | Retain SSE as a transport only if reconnect and replay work. Persist job state, event sequence, and cursor in SQLite. In-memory queues may wake streams but cannot be the only job record. |
| Existing utility areas | `advisor.py`, `mix_scorer.py`, `setplan_routes.py`, `setlist_routes.py`, `stats` in `bulk_routes.py`, `stem_routes.py`, UI `stems.js`, `rekordbox_*`, `serato_writer.py`, `organise_routes.py`, `duplicate_detector.py` | Keep, integrate, defer, or retire each area by explicit UX decision. Do not drop user data or features as a side effect of the classifier migration. Rekordbox/Serato and folder operations remain behind explicit preview, backup, and confirmation. |

The current frontend is not one page file. `app/static/app.js` initializes `LibraryToolbar`, theme, navigation, search, keyboard shortcuts, player, detail dock, inbox, sync center, tags sidebar, drag/drop, prepare panel, setlist timeline, and tracks tab. The redesign may reorganize those entry points, but it must account for every init function and preserve working non-classification functions by migration or a documented disposition.

## 3. Taxonomy and result contract

Use a versioned multi-axis taxonomy. A label has a stable machine ID, display name, axis, definition, inclusion examples, exclusion examples, and status. A vocabulary alias maps a personal label to a stable label or export string. Aliases never merge evidence or change the internal label. An export profile maps internal IDs to fields and values expected by a destination.

| Axis | Shape | Rules |
|---|---|---|
| `music_family` | One versioned label ID, or `unknown`, `mixed`, or `unsupported` | Current examples are Salsa, Bachata, Kizomba, Kompa, Cha-cha, and Boogaloo. The core release gates Salsa, Bachata, and Kizomba; later labels remain vocabulary-only or unsupported until enabled. Kompa must remain separate from Kizomba. |
| `style` | Zero or more IDs | Examples include Salsa Romántica, Salsa Dura, Timba, Bachata Dominicana, Bachata Moderna, and supported Kizomba styles. Each label needs examples and counterexamples. |
| `dance_use` | Zero or more IDs plus unknown state | Dance suitability describes use in a room, not musical identity. Bachata Sensual is a dance-use concept. Keep Charanga as a possible overlapping sound/arrangement cue and browse label. |
| `production` | Zero or more IDs and an explicit version state | Separate remix, live, acoustic, electronic production, fusion, and unknown version status. English vocals alone do not prove an English remix. |
| `vocal_presence` | `present`, `absent`, or `unknown` | Record whether language inference applies; an instrumental track has `absent`. |
| `vocal_language` | Zero or more languages; `mixed`, `unknown`, or `not_applicable` | Use `not_applicable` when vocal presence is absent. Language does not establish family or remix status. |
| `instrument_cue` | Zero or more supported IDs, otherwise absent | Include only cues with validated detector evidence or human provenance. Do not infer an ensemble from broad family predictions. |

A prediction is per axis and carries taxonomy version, model artifact ID and digest, feature version, head version, raw score, calibrated score or band, evidence references, creation time, and status. A score without calibration is a ranking value, never a probability. Use statuses `proposed`, `ready_for_review`, `auto_ready`, `abstained`, `unsupported`, `failed`, and `superseded`. `auto_ready` means the locked release gate is satisfied for that exact label. It does not authorize file writes.

A human decision records the selected track identity, axis, label IDs, source (`correction`, `acceptance`, `imported_tag`, or `curated_reference`), actor, time, and lock state. Acceptance records that the proposal was accepted; it is not a correction and does not become training truth. A correction creates or updates a lock that survives reanalysis. Imported Genre, Comment, folder, or external metadata remain evidence records with provenance and are never converted silently into a gold label.

Personal vocabulary mapping is lossless at the source boundary. Preserve the original Genre and raw Comment exactly. If the user maps an alias such as `English,fusion`, store the original string and an explicit mapping record. Never globally split comments by comma or normalize their delimiters. A per-user profile may export one broad Genre and a detailed Comment, but must show the mapped result before writing.

## 4. Persistence model and identities

The following SQLite entities are proposed. Keep row keys stable and use foreign keys for owned records. Do not destructively rewrite the existing `tracks` payload during rollout.

| Entity | Key and important fields | Purpose |
|---|---|---|
| `library_items` | `item_id` primary key; `current_path`; `path_revision`; `file_size`; `mtime_ns`; `full_file_sha256`; `audio_identity_id`; availability | One currently imported file location. Path can change. A file version is not merged with another version because metadata looks similar. |
| `audio_identities` | `audio_identity_id`; complete decoded-audio digest; decoder ID/version; canonical PCM parameters; preprocessing ID/version; encoder artifact digest; layer ID; feature schema | Identifies the exact audio feature input. The identity is valid only after full-file verification and successful decode under the recorded pipeline. |
| `feature_blobs` | `feature_id`; `audio_identity_id`; section/window plan version; payload location; payload checksum; completion state | Holds bounded reusable embeddings or features. Store large arrays in a checked local cache file; SQLite stores metadata and checksum. |
| `jobs` | `job_id`; `kind`; `state`; creation/update times; library scope; config snapshot; taxonomy/model versions; counters; cancel flag | Durable resumable operation. A job snapshots the scope and versions it started with. |
| `job_items` | `(job_id, item_id, stage)` key; state; cursor; attempt; error code/detail; started/finished times | Per-file progress and failure. A failed item does not abort the batch. |
| `predictions` | `prediction_id`; `item_id`; `audio_identity_id`; axis; label IDs; raw/calibrated scores; evidence JSON; version keys; status; revision | Immutable, versioned model output. Supersede rather than overwrite. |
| `decisions` | `decision_id`; `item_id`; axis; selected label IDs; source; lock; actor; revision; timestamp | Human/imported decisions and locks. Existing library values remain separately recoverable. |
| `write_previews` | `preview_id`; scope revision; selected fields; status; created time; expiry; serialized diff digest | Binds approval to the exact tracks, fields, and expected revisions. |
| `write_ledger` | `write_id`; `preview_id`; `item_id`; expected/current full checksum; backup reference; per-field old/new; status; readback; error | Durable per-file write outcome and recovery evidence. |
| `export_profiles` | `profile_id`; name; field mappings; vocabulary mappings; destination capabilities and version | User-reviewed internal-to-output mapping. No destination behavior is assumed. |
| `export_manifest` | `(profile_id, item_id, target)` key; audio identity; metadata revision; output checksum; status; timestamp | Incremental export state. It prevents redundant rewrite only when source identity and mapped metadata revision match. |

A taxonomy change creates a new taxonomy version. A label-head, calibration, or model artifact change creates a new prediction version. These invalidate predictions and thresholds. They do not invalidate features if decoded-audio identity, decoder, preprocessing, encoder, and layer keys match. A decode or feature-pipeline change invalidates the affected feature cache. A tag-only edit refreshes the full-file checksum for the write guard, then retains embeddings only if verified complete decoded-audio identity matches. Any decoded-audio difference invalidates them. The existing first-megabyte `content_hash` is not sufficient for either guard. A chromaprint or perceptual fingerprint may identify possible duplicates, but cannot validate cache reuse or suppress a distinct remix, live version, medley, speed edit, or master.

Cache files live under the user-writable application support directory, not in the PyInstaller bundle. Write feature files through a temporary path, flush, checksum, and atomically rename where the filesystem supports it. Record the complete row only after the blob verifies. Startup recovery removes or quarantines incomplete temporary blobs and marks interrupted items resumable. Never remove the last verified backup or source metadata as cache cleanup.

## 5. Job contract and lifecycle

All endpoint shapes in this section are proposed. Existing routes such as `/api/import`, `/api/analyze`, `/api/classify`, `/api/progress/<op_id>`, and `/api/review/write` have different behavior today. Do not present these proposed contracts as compatible existing APIs. Migrate callers as a single deliberate boundary, preserve legacy routes during transition where they are used, and retire them only after a caller search and compatibility test.

Start a job with a bounded request. For example:

```json
{
  "kind": "classify",
  "scope": {"library_id": "local", "item_ids": null, "filter": {"audio_state": "present"}},
  "axes": ["music_family", "style", "dance_use", "production", "vocal_language"],
  "model_profile": "local-latin-v1"
}
```

Return `202` with `job_id`, `state`, `created_at`, and a link to status. Validate the request and reject unsupported axes, profiles, or empty scope with stable error codes. A request that duplicates a live job with the same operation, scope, and version may return that job or a conflict with its ID; it must not start two model workers. Keep one active audio worker. Permit metadata inventory or UI reads concurrently when they do not saturate it.

`GET /api/v2/jobs/{job_id}` returns state, versions, counts by item state, current stage, timestamps, last event sequence, and resumability. `GET /api/v2/jobs/{job_id}/items?cursor=...&limit=...` returns stable IDs and per-file statuses in bounded pages. The page cursor is opaque and stable through retries. `POST /api/v2/jobs/{job_id}/pause`, `/resume`, and `/cancel` change durable state and return the accepted state. Cancel is cooperative; an item already at a non-interruptible safe write boundary finishes or rolls back before cancellation completes. A process exit moves an active job to `interrupted`, not `complete` or `failed`.

Events contain `job_id`, monotonically increasing `sequence`, `type`, timestamp, and small event-specific data. Event types include `job_started`, `stage_changed`, `item_completed`, `item_failed`, `counts_changed`, `pause_requested`, `paused`, `cancel_requested`, `cancelled`, and `completed`. Persist enough event history to reconnect with `Last-Event-ID` or fetch items and status after a stream gap. Do not send audio data or full absolute paths in progress events. The UI obtains the selected item details through normal local API calls.

Legal job states are `queued → running → pausing → paused → running`, `running → cancelling → cancelled`, `running → completed`, and `running → interrupted → queued` on explicit resume. A terminal failure describes job-level failure to initialize a model, open its database, or validate a required version. Per-item failures do not make the job terminal. Restart logic must not replay completed writes blindly; each stage is idempotent by item identity and version key.

Import scans in deterministic pages using canonical path plus file stat as a cheap inventory hint. Do not trust size or mtime as audio identity. For each newly changed or uncertain file, calculate the complete hash before making write decisions and decode when analysis is required. A skipped path can reuse previous analysis only when the complete verified audio identity and pipeline keys match. Different paths with proven identical audio may share a feature blob, but keep separate library items, tags, decisions, and write histories. Scanner errors, unsupported format, permission denial, disappearing file, and decode failure remain item-level outcomes.

## 6. Proposed API contracts

Use JSON errors shaped as `{"error":"stable_code","detail":"short explanation","request_id":"..."}`. Keep tracebacks and paths with private information in local logs, not API payloads. Validate types, ID scope, label membership, selected fields, and page limits at the API boundary.

| Proposed endpoint | Request | Result and failure behavior |
|---|---|---|
| `POST /api/v2/library/import-jobs` | Chosen local root, requested supported formats, stable pagination limit | `202` job reference. Reject unreadable/non-directory roots before enqueue. Do not write tags or remove old rows. |
| `GET /api/v2/library/items` | Cursor, limit, filters, sort, library revision | Stable page of item summaries plus `next_cursor` and revision. Return `409 stale_revision` if requested snapshot expired. |
| `GET /api/v2/items/{item_id}` | Item ID | Original tags, predictions, decisions, evidence references, revisions, and availability. Do not return embeddings. |
| `POST /api/v2/jobs` | Job kind, scoped IDs/filter, selected axes, optional approved model profile | `202` job. Reject unsupported taxonomy/model version before execution. |
| `GET /api/v2/jobs/{job_id}` | Job ID | Durable counts, versions, cursor summary, state, and resumability. `404` for unknown local job. |
| `GET /api/v2/jobs/{job_id}/items` | Stable cursor and bounded limit | Per-item outcomes without a library-sized response. |
| `GET /api/v2/jobs/{job_id}/events` | Optional sequence cursor | Replayable SSE or bounded event page. Client can recover from disconnect. |
| `POST /api/v2/reviews/previews` | Item IDs, per-item expected revisions, selected axis/field list | Immutable preview ID and field-by-field diff. Reject missing items; mark stale items for reload instead of guessing. |
| `POST /api/v2/reviews/decisions` | Preview ID, decision per item/axis, expected revision | Saved decision revision. Preserve lock state unless the user explicitly unlocks it. Acceptance and correction have different source values. |
| `POST /api/v2/writes/previews` | Item IDs, selected output fields, profile ID, expected decision/tag revisions | Preview ID, before/after diff, exact file IDs, current checksum, backup estimate, unsupported fields, and conflict state. No writes. |
| `POST /api/v2/writes/commit` | Preview ID and explicit `confirm: true` | `202` write job only when every selected file still matches the preview’s full checksum and field revisions. Stale files return `409` with item IDs requiring re-preview. |
| `GET /api/v2/writes/{write_id}` | Write ID | Per-file status: pending, backed up, written, read-back verified, conflict, failed, or recovery required. |
| `POST /api/v2/exports/previews` | Item IDs/filter, profile ID, destination handle, metadata revision | Dry-run count, bytes, mapping examples, conflicts, and manifest delta. No file copying. |
| `POST /api/v2/exports/commit` | Preview ID and explicit confirmation | Resumable export job and manifest reference. Reject stale source revisions or destination capability mismatch. |
| `GET /api/v2/taxonomy` | Optional version | Validated taxonomy and version. |
| `PUT /api/v2/taxonomy` | New full document plus expected prior version | Validate references and examples, then create a new version. Do not mutate historical predictions. |

The following UX actions have either a current reuse seam or a proposed durable contract; all `/api/v2` entries are proposed rather than existing behavior.

| UX action | Service contract |
|---|---|
| Saved views, sort, columns, and local layout | Proposed `GET`/`PUT /api/v2/views`; UI-local preferences are allowed until shared persistence is implemented. |
| Accept, correct, lock, or unlock a field | `POST /api/v2/reviews/decisions` with an explicit action and expected decision revision; current `review.js` routes are transition-only seams. |
| Play full track or evidence section | Reuse current `/api/audio` playback; proposed item evidence endpoint supplies section offsets. |
| Pause, resume, or cancel a job | Proposed `POST /api/v2/jobs/{job_id}/pause`, `/resume`, or `/cancel`; job lifecycle rules in section 5 apply. |
| Model install, pause, resume, cancel, verify, or repair | Proposed model-artifact job endpoints under `/api/v2/models`; persist artifact, license decision, checksum, and download state separately from classification jobs. |
| Settings save and scoped cache clear | Existing settings routes are seams; proposed versioned `GET`/`PUT /api/v2/settings` and `POST /api/v2/cache/clear-preview`/`commit` return exact affected bytes and exclude sources, decisions, and backups. |
| Restore preview and commit | Existing backup routes are seams; proposed `POST /api/v2/restores/previews` and `/commit` bind backup ID, current file checksum, fields, and explicit confirmation. |
| Prepare export, record user-confirmed transfer, or verify in djay | Proposed export preview/commit plus manifest-state actions. Use the state names and evidence required by [djay transfer guide](djay-transfer.md); no endpoint controls an iPad. |

The result schema example below is a proposed wire object, not the current `Track.to_dict()` shape:

```json
{
  "item_id": "item_01J...",
  "audio_identity": {"verified": true, "sha256": "...", "pipeline": "decoder-x/prep-2/encoder-y/layer-12"},
  "predictions": [
    {"axis": "music_family", "label_ids": ["salsa"], "raw_score": 0.91, "calibrated_band": "high", "status": "ready_for_review", "taxonomy_version": 3, "model_version": "local-latin-v1"},
    {"axis": "style", "label_ids": [], "status": "abstained", "reason_code": "no_supported_style_margin"}
  ],
  "decisions": [],
  "revisions": {"audio": 5, "tags": 9, "decisions": 2}
}
```

Do not make `raw_score` look like a probability in UI text. Display “model score” unless calibration has produced a defined probability or confidence band. Keep confidence separate for family and each other axis. A strong family result can stand when style abstains.

## 7. Concurrency, dirty state, and stale previews

Give each library item independent monotonically increasing revisions for audio identity, source tags, human decisions, and derived prediction set. Increment the tag revision after an external tag change, successful write, or import readback change. Increment the decision revision for any correction, acceptance, lock/unlock, or manual mapping that changes the chosen value. Increment the prediction-set revision when model/taxonomy recalculation changes the active set.

A review preview binds item IDs, selected axes, proposed values, source revisions, and a digest. If any bound revision changes before decision save, return `409 stale_preview` for affected items and keep non-stale items available for a new preview. Do not silently merge a stale approval into fresh values. A write preview binds exact file IDs, full file checksum, selected field values, expected tag and decision revisions, mapping profile version, and writer version. Recheck all of them immediately before backup and write. If a file disappeared, changed, became unreadable, or its selected value changed, mark conflict and require a fresh preview. Never apply a preview to a different file at the same path without re-verifying identity.

Serialize writes per file. A second operation targeting a locked item waits or returns a conflict; do not let concurrent jobs interleave tag changes. Use a short per-file transaction in SQLite to claim work, with a recoverable lease and expiry. Never hold a SQLite transaction during audio decode, inference, user confirmation, or an entire library job. On crash, reconcile the ledger against the file checksum and backup record. Do not claim undo when current file metadata no longer matches the known post-write version; show conflict and require the user to resolve it.

## 8. Audio feature and model runtime

The worker accepts one file at a time from a bounded queue. Its stage contract is: verify complete file identity; decode using a pinned decoder and canonical sample format; measure decode health and duration; create versioned representative windows; embed windows; store each complete feature blob; run one or more local heads; calibrate each axis; persist predictions and evidence; release decoded samples before the next file. Keep section offsets and the window plan with evidence so review can play the relevant original audio region. Do not copy long waveform payloads into events or every prediction row.

Benchmark candidate input needs against real target recordings. The audit suggests testing several 10-second CLAP windows and the published 30-second MAEST519 input, then choosing windows from measured accuracy and speed. This is an initial experiment, not a fixed production contract. Include intros, choruses, breakdowns, live sections, and medleys in validation. Expand windows only on uncertain or disagreeing heads if that improves measured outcomes. A model’s label inventory limits which labels it can support; never fill missing label classes by renaming unrelated model outputs.

Store model artifact digest, code version, decoder/preprocessor versions, sample rate, channels, window policy, pooling rule, label head, calibration version, and taxonomy version with each result. An exact feature cache hit requires matching complete decoded-audio identity and all feature-producing keys. Head and taxonomy changes can reuse embeddings but must produce new predictions and calibrated confidence. An encoder or preprocessing change requires new embeddings. A label-only tag edit refreshes the full-file checksum write guard but keeps embeddings only after verified complete decoded-audio identity matches. Audio differences invalidate the feature entry. A perceptual fingerprint is for duplicate discovery only.

Keep CPU as the correctness reference. Test Metal or other accelerators only after the same inputs produce equivalent outputs within a documented tolerance. Do not ship an accelerator-only path until fallback and packaging work offline on the target machine. Treat CLAP’s candidate similarity and MAEST519 output as ranking evidence until project calibration proves otherwise. Keep non-commercial MAEST519 weights out of a commercial release unless the exact licensing path permits it.

## 9. Safe write-back, backup, and export

The current `app/services/tag_writer.py` handles MP3 ID3 and writes Genre, a `COMM:subgenre:eng` comment, BPM, key, year, and selected custom fields. Its backup call captures only a subset of fields and a backup failure does not block writing. It writes an ID3 v2.4 file, has optional network album-art behavior, and does not provide the new plan’s required full format-specific round-trip guarantees. Treat it as a starting implementation, not proof that FLAC, M4A, WAV, AAC, OGG, AIFF, or all MP3 metadata cases are safe.

Before enabling a format, inventory all relevant frames/atoms, including multiple comments, encodings, artwork and unknown frames. Preserve untouched frames byte-for-byte where the library permits; otherwise show the exact unsupported-field risk and keep that format read-only. The approved profile controls which fields change. Default export profile keeps one broad Genre and maps detailed user labels to a compatible Comment only after a disposable route proves the receiving app sees, searches, and filters it. Do not replace the raw original comment. Append only with a profile-defined delimiter and preserve the original raw string in the ledger. If a destination cannot represent the detail reliably, keep it in the IDJLM catalogue and report that limitation.

For each file, verify access and checksum, create a complete sidecar backup of all writable tag state and a copy of original bytes where the format writer requires it, write to a sibling temporary file where supported, flush, atomically replace where the filesystem permits, reopen and read tags, confirm expected selected values, and confirm decoded-audio identity is unchanged. Record actual per-file outcome. If backup fails, stop before changing the file. If atomic replacement is unavailable, use a documented recovery protocol and do not claim atomicity. An explicit batch confirmation covers only the displayed selected file and field set.

Undo is another guarded write. It checks that the current file still matches the recorded post-write checksum and that the backup verifies. If either check fails, mark `undo_conflict` and preserve both versions for user resolution. Restore only the fields the ledger changed, unless a full-file restoration is required by the format writer and the user confirms the consequence. Do not overwrite newer unrelated metadata silently.

Export uses profile and destination capability records. Preview shows source count, new/changed/unchanged files, output size, existing target state, free space if available, unsupported mappings, and conflicts. Commit writes incrementally and records each source identity, metadata revision, target, and output checksum in the manifest. If a target exists with different audio or user data, stop for explicit conflict handling.

The [djay transfer guide](djay-transfer.md) is the single source for cable, wireless SMB, Music, and OneLibrary route capability, source links, profile behavior, and the prepared/transfer/verification contract. Engineering supplies the manifest, incremental staging, capability records, and truthful state transitions; it does not automate an undocumented iPad API, write private djay data, or treat M3U desktop paths as portable. Existing `applescript_routes.py` refreshes Music but not a device, and `sync-center.js` records `window.open()` rather than delivery; neither proves transfer.

## 10. Desktop security and local data boundaries

Keep the API bound to loopback. Do not change the sidecar to listen on `0.0.0.0` or add a LAN access mode. Treat every API path as untrusted even when the UI is local: validate IDs against the imported library, canonicalize selected paths, reject path traversal, and ensure a user-picked root does not grant an operation outside its declared scope. Resolve symlinks and recheck before destructive writes because paths can change after scan. Keep file writes behind the explicit selected-field approval and current identity check.

Do not place model credentials or service keys in bundle resources, job rows, event streams, logs, or exports. Default audio classification needs no credentials. Any optional remote enrichment remains separately configured and opt-in. Do not put absolute paths in analytics or progress feeds. Keep user data, databases, cache, logs, and backups in the app user data directories defined by `app/utils/paths.py` and `CLAUDE.md`; never write mutable runtime files into the PyInstaller bundle. The release package must disclose model artifact identity and license. This specification does not authorize fetching models or submitting audio anywhere.

## 11. Migration and compatibility plan

1. Add schema versioning and backups before adding durable records. Test migration on copies of old `tracks.db` and `session.json`. Preserve both source files until row counts and representative field comparisons pass.
2. Add library item, source metadata, decision, taxonomy version, and job records beside the current track facade. Provide a read-only adapter that can render old track rows into the new Library UI during transition.
3. Add new predictions beside existing `proposed_genre` and `proposed_subgenre`. Do not map old predictions to new axes as verified truth. Mark them `legacy_metadata_prediction` and keep them out of auto-ready evaluation.
4. Implement new taxonomy validation and import mapping in a dry-run migration. Report invalid labels, ambiguous aliases, and rows that need review. Commit a new taxonomy version only after a successful user-reviewed migration. Preserve the legacy file as a dated backup; do not rewrite it in place during initial rollout.
5. Route new jobs through persistent records. Search all callers of `/api/classify`, `/api/review/bulk-approve`, `/api/review/write`, and legacy taxonomy APIs before changing behavior. Keep compatibility adapters until UI, tests, and external callers are accounted for.
6. Run shadow prediction without writing tags. Compare model outputs with independently verified held-out labels. Existing accepted tags remain visible and do not count as newly automated coverage.
7. Enable per-format write-back only after disposable-copy round-trip, conflict, read-back, undo, and crash-recovery tests pass. Keep original files unchanged during evaluation.
8. Migrate all views according to [UX and UI specification](ux-ui-spec.md). Explicitly preserve or defer every ancillary feature. Remove a legacy path only after caller search, migration proof, and a release note.

## 12. Build phases and exit evidence

These work packages implement the [authoritative delivery sequence](README.md#authoritative-delivery-sequence): A is Stage 0, B Stage 1, C–D Stage 2, E Stage 3, and F Stage 4. A disposable route test is allowed in A; full-library export waits for route certification.

| Phase | Engineering deliverable | Exit condition |
|---|---|---|
| A. Compatibility inventory | Read-only inventory, disposable audio fixtures, folder and metadata route tests, migration snapshots | Current values and file identities are preserved; a route to djay is verified or its specific gap is recorded. |
| B. Model proof | Local baseline harness, grouped data splits, model/license record, M3 benchmark | Audio proves measurable Salsa value over metadata baseline on grouped development artists; one frozen final test follows locked model and thresholds. Otherwise stop and narrow the claim. |
| C. Durable core | Versioned taxonomy, item identity, persistent jobs, bounded worker, predictions, decisions, cache | Crash/restart, idempotency, cache invalidation, stale-state, and per-item failure checks pass on copies. No real tag writes. |
| D. Review UX | Library, Review, Categories, Export, Activity, Settings per UX spec | Keyboard and screen-reader paths work; family can be ready while style abstains; no selection or batch action is hidden. |
| E. Controlled write | Profile mappings, full backup, per-format writer, preview, ledger, read-back, guarded undo | Every enabled format passes destructive-path test suite on copies; stale checks block mutation. Unsupported formats remain read-only. |
| F. Scale and release | M3 100, 1,000, and 15,000-track runs; packaging, offline, lifecycle and route tests | Report accuracy, calibration, coverage, residual review minutes, cold/warm ETA, peak memory, failure recovery, and offline install. No metric is inferred from another machine. |

Accuracy gates and corpus rules live in [QA and delivery plan](qa-and-delivery.md) and the audit. They are release gates, not promises. Keep Salsa as the first supported family; add Bachata, Kizomba, and the fourth wave only after each label group has representative independently verified examples. A class without enough evidence remains review-only or unsupported.

## 13. Failure behavior

| Condition | Required behavior |
|---|---|
| Model missing or invalid license | Do not start classification. Show model state and next action. Never fall through to a paid/cloud provider. |
| Unsupported/corrupt file | Mark only that item failed or unsupported with a stable reason. Continue the job. Preserve prior tags and decisions. |
| Disk full or feature write interrupted | Keep the last verified feature blob. Mark the item resumable and remove or quarantine incomplete temp data on recovery. |
| Worker crash or app quit | Stop at safe boundary; mark job interrupted; persist completed items; restart sidecar normally and offer resume. |
| SQLite busy or disk error | Retry only bounded transient errors; surface durable failure when state cannot be recorded. Never report success before persistence. |
| Taxonomy changed while job runs | Finish only under its captured version or cancel before committing stale predictions. A new taxonomy triggers a new prediction version. |
| File moved, replaced, or edited | Recompute identity. Do not apply prior prediction or preview to different audio. Keep old record as unavailable/versioned history. |
| Stale preview or concurrent writer | Return conflict with exact item IDs and changed fields. Require a refreshed preview. Do not auto-merge. |
| Backup or post-write read-back fails | Stop that file before write if backup fails. If verification fails after write, report `recovery_required`, preserve backup, and block further writes to that item. |
| Destination capability unknown | Offer a dry-run and a small disposable compatibility test. Do not certify full-library export or claim Genre or Comment will display/search/filter in djay. |

## 14. Repository evidence and limits

The source map was checked against `app/__init__.py`, `app/models/track.py`, `app/services/track_store.py`, `app/services/scanner.py`, `app/services/classifier.py`, `app/services/analysis_cache.py`, `app/services/tag_writer.py`, `app/services/tag_backup.py`, `app/routes/import_routes.py`, `review_routes.py`, `audio_routes.py`, `export_routes.py`, `backup_routes.py`, `progress_routes.py`, `bulk_routes.py`, `applescript_routes.py`, the current UI module list, and `src-tauri/src/main.rs`. The current `TrackStore` is SQLite-backed but stores a serialized `Track` payload keyed by path; its `content_hash` is the first megabyte and must not be reused as the proposed complete-audio identity. The current review route approves from an uncalibrated confidence integer. The current writer is not a complete all-format round-trip system.

No app code or dataset was changed for this document. The spec does not prove candidate model performance, model use rights for an eventual release, independently verified data availability, M3 runtime, feature-cache size, destination transfer behavior, or iOS/djay field visibility. The team must measure those before making product claims or enabling writes.
