<p align="center">
  <img src="assets/icon_256.png" width="96" alt="IDJLM Pro logo" />
</p>

# IDJLM Pro

**Intelligent DJ Library Manager** — AI-powered genre + sub-genre classification for Latin dance music libraries.

**For:** DJs with Salsa, Bachata, Kizomba (and more) collections who want to bulk-classify tracks, analyze loudness and energy, and write clean ID3 tags so djay Pro smart playlists just work.

![IDJLM Pro v2.5 — Welcome & workflow](docs/screenshot-v2.5.4-import.png)

<p align="center">
  <img src="docs/screenshot-v2.5.4-settings.png" width="48%" alt="Settings — AI model, API keys, thresholds" />
  &nbsp;
  <img src="docs/screenshot-v2.5.4-setplanner.png" width="48%" alt="Set Planner — energy arc builder" />
</p>

## Download

Get the latest release from [Releases](../../releases/latest):
- **macOS** — download `IDJLM-Pro-vX.X.X-macOS.dmg`
- **Windows** — download `IDJLM-Pro-vX.X.X-Windows.zip`

No Python or terminal required — just open and run.

**New:** Click the version badge in the header or "Check for Updates" in Settings to update in-app. Downloads the latest `.dmg` and opens it for you.

## What it does

1. Point it at a folder of audio files (MP3, FLAC, WAV, M4A, AAC, OGG, AIFF)
2. Existing genre tags are read from each file immediately on import
3. AI classifies each track → genre + sub-genre + confidence
4. BPM, key (Camelot), energy, vocal/instrumental flag, LUFS loudness analyzed automatically
5. Preview any track with the built-in audio player
6. Review proposed tags, bulk-approve, edit individually, or **re-classify** with a different AI model
7. Tags written to ID3: `GENRE`, `COMMENT` (sub-genre), `BPM`, `KEY`, `YEAR`, cover art
8. Open djay Pro → smart playlists filter by genre + comment automatically

### Tabs

| Tab | What it does |
|-----|-------------|
| **Library** | Full library table — full-text search (17 fields), sort, filter, bulk edit, audio preview, LUFS column, Camelot wheel, key compatibility graph |
| **Organise** | Library health dashboard, filename → tag parser, folder auto-organiser, key validator, **tag backup & restore** |
| **Set Planner** | Auto-build a DJ set shaped to Warm-Up / Peak Hour / Cool-Down energy arc |
| **Setlist** | Manual setlist builder with drag-and-drop reordering, harmonic suggestions, **energy timeline chart** |
| **Playlists** | Build saved playlists with filters (genre, BPM, energy, key), export M3U for djay |
| **Taxonomy** | Edit genre/sub-genre definitions — AI adapts immediately. Export/import templates. |
| **Duplicates** | Detect, remove, or **merge** duplicate tracks (keep best fields from each) |
| **Settings** | API keys, AI model selection (Claude / Gemini / OpenRouter / Ollama), dynamic model listing, batch size, auto-approve threshold, **AI learning dashboard** |
| **Export** | M3U, CSV, JSON, Rekordbox XML with genre/BPM/key/energy filters |

## Requirements

- macOS (Apple Silicon M3 supported) or Windows
- One of:
  - [Anthropic API key](https://console.anthropic.com/) — Claude
  - [Google Gemini API key](https://aistudio.google.com/) — free tier available
  - [OpenRouter API key](https://openrouter.ai/) — 100+ models, free tier available (Gemini, Claude, Llama, Mistral, etc.)
  - Local [Ollama](https://ollama.com) — free, runs fully offline
- Spotify API credentials (optional — for year/metadata enrichment)

## Setup (run from source)

```bash
# 1. Clone the repo
git clone https://github.com/xonline/idjlm-pro.git
cd idjlm-pro

# 2. Copy the config template and add your API key(s)
cp config.example.env .env
# Edit .env — set at least one AI key (see AI Model Options below)

# 3. Launch
./start.sh
# Opens at http://localhost:5050
```

`start.sh` creates a Python virtual environment and installs all dependencies automatically on first run.

## Usage

### Import
1. Open the app (or http://localhost:5050 if running from source)
2. Click **Pick Folder** and choose your music folder — works with external drives
3. Tracks appear with any existing tags already loaded from their files
4. **Optional:** Use import filters (file type, date range, exclude subfolders) before importing
5. Click **Analyze All** → BPM, key (Camelot), energy, vocal/instrumental flag, LUFS loudness, tempo category, confidence scores
6. Click **Classify All** → AI returns genre + sub-genre + confidence for every track

**Tip:** Select specific tracks with the checkboxes and use the **Analyze** or **Classify** buttons in the selection bar to process only those tracks.

### Review + Write
7. **Review** tab → current vs proposed tags side by side
8. Set confidence threshold → **Bulk Approve ≥80%**
9. Click **Write Approved Tags** → written to file ID3 tags

**Tag Safety:** Every write operation backs up current tags first. Restore from any backup via Organise → Tag Backups.

### Re-classify
Select tracks → click **Re-classify** → pick an AI provider → force re-classify with a specific model. Useful when you want to try a different AI on low-confidence tracks.

### AI Learning
The AI learns from your approvals and edits. Over time it adapts to your classification style. View your correction history and reset learning in Settings.

### Bulk Edit
Select tracks with checkboxes → click **Bulk Edit** in the action bar → set genre, sub-genre, BPM, year for all selected tracks at once.

### Audio Preview
Click the ▶ play button on any track row to preview it inline. Supports MP3, FLAC, WAV, M4A, AAC, OGG, AIFF.

### djay Pro
After writing tags, djay Pro reads them immediately:
- Smart Playlist → filter by **Genre** = "Salsa" → **Comment** = "Romántica"
- BPM and Key (Camelot) appear in djay's key display

## ID3 Field Mapping

| Field | ID3 Frame | djay Pro uses for |
|-------|-----------|-------------------|
| Genre | TCON | Genre smart playlist filter |
| Sub-genre | COMM | Comment smart playlist filter |
| BPM | TBPM | BPM display + filter |
| Key | TKEY + TXXX:INITIALKEY | Key display (Camelot: 8B, 3A…) |
| Year | TDRC | Year filter |
| Album Art | APIC | Cover art in DJ software |
| Clave Pattern | COMM:clave | Latin rhythm metadata |
| Energy Score | COMM:energy | Perceived dance energy (1-10) |
| Vocal Flag | COMM:vocal | Vocal/instrumental detector |
| Tempo Category | COMM:tempo | Genre-aware slow/medium/fast label |
| LUFS | COMM:lufs | Loudness normalization reference |

## Configuring Sub-genres

Go to **Taxonomy** tab to add, rename, or remove genres and sub-genres.

Default taxonomy includes:
- **Salsa:** Romántica, Dura, Mambo, Jazz/Instrumental, Son Cubano, Timba, Salsa Choke
- **Bachata:** Dominicana/Tradicional, Moderna, Sensual, Remix/Urbana
- **Kizomba:** Clássica, Semba, Ghetto Zouk, Tarraxinha, Urban Kiz
- **Cha Cha, Merengue, Reggaeton, Zouk** (with sub-genres)

**Taxonomy Templates:** Export/import your taxonomy as JSON. Apply built-in templates (Salsa Complete, Bachata Complete, Latin Multi, Social DJ Essentials).

## Optional: Spotify + Multi-Source Enrichment

Add Spotify credentials to `.env` to fill in missing year/metadata. When Spotify fails, IDJLM automatically falls back to:
- **MusicBrainz** (free, no API key needed) — year, artist, album lookup
- **Discogs** (optional API token) — year, label, genre, cover art lookup

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
DISCOGS_TOKEN=your_discogs_token
```

Get credentials at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) (free) and [discogs.com/settings/developers](https://www.discogs.com/settings/developers).

## AI Model Options

Choose your preferred AI in the **Settings** tab. The model dropdown populates live from the provider's API — no hardcoding. OpenRouter models show free/paid badges.

| AI | Provider | API Key env var | Notes |
|----|----------|-----------------|-------|
| **Claude** | Anthropic | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) |
| **Gemini** | Google | `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/) — free tier available |
| **OpenRouter** | OpenRouter | `OPENROUTER_API_KEY` | [openrouter.ai](https://openrouter.ai/) — 100+ models, free models available |
| **Ollama** | Local (free) | — | No key needed. [ollama.com](https://ollama.com) |

You only need one. Set your preference in the **Settings** tab or via `AI_MODEL=claude` / `AI_MODEL=gemini` / `AI_MODEL=openrouter` / `AI_MODEL=ollama` in `.env`.

## Settings Persistence

Settings (API keys, model preference, thresholds) are stored in:
- **macOS:** `~/Library/Application Support/IDJLM Pro/.env`
- **Other:** `~/.idjlm-pro/.env`

They survive app updates, reinstalls, and DMG launches. Existing settings from earlier versions are migrated automatically.

## Stats Dashboard

The Library tab includes a stats dashboard with:
- **Collection Summary** — total tracks, % analyzed, % classified, % approved, average LUFS
- **Key Distribution** — horizontal bar chart showing track count per Camelot key
- **Energy Distribution** — bar chart bucketed by energy level
- **Camelot Wheel** — SVG visualization of your library's key distribution
- **Collection Age Analysis** — decade distribution, era breakdowns (Salsa Clásica/Romántica/Moderna, Bachata Tradicional/Moderna), median year
- **Key Compatibility Graph** — interactive network visualization showing which tracks mix harmonically

## Analysis Metrics

Every track shows these metrics after analysis:
- **BPM Confidence** (0-100) — computed from onset strength peak clarity. High = clear, detectable beat pattern.
- **Key Confidence** (0-100) — computed from chroma template correlation strength. High = clear major/minor tonality.
- **LUFS** (e.g., -11.2) — EBU R128 integrated loudness. Green = -14 to -8 (good range), Amber = -18 to -14 or -6 to -8, Red = extremes.
- **LUFS Range / LRA** — dynamic range. Higher = more compression.
- **True Peak** (dBFS) — maximum instantaneous level. Useful for gain staging.

Use confidence scores to identify tracks that may need manual review. Use LUFS to spot tracks that sound much quieter or louder than the rest of your library.

## Genre Normalization

On import, common genre variants are automatically mapped to your taxonomy:
- "Salsa Romántica" / "Salsa-Romantica" / "Latin Jazz" → **Salsa**
- "Bachata Sensual" / "Bachata Dominicana" → **Bachata**
- "Reggaetón" / "Reggaeton Lento" → **Reggaeton**
- And 30+ more mappings

This ensures consistent classification even when source tags are inconsistent.

## Keyboard Shortcuts

Press `?` or `Cmd+/` anytime to see the full shortcut reference. Key shortcuts:

| Shortcut | Action |
|----------|--------|
| `1-4` | Switch tabs (Library, Organise, Set Planner, Settings) |
| `/` | Focus search bar |
| `Space` | Play/pause audio preview |
| `Ctrl+A` / `Cmd+A` | Select all tracks |
| `Ctrl+Shift+A` | Deselect all |
| `Enter` | Approve selected tracks |
| `Delete` / `Backspace` | Skip selected tracks |
| `Ctrl+S` / `Cmd+S` | Save session |
| `?` | Open keyboard shortcut reference |

## Supported Audio Formats

MP3, FLAC, WAV, M4A, AAC, OGG, AIFF, AIF

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.
