"""Pytest fixtures for IDJLM Pro Flask application."""
import json
import os
import shutil

import pytest

from app import create_app


@pytest.fixture(scope="session")
def _test_taxonomy():
    """
    Ensure a taxonomy.json exists where the app expects it on this platform.
    On Linux the app checks ~/.idjlm-pro/taxonomy.json, then falls back to
    the bundle copy at <project>/taxonomy.json.
    """
    user_taxonomy = os.path.expanduser("~/.idjlm-pro/taxonomy.json")
    bundle_taxonomy = os.path.join(
        os.path.dirname(__file__), "..", "..", "taxonomy.json"
    )

    # If bundle taxonomy exists, ensure user copy exists too
    if os.path.exists(bundle_taxonomy):
        os.makedirs(os.path.dirname(user_taxonomy), exist_ok=True)
        if not os.path.exists(user_taxonomy):
            shutil.copy2(bundle_taxonomy, user_taxonomy)
        yield user_taxonomy
    else:
        # Create a minimal taxonomy for tests
        os.makedirs(os.path.dirname(user_taxonomy), exist_ok=True)
        minimal = {"genres": {"TestGenre": {"description": "test", "subgenres": {}}}}
        with open(user_taxonomy, "w") as f:
            json.dump(minimal, f)
        yield user_taxonomy

    # Cleanup: remove test-created file
    if os.path.exists(user_taxonomy):
        os.remove(user_taxonomy)


@pytest.fixture(scope="session")
def app(_test_taxonomy):
    """Create the Flask app once per session."""
    created = create_app()
    created.config["TESTING"] = True
    yield created


@pytest.fixture(scope="session")
def client(app):
    """Return a test client that persists across the session."""
    yield app.test_client()


@pytest.fixture(autouse=True)
def _cleanup_setlist_between_tests(request):
    """Reset setlist.json before and after each test so state doesn't leak."""
    setlist_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "setlist.json"
    )
    default_content = json.dumps({"tracks": [], "name": "My Set"})

    # Read valid original content (only if it has the expected structure)
    original = None
    if os.path.exists(setlist_path):
        with open(setlist_path) as f:
            raw = f.read()
        try:
            parsed = json.loads(raw)
            if "tracks" in parsed and "name" in parsed:
                original = raw
        except json.JSONDecodeError:
            pass

    # Reset to defaults before test
    with open(setlist_path, "w") as f:
        f.write(default_content)

    yield

    # Restore valid original, or clean up to defaults
    if original is not None:
        with open(setlist_path, "w") as f:
            f.write(original)
    else:
        with open(setlist_path, "w") as f:
            f.write(default_content)
