# IDJLM Pro — Multi-Agent Investigation Report
Generated: 2026-05-04
Investigators: pattern-scan, logic-scan, architecture-scan

---

## HIGH CONFIDENCE — Will auto-fix (found by 2+ investigators)

### 1. [CRITICAL] Early return in write_tags aborts entire tag write on bad album art
- **File:** `app/services/tag_writer.py:94-95`
- **Found by:** pattern-scan + logic-scan
- **Issue:** `return` exits the entire `write_tags()` function instead of just skipping the art download. Genre, BPM, key, and year tags are never written.
- **Fix:** Change `return` to `continue` (or log + skip art frame).

### 2. [CRITICAL] Path traversal in audio_routes when no music folder imported
- **File:** `app/routes/audio_routes.py:23-28`
- **Found by:** pattern-scan + logic-scan
- **Issue:** `if music_folder:` guard is falsy when empty, skipping the security check entirely. Allows arbitrary file reads via `?path=/etc/passwd`.
- **Fix:** Default-deny when no folder is set; validate resolved path is under allowed directory.

### 3. [CRITICAL] App crashes on startup if taxonomy.json missing or corrupt
- **File:** `app/__init__.py:79-81`
- **Found by:** pattern-scan + architecture-scan
- **Issue:** `json.load(f)` is unguarded. Missing/corrupt JSON raises unhandled exception, killing Flask before serving any request.
- **Fix:** Wrap in try/except, fallback to built-in default taxonomy, log warning.

### 4. [HIGH] Approval log writes to read-only bundle path on macOS
- **File:** `app/routes/review_routes.py:143`
- **Found by:** pattern-scan + logic-scan
- **Issue:** `log_path` resolves relative to `__file__` (PyInstaller bundle). On macOS, `.app` bundles are codesigned and read-only at runtime. `PermissionError` on every approval.
- **Fix:** Write to `~/Library/Application Support/IDJLM Pro/` (macOS) or `~/.idjlm-pro/` (Linux).

### 5. [HIGH] Non-atomic read-modify-write on taxonomy JSON
- **File:** `app/routes/bulk_routes.py:57`
- **Found by:** logic-scan
- **Issue:** `taxonomy.clear(); taxonomy.update(new_taxonomy)` exposes window where taxonomy is empty. File write is not atomic (no temp-file + rename).
- **Fix:** Write to temp file, `os.replace()`; remove `clear()` + `update()` window.

### 6. [HIGH] Race condition on global track_store between import and background threads
- **File:** `app/routes/import_routes.py:71`
- **Found by:** logic-scan
- **Issue:** `track_store.clear()` called without lock while background thread from `/api/analyze` may still be iterating.
- **Fix:** Add `threading.RLock()` around all track_store mutations.

---

## MEDIUM CONFIDENCE — Will auto-fix (found by 1 investigator, high impact)

### 7. [HIGH] No retry on transient AI/network errors
- **File:** `app/services/classifier.py:88-104`
- **Found by:** architecture-scan
- **Issue:** `_call_with_backoff` only retries rate-limit (429). Timeouts, 503s, connection resets are re-raised immediately.
- **Fix:** Retry on timeout, 503, connection errors with exponential backoff.

### 8. [HIGH] Unvalidated destination path in organise/folders
- **File:** `app/routes/organise_routes.py:247-303`
- **Found by:** pattern-scan
- **Issue:** `destination` body parameter passed straight to `os.makedirs()` and `shutil.move()` with no sanitization.
- **Fix:** Validate resolved path is under user-designated output area.

### 9. [HIGH] Single malformed AI response kills entire batch
- **File:** `app/services/classifier.py:403-433`
- **Found by:** architecture-scan
- **Issue:** Once any model returns success, provider loop breaks. If response is malformed, whole batch fails without trying fallback providers.
- **Fix:** Try next provider if response parsing fails.

### 10. [MEDIUM] Thread locks never released if worker crashes
- **File:** `app/routes/import_routes.py:164,283`
- **Found by:** pattern-scan + logic-scan
- **Issue:** `_analyze_lock` and `_classify_lock` released only at end of `run()`. If exception occurs, lock stays held forever.
- **Fix:** Use `try: ... finally: lock.release()` or context manager.

### 11. [MEDIUM] Session save failures silently swallowed
- **File:** `app/routes/import_routes.py:281`, `app/routes/review_routes.py:239`
- **Found by:** logic-scan
- **Issue:** `save_session` wrapped in `try: ... except Exception: pass`. Disk-full or permission errors discarded without feedback.
- **Fix:** Log the error; ideally surface to client.

### 12. [MEDIUM] dry_run falsely reports no overwrites
- **File:** `app/routes/organise_routes.py:288`
- **Found by:** logic-scan
- **Issue:** `would_overwrite = os.path.exists(dest_file) if not dry_run else False` — during dry-run, flag is always False even when destination exists.
- **Fix:** Check existence regardless of dry_run mode.

---

## LOW CONFIDENCE / REVIEW MANUALLY

- [MEDIUM] `datetime.utcnow()` deprecated across 4 files (pattern-scan)
- [MEDIUM] Logger f-strings disable lazy evaluation (pattern-scan)
- [MEDIUM] Platform path logic duplicated across 6+ files (pattern-scan)
- [MEDIUM] Multi-element BPM array crashes analyzer (logic-scan)
- [MEDIUM] Confidence 0 treated as missing in bulk-approve (logic-scan)
- [MEDIUM] Unbounded in-memory session state growth (architecture-scan)
- [MEDIUM] Duplicate async boilerplate across routes (architecture-scan)
- [MEDIUM] Tight frontend/backend coupling in Track model (architecture-scan)
- [MEDIUM] Critical-path test coverage gaps (architecture-scan)
- [MEDIUM] Silent Flask startup failure (architecture-scan)
- [LOW] Hardcoded AI model strings (pattern-scan)

---

## WHAT THE MODELS WOULD DO DIFFERENTLY

### Pattern-Scan Recommendations
1. Centralize platform paths into a single `app/utils/paths.py` module
2. Replace raw threading + manual locks with `ThreadPoolExecutor`
3. Add Flask global error handler instead of copy-pasting try/except in every route
4. Validate public inputs with a schema helper or Pydantic
5. Extract a unified AI API client for all providers
6. Use lazy logging everywhere (no f-strings)
7. Make startup resilient with fallback defaults

### Logic-Scan Recommendations
1. Use `threading.RLock()` around all `track_store`/`taxonomy` mutations, or switch to SQLite/LMDB
2. Write JSON files atomically (temp file + `os.replace()`)
3. Extract album-art download into standalone helper to avoid early return bugs
4. Remove all `except Exception: pass` patterns
5. Add `finally:` blocks around all thread-spawned locks

### Architecture-Scan Recommendations
1. Centralized AsyncJobManager with TTL cleanup for progress queues
2. Circuit-breaker + unified retry wrapper for all external APIs
3. Split domain model from UI/session state (CoreTrack vs TrackView)
4. Graceful startup degradation with health probes
5. Structured logging and lightweight metrics endpoint

