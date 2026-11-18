# Reliability check · 19 November 2026

This note records the current review-branch evidence for PR #44. It is not a
release certificate and does not describe the public `main` branch or the
latest public release.

## Checks that passed

- The isolated Python suite was run with `PYTHONDONTWRITEBYTECODE=1` and
  `-p no:cacheprovider`: **387 passed, 14 skipped, 6 warnings** in 5m55s.
  The run sets `IDJLM_USER_DATA_DIR` before importing the application; it did
  not open a personal library or runtime database.
- `ruff check app/ --select E,F,W --ignore E501,E701` passed.
- Focused route, store, settings-isolation, safe-format, and warm-import
  checks passed: **28 passed**.
- The compiled-bundle browser harness passed with isolated synthetic media at
  `/tmp/idjlm-latin-ui-09vcdm85`: `ok:true`, the production bundle loaded, and
  there were no page or request errors. It covered additive import/rescan,
  review decisions, safe write/restore, export preview/commit/replacement, and
  stale-preview invalidation.

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
- Obsolete tracked runtime JSON/bytecode, screenshots, and superseded planning
  files were copied to `~/.restore-bin/idjlm-repository-cleanup-2026-11-19/`
  before removal from the review branch. The initial modified tracked bytecode
  file was preserved there exactly, never reset.

## Remaining gates

The local suite emitted native `librosa`/`numba` child-worker segmentation
fault traces while exercising the legacy analyzer, although pytest completed
with exit status zero. This host-runtime signal needs clean CI confirmation and
separate diagnosis; it is not evidence that the legacy analyzer is reliable.

Issue #879 remains open for representative Latin corpus accuracy evaluation,
M3 16 GB real-library scale measurement, real iPad/djay transfer discovery,
and signing/notarization before a public release.
