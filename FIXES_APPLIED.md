# IDJLM Pro - Critical Bug Fixes (April 7, 2026)

## Summary
Fixed critical bugs preventing AI classification from working. The main issue was that **saving API keys in Settings did NOT reload environment variables**, so the classifier couldn't see the Gemini API key even after you saved it.

## Bugs Found & Fixed

### 1. **CRITICAL: Settings Save Didn't Reload Environment Variables** 
**File**: `app/routes/settings_routes.py`

**Problem**: 
- When you entered your Gemini API key in Settings and clicked Save
- The key was written to `~/.idjlm-pro/.env` file ✓
- BUT the running Flask app's environment variables were NOT updated ✗
- So when classifier ran `os.getenv("GEMINI_API_KEY")`, it returned `None`
- Classification immediately failed with "GEMINI_API_KEY not set"

**Fix**:
```python
# After writing .env file, reload into running process
from dotenv import load_dotenv
load_dotenv(get_env_path(), override=True)
```

**Impact**: This was THE MAIN BUG preventing AI classification from working.

---

### 2. **Gemini API Model Deprecated**
**File**: `app/services/classifier.py`

**Problem**:
- Code used `gemini-2.0-flash` model
- Google deprecated this model on March 31, 2026
- Today is April 7, 2026 - model no longer works

**Fix**:
- Updated to use `gemini-2.5-flash` (current recommended model)
- Added automatic fallback to `gemini-2.0-flash` if 2.5 fails
- Updated OpenRouter default model to `google/gemini-2.5-flash:free`

---

### 3. **Deprecated google.generativeai Package**
**File**: `app/services/classifier.py`

**Problem**:
- `google.generativeai` package is deprecated and shows warnings
- Google recommends using new `google.genai` package (2026+)

**Fix**:
```python
try:
    import google.genai as genai  # New API (2026+)
    USES_NEW_API = True
except ImportError:
    import google.generativeai as genai  # Legacy fallback
    USES_NEW_API = False
```
- Updated `_classify_with_gemini()` to use both APIs
- Tries new API first, falls back to legacy if needed

---

### 4. **Added Comprehensive Debug Logging**
**Files**: 
- `app/routes/import_routes.py`
- `app/services/classifier.py`

**Added logging**:
- Track import/analysis/classification progress
- API key availability checks
- Error details for troubleshooting
- Model selection information

**Example logs**:
```
[classifier] Starting classification: ai_model=gemini, batch_size=15
[classifier] GEMINI_API_KEY set: True
[classifier] Tracks to classify: 10
Analyze request: 10 tracks, store has 10 tracks
```

---

## How to Use (Correct Workflow)

### Prerequisites
1. Get a Gemini API key: https://aistudio.google.com/apikey (FREE)
2. Have MP3/music files in a folder

### Steps

1. **Start the App**
   ```bash
   cd ~/dj-library-manager
   source .venv/bin/activate
   python3 -c "from app import create_app; app = create_app(); app.run(port=5050)"
   ```
   Or use the desktop app if on macOS

2. **Configure Gemini API Key**
   - Go to **Settings** tab
   - Select AI Model: **gemini**
   - Paste your Gemini API key
   - Click **Save**
   - ✓ Key is now saved AND immediately available (fixed!)

3. **Import Music Folder**
   - Go to **Library** tab
   - Click **Get Started** or **Change**
   - Select your music folder
   - Wait for import to complete

4. **Analyze Tracks** (Audio Features)
   - Click **▶ Analyze All**
   - This extracts: BPM, Key (Camelot), Energy, Vocal detection
   - Uses librosa (local, no API needed)
   - Wait for progress to complete

5. **Classify with AI** (Genre Categorization)
   - Click **✦ Classify All**
   - This uses Gemini AI to categorize into:
     - Salsa, Bachata, Merengue, Kizomba, etc.
     - Subgenres (Romántica, Sensual, Urbana, etc.)
   - Takes 10-30 seconds per batch
   - Shows confidence scores and reasoning

6. **Review & Approve**
   - Go to **Organise** tab
   - Review AI suggestions
   - Click **✓ Approve** for correct classifications
   - Edit any incorrect ones manually

7. **Write Tags** (Optional)
   - Click **✎ Write Tags**
   - Writes approved genres to MP3 metadata

---

## Testing

### Quick Test
```bash
# Server must be running on port 5566
python3 /tmp/test_quick_analyze.py
```

### Full Integration Test
```bash
# Will prompt for Gemini API key
python3 /tmp/test_full_workflow.py
```

### Check Logs
```bash
tail -f ~/.idjlm-pro/logs/idjlm.log
```

---

## Files Modified

1. ✅ `app/routes/settings_routes.py` - Environment reload fix
2. ✅ `app/services/classifier.py` - Gemini API updates + new genai package
3. ✅ `app/routes/import_routes.py` - Better error logging
4. ✅ Updated model defaults to current Gemini versions

---

## What's Working Now

✅ **Settings Save** - API keys are immediately available after saving  
✅ **Gemini API** - Using current models with fallbacks  
✅ **Audio Analysis** - BPM, Key, Energy detection via librosa  
✅ **AI Classification** - Genre categorization with confidence scores  
✅ **Error Logging** - Detailed logs for troubleshooting  

---

## Common Issues & Solutions

### "Classification failed: GEMINI_API_KEY not set"
**Solution**: Go to Settings, enter your Gemini API key, click Save. The fix ensures it's immediately available.

### "No tracks to classify"
**Solution**: You must Analyze tracks first before Classifying. Click "Analyze All" then wait for it to complete.

### "Import failed: No module named 'mutagen'"
**Solution**: Run `source .venv/bin/activate && pip install -r requirements.txt`

### Classification is slow
**Normal**: AI classification takes 10-30 seconds per batch (15 tracks). This is expected.

---

## Next Steps for User

1. **Get your Gemini API key** from https://aistudio.google.com/apikey
2. **Start the app** 
3. **Enter API key in Settings** and save
4. **Import your music folder**
5. **Click Analyze All** (extracts audio features)
6. **Click Classify All** (AI categorizes genres) ← This is where the magic happens!
7. **Review results** in Organise tab

The app will now actually use Gemini AI to help categorize your salsa/bachata/etc music as promised! 🎵
