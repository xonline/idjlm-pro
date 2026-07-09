# IDJLM Pro — Bug Report
**Date:** 2026-05-28  
**Tester:** Jarvis (automated)  
**App version:** v3.5.0  
**State:** 41 tracks imported from `/home/ubuntu/upload/songs test/`, analysis in progress (10/41 done at time of testing)

---

## BUG-001 — `/api/classify/start` route does not exist [P1]
- **What**: The task description references `POST /api/classify/start` but this route returns 404. The correct endpoint is `POST /api/classify`. Any documentation or external tooling pointing at `/api/classify/start` will fail silently.
- **Where**: `app/routes/import_routes.py` — route registered at `/api/classify`, not `/api/classify/start`
- **Steps**: `curl -X POST http://localhost:5050/api/classify/start -H "Content-Type: application/json" -d '{}'` → 404
- **Impact**: Any integrations or tests expecting `/api/classify/start` fail completely. The classify endpoint itself (`/api/classify`) works correctly and returns `{"op_id": "...", "total": N}` with HTTP 202.

---

## BUG-002 — `stat-analyzed` ID mismatch: element never updates [P1]
- **What**: `navigation.js` line 69 reads `document.getElementById('stat-analyzed')` (American spelling) but the HTML template uses `id="stat-analysed"` (British spelling). The element is never found, so the "analysed" count in the stats bar always shows 0 — even after 10 tracks are analyzed.
- **Where**: `app/static/modules/navigation.js:69` vs `templates/index.html:142`
- **Steps**: Import tracks, run Analyse. Stats bar shows `0 analysed` despite pipeline stepper showing `10/41`. Console: `el('stat-analyzed')` returns null.
- **Impact**: Users can't see how many tracks have been analyzed. The stat silently stays at 0 throughout the workflow.

---

## BUG-003 — `health-analyzed` ID mismatch: Stats & Library health panel shows dashes [P1]
- **What**: `pipeline.js` line 1510 sets `document.getElementById('health-analyzed').textContent` but the HTML uses `id="health-analysed"`. Causes a JS TypeError: `Cannot set properties of null (setting 'textContent')` on every tab switch to Stats & Library.
- **Where**: `app/static/modules/pipeline.js:1510` vs `templates/index.html:330`
- **Steps**: Switch to "Stats & Library" tab. Console error fires. All health stat cards (Analysed, Classified, Approved, Tags Written, Duplicates) show `—` instead of real values.
- **Impact**: The Stats & Library health dashboard is completely broken — all values remain at dashes, making it useless for monitoring library status.

---

## BUG-004 — `review.js` old bulk-approve calls `result.forEach()` on object [P1]
- **What**: The old `initReviewTab()` bulk-approve handler in `review.js` (line 101) does `result.forEach(trackPath => ...)` after calling `POST /api/review/bulk-approve`. The API returns `{"approved": N}` (an object), not an array. This throws `TypeError: result.forEach is not a function`, crashing the handler silently (caught by the outer try/catch which shows nothing).
- **Where**: `app/static/modules/review.js:101`  
  Backend returns: `{"approved": 0}` (see `review_routes.py:107`)
- **Steps**: Go to Library tab, select tracks, click "Bulk Approve" from the Review panel. Toast may fire but track statuses don't update. JS console shows TypeError.
- **Impact**: Bulk-approve from the Review panel does not update track statuses in the UI. Users think tracks are approved but the UI doesn't reflect changes.

---

## BUG-005 — `review.js` write-tags calls `result.forEach()` on async op_id object [P1]
- **What**: The `initReviewTab()` write-tags handler in `review.js` (line 127) does `result.forEach(trackPath => ...)` after calling `POST /api/review/write`. The API returns `{"op_id": "...", "total": N}` (202 Accepted, async). This is both a response format mismatch and a synchronous/async mismatch — the old handler treats the write as synchronous but it's now an async SSE operation.
- **Where**: `app/static/modules/review.js:127`  
  Backend returns: `{"op_id": "d2330eac", "total": 0}` with HTTP 202
- **Steps**: Approve tracks, then click "Write Tags" from the Review panel. JS TypeError fires, tags are never written from this path.
- **Impact**: Write Tags from the Review tab is completely broken. The Library toolbar's Write Tags button (in `library.js`) correctly handles the async op_id pattern; the Review tab button does not.

---

## BUG-006 — Onboarding overlay intercepts clicks even after close button pressed [P2]
- **What**: Clicking the `×` button on the onboarding overlay (`completeOnboarding()`) hides the overlay but it still intercepts pointer events for the Resume Session button behind it. The overlay element remains in the DOM at `display:none` but pointer-events are not being fully suppressed in some browser states.
- **Where**: `app/static/modules/pipeline.js:2275` (`completeOnboarding` function), `templates/index.html` (onboarding overlay z-index/pointer-events)
- **Steps**: On fresh load (no `idjlm-onboarding-done` in localStorage), close the onboarding with `×`. Then try clicking the "Resume" session button — click is intercepted by the overlay.
- **Impact**: New users who dismiss onboarding can't resume their previous session without reloading the page.

---

## BUG-007 — Onboarding shows on every reload when session exists but has no tracks in memory [P2]
- **What**: `showOnboardingIfNeeded()` checks `window.tracks.length > 0` before deciding whether to show onboarding. On page load, `window.tracks` is always empty (tracks live in server memory, not localStorage). The session resume banner appears, but the onboarding overlay also appears on top of it. Users with existing sessions always see the onboarding wizard on reload.
- **Where**: `app/static/modules/pipeline.js:2256-2261`
- **Steps**: Have an existing session (41 tracks imported). Reload the page. Onboarding appears instead of going straight to the library.
- **Impact**: Returning users see first-time onboarding on every page reload, blocking access to the Resume button. Poor UX for normal usage pattern.

---

## BUG-008 — Settings tab: model dropdown shows "Error loading models" on page load [P2]
- **What**: `loadSettings()` in `settings.js` calls `fetchModels(provider)` immediately on init. When no API key is saved, `POST /api/list_models` returns HTTP 400 (`{"error":"API key required for claude"}`). `apiFetch` treats 400 as an error and throws, causing the model dropdown to show "Error loading models" before the user has interacted with anything.
- **Where**: `app/static/modules/settings.js:271` (`loadSettings` → `fetchModels`)
- **Steps**: Open Settings tab with no API keys configured. Model dropdown immediately shows "Error loading models".
- **Impact**: Confusing error state shown before user has done anything wrong. Should show "Enter API key first" or leave the dropdown empty with a hint.

---

## BUG-009 — Settings "Test" button does not test the key typed in the input [P2]
- **What**: `testApiKey(provider)` in `pipeline.js` sends `{ provider: provider }` to `/api/test_key` without including the value currently typed in the API key input field. The backend then tries to use the key from `.env`. If a user pastes a new key and clicks Test (before saving), they're actually testing the old saved key, not the new one.
- **Where**: `app/static/modules/pipeline.js:2374-2377`
- **Steps**: Paste a new API key in the Anthropic field but don't click Save. Click "Test". Backend uses the old `.env` key for the test, not the typed value.
- **Impact**: Test button gives misleading results — new users with no saved key see a test failure even if they typed a valid key; users testing a replacement key test the old one.

---

## BUG-010 — Error responses swallow real exception message across 28 endpoints [P2]
- **What**: All catch blocks in route handlers return the generic `{"error": "Operation failed. Check server logs."}` string instead of the actual exception message. This makes debugging impossible from the UI and API responses are uninformative.
- **Where**: 28 occurrences across:
  - `app/routes/import_routes.py:38, 91, 171, 290`
  - `app/routes/bulk_routes.py:52, 85, 124, 153, 188, 307`
  - `app/routes/settings_routes.py:518, 658`
  - `app/routes/review_routes.py:50, 77, 111, 259, 356`
  - `app/routes/track_routes.py:69, 115, 137`
  - `app/routes/organise_routes.py:121, 190, 245, 349`
  - `app/routes/session_routes.py:36, 76, 109`
- **Steps**: Trigger any server error (e.g. pass invalid data). Response: `{"error": "Operation failed. Check server logs."}` — no detail about what failed.
- **Impact**: Developers can't debug without SSH access to the server. End users get no actionable error information. The actual exception is logged server-side via `logger.exception()` but never surfaced in the API response.

---

## BUG-011 — Multiple password fields not in a `<form>` element [P2]
- **What**: All 9 API key input fields (`type="password"`) are bare inputs inside `<div>` elements, not wrapped in a `<form>`. Browsers report this as a DOM violation and it disables browser password manager integration (cannot auto-fill or save keys).
- **Where**: `templates/index.html:681, 690, 700, 710, 720` and similar lines for qwen, deepseek, groq, lastfm
- **Steps**: Open Settings tab. Browser console shows: `Password field is not contained in a form` (9 occurrences on page load).
- **Impact**: Browser password managers can't save/fill API keys. Users must re-enter keys after clearing localStorage.

---

## BUG-012 — `classify` POST from `library.js` toolbar calls `/api/classify` not `/api/classify/start` — but there's a stale `classify/start` reference in the task description [P3]
- **What**: The toolbar "Classify All" button in `library.js` line 141 correctly calls `POST /api/classify`. The task description says to test `/api/classify/start` — that endpoint doesn't exist (404). This is a documentation/spec inconsistency, not a code bug, but it means any external docs are wrong.
- **Where**: Task description vs `app/routes/import_routes.py` (route is `/api/classify`)
- **Steps**: `curl -X POST http://localhost:5050/api/classify/start` → 404. `curl -X POST http://localhost:5050/api/classify` → 202.
- **Impact**: Documentation or external tools built against `/api/classify/start` will fail.

---

## BUG-013 — Library track table invisible due to pipeline stepper widget overflow [P3]
- **What**: On a standard viewport (780px wide), the pipeline stepper widget (showing `41/41`, `10/41`, `0/41`, `0/41`) renders above the toolbar and stats bar, pushing the track table completely below the visible area. The track table is rendered and functional (41 rows) but users can't see it without scrolling, and there's no visual affordance to scroll down.
- **Where**: `templates/index.html` — pipeline stepper layout, CSS
- **Steps**: Load app with 41 tracks. The pipeline stepper is large and the track table is below the fold. No scroll indicator.
- **Impact**: Users may think no tracks are loaded even though all 41 are present. The "No tracks match filters" empty state shown by the placeholder row is confusing.

---

## Summary

| ID | Severity | Area | Description |
|----|----------|------|-------------|
| BUG-001 | P1 | API | `/api/classify/start` is 404, correct route is `/api/classify` |
| BUG-002 | P1 | UI/Stats | `stat-analyzed` ID typo — analysed count never updates |
| BUG-003 | P1 | UI/Stats | `health-analyzed` ID typo — Stats & Library health all shows `—` |
| BUG-004 | P1 | API contract | review.js bulk-approve calls `.forEach()` on `{"approved":N}` object |
| BUG-005 | P1 | API contract | review.js write-tags calls `.forEach()` on async op_id response |
| BUG-006 | P2 | UI | Onboarding close doesn't fully release pointer events |
| BUG-007 | P2 | UI | Onboarding shown every reload when session exists but tracks unloaded |
| BUG-008 | P2 | Settings | Model dropdown shows "Error loading models" on Settings load with no key |
| BUG-009 | P2 | Settings | Test button tests saved `.env` key, not the key typed in the field |
| BUG-010 | P2 | Error handling | 28 endpoints swallow real exception message behind generic error |
| BUG-011 | P2 | Settings | 9 password fields not in `<form>` — browser warns, password manager disabled |
| BUG-012 | P3 | Docs | `/api/classify/start` referenced in task description doesn't exist |
| BUG-013 | P3 | UI/Layout | Track table pushed below viewport by pipeline stepper on narrow screens |
