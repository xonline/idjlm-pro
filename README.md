# XDJ Library Manager

![Version](https://img.shields.io/badge/version-1.0.0-blue)

Automatically classify your DJ music library by genre and sub-genre using AI — in bulk.

Built for DJs with large Latin dance collections (Salsa, Bachata, Kizomba, and more).

---

## Download

Go to the **[Releases](https://github.com/xonline/dj-library-manager/releases)** page and download for your platform:

| Platform | What to download |
|----------|------------------|
| 🍎 Mac | `XDJ-Library-Manager-mac.zip` |
| 🪟 Windows | `XDJ-Library-Manager-windows.zip` |

**Mac:** Unzip → double-click `XDJ Library Manager.app`
**Windows:** Unzip → double-click `XDJ Library Manager.exe`

> **Mac note:** First time you open it, macOS may say "unidentified developer".
> Right-click the app → **Open** → **Open anyway**. Only needed once.

No Python. No Terminal. No installation.

---

## Setup (first time only)

You need a free **Gemini API key** to use the AI classification.

1. Go to [aistudio.google.com](https://aistudio.google.com/) — sign in with your Google account
2. Click **Get API key** → **Create API key**
3. Open **XDJ Library Manager** → go to the **Settings** tab
4. Paste your API key → Save

That's it. The app is ready.

---

## How to use

### Import your music
1. Click **Import Folder**
2. Select the folder with your MP3s (works recursively — subfolders included)
3. All tracks appear in the list with their existing tags

### Analyse tracks
- Click **Analyse All** — detects BPM, musical key (Camelot notation), and energy level
- Takes about 5–10 seconds per track

### Classify with AI
- Click **Classify All** — AI reads each track's metadata + audio features and suggests genre + sub-genre
- Shows confidence score (0–100%) and reasoning

### Review and approve
- Go to the **Review** tab
- Each track shows: current tags vs. AI suggestion
- Click **Approve** to accept, **Skip** to leave unchanged, or edit manually
- **Bulk approve** — approve everything above a confidence threshold in one click

### Write tags
- Click **Write Tags** — approved changes are saved to the MP3 files (ID3 tags)
- Genre → TCON, Sub-genre → Comment, BPM → TBPM, Key → TKEY

---

## Genre taxonomy

The app ships with 7 Latin dance genres:

| Genre | Sub-genres |
|-------|------------|
| Salsa | Salsa Romantica, Salsa Dura, Timba, Salsa Choke, Salsa Sensual, Guaracha, Son Cubano |
| Bachata | Bachata Tradicional, Bachata Sensual, Bachata Moderna, Bachata Urbana |
| Kizomba | Kizomba Tradicional, Urban Kiz, Semba, Ghetto Zouk, Tarraxinha |
| Cha Cha | — |
| Merengue | — |
| Reggaeton | — |
| Zouk | — |

Edit the **Taxonomy** tab to add your own sub-genres. Changes apply immediately.

---

## Changelog

### Latest
- Initial release
- Mac + Windows standalone app (no installation needed)
- AI genre + sub-genre classification via Gemini 1.5 Flash
- BPM, Camelot key, energy analysis via librosa
- Spotify enrichment (optional — year, popularity)
- Review queue with bulk approve
- ID3 tag writer (genre, comment, BPM, key)
- Folder watcher — auto-import new files
- Session save/load
- Taxonomy editor
- Version system with `/api/version` endpoint

---

## For developers

```bash
git clone https://github.com/xonline/dj-library-manager.git
cd dj-library-manager
cp config.example.env .env
# Add GEMINI_API_KEY to .env
./start.sh
# Open http://localhost:5050
```

**Build standalone app (Mac):**
```bash
./build-mac.sh
# Requires Python 3.10+ (brew install python@3.12)
# Output: dist/XDJ Library Manager.app
```
