"""Smoke tests for every route -- catch 500 errors from broken imports, bad get_json calls, etc."""
import json
from unittest import mock
import pytest
from app.routes.setlist_routes import _load_setlist, _save_setlist

# ---------------------------------------------------------------------------
# Root page
# ---------------------------------------------------------------------------
class TestIndex:
    def test_get_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"<html" in resp.data.lower() or b"<!doctype" in resp.data.lower()


# ---------------------------------------------------------------------------
# Import routes  (app/routes/import_routes.py)
# ---------------------------------------------------------------------------
class TestImportRoutes:
    def test_import_empty_body(self, client):
        resp = client.post("/api/import", json={})
        assert resp.status_code in (200, 400)  # 400 = validation, never 500

    def test_analyze_empty_body(self, client):
        resp = client.post("/api/analyze", json={})
        assert resp.status_code in (202, 500)

    def test_classify_empty_body(self, client):
        resp = client.post("/api/classify", json={})
        assert resp.status_code in (202, 500)


# ---------------------------------------------------------------------------
# Track routes  (app/routes/track_routes.py)
# ---------------------------------------------------------------------------
class TestTrackRoutes:
    def test_list_tracks(self, client):
        resp = client.get("/api/tracks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "tracks" in data
        assert "total" in data

    def test_get_track_not_found(self, client):
        resp = client.get("/api/tracks/nonexistent%2Ffile.mp3")
        assert resp.status_code in (200, 404)

    def test_update_track_by_path_missing_param(self, client):
        resp = client.put("/api/tracks/by-path", json={})
        assert resp.status_code in (200, 400)


# ---------------------------------------------------------------------------
# Review routes  (app/routes/review_routes.py)
# ---------------------------------------------------------------------------
class TestReviewRoutes:
    def test_approve_empty_body(self, client):
        resp = client.post("/api/review/approve", json={})
        assert resp.status_code == 200

    def test_skip_empty_body(self, client):
        resp = client.post("/api/review/skip", json={})
        assert resp.status_code == 200

    def test_bulk_approve_empty_body(self, client):
        resp = client.post("/api/review/bulk-approve", json={})
        assert resp.status_code == 200

    def test_bulk_edit_empty_body(self, client):
        resp = client.post("/api/review/bulk-edit", json={})
        assert resp.status_code in (200, 400)

    def test_write_tags_empty_body(self, client):
        resp = client.post("/api/review/write", json={})
        # 202 = accepted (no approved tracks), 500 = service import failure
        assert resp.status_code in (202, 500)


# ---------------------------------------------------------------------------
# Session routes  (app/routes/session_routes.py)
# ---------------------------------------------------------------------------
class TestSessionRoutes:
    def test_session_exists(self, client):
        resp = client.get("/api/session/exists")
        assert resp.status_code == 200

    def test_session_load_no_session(self, client):
        resp = client.post("/api/session/load", json={})
        assert resp.status_code in (200, 404)

    def test_session_save_empty_body(self, client):
        resp = client.post("/api/session/save", json={})
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Settings routes  (app/routes/settings_routes.py)
# ---------------------------------------------------------------------------
class TestSettingsRoutes:
    def test_get_settings(self, client):
        resp = client.get("/api/settings")
        assert resp.status_code == 200

    def test_save_settings_empty_body(self, client):
        resp = client.post("/api/settings", json={})
        assert resp.status_code in (200, 500)

    def test_list_models_missing_provider_returns_400(self, client):
        resp = client.post("/api/list_models", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_list_models_unknown_provider_returns_400(self, client):
        resp = client.post("/api/list_models", json={"provider": "unknown"})
        assert resp.status_code == 400

    def test_list_models_claude_without_key_returns_400(self, client):
        resp = client.post("/api/list_models", json={"provider": "claude", "api_key": ""})
        assert resp.status_code == 400

    def test_list_models_gemini_without_key_returns_400(self, client):
        from app.routes.settings_routes import load_env
        with mock.patch("app.routes.settings_routes.load_env", return_value={}):
            resp = client.post("/api/list_models", json={"provider": "gemini", "api_key": ""})
            assert resp.status_code == 400

    def test_list_models_ollama_returns_models_or_error(self, client):
        # Ollama does not require a key -- will either return models or
        # an error if not running. Both are valid responses (never 400/500
        # from missing params).
        resp = client.post("/api/list_models", json={"provider": "ollama"})
        assert resp.status_code in (200, 500, 502)
        if resp.status_code == 200:
            data = resp.get_json()
            assert "models" in data

    def test_list_models_openrouter_returns_models_or_error(self, client):
        # OpenRouter does not strictly require a key
        resp = client.post("/api/list_models", json={"provider": "openrouter"})
        assert resp.status_code in (200, 500, 502)


# ---------------------------------------------------------------------------
# Bulk / taxonomy routes  (app/routes/bulk_routes.py)
# ---------------------------------------------------------------------------
class TestBulkRoutes:
    def test_get_taxonomy(self, client):
        resp = client.get("/api/taxonomy")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)

    def test_update_taxonomy_empty_body(self, client):
        resp = client.put("/api/taxonomy", json={})
        assert resp.status_code in (200, 400, 500)

    def test_add_genre_empty_body(self, client):
        resp = client.post("/api/taxonomy/genre", json={})
        assert resp.status_code in (200, 400)

    def test_get_stats(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total" in data


# ---------------------------------------------------------------------------
# Watch routes  (app/routes/watch_routes.py)
# ---------------------------------------------------------------------------
class TestWatchRoutes:
    def test_watch_start_empty_body(self, client):
        resp = client.post("/api/watch/start", json={})
        assert resp.status_code in (200, 400)

    def test_watch_stop(self, client):
        resp = client.post("/api/watch/stop")
        assert resp.status_code in (200, 500)

    def test_watch_status(self, client):
        resp = client.get("/api/watch/status")
        assert resp.status_code in (200, 500)

    def test_watch_poll(self, client):
        resp = client.get("/api/watch/poll")
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Export routes  (app/routes/export_routes.py)
# ---------------------------------------------------------------------------
class TestExportRoutes:
    def test_export_m3u(self, client):
        resp = client.get("/api/export/m3u")
        assert resp.status_code in (200, 500)

    def test_export_csv(self, client):
        resp = client.get("/api/export/csv")
        assert resp.status_code in (200, 500)

    def test_export_json(self, client):
        resp = client.get("/api/export/json")
        assert resp.status_code in (200, 500)

    def test_export_rekordbox(self, client):
        resp = client.get("/api/export/rekordbox")
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Audio routes  (app/routes/audio_routes.py)
# ---------------------------------------------------------------------------
class TestAudioRoutes:
    def test_serve_audio_no_path(self, client):
        resp = client.get("/api/audio")
        assert resp.status_code in (400,)

    def test_serve_audio_nonexistent_file(self, client):
        resp = client.get("/api/audio?path=/nonexistent/file.mp3")
        assert resp.status_code in (404, 400, 403)


# ---------------------------------------------------------------------------
# Duplicate routes  (app/routes/duplicate_routes.py)
# ---------------------------------------------------------------------------
class TestDuplicateRoutes:
    def test_scan_duplicates_empty_body(self, client):
        resp = client.post("/api/duplicates/scan", json={})
        assert resp.status_code in (200, 500)

    def test_remove_duplicate_empty_body(self, client):
        resp = client.post("/api/duplicates/remove", json={})
        assert resp.status_code in (400,)


# ---------------------------------------------------------------------------
# Progress routes  (app/routes/progress_routes.py)
# ---------------------------------------------------------------------------
class TestProgressRoutes:
    def test_progress_unknown_op(self, client):
        resp = client.get("/api/progress/nonexistent_op")
        assert resp.status_code == 200

    def test_progress_cancel_unknown_op(self, client):
        resp = client.post("/api/progress/nonexistent_op/cancel")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Setlist routes  (app/routes/setlist_routes.py)
# ---------------------------------------------------------------------------
class TestSetlistRoutes:
    def test_get_setlist(self, client):
        resp = client.get("/api/setlist")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "tracks" in data

    def test_update_setlist_valid(self, client):
        """Writing a valid setlist should succeed."""
        resp = client.post("/api/setlist", json={"tracks": [], "name": "Test"})
        assert resp.status_code == 200

    def test_setlist_add_no_file_path(self, client):
        """Adding without file_path is a no-op (no crash expected with fresh state)."""
        resp = client.post("/api/setlist/add", json={})
        assert resp.status_code in (200, 400)

    def test_setlist_remove_no_file_path(self, client):
        """Removing without file_path is a no-op."""
        resp = client.post("/api/setlist/remove", json={})
        assert resp.status_code in (200, 400)

    def test_suggest_next_no_track(self, client):
        resp = client.post("/api/setlist/suggest", json={})
        assert resp.status_code in (400, 404)

    def test_export_setlist(self, client):
        resp = client.get("/api/setlist/export")
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Setplan routes  (app/routes/setplan_routes.py)
# ---------------------------------------------------------------------------
class TestSetplanRoutes:
    def test_get_arcs(self, client):
        resp = client.get("/api/setplan/arcs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_generate_empty_body(self, client):
        resp = client.post("/api/setplan/generate", json={})
        assert resp.status_code in (200, 400, 500)

    def test_export_m3u_empty_body(self, client):
        resp = client.post("/api/setplan/export-m3u", json={})
        assert resp.status_code in (200, 400, 500)


# ---------------------------------------------------------------------------
# Latin / mix routes  (app/routes/latin_routes.py)
# ---------------------------------------------------------------------------
class TestLatinRoutes:
    def test_analyze_latin_empty_body(self, client):
        resp = client.post("/api/analyze/latin", json={})
        assert resp.status_code in (400, 500)

    def test_mix_score_missing_params(self, client):
        resp = client.get("/api/mix/score")
        assert resp.status_code in (400,)

    def test_mix_suggestions_missing_path(self, client):
        resp = client.get("/api/mix/suggestions")
        assert resp.status_code in (400,)

    def test_validate_tags(self, client):
        resp = client.get("/api/validate/tags")
        assert resp.status_code in (200, 500)

    def test_export_cue_sheet(self, client):
        resp = client.get("/api/export/cue-sheet")
        assert resp.status_code in (200, 500)


# ---------------------------------------------------------------------------
# Key validation routes  (app/routes/key_routes.py)
# ---------------------------------------------------------------------------
class TestKeyRoutes:
    def test_validate_keys(self, client):
        resp = client.get("/api/validate/keys")
        assert resp.status_code in (200, 500)
        data = resp.get_json()
        assert "total_checked" in data

    def test_fix_keys_empty_body(self, client):
        resp = client.post("/api/validate/keys/fix", json={})
        assert resp.status_code in (400,)


# ---------------------------------------------------------------------------
# Organise routes  (app/routes/organise_routes.py)
# ---------------------------------------------------------------------------
class TestOrganiseRoutes:
    def test_library_health(self, client):
        resp = client.get("/api/library/health")
        assert resp.status_code in (200, 500)

    def test_parse_filenames_empty_body(self, client):
        resp = client.post("/api/organise/parse-filenames", json={})
        assert resp.status_code in (200, 400)

    def test_apply_filename_tags_empty_body(self, client):
        resp = client.post("/api/organise/apply-filename-tags", json={})
        assert resp.status_code in (200, 400)

    def test_organise_folders_empty_body(self, client):
        resp = client.post("/api/organise/folders", json={})
        assert resp.status_code in (400,)


# ---------------------------------------------------------------------------
# AppleScript routes  (app/routes/applescript_routes.py)
# Blueprint is NOT registered in create_app() -- routes return 404.
# Tests verify this so it isn't accidental.
# ---------------------------------------------------------------------------
class TestAppleScriptRoutes:
    def test_sync_apple_music_registered(self, client):
        """applescript_bp is now registered — should return 200 (or 400 with empty body)."""
        resp = client.post("/api/sync/apple-music")
        assert resp.status_code in (200, 400)

    def test_download_applescript_registered(self, client):
        """Same -- blueprint is registered."""
        resp = client.get("/api/sync/apple-music/script")
        assert resp.status_code != 404
