# Latin classifier redesign: JB implementation plan

This folder is the implementation brief for a local Latin music classifier that can sort a library of about 15,000 tracks on Poy’s M3 MacBook Air with 16 GB memory. JB can build the plan in phases after Poy authorizes implementation. The plan preserves the Tauri desktop shell, Flask sidecar, SQLite store, existing import and review foundation, and export path where tests show they work.

The product must classify audio, keep unlike music and dance concepts on separate axes, and leave uncertainty visible. It prioritizes Salsa, then Bachata, then Kizomba. Cha-cha, Charanga, and Boogaloo form the next wave. Kompa remains distinct from Kizomba. Later styles such as Reggaeton and Bolero are useful hard negatives before they become supported labels. “Unknown,” “Mixed,” and “Unsupported” are valid outcomes. Do not promise perfect accuracy, overnight completion, or automatic writes from confidence alone.

## Read these plans in order

- [Engineering specification](engineering-spec.md) defines module ownership, proposed data and API contracts, job behavior, persistence, cache identity, and write safety.
- [UX and UI specification](ux-ui-spec.md) defines every page, navigation, controls, states, and accessibility behavior.
- [QA and delivery plan](qa-and-delivery.md) defines evaluation data, acceptance gates, failure tests, packaging checks, and release conditions.
- [djay transfer design and device verification](djay-transfer.md) is the authoritative route order, export-state contract, device test, and source guide for cable, wireless, Music, and OneLibrary candidates.
- [Existing redesign audit](../latin-classifier-redesign-2026-10-18.md) is the evidence record and source for current bug findings and external model, licensing, and workflow references.

The audit describes the current repository at branch `chore/tauri-release-consolidation`, commit `0d033f7`. Its findings are verified against that snapshot. Recheck current callers before implementation if the branch has moved.

## Non-negotiable design choices

Use the existing Tauri + Flask sidecar + SQLite + JavaScript stack. Run one resident local audio-model worker and cache embeddings only by a verified complete audio identity plus decoder, preprocessing, encoder, and layer versions. Benchmark CLAP and MAEST519 candidates, with the metadata classifier as a baseline; choose a shipping model only after representative held-out evaluation and artifact-license review. Do not train a large model from scratch by default, call an LLM once per song, require a paid API, or require a cloud service for classification.

Store original file metadata, predictions, human decisions, provenance, jobs, and write/export outcomes as distinct records. Human locks survive reanalysis. A taxonomy or prediction-head change invalidates predictions but can reuse compatible embeddings. Tag-only edits keep embeddings only after a complete-audio identity check. Predictions and accepted labels are not expert training truth. Do not use the frozen final test for training, prompt hints, or threshold selection.

A user reviews a field-level diff and approves the selected batch once. Before writing, check the full current file checksum and selected-field revisions against the preview. Back up all changed metadata, write with a format-aware writer, read back the values, verify audio identity, and report a truthful per-file result. Preserve raw original comments and append or map detailed labels only through an explicit profile. Never split an existing comment on guessed commas. Do not write private djay database files or claim an unsupported transfer API.

## Authoritative delivery sequence

This is the authoritative sequence. Engineering phases A–F and QA phases 0–6 are work-package cross-references, not a competing order: A/QA 0 map to Stage 0, B/QA 1–2 to Stage 1, C–D/QA 3 to Stage 2, E/QA 4–5 to Stage 3, and F/QA 6 to Stage 4.

1. **Stage 0 — compatibility inventory:** Recheck callers, capture disposable fixtures, inventory tags, comments, folders, and formats, and run the small device route test in the [transfer guide](djay-transfer.md). This allows a disposable compatibility test while keeping full-library export uncertified.
2. **Stage 1 — evidence and Salsa model proof:** Build lawful grouped splits and independent verification, then compare metadata-only, CLAP, and MAEST519 on Salsa and hard negatives. Measure M3 cold/warm behavior, memory, and interruption recovery. Stop before broad UI work if audio does not improve held-out Salsa results.
3. **Stage 2 — durable classifier and review core:** Implement the multi-axis taxonomy, durable jobs, identity, predictions, field-level review, locks, and measured abstention. Migrate without deleting legacy state and run shadow prediction beside current tags.
4. **Stage 3 — safe output and route integration:** Add format-gated write-back, staged incremental export, and the supported djay route. Use copies until round-trip, conflict, backup, read-back, recovery, and device acceptance pass.
5. **Stage 4 — supported scale and expansion:** Measure 100-, 1,000-, and 15,000-track workload, then add Bachata, Kizomba, and the fourth wave only behind their own evidence gates.

The compatibility and model proof gates precede a full UI rewrite. A static page prototype and test fixtures may proceed in parallel. Do not request a complete labelled corpus from Poy up front.

## Completion means

- The first M3 benchmark records correctness, classwise precision and recall, coverage, confidence intervals, cold and warm time, memory, and remaining review load.
- The supported taxonomy keeps family, style, dance use, production/remix, vocal language, provenance, unknown, mixed, and unsupported distinct.
- Imports, jobs, and reanalysis resume after interruption without overwriting original tags or human decisions.
- Stale previews and changed files are rejected for re-preview, and batch writes can be undone or recovered from verified backups.
- The export route works on disposable copies and produces searchable, filterable target fields in the tested djay path.
- Every existing ancillary area has a documented keep, integrate, defer, or retire decision. The plan does not silently discard Set Planner, Advisor, Stats, stems, Rekordbox, Serato, or Organise features.
- The UI stays responsive at measured library scale, and all accuracy, speed, memory, and workload claims match evidence.

## Scope and open evidence

These documents are a written plan, not authorization to alter production code, taxonomy files, models, music, tags, folders, databases, or device libraries. Candidate model choice, representative dataset availability, independent verification, target-M3 speed and memory, app-sidecar lifecycle under sustained work, and the exact end-to-end Mac-to-iPad djay transport remain unmeasured. The implementation team must settle those with bounded evidence before it depends on them. No new hardware or paid subscription is assumed or will be purchased for the plan; the applicable installed djay entitlement must be recorded during the device test.

## Plan checks

The document set has been cross-checked for the delivery sequence, state vocabulary, route ownership, audit links, and source-file references. Those are documentation checks only. All product, device, audio, performance, accessibility, and release evidence remains **NOT RUN** until implementation produces the ledger artifacts in [QA and delivery](qa-and-delivery.md).
