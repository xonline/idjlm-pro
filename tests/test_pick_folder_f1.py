"""Regression tests for F.1: cross-platform folder picker.

Closes xonline/jobs#211. The macOS-only ``osascript`` picker on the core
import flow broke the import URL on Windows/Linux. The route now uses
``tkinter`` (with the Tauri ``pick_folder`` command as the primary desktop
path on the frontend). These tests pin the contract so a future regression
that reintroduces ``osascript`` or returns a 500 on a headless host is caught
before it ships.
"""
import ast
import inspect
import sys
import textwrap

from app.routes import import_routes


# ---------------------------------------------------------------------------
# AST code-shape helper — scans executable code, ignores docstrings/comments
# ---------------------------------------------------------------------------

def _route_names(route_callable) -> set:
    """Return the set of identifier names referenced in a route's body.

    Stripping docstrings/comments means a docstring that mentions
    ``osascript`` (for explanatory purposes) does not trip the regression
    assert — only an actual ``osascript`` Name/Call in the code does.
    """
    src = textwrap.dedent(inspect.getsource(route_callable))
    tree = ast.parse(src)
    # Drop Expr nodes whose value is a bare string literal (docstrings).
    clean = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            continue
        clean.append(node)
    names = set()
    for node in clean:
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


# ---------------------------------------------------------------------------
# tkinter stub helper
# ---------------------------------------------------------------------------

def _stub_tkinter(monkeypatch, *, askdirectory_returns="", tk_raises=None):
    """Replace ``tkinter`` + ``tkinter.filedialog`` in sys.modules per-test.

    The route does ``import tkinter`` / ``from tkinter import filedialog``
    lazily inside the request, so this stub does not touch the real toolkit
    and does not require a display.
    """

    class _FakeRoot:
        def __init__(self, *a, **kw):
            if tk_raises is not None:
                raise tk_raises
        def withdraw(self): ...
        def lift(self): ...
        def attributes(self, *a, **kw): ...
        def destroy(self): ...

    class _FakeFiledialog:
        @staticmethod
        def askdirectory(title=""):
            return askdirectory_returns

    import types
    fake_tk = types.ModuleType("tkinter")
    fake_tk.Tk = _FakeRoot
    fake_tk.filedialog = _FakeFiledialog  # from tkinter import filedialog

    fake_fd = types.ModuleType("tkinter.filedialog")
    fake_fd.askdirectory = _FakeFiledialog.askdirectory

    monkeypatch.setitem(sys.modules, "tkinter", fake_tk)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", fake_fd)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPickFolderCrossPlatform:
    """Pins the F.1 contract: tkinter picker, no osascript, never 500."""

    def test_route_uses_tkinter_not_osascript(self):
        """The pick_folder code references tkinter and never references
        osascript. AST scan ignores docstrings so an explanatory mention of
        osascript in the docstring is fine; an actual call is not."""
        names = _route_names(import_routes.pick_folder)
        assert "tk" in names, "F.1 regression: tkinter picker missing"
        assert "askdirectory" in names, (
            "F.1 regression: tkinter.filedialog.askdirectory not called"
        )
        assert "osascript" not in names, (
            "F.1 regression: osascript reintroduced into /api/pick-folder — "
            "this breaks the import flow on Windows/Linux"
        )

    def test_pick_folder_returns_path_on_selection(self, client, monkeypatch):
        """A successful tkinter selection returns {path: ...} with 200."""
        _stub_tkinter(monkeypatch, askdirectory_returns="/tmp/test-music")

        resp = client.get("/api/pick-folder")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("path") == "/tmp/test-music"
        assert not body.get("cancelled")
        assert not body.get("unavailable")

    def test_pick_folder_returns_cancelled_on_empty(self, client, monkeypatch):
        """User dismissing the dialog returns {cancelled: true}, not 500."""
        _stub_tkinter(monkeypatch, askdirectory_returns="")

        resp = client.get("/api/pick-folder")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("cancelled") is True
        assert "path" not in body

    def test_pick_folder_no_display_returns_unavailable(self, client, monkeypatch):
        """Headless host (no $DISPLAY) — tk.Tk() raises — must NOT 500."""
        _stub_tkinter(monkeypatch, tk_raises=RuntimeError("no display"))

        resp = client.get("/api/pick-folder")
        assert resp.status_code == 200, (
            "F.1 regression: /api/pick-folder returned 500 on a headless "
            "host — this is the original Windows/Linux-broken behaviour"
        )
        body = resp.get_json()
        assert body.get("unavailable") is True
        assert "message" in body

    def test_pick_folder_tkinter_missing_returns_unavailable(
        self, client, monkeypatch
    ):
        """tkinter not installed — must return unavailable, not 500."""
        # Force ``import tkinter`` inside the route to raise ImportError.
        real_tk = sys.modules.pop("tkinter", None)
        real_fd = sys.modules.pop("tkinter.filedialog", None)

        # Block re-import by inserting a failing finder.
        class _BlockTkinter:
            def find_module(self, name, path=None):
                if name == "tkinter" or name == "tkinter.filedialog":
                    return self
            def load_module(self, name):
                raise ImportError(f"blocked: {name}")

        finder = _BlockTkinter()
        sys.meta_path.insert(0, finder)
        try:
            resp = client.get("/api/pick-folder")
            assert resp.status_code == 200, (
                "F.1 regression: 500 returned when tkinter is unavailable"
            )
            body = resp.get_json()
            assert body.get("unavailable") is True
        finally:
            sys.meta_path.remove(finder)
            if real_tk is not None:
                sys.modules["tkinter"] = real_tk
            if real_fd is not None:
                sys.modules["tkinter.filedialog"] = real_fd
