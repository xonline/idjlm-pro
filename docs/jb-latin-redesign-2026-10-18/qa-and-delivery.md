# IDJLM Latin redesign: QA and delivery plan

This plan defines the evidence required before implementation is called ready. It separates interface behavior, audio classification quality, metadata write safety, and transfer into djay. No result below is measured unless the evidence ledger says so. The implementation remains local-first and targets an M3 MacBook Air with 16 GB of memory and about 15,000 tracks.

## Delivery order and gates

Do not spend effort on a broad UI rewrite before an audio candidate demonstrates useful accuracy on the prioritized styles. The first delivery is a transport and data compatibility spike, followed by evidence and model selection. The actual device, library, and subscription state are not yet confirmed, so do not promise a calendar date or use a device-transfer assumption as a release gate until it is tested. These phases map to the [authoritative delivery sequence](README.md#authoritative-delivery-sequence): QA 0 is Stage 0, QA 1–2 Stage 1, QA 3 Stage 2, QA 4–5 Stage 3, and QA 6 Stage 4. Route mechanics and primary sources are centralized in the [djay transfer guide](djay-transfer.md).

| Phase | Deliverable | Pass gate | Stop or hold when |
|---|---|---|---|
| 0. Inventory and compatibility spike | Read-only inventory design, accessible tag-field sample, disposable Genre and Comment write/readback, and target-path matrix for direct files, Apple Music, Finder transfer, and optional OneLibrary. | At least one viable route ends with tracks in a djay source that supports the needed category browsing, search, filter, and playback. Record exact receiving location and constraints. | Only raw Files browsing works and cannot meet search/category needs; tags disappear; a route requires unapproved purchase, private database writing, or untested network service. |
| 1. Taxonomy, provenance, and baseline | Versioned axis definitions, label rubric, lawful dataset inventory, data provenance report, current metadata-only baseline, and fixed train/dev/calibration/test split plan. | Salsa, Bachata, Kizomba priority boundaries and hard negatives are explicit. No artist, album, duplicate recording, or remix version crosses partitions. | Available evidence cannot distinguish target classes or licenses cannot support the intended use. Report the gap; do not assign a large labeling task to Poy. |
| 2. Audio candidate benchmark | Compare metadata baseline, permissive CLAP, and Discogs MAEST519; measure latency, memory, and classwise errors on the same verified split. Evaluate Essentia EffNet400 only as a speed reference because its published classes omit priority labels. | Held-out report includes confidence calibration, abstention, classwise precision/recall, coverage, confidence intervals, and false positives on hard negatives. | No candidate clears early research gates or uncertainty is too large. Continue research or narrow enabled labels. Do not start a UI rewrite. |
| 3. Supported classifier and review core | Versioned local model runner, persistent queue, cached audio embeddings, per-axis results, corrections and locks, unknown/mixed states, and review-scope diff. | Reclassification preserves human locks; accepts do not train; restarted jobs resume idempotently; product gates are tested on a frozen test set. | Review workload remains impractical or accuracy falls as queue scope is reduced. Do not reduce the precision gate to manufacture coverage. |
| 4. Library and write safety | Virtualized Library, Review, Categories, Activity, Settings, track inspector, import wizard, and format-aware write/restore jobs. Run against synthetic large-library fixtures before any real track write. | UI contracts pass at 15,000 rows. Every supported format has backup, write, readback, conflict, recovery, and restore evidence. | A write can report success without readback, a backup can omit changed fields, or migration risks original/human data. Keep the release in read-only/shadow mode. |
| 5. djay delivery and device acceptance | Tested export adapter and step-by-step user status with a target Mac and iPad. | A disposable collection proves field survival, indexing, search/filter use, playback, and retag behavior in each route declared supported. | Only a route that lacks required search/category behavior works, a transfer is falsely marked verified, or the device or library state needed for the test is unavailable. |
| 6. 15,000-track soak and supported release | Cold first scan, warm rescan, changed-file-only scan, recovery, storage, and residual review workload on the target M3. | Report measured duration, peak memory, disk/cache use, classwise uncertainty, errors, and remaining review minutes. Supported labels and routes are listed narrowly. | No real M3 evidence, excessive review burden, memory instability, incomplete checkpoint recovery, or required precision does not hold. |

Engineering owns lawful dataset discovery, tag inventory, bootstrap cleaning, split construction, and finding expert verification sources. Poy is not asked to label thousands of recordings. If independent specialist verification cannot be sourced, keep the classifier in research or conservative assistive status and write down that gap. Existing comments, Mp3tag Genre values, folders, uploader tags, and artist heuristics are provenance-marked evidence, not gold labels by default.

## Classifier benchmark contract

Prioritize Salsa, then Bachata, then Kizomba, then the fourth wave of Cha-cha, Charanga, and Boogaloo. Reggaeton, Bolero, and other styles are later expansion and hard negatives for early evaluation. Measure family separately from style, dance suitability, production/version, and vocal language. English vocals alone do not prove a remix. A confident family may be accepted while a style remains unknown.

Benchmark at least three baselines on the same decoded audio and split: current metadata-only prompts, permissively licensed CLAP embeddings, and Discogs MAEST519. MAEST519 has a 30-second input and includes some fourth-wave classes and Bachata or Timba, but not Kizomba, Salsa Romántica, or Salsa Dura. It is a candidate, not a selected model or validated answer. EffNet400 can measure a speed baseline but omits Bachata, Timba, and Kizomba from its published classes. Audit exact weight, dependency, and distribution licenses before use. CLAP raw cosine or softmax scores are not calibrated probabilities.

For each model, record preprocessing and version, model license, input windows, full-decode cost, embeddings, classification cost, cold and warm cache behavior, peak resident memory, CPU and Metal parity, per-family and per-style confusion matrix, macro and per-class precision/recall, calibration error, abstention coverage, and false positives on negative groups. Candidate windows sample distributed sections after a cheap full-track silence and section-change pass. Start with the model’s supported window size. Expand to disputed sections only after disagreement. Never average a full medley into one forced label.

Use an artist-, album-, recording-, and version-separated train/dev/calibration/held-out test split. Put remixes, live versions, speed-edited copies, and sections of the same recording in one partition. Keep the final test frozen. Strip artist and title metadata during audio-only evaluation. Include unseen artists, audio quality variants, non-target Latin styles, same-BPM pop, son, mambo, bolero, and unrelated genres as negative cases. Avoid random foundation-model training. Compare frozen embeddings with a small regularized classifier before considering expensive fine-tuning.

The research target is at least 0.90 macro F1 for supported core families, with per-class results and uncertainty. An auto-ready subset requires at least 98% measured precision overall and 95% for each enabled family at meaningful lower confidence bounds. These are proposed gates, not results or a guarantee. Report coverage and the supported-label set; an abstain-all system cannot pass. For detailed labels, use a proposed 0.85 macro F1 research gate and at least 95% precision on accepted labels. Narrow classes cannot be certified from a handful of examples. Report false positives on adjudicated Cha-cha negatives. Expert review must adjudicate disagreements and retain multi-label or uncertain decisions when no reliable single answer exists.

Report automation as newly auto-classified tracks only. Count preserved human labels and corrected labels separately. Report parent-family completion separately from detail-label completion, unsupported tracks, and unknown axes. Do not count a blank style as style completion. At 15,000 tracks, 70% automation leaves 4,500 to review and is not an acceptable efficiency goal. A proposed 95% broad-family auto-ready target leaves about 750 tracks when all 15,000 qualify; this is a target, not evidence. At 14,250 auto-ready tracks, 98% precision can still imply about 285 incorrect labels. This arithmetic is illustrative, not a forecast. Product signoff shows expected residual workload, measured human review minutes, precision by class, uncertainty intervals, and queue behavior as filters tighten. Stop if the workflow would require Poy to perform an impractical listening burden.

## UI and workflow contract tests

Use deterministic API fixtures and synthetic track records for interface tests. They prove state transitions and scope behavior, not classifier accuracy. Seed 15,000 rows without real audio and verify the UI never creates 15,000 DOM rows. Use stable IDs independent of path and position. Test server pagination or virtualization at first, middle, and last pages. Assert that filters and selection survive paging, while **Select visible** and **Select all filtered** remain distinct.

The following journeys use IDs from [the UX/UI specification](ux-ui-spec.md). They are release-contract tests, not claims that current endpoints already implement the planned response schemas.

| Test | Journey and expected result |
|---|---|
| Q-UI-01 | U-001/U-023: Complete import wizard with supported, unsupported, duplicate, unreadable, and permission-denied files. Originals do not move. The preview count matches the durable job manifest. |
| Q-UI-02 | U-002/U-003: Load 15,000 synthetic tracks, filter to 1,248, select visible, then select all filtered. Page, sort, and reopen the view. Exact IDs and scope labels remain stable. |
| Q-UI-03 | U-004/U-009: Return family Salsa with unknown style. The row is family-ready and detail-incomplete. Preserved human labels are excluded from new-automation coverage. |
| Q-UI-04 | U-005/U-012: Save a stacked “Bachata influenced / English remix” view, reopen it, and verify no field changed. If version evidence is absent, the view does not silently treat English vocals as remix proof. |
| Q-UI-05 | U-006/U-008: Accept a proposal, explicitly correct another, lock family only, then reclassify. Acceptance does not enter training; the correction and lock remain; unrelated axes can update. |
| Q-UI-06 | U-007/U-025: Select 12 tracks across pages, edit Comment append mode, and preview. Literal commas remain intact. The diff lists exactly 12 IDs and only the selected field changes. |
| Q-UI-07 | U-013/U-014/U-026: Preview a mixed batch with supported and unsupported formats, conflict, and backup failure. Only safe rows are included after approval. Prepared, transferred, and verified states cannot be skipped. |
| Q-UI-08 | U-017/U-019: Start an analysis job, stop the process at a file boundary, restart, and resume. Completed rows are not duplicated and failures are not counted as complete. |
| Q-UI-09 | U-018: Restore a backup after a file changes externally. The app detects the revision mismatch and blocks overwrite. A matching revision restores only the intended fields and reads them back. |
| Q-UI-10 | U-020/U-021/U-022: Fresh setup with no network and no model reports the offline limitation without API-key prompt. Interrupted model download resumes, checksum failure blocks installation, and cache clearing preserves backups and corrections. |
| Q-UI-11 | U-024/U-027: Use keyboard-only navigation, screen zoom, and reduced motion. Opening/closing inspector restores focus, playback remains single-owner, and no shortcut writes without explicit confirmation. |
| Q-UI-12 | U-015/U-016: Run only a route declared supported. The resulting track is confirmed usable in djay. Unsupported or untested Apple Music/Finder routes remain labeled as unverified. |

For each page, test empty, loading, partial, error, offline, selection, and dirty states. Verify visible text communicates what happened, what remains, and the next action. Errors should include a track or job reference and not disappear on navigation. Network loss must not disable local review of saved results. A stale write preview expires if the file revision, field mapping, or batch scope changes.

## Files, tags, backup, and recovery

Test MP3, FLAC, WAV, M4A, AAC, OGG, and AIFF only if each format is listed as write-supported. Until an individual format passes, allow scan or preview but block write-back with an explicit reason. Use disposable copies, not the user’s music directory. Capture every changed field and relevant raw tag frame in a unique job and file backup. Simulate backup creation failure, write failure, partial write, process crash after write but before DB update, full disk, readback mismatch, permission revocation, and external edits after preview.

For each successful format, write Genre and Comment while preserving unrelated fields, reopen with an independent tag reader, and compare exact values and encoding. Verify original audio bytes or decoded audio remain unchanged. Make retry idempotent. Do not overwrite changed files. Confirm the DB state advances to `written_verified` only after file readback. Restore must check the recorded revision and retain the failed or conflicting backup. A visible success toast without per-file verification fails this phase.

Cache tests use complete-file identity for write conflict and cache invalidation. Exact identical audio bytes may share embeddings only with matching decoder, preprocessing, encoder, and layer versions. A perceptual similarity match can help navigation but never merges live takes, remixes, or speed changes. Taxonomy or compatible classifier-head changes invalidate predictions and calibration, not embeddings. Encoder changes invalidate embeddings. Cache restore must either contain every required analysis field or mark missing values and recompute. Do not use first-megabyte hash as audio identity.

## djay transfer and indexing acceptance

The release requirement is tracks discoverable by family and useful substyle in djay, not files that merely play from a folder. Apply the cable-first, wireless-SMB, Music fallback, and optional OneLibrary order in the [djay transfer guide](djay-transfer.md). A route with unknown capability can run its small disposable compatibility test but cannot be certified for a full-library export. Do not write private databases, assume M3U portability, enable a subscription, or present staging as device delivery.

Use the guide’s 20-copy fixture: priority-family and fourth-wave examples, mixed formats, detailed Comment/no Comment, a multi-style candidate, and an already-imported retag. Verify initial import, retag, Genre browsing/search/filter, detailed-category behavior, offline playback, disconnect/retry, duplicates and cue preservation where applicable, source preservation, storage preflight, and exact receiving location. Record iPad, djay, and entitlement version and the observed field behavior. If Comment is not useful for category discovery, test the staged-copy `djay extended Genre` profile and record its exact result.

Use exactly these product states: **Draft**, **Prepared**, **Transferred (user-confirmed)**, **Transfer unverified**, **Verified in djay**, **Failed**, **Missing media**, and **Stale**. Only the last verification state follows dated device evidence whose scope says sample or complete export. If category search fails, direct Files playback is not equivalent success.

## Accessibility, device, and workload matrix

Run the UI contract at 1024×768 and 1440-wide viewports. Test keyboard-only operation, VoiceOver labels and status announcements on macOS, focus visibility in light and dark themes, 200% text zoom, reduced motion, table headers, dialog focus traps, and color contrast. Use WCAG 2.2 AA contrast thresholds for text and controls. Announce queue count and progress without speaking every file. Do not flash progress. Provide keyboard alternatives for drag-and-drop and icon-only actions.

Run on the specified M3 MacBook Air with 16 GB RAM. Start with CPU behavior; evaluate Metal only after output parity. A proposed analysis-worker ceiling is 4 GB, to be measured and revisited based on model fit. Measure model load, single-track decode, representative windows, embedding cache hit, cold scan, warm rescan, changed-file scan, cancellation, and resumed scan separately. Test at 100, 1,000, and 15,000 tracks with varied duration, codec, and file quality. Report actual duration, peak memory, cache/storage size, UI responsiveness, thermals or sustained throttling, failures, and review workload. No speed promise is made before these measurements.

| Platform | Minimum acceptance |
|---|---|
| M3 MacBook Air, 16 GB | Offline classification after optional model install; responsive UI during analysis; bounded worker memory; no data loss on sleep, restart, cancellation, or full disk. |
| iPad running target djay version | Imported or transferred tracks open and play offline; required Genre/Comment visibility and search/filter are verified in a supported source. Record model, OS, storage, djay version, and subscription state. |
| Mac djay, if available | Verify OneLibrary or indexed route only when the app/version and account are available. Absence does not block the plan; it marks that route unverified. |
| No model/network | Library, saved results, corrections, tags, and Activity remain usable. Download-dependent actions explain their limits and can resume later. |

## Evidence ledger (all entries start not run)

Keep this ledger with implementation evidence. Attach test command or scripted scenario, environment, date, observed result, and artifact path. A blank or **NOT RUN** entry is not a pass. Do not fill predicted results as actual results.

| Evidence ID | Area | Required artifact | Status |
|---|---|---|---|
| E-01 | Tag and field inventory | Field/value counts with personal vocabulary separated from assignments | NOT RUN |
| E-02 | djay route discovery | Route matrix with exact iPad destination, source type, field visibility, search/filter, and retag behavior | NOT RUN |
| E-03 | Dataset and rights | Candidate dataset/model manifest with per-artifact and intended-use license decision | NOT RUN |
| E-04 | Frozen benchmark | Split manifest, adjudication provenance, confusion matrices, classwise confidence intervals and coverage | NOT RUN |
| E-05 | M3 performance | Cold, warm, and changed-file measurements at 100, 1,000, and 15,000 tracks | NOT RUN |
| E-06 | 15k UI contract | Automated virtualization, pagination, selection, filters, saved-view and recovery results | NOT RUN |
| E-07 | Write safety | Per-format backup, write/readback, preservation, conflict, failure, and restore evidence | NOT RUN |
| E-08 | Restart recovery | Persistent job checkpoint and idempotent retry evidence | NOT RUN |
| E-09 | Accessibility | Contrast report, keyboard walkthrough, VoiceOver status checks, zoom and reduced-motion results | NOT RUN |
| E-10 | djay acceptance | Disposable import and retag observations for every route claimed supported | NOT RUN |
| E-11 | Human workload | Newly auto-ready count, preserved and corrected counts, unresolved count, measured review minutes | NOT RUN |
| E-12 | Release scope | Exact supported labels, formats, routes, known limitations, and independent verification gap | NOT RUN |

## Traceability to the UX specification

Use this matrix to keep the implementation and QA handoffs aligned.

| UX area | Required contract | QA evidence |
|---|---|---|
| Library U-001–U-005 | Import, 15k virtualization, exact selection, unknown style, saved view | Q-UI-01–04, E-06 |
| Review U-006–U-009 | Human decision provenance, locks, scoped diff, distinct completion counts | Q-UI-03, Q-UI-05–07, E-04, E-11 |
| Categories U-010–U-012 | Shared schema, vocabulary-only state, non-destructive saved filters | Q-UI-04, E-01 |
| Export U-013–U-016 | Field diff, staged status, djay compatibility, legacy routes retained until tested | Q-UI-07, Q-UI-12, E-02, E-10 |
| Activity U-017–U-019 | Durable jobs, idempotent resume, verified restore | Q-UI-08–09, E-07–08 |
| Settings U-020–U-022 | Optional local model, resumable/checksummed install, scoped cache clear | Q-UI-10, E-03, E-05 |
| Shared flow U-023–U-027 | Safe import, inspector, exact batch behavior, write approval, safe shortcuts | Q-UI-01, Q-UI-06–07, Q-UI-11, E-06–09 |

