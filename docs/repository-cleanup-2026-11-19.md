# Repository cleanup inventory · 19 November 2026

This inventory records tracked files that appear obsolete or misplaced. It does not delete files. References were checked in the repository with `rg`; a reference only from another obsolete document does not establish a current use. Before removing anything, preserve the exact path under `~/.restore-bin/` as required by the shared repository policy.

## Remove candidates

| Path | Evidence | Recommendation |
|---|---|---|
| `.trigger-ci` | Tracked but zero bytes. `rg` finds no repository reference. Git history shows it was used in old `ci: trigger re-check` commits. Current workflows trigger on PRs, pushes to `main`, or version tags. | Remove. It is a leftover trigger marker with no current repository consumer. |
| `app/models/__pycache__/__init__.cpython-312.pyc` | Tracked generated Python bytecode. Source file is the reproducible input. | Remove from version control. |
| `app/models/__pycache__/track.cpython-312.pyc` | Tracked generated Python bytecode. The worktree copy is currently modified by another worker. | Remove from version control only after preserving that modified copy. Do not replace or discard the worktree copy as part of this cleanup. |
| `tests/tests/docs/BASELINE-METRICS.md` | Old manual QA baseline. Its companion prompt points to `tests/docs/BASELINE-METRICS.md`, a path that does not exist. | Remove with the obsolete manual QA bundle below. |
| `tests/tests/docs/MASTER-QA-PROMPT.md` | Uses the wrong `tests/docs/` paths and directs an agent to make ongoing edits to legacy tracking templates. No application or current test runner consumes it. | Remove with the obsolete manual QA bundle below. |
| `tests/tests/docs/README.md` | Describes the same misplaced manual QA bundle. Repository tests live directly under `tests/`. | Remove with the obsolete manual QA bundle below. |
| `tests/tests/docs/templates/BUG-TRACKING-TEMPLATE.csv` | Template referenced only by the obsolete QA prompt and its local README. | Remove with the obsolete manual QA bundle below. |
| `tests/tests/docs/templates/TEST-EXECUTION-TRACKING.csv` | Template referenced only by the obsolete QA prompt and its local README. | Remove with the obsolete manual QA bundle below. |
| `tests/tests/docs/templates/WEEKLY-PROGRESS-REPORT.md` | Template referenced only by the obsolete QA prompt and its local README. | Remove with the obsolete manual QA bundle below. |
| `DEPLOYMENT_CHECKLIST.md` | Calls a pre-Tauri frontend “ready for testing,” lists endpoints as unimplemented, and describes a rollback workflow for the earlier app. No current document links to it. | Remove; its status and instructions are stale. |
| `DESKTOP_APP_ANALYSIS.md` | The file itself says it is a superseded April 2026 pywebview evaluation. The repository now uses Tauri with a Flask sidecar. | Remove; retain history in Git. |
| `FEATURES_ADDED.md` | Describes the earlier single-page interface and feature set. The current changelog and implementation status replace this summary. No current document links to it. | Remove. |
| `FIXES_APPLIED.md` | April 2026 Gemini/API-key troubleshooting notes for the earlier workflow. No current document links to it. | Remove. |
| `IMPLEMENTATION_NOTES.md` | Describes the old monolithic frontend and old Stats, Camelot, and watcher implementation. The source map and current docs supersede it. No current document links to it. | Remove. |
| `INVESTIGATION_REPORT.md` | Generated May 2026 audit of old routes and services, with recommendations tied to the pre-redesign architecture. No current document links to it. | Remove; retain history in Git. |
| `QWEN.md` | Contains old release instructions naming `release-auto.yml`, pushing directly to `main`, and tagging every update. The current workflow is `release.yml`; the release gate blocks unsigned publication. No current document links to this file. | Remove as stale operational guidance. |
| `docs/screenshot-v2.5.4-import.png` | No reference found in current Markdown or source. It depicts an older interface. | Remove. |
| `docs/screenshot-v2.5.4-library.png` | No reference found in current Markdown or source. It depicts an older interface. | Remove. |
| `docs/screenshot-v2.5.4-setplanner.png` | No reference found in current Markdown or source. It depicts an older interface. | Remove. |
| `docs/screenshot-v2.5.4-settings.png` | No reference found in current Markdown or source. It depicts an older interface. | Remove. |
| `docs/superpowers/plans/2026-04-05-idjlm-pro-ui-redesign.md` | Historical plan for the old UI. Its only discovered spec reference contains a misspelled filename. Current redesign docs cover the active workflow. | Remove as superseded. |
| `docs/superpowers/plans/2026-05-28-phase1-bug-fixes.md` | Historical phase plan for the v4 interface; no active document or code reference found. | Remove as superseded. |
| `docs/superpowers/plans/2026-05-28-phase2-ui-redesign.md` | Historical plan for the old UI; screenshot references are internal to the archived plan. Current redesign docs cover the active workflow. | Remove as superseded. |
| `docs/superpowers/plans/2026-05-28-phase3-tauri.md` | Historical Tauri migration plan. Current `src-tauri/` and release workflow contain the implementation. No active document or code reference found. | Remove as superseded. |
| `docs/superpowers/plans/2026-05-29-zero-dep-distribution.md` | Historical distribution plan; current release workflow and README describe actual installer and signing status. No active document or code reference found. | Remove as superseded. |
| `docs/superpowers/specs/2026-04-05-idjlm-pro-ui-redesign.md` | Historical UI specification for the replaced interface. No active document or code reference found. | Remove as superseded. |
| `docs/superpowers/specs/2026-05-28-idjlm-v4-design.md` | Historical v4 visual design. No active document or code reference found. | Remove as superseded. |
| `docs/superpowers/specs/2026-05-29-idjlm-zero-dep-distribution.md` | Historical distribution specification. Current Tauri configuration and release workflow describe implementation. No active document or code reference found. | Remove as superseded. |

## Keep

- Keep `docs/screenshot-v2.4.0.png`. `CHANGELOG.md` links to it.
- Keep `CODEX_REVIEW_2026-04-05.txt`. `tests/test_a3_p2_regressions.py` identifies it as the source for its historical regression findings, and `tests/BUGS-FOUND.md` cites it.
- Keep the `docs/jb-latin-redesign-2026-10-18/` brief and specifications. They describe the current Latin workflow and remain linked from project documentation.
- Keep `docs/implementation-status-2026-11-10.md`. It records test evidence and open limits, and remains linked from the README.
- Keep `docs/competitor-refresh-2026-11-10.md` unless its owning product research is deliberately retired; the README does not present it as a setup or review guide.
- Keep taxonomy, license, icon, and vendored font or other runtime assets. This inventory does not establish that any of them are unnecessary.
- Do not inspect or clean `.env`, `.qwen` settings, `setlist.json`, music files, databases, or local user data as part of repository hygiene.

## Evidence and limits

- `git ls-files` shows both Python bytecode files, the empty `.trigger-ci`, all six nested QA files, eight root report files examined, four v2.5.4 screenshots, and eight `docs/superpowers/` files are tracked.
- `rg` found no live code or current documentation references to the listed removal candidates. For the nested QA bundle and the one old spec cross-reference, matches are confined to the obsolete documents themselves.
- The current README, GOALS, changelog, implementation status, and redesign brief identify the newer workflow and its limits.
- This is a reference and staleness check, not proof that an external process never reads a path. Preserve the modified bytecode worktree copy before untracking it.

## Completed cleanup

On 19 November 2026, the 28 reviewed paths above were copied with their
relative paths to `~/.restore-bin/idjlm-repository-cleanup-2026-11-19/` before
being removed from version control. The then-current modified tracked
`app/models/__pycache__/track.cpython-312.pyc` copy was preserved there; it was
never reset to its Git version. The now-unused tracked `setlist.json` was
also preserved in that restore-bin directory and removed after the Setlist
route moved to the user-data SQLite document store. `setlist.json` is now
ignored alongside `playlists.json`, so runtime state cannot be recommitted.
