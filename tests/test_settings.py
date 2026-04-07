"""Settings-specific tests for the cascading provider-model selector."""
import json
import os
import tempfile
from unittest import mock

import pytest


class TestSaveSettingsNewFields:
    """Test that save_settings correctly handles provider and model_id."""

    def test_save_ai_model_openrouter(self, client, tmp_path):
        """Saving ai_model=openrouter should write AI_MODEL to .env."""
        env_path = tmp_path / ".env"
        with mock.patch(
            "app.routes.settings_routes.get_env_path", return_value=str(env_path)
        ):
            resp = client.post("/api/settings", json={
                "ai_model": "openrouter",
                "auto_approve_threshold": 80,
            })
            assert resp.status_code == 200
            content = env_path.read_text()
            assert "AI_MODEL=openrouter" in content

    def test_save_model_id_openrouter(self, client, tmp_path):
        """model_id with ai_model=openrouter should write OPENROUTER_MODEL."""
        env_path = tmp_path / ".env"
        with mock.patch(
            "app.routes.settings_routes.get_env_path", return_value=str(env_path)
        ):
            resp = client.post("/api/settings", json={
                "ai_model": "openrouter",
                "model_id": "google/gemini-2.5-flash:free",
                "auto_approve_threshold": 80,
            })
            assert resp.status_code == 200
            content = env_path.read_text()
            assert "OPENROUTER_MODEL=google/gemini-2.5-flash:free" in content

    def test_save_model_id_ollama(self, client, tmp_path):
        """model_id with ai_model=ollama should write OLLAMA_MODEL."""
        env_path = tmp_path / ".env"
        with mock.patch(
            "app.routes.settings_routes.get_env_path", return_value=str(env_path)
        ):
            resp = client.post("/api/settings", json={
                "ai_model": "ollama",
                "model_id": "qwen3:1.7b",
                "auto_approve_threshold": 80,
            })
            assert resp.status_code == 200
            content = env_path.read_text()
            assert "OLLAMA_MODEL=qwen3:1.7b" in content

    def test_save_model_id_claude(self, client, tmp_path):
        """model_id with ai_model=claude should write ANTHROPIC_MODEL."""
        env_path = tmp_path / ".env"
        with mock.patch(
            "app.routes.settings_routes.get_env_path", return_value=str(env_path)
        ):
            resp = client.post("/api/settings", json={
                "ai_model": "claude",
                "model_id": "claude-sonnet-4-6-20260219",
                "auto_approve_threshold": 80,
            })
            assert resp.status_code == 200
            content = env_path.read_text()
            assert "ANTHROPIC_MODEL=claude-sonnet-4-6-20260219" in content

    def test_save_model_id_gemini(self, client, tmp_path):
        """model_id with ai_model=gemini should write GEMINI_MODEL."""
        env_path = tmp_path / ".env"
        with mock.patch(
            "app.routes.settings_routes.get_env_path", return_value=str(env_path)
        ):
            resp = client.post("/api/settings", json={
                "ai_model": "gemini",
                "model_id": "gemini-2.5-flash",
                "auto_approve_threshold": 80,
            })
            assert resp.status_code == 200
            content = env_path.read_text()
            assert "GEMINI_MODEL=gemini-2.5-flash" in content

    def test_get_settings_returns_ai_model(self, client):
        """GET /api/settings should return ai_model field."""
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ai_model" in data
        assert data["ai_model"] in ("claude", "gemini", "ollama", "openrouter")
