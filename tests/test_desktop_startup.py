"""Focused contracts for packaged desktop startup readiness."""

import json
import os
import errno
import socket

import pytest

import run_app


def test_sidecar_ready_file_is_atomic_and_contains_bound_port(tmp_path):
    ready = tmp_path / "sidecar-ready.json"

    run_app._publish_sidecar_ready(ready, "launch-token", 51423, "fallback")

    assert json.loads(ready.read_text()) == {
        "version": 1,
        "token": "launch-token",
        "port": 51423,
        "mode": "fallback",
    }
    assert not list(tmp_path.glob("*.tmp"))


def test_desktop_ui_witness_requires_launch_token_and_is_fixed(tmp_path, monkeypatch):
    from app import create_app

    state = tmp_path / "state"
    state.mkdir()
    ready = tmp_path / "ui-ready.json"
    monkeypatch.setenv("IDJLM_USER_DATA_DIR", str(state))
    monkeypatch.setenv("IDJLM_DESKTOP_SAME_ORIGIN", "1")
    monkeypatch.setenv("IDJLM_UI_READY_FILE", str(ready))
    monkeypatch.setenv("IDJLM_UI_READY_TOKEN", "launch-token")
    app = create_app()
    client = app.test_client()

    assert client.post("/__desktop/ui-ready").status_code == 403
    response = client.post(
        "/__desktop/ui-ready", headers={"X-IDJLM-UI-Ready": "launch-token"}
    )

    assert response.status_code == 204
    assert json.loads(ready.read_text()) == {
        "version": 1,
        "page": "library",
        "title": "Library",
        "shellVisible": True,
        "libraryVisible": True,
        "browserControlsVisible": True,
        "launchMode": "",
        "nativePickerAvailable": False,
    }


def test_desktop_same_origin_mode_does_not_grant_5050_cors(tmp_path, monkeypatch):
    from app import create_app

    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("IDJLM_USER_DATA_DIR", str(state))
    monkeypatch.setenv("IDJLM_DESKTOP_SAME_ORIGIN", "1")
    app = create_app()

    response = app.test_client().get("/api/version", headers={"Origin": "http://localhost:5050"})

    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") is None
    assert response.get_json()["product"] == "idjlm-pro"


@pytest.mark.skipif(os.name == "nt", reason="POSIX flock contract")
def test_desktop_lock_rejects_a_second_sidecar_before_app_startup(tmp_path, monkeypatch):
    import fcntl

    state = tmp_path / "state"
    state.mkdir()
    held_lock = (state / ".desktop-instance.lock").open("a+")
    fcntl.flock(held_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    monkeypatch.setenv("IDJLM_USER_DATA_DIR", str(state))
    monkeypatch.setenv("IDJLM_DESKTOP_SAME_ORIGIN", "1")
    previous = run_app._desktop_instance_lock
    run_app._desktop_instance_lock = None
    try:
        with pytest.raises(RuntimeError, match="Another IDJLM Pro desktop window"):
            run_app._acquire_desktop_instance_lock()
    finally:
        run_app._desktop_instance_lock = previous
        fcntl.flock(held_lock.fileno(), fcntl.LOCK_UN)
        held_lock.close()


def test_late_5050_collision_retries_on_ephemeral_loopback(monkeypatch):
    calls = []

    def open_listener(port):
        calls.append(port)
        if port == 5050:
            raise OSError(errno.EADDRINUSE, "Address already in use")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        return listener

    class FakeServer:
        server_port = 0

    def make_server(host, port, app, threaded, fd):
        assert (host, threaded) == ("127.0.0.1", True)
        assert port != 5050
        assert fd >= 0
        server = FakeServer()
        server.server_port = port
        return server

    monkeypatch.setattr(run_app, "_open_loopback_listener", open_listener)
    monkeypatch.setattr(run_app, "_is_idjlm_listener", lambda port: False)

    server = run_app._make_desktop_server(object(), 5050, make_server)

    assert calls == [5050, 0]
    assert server.server_port != 5050


def test_late_5050_idjlm_collision_does_not_start_second_sidecar(monkeypatch):
    def occupied(port):
        raise OSError(errno.EADDRINUSE, "Address already in use")

    monkeypatch.setattr(run_app, "_open_loopback_listener", occupied)
    monkeypatch.setattr(run_app, "_is_idjlm_listener", lambda port: True)

    with pytest.raises(RuntimeError, match="Another IDJLM Pro desktop window"):
        run_app._make_desktop_server(object(), 5050, lambda **_: None)
