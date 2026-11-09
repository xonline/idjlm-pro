# IDJLM Latin redesign: UX and UI specification

This specification turns the classifier redesign into a usable 15,000-track local workflow. It is a plan, not an implemented interface. The current app already has a Tauri shell, Python routes, SQLite-backed tracks, a Library, review controls, playlist builder, taxonomy editor, settings, player, and export utilities. The redesign keeps that base where verified and replaces the page model around classification evidence, safe review, and delivery into Algoriddim djay. Route order and device verification live in the [djay transfer guide](djay-transfer.md).

The priority order is Salsa, Bachata, Kizomba, then Cha-cha, Charanga, and Boogaloo. Reggaeton, Bolero, and other styles are later taxonomy expansion and useful early hard negatives. Do not claim recognition for a label until its benchmark gate passes.

## Shared shell and visual rules

Use the sidebar navigation **Library**, **Review**, **Categories**, **Export**, **Activity**, and **Settings**. Keep the persistent mini-player at the bottom. A selected track opens a right-side **Track inspector** from Library or Review. It is a drawer, not another navigation item. Global dialogs handle import, batch edits, write preview, and help. The current `templates/partials/sidebar.html`, `tab-library.html`, `tab-inbox.html`, `tab-playlists.html`, `tab-setplan.html`, `tab-settings.html`, `tab-sync-center.html`, and `track-detail-panel.html` supply reusable controls and layout patterns. `app/static/modules/navigation.js`, `store.js`, `library.js`, `review.js`, `tracks.js`, `taxonomy.js`, `playlists-export.js`, and `settings.js` are the current front-end seams. API examples below name current endpoints; new fields and durable job contracts require implementation work.

At 1024×768, the app keeps the sidebar collapsible and table columns responsive. At widths through 1440, use a fixed-width sidebar, flexible work area, and optional inspector. Never render 15,000 rows into the DOM. Use server pagination or a virtualized window with keyboard row semantics, retain a stable track ID across sorting and filters, and show “Select visible” separately from “Select all 1,248 filtered tracks.” Selection survives paging and sorting; a filter change does not silently expand the selected set. Persist filters, sort, column choices, page or scroll position, and active saved view locally.

Only one playback owner exists. Navigating between pages, opening the inspector, or starting a preview must not start a second audio stream. Playback follows the selected track only when the user presses **Play**. For disputed tracks, offer labeled short sections and a seekable full track. Do not ask the user to replay the whole library. Similarity groups help navigation, but an exemplar preview never approves the rest of the group.

Keep the current dark and light theme options, but define semantic color tokens for page, panel, text, muted text, border, focus, success, warning, and error. Existing variables live in `app/static/style.css`; preserve their semantic aliases while auditing every theme. Do not encode confidence or job state by color alone. Meet WCAG 2.2 AA [contrast minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) of 4.5:1 for normal text and 3:1 for large text, use [24×24 CSS-pixel targets or documented criterion exceptions](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html), and keep focus [not obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html). Support keyboard-only navigation, 200% text zoom, reduced motion, and no flashing. Drag-and-drop taxonomy ordering needs buttons or keyboard alternatives. BPM and key remain readable at the dense table setting. Do not pick new hex values until contrast is measured.

Use one durable job vocabulary throughout: **Queued**, **Running**, **Pausing**, **Paused**, **Cancel requested**, **Cancelled**, **Completed**, **Completed with errors**, **Failed**, and **Interrupted**. Show current file, completed count, total count, skipped count, errors, elapsed time, and last checkpoint. Pause and cancel take effect only at a safe file boundary. If a write is already in its non-interruptible boundary, it finishes or rolls back before becoming Paused or Cancelled; a process exit becomes Interrupted. On restart, resume idempotently from the last verified file. A permission loss, corrupt file, full disk, removed folder, disconnected iPad, or offline model source names the affected item and offers a safe next action. Never report a write or transfer as complete before reading back the result.

The library vocabulary is personal, not a universal ontology. Preserve existing Genre and Comment values exactly until the user approves a scoped diff. Keep broad standard **Genre** and detailed compatible **Comment** as the preferred external profile. Do not split literal text such as `english,fusion` without checking stored values. Internally track music family, style labels, dance suitability, production or remix attributes, language, provenance, and confidence separately. An unresolved style must not erase a confident family. English vocals alone never prove a remix or Bachata influence.

For every page below, **Empty** means a useful next action, **Loading** means a skeleton plus status text, **Partial** means completed and outstanding counts, **Error** means a recoverable item-specific explanation, and **Offline** means local library operations continue while unavailable transfer/model services are marked unavailable. A dirty edit shows **Unsaved changes** and blocks navigation only when leaving would lose them. `Escape` closes the topmost drawer or dialog and returns focus to its opener. Focus remains trapped in a modal and returns to the launching control on close.

## Library

**Purpose and layout:** The Library is the main work surface for importing, finding, analyzing, and preparing tracks. Entry is the default page; exit is any nav destination, with current view and selection retained. Place a header row with library name, **Add folder**, **Scan changes**, and counts for total, preserved human labels, newly ready family labels, needs review, failed, and detailed labels still unknown. Under it place search, familiar family chips, stacked filters, saved views, a scope selector, and the virtualized table. Default columns are title/artist, existing Genre and Comment, proposed music labels, **Ready** or **Needs review**, and a clear conflict/write state; BPM and key are optional. Model names, taxonomy versions, raw scores, hashes, and pipeline revisions appear only in an expandable **Evidence & diagnostics** panel.

```text
Library  15,002 tracks     1,084 new ready     612 review     9 failures
[Add folder] [Scan changes] [Search…] [Filters ▾] [Saved view ▾]
Genre: Salsa ×   Style: Timba ×   Vocal: English ×   [Save view]
[Select visible] [Select all 612 filtered]                         1–100 of 612
□ Title / Artist | Existing Genre · Comment | Proposed music labels | Ready / Needs review | conflict
□ …
```

**Actions and results:** **Add folder** opens the import wizard. **Scan changes** enqueues only files whose full content or supported metadata identity changed; it does not move files. **Analyze selection** and **Classify eligible** create persistent jobs and show a scope summary before start. **Review selected** opens Review with the same IDs. **Edit fields** opens a batch-edit dialog. **Preview writes** opens the write-preview dialog. Selecting a row opens its inspector; double-click does not write tags. A saved view stores filter rules, columns, and sort, not a copied playlist. Category views such as “Bachata influenced / English remix” are user-owned filters, not model classes.

**States:** Empty: explain that files remain in place and offer **Add folder**. Loading: show the job banner and a table skeleton; leave navigation responsive. Partial: show scanned, analyzed, proposed, and failed totals separately and allow opening completed tracks. Error: retain imported records, list failed paths in **Activity**, and offer retry for failed IDs. Offline: analysis and review stay usable when models are already installed; show model setup for missing weights and transfer status unavailable when iPad is disconnected. Selection: toolbar names exact selected count and whether scope is visible or all filtered. Dirty: filter changes are not dirty; cell edits are, and a batch edit displays a before/after count before Apply.

**Data and service seams:** Current import and scan actions use `app/static/modules/library.js` and `/api/pick-folder`, `/api/import`, `/api/analyze`, `/api/classify`, `/api/tracks`, `/api/progress/{op_id}`, and its cancel route. Track lookup and playback use `tracks.js`, `/api/tracks/by-path`, and `/api/audio`. Add cursor/page queries, stable IDs, full-file revision identity, per-axis result/provenance, persisted view state, and durable job records. Do not pass file paths as identity across mutations.

**Acceptance:** U-001 Add-folder wizard imports without moving originals. U-002 Virtualization remains responsive at 15,000 fixture rows. U-003 Selection scope stays exact across filters and pages. U-004 A family result can be ready while style remains unknown. U-005 Saved view restores filters and scroll without changing track labels.

## Review

**Purpose and layout:** Review holds uncertain model results and explicit corrections. It has tabs or filters for **Needs review**, **Ready in bulk**, **Preserved existing**, **Human corrected**, and **Write failed**. Each group shows new auto-predictions separately from previously human-tagged tracks. A row displays existing and proposed music labels, plain-language confidence and evidence source, lock state, last decision, and any conflict. **Evidence & diagnostics** expands to model and taxonomy versions, scores, audio sections, and provenance for JB or a curious user. No single blended confidence hides uncertainty in language, dance suitability, style, or family.

```text
Review  [Needs review 612] [Ready 1,084] [Preserved] [Corrected] [Write failed]
[Family ▾] [Style ▾] [Evidence ▾] [Play disputed section]       1–50 of 612
Track | existing | proposed family · style | confidence | evidence | lock | decision
…
Selected: 12 tracks  [Accept proposal] [Correct] [Lock field] [Approve ready group]
```

**Actions and results:** **Accept proposal** records human acceptance but does not alter training data. **Correct** changes only explicitly chosen axes and stores a correction event with provenance. **Lock field** prevents future model runs from replacing that field. **Approve ready group** opens one scoped diff. It lists exact track IDs, changed fields, preserved fields, skipped unsupported values, and conflicts. One confirmation applies the reviewed scope; there is no per-track click requirement for a ready batch. **Write approved changes** moves to the write preview and requires a separate approval. Review state becomes `accepted`; file status changes only after verified write. Export delivery is tracked separately.

**States:** Empty: report “No tracks need review” with counts for unsupported and already preserved tracks; do not imply perfect coverage. Loading: retain the current queue and announce result loading. Partial: keep completed decisions visible and show remaining count; correction failures stay in the queue. Error: one bad track does not discard other decisions; show retry or keep current value. Offline: review saved proposals and corrections locally; disable unavailable model calls but preserve queued work. Selection: bulk actions name the exact cohort and do not silently include hidden rows. Dirty: corrections stay in a draft until **Save correction**; closing prompts save/discard/cancel.

**Data and service seams:** Current `app/static/modules/review.js` calls `/api/review/approve`, `/api/review/skip`, `/api/review/bulk-approve`, and `/api/review/write`. The redesign needs separate proposal acceptance, per-axis correction and lock records, calibrated confidence, explicit scope tokens, write-job IDs, and truthful per-file outcomes. Never feed approvals to the current `learning.py` prompt hints automatically.

**Acceptance:** U-006 Acceptance is not recorded as a training correction. U-007 Group approval displays exact scope and field diff. U-008 Per-axis uncertainty and field locks survive reclassification. U-009 New automation, preserved tags, and human corrections are separately counted.

## Categories

**Purpose and layout:** Categories gives Poy familiar family chips and saved views while storing separate axes internally. The main surface starts with Salsa, Bachata, Kizomba, Cha-cha, Charanga, and Boogaloo chips; choosing one shows its styles, dance use, production/version, and language filters. Each label has a plain definition, aliases, support status, and provenance; parent constraints and version metadata sit in **Evidence & diagnostics**. Charanga may be an arrangement cue and a browsing category that overlaps Salsa or Cha-cha. Preserve user terms and aliases without forcing them into one exclusive tree. Later labels include Reggaeton and Bolero. Distinguish Kompa, Douceur, Tarraxo, and related Kiz-adjacent labels rather than flattening them into Kizomba.

```text
Categories  [Salsa] [Bachata] [Kizomba] [Cha-cha] [Charanga] [Boogaloo] [More ▾]
Labels                         Definition and evidence
Salsa ▸                        status: supported · [Edit definition]
  Salsa Romántica              examples | exclusions | aliases | [Create saved view]
  Timba                        Vocabulary only | [Enable after benchmark]
[Add label] [Merge alias] [Export vocabulary]       [Unsaved changes: Review diff]
```

**Actions and results:** **Add label** creates a vocabulary entry in draft status. It does not certify model recognition. **Edit definition** changes taxonomy version and invalidates label predictions and calibration, not reusable audio embeddings. **Merge alias** preserves prior display strings and field provenance. **Create saved view** opens a filter builder that combines axes; it does not rewrite tags. The saved “Bachata influenced / English remix” view requires explicit evidence on influence, language, and version; otherwise the relevant axis remains unknown. Do not assume `english,fusion` is two tags. **Export vocabulary** saves a versioned JSON copy.

**States:** Empty: show built-in priority families and a clear **Add label** action. Loading: display version and source while reading taxonomy. Partial: unsupported labels stay visible as **Vocabulary only**. Error: reject invalid parents, duplicate IDs, and malformed schema without partial save. Offline: editing local definitions remains possible; model support state is last-known and clearly dated. Selection: multi-select enables alias or active-state changes only. Dirty: show taxonomy version diff and affected labels before save; cancel restores the previous draft.

**Data and service seams:** Current `taxonomy.js` uses `/api/taxonomy`, template and OneTagger import routes. `app/static/modules/editor.js` and `taxonomy.js` currently disagree with the default `subgenres` mapping shape. Replace these with one validated schema at API and persistence boundaries; do not silently migrate or reinterpret existing comments. Keep imported labels as observations.

**Acceptance:** U-010 Schema validation is shared by UI, API, and SQLite. U-011 Adding a label shows “Vocabulary only” until a benchmark enables it. U-012 Saved filters combine axes without modifying track metadata.

## Export

**Purpose and layout:** Export prepares selected or saved-view tracks for djay. The default is direct tagged-file staging to a selected Mac folder; source files remain in place. Route order, capability limits, metadata profiles, and the device test are authoritative in the [djay transfer guide](djay-transfer.md). The UI must not assume a receiving container, device API, custom-frame, or M3U behavior.

```text
Export  Scope: Salsa Romántica (642 tracks)     [Change scope]
Route:  ○ Direct cable  ○ Wireless SMB  ○ Music  ○ OneLibrary  [Test route]
Profile: Broad Genre + raw Comment ▾            [View field diff]
Preflight: 628 prepared · 8 changed · 6 missing · 14.2 GB · 21.0 GB free
Destination: /JB Export/Salsa                   [Prepare files]
Prepared: 628  Transfer unverified: 0  Verified in djay: 0    [Open Activity]
```

**Actions and results:** Choose a saved view or explicit track scope. Select the standard broad Genre plus detailed Comment profile, or the experimental `djay extended Genre` copy profile only after compatibility testing enables it. A side-by-side preview shows original fields, proposed fields, preserved literal text, missing values, path changes, and conflicts. **Prepare files** creates a durable copy/export job only after the user chooses an output folder. **Transfer** opens the selected supported handoff; it must not claim delivery. **Verify in djay** records the source, exact search/filter used, field visibility, and playback. Export states are **Draft**, **Prepared**, **Transferred (user-confirmed)**, **Transfer unverified**, **Verified in djay**, **Failed**, **Missing media**, and **Stale**.

**States:** Empty: ask for a saved view or selection. Loading: show per-file staging progress. Partial: allow opening the error manifest; report prepared and failed counts separately. Error: preserve the prepared output and identify each failed file; never mark the whole batch successful. Offline: direct file preparation works locally; device transfer is unavailable and says so. Selection: state whether selected IDs or every saved-view match are included. Dirty: changing field mappings or folder structure after preview marks it stale and requires a new diff.

**Data and service seams:** Existing `playlists-export.js`, `/api/export/m3u`, `/api/export/csv`, `/api/export/json`, `/api/export/rekordbox`, `/api/settings/field-mappings`, and tag-writing routes are starting points, not proof of iPad support. Add a target adapter interface with capabilities, staged file manifest, checksums, field mapping profile, and truthful status transitions. Test format-specific writes before enabling a format. Keep Comment bytes/text as entered; do not split delimiters by guess.

**Acceptance:** U-013 Preview shows every included field change and preserved comment. U-014 Prepared never equals Transferred or Verified. U-015 At least one tested route produces tracks discoverable in djay by the needed family and substyle without manual folder browsing; Comment behavior is documented separately. U-016 Existing Apple Music and Finder paths remain available until replacements pass acceptance.

## Activity

**Purpose and layout:** Activity is the durable job ledger and recovery page. List import, analysis, classification, tag write, export, and restore jobs with status, time, scope, counts, model or taxonomy version, and a concise error. Selecting a job opens per-file results and its input snapshot. The Restore panel lists verified backups and changed fields.

```text
Activity  [All jobs ▾] [Running] [Needs action] [Exports] [Restore]
Job                         state        completed / total    checkpoint       [Open]
Classify Salsa · local-v1   Pausing      1,284 / 3,000         track 1,285
Export Salsa Romántica      Prepared       628 / 628           profile v3       [Verify in djay]
Restore job 41              Completed       12 / 12            read-back passed [View diff]
```

**Actions and results:** **Pause**, **Resume**, **Cancel**, and **Retry failed files** act on the job ID. Retry reuses completed verified results and does not duplicate outputs. **Restore** previews original versus current fields and checks whether a file changed after backup. Restore writes only when the saved snapshot still matches the expected revision, then reads back and verifies. If the file changed externally, the app blocks overwrite and offers export of the backup or manual conflict resolution.

**States:** Empty: explain that jobs appear after import or analysis. Loading: show job skeleton and preserve filters. Partial: keep completed work visible while failed files remain actionable. Error: show error code, file, phase, and retry eligibility. Offline: local history and restore remain available; target-device checks show unavailable. Selection: bulk retry includes failed files only and displays count. Dirty: restore selection is a preview, not a change; navigation away discards the preview without writing.

**Data and service seams:** Existing progress routes expose `/api/progress/{op_id}` and cancellation; backup routes list, fetch, and restore. Extend the front-end `library.js`/`review.js` job handling into a shared durable job service and use Activity as the source of truth. Do not rely on an in-memory OpsBar as job persistence.

**Acceptance:** U-017 Restart preserves job state and idempotent retry. U-018 Restore blocks on external file changes and verifies successful restoration. U-019 Failed files are never counted as completed writes.

## Settings

**Purpose and layout:** Settings contains local model, library, output, accessibility, and compatibility controls. Keep classification defaults local and offline after an optional initial download. The model panel offers the engineering-selected recommended local model with plain install size, license status, progress, and offline effect; Poy does not choose an ML architecture. Artifact name, source, version, checksum, and install location sit in **Evidence & diagnostics**. Provide **Download**, **Pause**, **Resume**, **Cancel**, and **Verify**. Do not require Python, Ollama, paid API, cloud account, or external hardware for the default path.

```text
Settings  [Models] [Library] [Output] [Accessibility] [Compatibility]
Recommended local model: not installed   storage: 0 GB
[Download] [Verify]                  Download job: Queued / Paused / Failed
Library roots (2) [Manage]   Cache: 6.4 GB [Review clear scope]
Output profile: Broad Genre + raw Comment ▾   [Test djay route]
[Apply changes] [Cancel]
```

Add library roots, ignored paths, cache use, storage budget, output profile, theme, text size, reduced motion, and keyboard shortcuts. Separate optional metadata lookup from classification. Saved credentials and cloud services stay disabled unless the user configures them. Avoid a key-gated onboarding screen.

**Actions and results:** Download is resumable and validates checksum/license manifest before installation. A changed model version creates new versioned analysis jobs; old results remain inspectable. **Clear cache** reports exact reclaimable space and does not delete source audio, human corrections, or backups. **Reset corrections** requires a scoped export backup and explicit confirmation. **Test djay route** opens a disposable compatibility checklist and never edits real library tracks.

**States:** Empty: show “No local model installed” with download size and offline consequences. Loading: show artifact metadata before progress. Partial: report bytes, checksum state, and ability to resume. Error: distinguish network failure, disk full, checksum mismatch, unsupported device, and license block. Offline: installed models remain usable; new download and optional enrichment are disabled. Selection: settings are scalar; multi-selection is not applicable. Dirty: unsaved settings show changed fields and apply/cancel controls.

**Data and service seams:** Current settings use `/api/settings`, `/api/list_models`, learning stats, and taxonomy APIs. Replace API-provider-first setup with a local model registry, download worker, checksum verifier, storage report, and settings schema. Preserve existing API settings as optional legacy configuration until a migration is approved.

**Acceptance:** U-020 Fresh setup needs no API key. U-021 Model install resumes after restart and rejects checksum/license failures. U-022 Clear-cache scope preserves sources, corrections, and backups.

## Guided import, track inspector, and shared dialogs

**Add-folder wizard:** Step 1 selects folders using a native picker, with keyboard-accessible alternative and drag-and-drop. Step 2 previews supported, unsupported, duplicate, unreadable, and permission-denied files without moving anything. Step 3 asks whether to preserve current tags as observations; default yes, with no claim that they are truth. Step 4 summarizes file count, disk/cache needs, and job plan. **Import** creates a persistent job. Cancel stops after the current file and retains the completed inventory. The wizard shows library roots and warns if a folder is already watched. Acceptance U-001 and U-023.

**Track inspector drawer:** Show editable standard Genre and Comment, observed tags, proposed values by axis, plain confidence, BPM, key, selected audio sections, review/lock/write/delivery status, and history. An expandable **Evidence & diagnostics** panel holds file identity and revision, model/taxonomy/pipeline versions, raw scores, and provenance. Separate **Play selected section**, **Play full track**, **Accept**, **Correct**, **Lock field**, and **Open in Library**. Do not invent instrumentation explanations or a single opaque “why” string. A human edit marks only touched axes as locked. If the file changes externally, mark its analysis stale. Acceptance U-024 checks focus return, single playback owner, and no overwrite of locked values.

**Batch-edit dialog:** Show scope count and filter snapshot. Select fields individually. For Comment, offer **Replace**, **Append**, or **Keep** and preview exact literal output; default Keep. Never tokenize commas or slashes. For Genre, show broad existing and proposed values with a per-track diff. Buttons are **Cancel**, **Preview**, and **Apply to N tracks**. The dialog records a batch edit event and does not write files. Acceptance U-025 verifies no unselected field changes.

**Write-preview dialog:** List files, format support, source revision, backup readiness, and every changed field. Rows with unsupported format, missing write support, conflict, or backup failure are excluded and explained. The confirmation names exact scope, such as “Write Genre and Comment to 642 files.” Require one explicit approval for this scope, not one click per file. Start a durable job; report verified success only after write-readback. Acceptance U-026 requires no write before approval and per-file truthful outcomes.

**Keyboard help:** `?` opens a searchable modal with shortcuts and focus order. Suggested shortcuts: `/` search when focus is not in an editor, `Space` play selected, `J/K` next/previous row when table focused, `Enter` open inspector, `Escape` close top layer, `Shift+D` toggle inspector, and `Ctrl/Cmd+Enter` apply only in a focused reviewed dialog. Every shortcut has a visible alternative and respects text inputs. Acceptance U-027 checks no shortcut triggers a write implicitly.

## Navigation and legacy feature disposition

Map existing features deliberately; keep user data until an explicit migration and export exist.

| Current feature | Destination |
|---|---|
| Library import, analysis, table, health | Library and Activity; keep source files in place. |
| Inbox/watch-folder organizer | Library import source and Settings; defer automatic file movement. |
| Review queue | Review with axis-level corrections and the write preview. |
| Taxonomy editor | Categories, with versioning and “vocabulary only” state. |
| Playlist builder | Saved category views in Library and Export; preserve existing named playlists and filters. |
| Set Planner | Hide from primary navigation during classifier work; preserve setlist records and offer export. Reconsider only after classifier gates. |
| Advisor and Stats | Merge measured quality, coverage, and workload into Activity or Library summary; preserve historical reports. |
| Stems, Rekordbox, Serato, Organise | Defer or keep behind an advanced/legacy section. Preserve configuration and outputs. Do not remove until data migration and user-approved scope exists. |
| Sync Center | Replace with Export route status and compatibility checks. Keep legacy exporter until replacement is verified. |

Navigation must keep the selected track and filters when switching between Library and Review. A route that cannot retain stable IDs asks the user before discarding a selection. Cross-page actions say where they go and what remains pending. Avoid an interface rewrite until an audio candidate passes its research gate.

