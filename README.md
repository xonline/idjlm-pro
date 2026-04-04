# DJ Library Manager

A web-based music library management system for DJs. Automatically analyze tracks (BPM, key, energy), classify genres using AI, enrich with Spotify metadata, and maintain a structured music database.

## Features

- **Audio Analysis**: Extract BPM, musical key (Camelot notation), and energy levels using librosa
- **AI Classification**: Genre and subgenre classification via Google Gemini API
- **Spotify Integration**: Optional metadata enrichment (artist, genres, release year)
- **Tag Management**: Read/write ID3v2 tags with mutagen
- **Folder Watching**: Auto-import new MP3s as they arrive
- **Review Workflow**: Approve or modify AI suggestions before writing tags
- **Playlist Export**: Generate M3U playlists filtered by genre/status
- **Session Persistence**: Save and load your entire library state
- **Premium UI**: Dark/light theme with responsive design

## Quick Start

### Prerequisites
- Python 3.10+ (macOS build requires 3.10+)
- Gemini API key (free at https://aistudio.google.com)

### Install & Run

```bash
./start.sh
# Opens http://localhost:5050
```

### Configuration

Create `.env` from `config.example.env`:

```bash
GEMINI_API_KEY=your-api-key-here
SPOTIFY_CLIENT_ID=optional
SPOTIFY_CLIENT_SECRET=optional
FLASK_PORT=5050
FLASK_DEBUG=false
```

## API Keys

- **Gemini** (required): Get free at https://aistudio.google.com/app/apikey
- **Spotify** (optional): Get at https://developer.spotify.com/dashboard

## Build macOS App

```bash
./build-mac.sh
# Creates: dist/DJ Library Manager.app
```

Requirements: Python 3.10+, PyInstaller, macOS.

## Taxonomy

Edit `taxonomy.json` to customize genres and subgenres:

```json
{
  "genres": [
    {
      "name": "Salsa",
      "subgenres": ["Cuban", "Puerto Rican"],
      "bpm_range": [160, 220]
    }
  ]
}
```

## Architecture

- **Backend**: Flask REST API with blueprints for import, track management, review, analytics
- **Audio**: librosa for BPM/key detection, mutagen for ID3 tags
- **AI**: Google Gemini 1.5 Flash for classification (batched up to 10 tracks)
- **Database**: In-memory store with JSON session persistence
- **Frontend**: Vanilla JavaScript + CSS (dark theme, responsive)

## API Endpoints

### Import
- `POST /api/import/pick-folder` - Native macOS folder picker
- `POST /api/import/import` - Scan folder for MP3s
- `POST /api/import/analyze` - Extract BPM/key/energy
- `POST /api/import/classify` - AI genre classification + Spotify enrichment

### Tracks
- `GET /api/tracks` - List with sort/filter
- `PUT /api/tracks/<id>` - Update overrides
- `GET /api/audio/<id>` - Stream MP3 with range support

### Review
- `POST /api/review/approve` - Mark as approved
- `POST /api/review/skip` - Skip review
- `POST /api/review/bulk-approve` - Batch approve above threshold
- `POST /api/review/write-tags` - Persist to ID3 tags

### Taxonomy
- `GET /api/bulk/taxonomy` - Get all genres
- `PUT /api/bulk/taxonomy/<genre>` - Update genre
- `POST /api/bulk/taxonomy` - Add genre
- `DELETE /api/bulk/taxonomy/<genre>` - Delete genre

### Session
- `POST /api/session/save` - Save library state
- `POST /api/session/load` - Restore from backup
- `GET /api/session/stats` - Track counts (total/analyzed/classified/approved)

### Settings
- `GET /api/settings` - Get API key status
- `POST /api/settings` - Update API keys

### Watch
- `POST /api/watch/start` - Start folder monitoring
- `POST /api/watch/stop` - Stop monitoring
- `GET /api/watch/poll` - Check for new files

### Export
- `GET /api/export/m3u` - Generate M3U playlist (filters: genre, subgenre, status)

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_app.py  # Standalone launcher with WebKit
# or
flask run  # Web-only, default http://localhost:5000
```

## License

MIT
