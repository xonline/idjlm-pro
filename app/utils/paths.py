"""Cross-platform user data paths.

Single source of truth for filesystem locations that used to be duplicated
inline across 7+ files. Reads/writes under the user's home on every OS:

- macOS:    ~/Library/Application Support/IDJLM Pro  (data)
            ~/Library/Logs/IDJLM Pro                  (logs)
- Linux:    ~/.idjlm-pro                              (data)
            ~/.idjlm-pro/logs                         (logs)
- Windows:  %USERPROFILE%/.idjlm-pro                  (data)
            %USERPROFILE%/.idjlm-pro/logs             (logs)
"""
import json
import os
import platform
import tempfile
from pathlib import Path


_IS_DARWIN = platform.system() == "Darwin"
_IS_WINDOWS = platform.system() == "Windows"


def is_darwin() -> bool:
    return _IS_DARWIN


def is_windows() -> bool:
    return _IS_WINDOWS


def app_user_dir() -> str:
    """User-writable data directory.

    Created lazily by callers; this function only resolves the path.
    """
    if _IS_DARWIN:
        return os.path.expanduser("~/Library/Application Support/IDJLM Pro")
    home = os.path.expanduser("~/.idjlm-pro")
    if _IS_WINDOWS:
        home = home.replace("\\", "/")
    return home


def app_user_log_dir() -> str:
    """Log directory; same parent as app_user_dir on Darwin namespaced under Logs/."""
    if _IS_DARWIN:
        return os.path.expanduser("~/Library/Logs/IDJLM Pro")
    return os.path.join(app_user_dir(), "logs")


def user_data_path(filename: str) -> str:
    """Path to a file in the user data dir."""
    return os.path.join(app_user_dir(), filename)


def settings_dir() -> str:
    """Alias for app_user_dir() for sites that call it 'settings dir'."""
    return app_user_dir()


def ensure_dir(path: str) -> str:
    """Create the dir if missing; return the path."""
    os.makedirs(path, exist_ok=True)
    return path


def ensure_app_user_dir() -> str:
    """app_user_dir() + ensure created. Convenience for save paths."""
    return ensure_dir(app_user_dir())


def ensure_app_user_log_dir() -> str:
    return ensure_dir(app_user_log_dir())


def rekordbox_master_db_candidates() -> list[str]:
    """Pioneer installs rekordbox at varying paths. Return the candidates
    that exist on disk on macOS; empty on other platforms (rekordbox is not
    available on Linux/Windows from Pioneer).
    """
    if not _IS_DARWIN:
        return []
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Library/Pioneer/rekordbox/master.db"),
        os.path.join(home, "Library/Pioneer/rekordbox3/master.db"),
    ]
    return [p for p in candidates if os.path.exists(p)]


def safe_path_for(path: str) -> str:
    """Normalize a path for the current platform (no-op on POSIX; replaces
    backslashes on Windows where relevant)."""
    if _IS_WINDOWS:
        return str(Path(path))
    return path


def atomic_write(path: str, data, **dump_kwargs) -> None:
    """Write JSON to *path* atomically via temp-file + rename.

    Writes to a temporary file in the same directory (same filesystem
    mount = guaranteed atomic ``os.replace``) then renames over the
    target.  If the process crashes mid-write, the target file remains
    intact (either the old version or not yet replaced).

    *dump_kwargs* are forwarded to ``json.dump`` (indent, sort_keys, …).
    """
    dirname = os.path.dirname(path) or "."
    os.makedirs(dirname, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        suffix=".tmp",
        prefix=os.path.basename(path) + ".",
        dir=dirname,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, **dump_kwargs)
    except BaseException:
        _try_unlink(tmp)
        raise
    os.replace(tmp, path)


def _try_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass
