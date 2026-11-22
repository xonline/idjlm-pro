# Reliability check · 19 November 2026

**Updated 21 November 2026.** This record remains historical verification
evidence. Check [PR #44](https://github.com/xonline/idjlm-pro/pull/44) for the
current review-build commit and its desktop-check artifacts.

This note records the current review-branch evidence for PR #44. It is not a
release certificate and does not describe the public `main` branch or the
latest public release.

## Checks that passed

- A fresh temporary Python 3.12 environment installed from
  `requirements.txt` ran the isolated suite with
  `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and native-crash output
  detection: **388 passed, 14 skipped, 2 warnings** in 5m04s. The run sets
  `IDJLM_USER_DATA_DIR` before importing the application; it did not open a
  personal library or runtime database.
- `ruff check app/ --select E,F,W --ignore E501,E701` passed.
- Focused route, store, settings-isolation, safe-format, and warm-import
  checks passed: **28 passed**.
- The compiled-bundle browser harness passed with isolated synthetic media at
  `/tmp/idjlm-latin-ui-09vcdm85`: `ok:true`, the production bundle loaded, and
  there were no page or request errors. It covered additive import/rescan,
  review decisions, safe write/restore, export preview/commit/replacement, and
  stale-preview invalidation.
- The sidecar's synthetic analyzer verifier ran two disposable WAV tracks in a
  spawned worker on that pinned environment and exited successfully in 14.4 s.
  It checked completed analysis records with positive duration and RMS plus
  waveform data; it did not use a music library or model download.

## Synthetic 15,000-item catalogue check

`scripts/benchmark_v2_catalog.py --items 15000 --runs 5` creates a temporary
SQLite catalogue and sets `IDJLM_USER_DATA_DIR` before importing the app. It
uses no audio files, model downloads, source writes, staged copies, or network
services. Its five-run Linux result checked a 15,000-item page, a 7,500-item
Salsa filter, frozen all-filtered review/write/export preview scopes, and a
7,500-item durable job restart:

| Operation | Median | Range |
| --- | ---: | ---: |
| 100-row library page | 23 ms | 14–27 ms |
| 100-row filtered page | 17 ms | 17–21 ms |
| all-filtered scope, 15,000 items | 1.49 s | 1.36–1.77 s |
| filtered scope, 7,500 items | 0.91 s | 0.82–1.06 s |

The host was busy (four CPUs, load average 7.98) during the run. These figures
are repeatable synthetic Linux API measurements, not M3 performance, scanner
or model throughput, music-classification accuracy, transfer performance, or a
15,000-track completion-time claim.

## Reliability fixes in this review branch

- All-filtered scope resolution loads item relations in SQLite chunks instead
  of one full-detail query per selected item.
- Warm folder imports skip unchanged POSIX files using mtime, size, and ctime;
  a same-size edit with restored mtime still rescans. Windows disables this
  optimization because Python exposes `st_ctime` there as creation time.
- The legacy Setlist and Playlist routes now use the user-data SQLite document
  store. Normal source-tree upgrades may perform the existing one-time legacy
  JSON migration; an explicit `IDJLM_USER_DATA_DIR` never probes project-root
  JSON or `.env` files.
- Legacy `librosa` analysis now uses one spawned worker for a batch instead of
  inheriting native state through `fork` or compiling cold Numba kernels in
  parallel. A two-worker cold-cache probe timed out after 240 s; the serial
  limit is deliberate pending a target-hardware concurrency measurement. This
  is a reliability guard, not an analysis-throughput result.
- Obsolete tracked runtime JSON/bytecode, screenshots, and superseded planning
  files were copied to `~/.restore-bin/idjlm-repository-cleanup-2026-11-19/`
  before removal from the review branch. The then-current modified tracked
  bytecode copy was preserved there, never reset to its Git version.

## Remaining gates

The 19 November Linux and cross-platform installer evidence does not establish
the current review head, M3 performance, or installer behavior. A native Apple
Silicon review artifact must be built and checked before it is offered as an
M3 download. An Intel macOS artifact may help exercise the manual workflow
through Rosetta, but is not equivalent evidence for the optional local audio
runtime.

Issue #879 remains open for representative Latin corpus accuracy evaluation,
M3 16 GB real-library scale measurement, real iPad/djay transfer discovery,
and signing/notarization before a public release.
