# IDLM Pro

**Intelligent DJ Library Manager** — AI-powered genre + sub-genre classification for Latin dance music libraries.

**For:** DJs with Salsa, Bachata, Kizomba (and more) collections who want to bulk-classify tracks and write clean ID3 tags so djay Pro smart playlists just work.

## What it does

1. Point it at a folder of MP3s
2. AI (Claude) classifies each track → genre + sub-genre
3. Review proposed tags, bulk-approve or edit
4. Tags written to ID3: `GENRE`, `COMMENT` (sub-genre), `BPM`, `KEY`, `YEAR`
5. Open djay Pro → smart playlists filter by genre + comment automatically

## Requirements

- macOS (Apple Silicon M3 supported)
- Python 3.11+
- Gemini API key (required, free) — get one at aistudio.google.com/apikey
- Spotify API credentials (optional, for year/metadata enrichment)

## Setup

```bash
# 1. Clone / copy the project folder to your Mac
cd idlm-pro

# 2. Copy the config template and add your API key
cp config.example.env .env
# Edit .env and set ANTHROPIC_API_KEY=your_key_here

# 3. Launch
./start.sh
# Opens at http://localhost:5050
```

`start.sh` creates a Python virtual environment and installs all dependencies automatically on first run.

## Usage

### Import
1. Open http://localhost:5050
2. Enter your MP3 folder path (e.g. `/Users/yourname/Music/Downloads`) — works with external drives too
3. Click **Import** — tracks appear in the list with existing tags

### Analyze + Classify
4. Click **Analyze All** — extracts BPM, key (Camelot), energy from audio
5. Click **Classify All** — sends to Claude AI, returns genre + sub-genre + confidence

*Note: Analysis is CPU-intensive. ~2-5s per track for librosa analysis on M3.*

### Review
6. Go to **Review** tab — see current tags vs proposed tags side by side
7. Set confidence threshold (default 80%) → click **Bulk Approve ≥80%**
8. Manually approve/edit/skip any remaining tracks
9. Click **Write Approved Tags** — writes to MP3 ID3 tags

### djay Pro
After writing tags, djay Pro reads them immediately:
- Smart Playlist → filter by **Genre** = "Salsa" → **Comment** = "Romántica"
- BPM and Key (Camelot) populate in djay's key display

## ID3 Field Mapping

| Field | ID3 Frame | djay Pro uses for |
|-------|-----------|-------------------|
| Genre | TCON | Genre smart playlist filter |
| Sub-genre | COMM | Comment smart playlist filter |
| BPM | TBPM | BPM display + filter |
| Key | TKEY | Key display (Camelot: 8B, 3A…) |
| Year | TDRC | Year filter |

## Configuring Sub-genres

Go to **Taxonomy** tab to add, rename, or remove genres and sub-genres. Changes are saved immediately and the AI adapts to your taxonomy on the next classify run.

Default taxonomy includes:
- **Salsa:** Romántica, Dura, Mambo, Jazz/Instrumental, Son Cubano, Timba, Salsa Choke
- **Bachata:** Dominicana/Tradicional, Moderna, Sensual, Remix/Urbana
- **Kizomba:** Clássica, Semba, Ghetto Zouk, Tarraxinha, Urban Kiz
- **Cha Cha, Merengue, Reggaeton, Zouk** (with sub-genres)

## Optional: Spotify Enrichment

Add Spotify credentials to `.env` to fill in missing year/metadata:

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
```

Get credentials at https://developer.spotify.com/dashboard (free).

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.
