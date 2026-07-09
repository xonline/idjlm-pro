# IDJLM v4 Phase 1 — Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 13 confirmed bugs from the QA audit plus 3 analysis accuracy issues so the existing app works correctly end-to-end.

**Architecture:** Pure surgical fixes to existing files — no new architecture, no refactoring unrelated code. Backend stays identical; only broken logic is corrected.

**Tech Stack:** Python 3.12, Flask 3.x, vanilla JS (ES modules), librosa, mutagen, soundfile

**Test songs:** `/home/ubuntu/upload/songs test/` — run the server with `.venv/bin/python3 run_app.py`

---

### Task 1: Fix analysis quality — BPM precision + PySoundFile + energy calibration

**Files:**
- Modify: `app/services/analyzer.py`

- [ ] **Install soundfile into the project venv**

```bash
cd /home/ubuntu/projects/idjlm
.venv/bin/pip install soundfile
sudo apt-get install -y libsndfile1 2>/dev/null || true
```

Expected: `Successfully installed soundfile-X.X.X` (or already satisfied)

- [ ] **Verify soundfile works**

```bash
.venv/bin/python3 -c "import soundfile; print('soundfile OK:', soundfile.__version__)"
```

Expected: `soundfile OK: 0.12.x`

- [ ] **Fix BPM precision — open `app/services/analyzer.py`, find the BPM assignment**

Look for the line that sets `track.analyzed_bpm`. It will look like:
```python
track.analyzed_bpm = float(tempo[0])
```
Change to:
```python
track.analyzed_bpm = round(float(tempo[0]), 1)
```

- [ ] **Fix energy calibration — in `app/services/analyzer.py`, find `_normalize_energy`**

Change the empirical max from 0.2 to 0.35 so salsa/high-energy tracks don't all cluster at 9-10:
```python
normalized = min(1.0, rms_mean / 0.35)   # was 0.2
```

- [ ] **Verify the changes didn't break imports**

```bash
cd /home/ubuntu/projects/idjlm && .venv/bin/python3 -c "
from app.services.analyzer import _normalize_energy
import numpy as np
rms = np.array([[0.15]])
score = _normalize_energy(rms)
print('Energy score for 0.15 RMS:', score)
assert 1 <= score <= 10
print('OK')
"
```

Expected: `Energy score for 0.15 RMS: 4` (was 7 before), `OK`

- [ ] **Commit**

```bash
cd /home/ubuntu/projects/idjlm
git add app/services/analyzer.py
git commit -m "fix: round BPM to 1dp, fix energy calibration, add soundfile dep"
```

---

### Task 2: Fix analyzed/analysed ID typos (BUG-002, BUG-003)

**Files:**
- Modify: `app/static/modules/navigation.js` (line ~69)
- Modify: `app/static/modules/pipeline.js` (line ~1510)

- [ ] **Fix BUG-002 in navigation.js**

```bash
grep -n "stat-analyzed" /home/ubuntu/projects/idjlm/app/static/modules/navigation.js
```

Find the line (should be around line 69). Change:
```javascript
document.getElementById('stat-analyzed')
```
to:
```javascript
document.getElementById('stat-analysed')
```

- [ ] **Fix BUG-003 in pipeline.js**

```bash
grep -n "health-analyzed" /home/ubuntu/projects/idjlm/app/static/modules/pipeline.js
```

Change every occurrence of `health-analyzed` to `health-analysed`:
```bash
sed -i "s/health-analyzed/health-analysed/g" /home/ubuntu/projects/idjlm/app/static/modules/pipeline.js
```

Verify no `health-analyzed` remain:
```bash
grep -c "health-analyzed" /home/ubuntu/projects/idjlm/app/static/modules/pipeline.js
```
Expected: `0`

- [ ] **Manual verification**

Start the server, import the test folder, run Analyse. Open Stats & Library tab. All stat values should show numbers instead of `—`.

- [ ] **Commit**

```bash
cd /home/ubuntu/projects/idjlm
git add app/static/modules/navigation.js app/static/modules/pipeline.js
git commit -m "fix: correct analyzed/analysed ID spelling mismatches (BUG-002, BUG-003)"
```

---

### Task 3: Fix review.js forEach crashes (BUG-004, BUG-005)

**Files:**
- Modify: `app/static/modules/review.js`

- [ ] **Read the current bulk-approve handler**

```bash
sed -n '90,120p' /home/ubuntu/projects/idjlm/app/static/modules/review.js
```

- [ ] **Fix BUG-004 — bulk-approve forEach**

Find the handler that calls `/api/review/bulk-approve` and does `result.forEach(...)`. The API returns `{"approved": N}`. Replace the forEach block with:

```javascript
// was: result.forEach(trackPath => { ... })
// API returns {"approved": N} — update UI count directly
const approvedCount = result.approved || 0;
showToast(`${approvedCount} track${approvedCount !== 1 ? 's' : ''} approved`, 'success');
renderTracks();
updateStats();
```

- [ ] **Read the write-tags handler**

```bash
sed -n '115,145p' /home/ubuntu/projects/idjlm/app/static/modules/review.js
```

- [ ] **Fix BUG-005 — write-tags async mismatch**

The API now returns `{"op_id": "...", "total": N}` with HTTP 202. Replace the sync forEach handler with an async pattern matching how `library.js` handles it:

```javascript
// was: result.forEach(trackPath => { ... })
// API returns async op_id — poll progress
if (result.op_id) {
  trackWriteProgress(result.op_id, result.total, () => {
    showToast('Tags written successfully', 'success');
    renderTracks();
  });
} else {
  showToast('Write tags started', 'info');
}
```

Note: `trackWriteProgress` must match the existing function name used in `library.js` for the same pattern. Check with:
```bash
grep -n "trackWriteProgress\|pollProgress\|trackProgress" /home/ubuntu/projects/idjlm/app/static/modules/library.js | head -5
```
Use whatever function name library.js uses — do not invent a new one.

- [ ] **Manual verification**

Import test songs → Analyse → Classify a few → open Review tab → Bulk Approve → confirm toast fires and statuses update. Then Write Tags → confirm tags are written.

- [ ] **Commit**

```bash
cd /home/ubuntu/projects/idjlm
git add app/static/modules/review.js
git commit -m "fix: review.js forEach on object crash for bulk-approve and write-tags (BUG-004, BUG-005)"
```

---

### Task 4: Fix onboarding UX (BUG-006, BUG-007)

**Files:**
- Modify: `app/static/modules/pipeline.js`
- Modify: `templates/index.html` (onboarding overlay CSS)

- [ ] **Find the onboarding overlay in index.html**

```bash
grep -n "onboarding\|pointer-events" /home/ubuntu/projects/idjlm/templates/index.html | head -10
```

- [ ] **Fix BUG-006 — pointer-events leak**

Find the CSS rule for the onboarding overlay. Add `pointer-events: none` to the hidden state. If it's controlled by JS, find the `completeOnboarding` function in pipeline.js:

```bash
grep -n "completeOnboarding\|onboarding" /home/ubuntu/projects/idjlm/app/static/modules/pipeline.js | head -10
```

In `completeOnboarding()`, after hiding the overlay, add:
```javascript
const overlay = document.getElementById('onboarding-overlay'); // use the actual ID
if (overlay) {
  overlay.style.display = 'none';
  overlay.style.pointerEvents = 'none';
}
```

- [ ] **Fix BUG-007 — onboarding shown every reload**

Find `showOnboardingIfNeeded()` in pipeline.js. Change the condition from checking `window.tracks.length` to checking localStorage:

```javascript
function showOnboardingIfNeeded() {
  if (localStorage.getItem('idjlm-onboarding-done')) return;  // add this line first
  // rest of existing logic unchanged
}
```

- [ ] **Verify: reload the page with test tracks already imported (via Resume)**

Reload → should NOT show onboarding (localStorage key is set). Clear localStorage → reload → SHOULD show onboarding.

- [ ] **Commit**

```bash
cd /home/ubuntu/projects/idjlm
git add app/static/modules/pipeline.js templates/index.html
git commit -m "fix: onboarding pointer-events leak and re-show on every reload (BUG-006, BUG-007)"
```

---

### Task 5: Fix Settings — model loading and Test button (BUG-008, BUG-009)

**Files:**
- Modify: `app/static/modules/settings.js`
- Modify: `app/static/modules/pipeline.js`

- [ ] **Fix BUG-008 — model dropdown error on page load**

```bash
grep -n "fetchModels\|loadSettings" /home/ubuntu/projects/idjlm/app/static/modules/settings.js | head -15
```

Find where `fetchModels` is called during `loadSettings`. Guard it so it only runs if a key is actually saved:

```javascript
// Before calling fetchModels, check if key exists
const savedKey = /* however the settings reads the saved key */ '';
if (savedKey && savedKey.length > 0) {
  await fetchModels(provider);
} else {
  // Set placeholder text in dropdown
  const modelSelect = document.getElementById('model-select'); // use actual ID
  if (modelSelect) {
    modelSelect.innerHTML = '<option value="">Enter API key first</option>';
  }
}
```

Find the actual saved-key read pattern by checking `loadSettings` — it reads from a response object or localStorage. Use the same pattern.

- [ ] **Fix BUG-009 — Test button tests .env key not input field**

```bash
grep -n "testApiKey\|test_key" /home/ubuntu/projects/idjlm/app/static/modules/pipeline.js | head -10
```

Find `testApiKey(provider)`. It currently sends only `{ provider }`. Change to also send the current field value:

```javascript
async function testApiKey(provider) {
  // Get the input value for this provider
  const inputEl = document.querySelector(`[data-provider="${provider}"] input[type="password"], #key-${provider}, input[name="${provider}_key"]`);
  const keyValue = inputEl ? inputEl.value.trim() : '';

  const payload = { provider };
  if (keyValue) payload.key = keyValue;  // send typed key if present

  const result = await apiFetch('/api/test_key', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  // rest of handler unchanged
}
```

Also update the backend `/api/test_key` handler to prefer the `key` field from the request body over the `.env` key:

```bash
grep -n "test_key\|testApiKey" /home/ubuntu/projects/idjlm/app/routes/settings_routes.py | head -10
```

In the route handler, read the optional `key` param:
```python
data = request.get_json(silent=True) or {}
provider = data.get('provider', '')
override_key = data.get('key', '').strip()  # add this
# Then use override_key if provided, else fall back to env key
```

- [ ] **Commit**

```bash
cd /home/ubuntu/projects/idjlm
git add app/static/modules/settings.js app/static/modules/pipeline.js app/routes/settings_routes.py
git commit -m "fix: model dropdown empty state on load, Test button uses typed key (BUG-008, BUG-009)"
```

---

### Task 6: Fix error responses and password form wrappers (BUG-010, BUG-011)

**Files:**
- Modify: All route files listed in BUG-010
- Modify: `templates/index.html`

- [ ] **Fix BUG-010 — surface real error messages**

In each of the 28 catch blocks across these files:
`import_routes.py`, `bulk_routes.py`, `settings_routes.py`, `review_routes.py`, `track_routes.py`, `organise_routes.py`, `session_routes.py`

Change the catch-all from:
```python
except Exception as e:
    logger.exception("Error in /api/...")
    return jsonify({"error": "Operation failed. Check server logs."}), 500
```
to:
```python
except Exception as e:
    logger.exception("Error in /api/...")
    return jsonify({"error": str(e)}), 500
```

Run this across all 7 files at once:
```bash
cd /home/ubuntu/projects/idjlm
for f in app/routes/import_routes.py app/routes/bulk_routes.py app/routes/settings_routes.py \
          app/routes/review_routes.py app/routes/track_routes.py \
          app/routes/organise_routes.py app/routes/session_routes.py; do
  sed -i 's/return jsonify({"error": "Operation failed. Check server logs."}), 500/return jsonify({"error": str(e)}), 500/g' "$f"
done
```

Verify the replacement worked:
```bash
grep -rn "Operation failed. Check server logs." /home/ubuntu/projects/idjlm/app/routes/
```
Expected: 0 matches

- [ ] **Fix BUG-011 — wrap password inputs in forms**

```bash
grep -n 'type="password"' /home/ubuntu/projects/idjlm/templates/index.html
```

For each API key input, wrap in a `<form autocomplete="off" onsubmit="return false;">...</form>`. Since there are 9 inputs, do a targeted edit around lines 681, 690, 700, 710, 720 etc. Each input needs its own form:

Before:
```html
<input type="password" id="key-gemini" ...>
```
After:
```html
<form autocomplete="off" onsubmit="return false;">
  <input type="password" id="key-gemini" ...>
</form>
```

- [ ] **Verify console warnings gone**

Restart server, open Settings. Console should show 0 "Password field not in form" warnings.

- [ ] **Commit**

```bash
cd /home/ubuntu/projects/idjlm
git add app/routes/*.py templates/index.html
git commit -m "fix: surface real error messages in all routes, wrap API key inputs in forms (BUG-010, BUG-011)"
```

---

### Task 7: End-to-end smoke test

- [ ] **Kill any running server and start fresh**

```bash
pkill -f "python3 run_app.py" 2>/dev/null; sleep 1
cd /home/ubuntu/projects/idjlm && .venv/bin/python3 run_app.py > /tmp/idjlm-smoke.log 2>&1 &
sleep 3
```

- [ ] **Run the full pipeline via API**

```bash
# 1. Import
curl -s -X POST http://localhost:5050/api/import \
  -H "Content-Type: application/json" \
  -d '{"folder_path":"/home/ubuntu/upload/songs test"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('Imported:', d.get('count'), 'tracks')"

# 2. Start analysis
OP=$(curl -s -X POST http://localhost:5050/api/analyze \
  -H "Content-Type: application/json" -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('op_id'))")
echo "Analysis op_id: $OP"

# Wait ~90s for analysis to complete (use background wait)
sleep 90

# 3. Check tracks have BPM with 1dp precision
curl -s http://localhost:5050/api/tracks | python3 -c "
import sys,json,urllib.request
with urllib.request.urlopen('http://localhost:5050/api/tracks') as r:
    d = json.loads(r.read())
tracks = d.get('tracks',[])
analyzed = [t for t in tracks if t.get('analysis_done')]
print(f'Analyzed: {len(analyzed)}/{len(tracks)}')
for t in analyzed[:3]:
    bpm = t.get('analyzed_bpm')
    # Check BPM has at most 1 decimal place
    if bpm:
        assert len(str(bpm).split('.')[-1]) <= 1, f'BPM too precise: {bpm}'
    print(f'  {t[\"display_title\"][:25]:25} BPM:{bpm} Key:{t.get(\"analyzed_key\")}')
print('BPM precision OK')
"
```

- [ ] **Verify no console errors in browser**

Navigate to http://localhost:5050, open DevTools. Expected console errors: 0 (was 2 on page load before fixes)

- [ ] **Verify Stats & Library shows real values**

Click Stats & Library tab. All health cards should show numbers, not `—`.

- [ ] **Tag the phase as complete**

```bash
cd /home/ubuntu/projects/idjlm
git tag v3.5.1-bugfix
echo "Phase 1 complete — all 13 bugs fixed"
```

