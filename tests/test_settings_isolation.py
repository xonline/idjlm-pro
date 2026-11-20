"""Regression coverage for explicit test/runtime data-directory isolation."""
from unittest.mock import patch

import pytest

from app.routes import settings_routes
from app.utils import paths


def test_explicit_data_dir_does_not_probe_or_copy_legacy_env(monkeypatch):
    """An isolated runtime must not migrate settings from the repository."""
    isolated_dir = "/tmp/idjlm-isolated-settings"
    new_path = f"{isolated_dir}/.env"
    monkeypatch.setenv("IDJLM_USER_DATA_DIR", isolated_dir)

    with (
        patch("app.utils.paths.ensure_app_user_dir", return_value=isolated_dir),
        patch("app.routes.settings_routes.os.path.exists", return_value=False) as exists,
        patch("shutil.copy2") as copy2,
    ):
        assert settings_routes.get_env_path() == new_path

    exists.assert_not_called()
    copy2.assert_not_called()


def test_default_data_dir_still_migrates_legacy_env(monkeypatch):
    """Existing installs retain the one-time settings migration."""
    default_dir = "/tmp/idjlm-default-settings"
    new_path = f"{default_dir}/.env"
    legacy_path = "/tmp/idjlm-legacy-settings/.env"
    monkeypatch.delenv("IDJLM_USER_DATA_DIR", raising=False)

    def exists(path):
        return path == legacy_path

    with (
        patch("app.utils.paths.ensure_app_user_dir", return_value=default_dir),
        patch("app.routes.settings_routes.os.path.exists", side_effect=exists),
        patch("app.routes.settings_routes.os.path.normpath", return_value=legacy_path),
        patch("shutil.copy2") as copy2,
    ):
        assert settings_routes.get_env_path() == new_path

    copy2.assert_called_once_with(legacy_path, new_path)


@pytest.mark.parametrize("darwin", [False, True])
def test_explicit_data_dir_keeps_logs_isolated_on_every_platform(monkeypatch, darwin):
    isolated_dir = "/tmp/idjlm-isolated-logs"
    monkeypatch.setenv("IDJLM_USER_DATA_DIR", isolated_dir)
    monkeypatch.setattr(paths, "_IS_DARWIN", darwin)

    assert paths.app_user_log_dir() == f"{isolated_dir}/logs"
