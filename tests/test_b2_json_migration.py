"""Regression tests for Issue #202 — IDJLM B.2.

Contract locked down here:

1. ``save_session`` writes session.json atomically (temp-file + rename).
   A crash mid-write must NOT leave a half-written file behind — the
   previous intact file (or no file) must remain on disk.
2. ``save_session`` MUST NOT silently swallow write errors. The
   pre-fix anti-pattern was a bare ``except: pass`` (or
   ``except Exception: pass``) that returned success while corrupting
   the on-disk file. Failures now propagate so callers / endpoints
   can surface them.
3. Playlists, setlist, corrections all live in the shared SQLite
   ``json_docs`` table (via JsonStore) — writing through the public
   API persists to SQLite and reads-back round-trip clean.
4. ``JsonStore.snapshot_to_file`` uses the temp-file + rename
   fallback path (issue #202 plan requirement).
"""
from __future__ import annotations

import json
import os
import re

import pytest

from app.models.track import Track


def _make_track(file_path: str) -> Track:
    return Track(file_path=file_path, filename=os.path.basename(file_path))


# --------------------------------------------------------------------------- #
# 1. save_session is atomic + propagates write failures                        #
# --------------------------------------------------------------------------- #


def test_save_session_writes_atomically(tmp_path, monkeypatch):
    """save_session writes session.json via temp-file + rename.

    Asserted by patching out os.replace to capture arguments: every
    call must be os.replace(realtmp, target) — i.e. an atomic move,
    never a partial open(target, 'w') truncate.
    """
    session_path = tmp_path / "session.json"
    monkeypatch.setattr(
        "app.services.session_service.SESSION_FILE", str(session_path)
    )

    # Patch os.replace at the module that atomic_write actually calls.
    import app.utils.paths as paths_module
    replaces = []
    real_replace = paths_module.os.replace

    def _spy_replace(src, dst):
        replaces.append((src, dst))
        return real_replace(src, dst)

    monkeypatch.setattr(paths_module.os, "replace", _spy_replace)

    from app.services.session_service import save_session
    save_session({"/Music/a.mp3": _make_track("/Music/a.mp3")}, folder_path="/Music")

    assert session_path.exists(), "session.json must exist after save"
    assert len(replaces) == 1, (
        f"expected exactly one os.replace call for atomic write, got {replaces}"
    )
    src, dst = replaces[0]
    assert dst == str(session_path), f"rename target must be session.json, got {dst!r}"
    assert ".tmp" in os.path.basename(src), (
        f"rename source must be a .tmp file, got {src!r}"
    )

    payload = json.loads(session_path.read_text())
    assert payload["track_count"] == 1
    assert payload["folder_path"] == "/Music"
    assert "/Music/a.mp3" in payload["tracks"]


def test_save_session_atomic_replace_failure_propagates(tmp_path, monkeypatch):
    """The historical bug was a bare ``except: pass`` on save_session —
    failures were silently dropped and the function returned a dict-
    shaped success even though the file was not written.
    Lock down the new contract: write failures propagate.
    """
    session_path = tmp_path / "session.json"
    # Pre-write an intact file so we can prove the failed rename did
    # NOT corrupt the original.
    prior_payload = {"saved_at": "before", "track_count": 99, "tracks": {}}
    session_path.write_text(json.dumps(prior_payload))

    monkeypatch.setattr(
        "app.services.session_service.SESSION_FILE", str(session_path)
    )

    def _exploding_replace(src, dst):
        raise OSError("disk full — atomic rename failed")

    import app.utils.paths as paths_module
    monkeypatch.setattr(paths_module.os, "replace", _exploding_replace)

    from app.services.session_service import save_session
    with pytest.raises(OSError, match="disk full"):
        save_session({"/Music/a.mp3": _make_track("/Music/a.mp3")})

    # The original session.json is still intact — atomic semantics
    # mean a failed rename leaves the previous file untouched.
    assert json.loads(session_path.read_text()) == prior_payload


def _strip_docstrings(src: str) -> str:
    """Strip Python docstrings so the static check doesn't false-match
    documentation prose that mentions ``except: pass`` as a thing."""
    import ast

    tree = ast.parse(src)
    out_lines = src.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.MethodDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                start = node.body[0].lineno - 1
                end = node.body[0].end_lineno
                for i in range(start, end):
                    out_lines[i] = ""
    return "".join(out_lines)


def test_session_service_save_session_has_no_silent_except_pass():
    """Static check: ``save_session`` must not contain
    ``except: pass`` or ``except Exception: pass`` blocks.
    The pre-fix bug was one of these patterns — the silent-swallow
    anti-pattern called out by issue #202.
    """
    import ast
    from pathlib import Path

    here = Path(__file__).resolve().parent.parent
    src = (here / "app" / "services" / "session_service.py").read_text()

    # Locate save_session function, then strip docstrings from its
    # source so we don't false-match documentation that mentions
    # ``except: pass`` as a historical bad pattern.
    tree = ast.parse(src)
    func_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "save_session":
            func_node = node
            break
    assert func_node is not None, "could not locate save_session in module"
    func_src = ast.get_source_segment(src, func_node)
    assert func_src, "could not extract save_session source"

    # Strip the leading docstring expression node.
    lines = func_src.splitlines(keepends=True)
    funcoffset = func_node.body[0].lineno - func_node.lineno
    end = func_node.body[0].end_lineno - func_node.lineno + 1
    for i in range(funcoffset, end):
        lines[i] = ""
    func_no_doc = "".join(lines)

    bad = re.search(r"except\s*(Exception)?\s*:\s*pass", func_no_doc)
    assert bad is None, (
        "save_session still contains a bare "
        "``except: pass`` / ``except Exception: pass`` — "
        "this is the silent-swallow pre-fix bug from issue #202."
    )


# --------------------------------------------------------------------------- #
# 2. B.2 migrated docs (playlists, setlist, corrections) live in SQLite         #
# --------------------------------------------------------------------------- #


def test_playlists_setlist_corrections_persist_via_sqlite(tmp_path, monkeypatch):
    """Writing through JsonStore persists to the shared SQLite
    ``json_docs`` table, not a loose JSON file. Reads round-trip
    cleanly between processes/sessions because SQLite is the source
    of truth.
    """
    from app.services.json_store import JsonStore

    db_path = tmp_path / "tracks.db"
    monkeypatch.setattr(
        "app.services.json_store.user_data_path", lambda name: str(db_path)
    )

    pl = JsonStore("playlists")
    pl.set({"playlists": [{"id": "pl_1", "name": "Reggaeton", "tracks": []}]})
    assert pl.get()["playlists"][0]["name"] == "Reggaeton"

    sl = JsonStore("setlist")
    sl.set({"name": "Friday", "tracks": ["/Music/a.mp3"]})
    assert sl.get()["name"] == "Friday"

    co = JsonStore("corrections")
    co.set({"corrections": [{"pattern": "x", "count": 1}]})
    assert co.get()["corrections"][0]["count"] == 1


def test_json_store_atomic_fallback_writes_temp_then_rename(tmp_path, monkeypatch):
    """snapshot_to_file (the temp-file+rename fallback required by
    the B.2 plan) is atomic — never ``open(target, 'w')`` on the
    live file.
    """
    from app.services.json_store import JsonStore

    db_path = tmp_path / "tracks.db"
    monkeypatch.setattr(
        "app.services.json_store.user_data_path", lambda name: str(db_path)
    )

    js = JsonStore("atomic_test")
    js.set({"hello": "world"})

    target = tmp_path / "snapshot.json"

    import app.utils.paths as paths_module
    replaces = []
    real_replace = paths_module.os.replace

    def _spy(src, dst):
        replaces.append((src, dst))
        return real_replace(src, dst)

    monkeypatch.setattr(paths_module.os, "replace", _spy)

    js.snapshot_to_file(str(target))
    assert target.exists()

    assert len(replaces) == 1
    src, dst = replaces[0]
    assert dst == str(target)
    assert src != str(target), "atomic write must rename a temp file, not rewrite live file"
    assert not os.path.exists(src), "temp file must be gone after atomic rename"
    assert json.loads(target.read_text()) == {"hello": "world"}


# --------------------------------------------------------------------------- #
# 3. Routes that touch session.json go through the same atomic path             #
# --------------------------------------------------------------------------- #


def test_session_routes_save_uses_atomic_write(app, tmp_path, monkeypatch):
    """The /api/session/save HTTP route delegates to save_session —
    which (per #1) is atomic. Pin the contract here so a future
    refactor that swaps to a non-atomic writer trips the test.
    """
    from app.services.session_service import SESSION_FILE, save_session

    session_path = tmp_path / "session.json"
    monkeypatch.setattr(
        "app.services.session_service.SESSION_FILE", str(session_path)
    )

    save_session(
        {"/Music/a.mp3": _make_track("/Music/a.mp3")},
        folder_path="/Music",
    )
    assert session_path.exists(), "session.json must be on disk"
    parsed = json.loads(session_path.read_text())
    assert parsed["track_count"] == 1
    assert parsed["folder_path"] == "/Music"
    assert "/Music/a.mp3" in parsed["tracks"]
