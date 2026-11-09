"""Pytest fixtures for IDJLM Pro Flask application."""
import json
import os
import shutil
import tempfile

import pytest

# Tests must never open or modify the operator's IDJLM library.  Set this
# before importing app modules, whose path constants resolve at import time.
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="idjlm-tests-")
os.environ["IDJLM_USER_DATA_DIR"] = _TEST_DATA_DIR

from app import create_app


@pytest.fixture(scope="session")
def _test_taxonomy():
    """
    Ensure a taxonomy.json exists where the app expects it on this platform.
    On Linux the app checks ~/.idjlm-pro/taxonomy.json, then falls back to
    the bundle copy at <project>/taxonomy.json.
    """
    user_taxonomy = os.path.join(_TEST_DATA_DIR, "taxonomy.json")
    bundle_taxonomy = os.path.join(
        os.path.dirname(__file__), "..", "taxonomy.json"
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

    # The complete isolated directory is left for the OS temporary-file
    # cleaner. Never delete or alter a real user taxonomy from tests.


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
    # Canonical setlist.json path: same file the app reads/writes.
    # Derive from the app's SETLIST_PATH constant so test and app cannot drift.
    from app.routes.setlist_routes import SETLIST_PATH as setlist_path
    default_content = json.dumps({"tracks": [], "name": "My Set"})

    # Reset to defaults before test
    with open(setlist_path, "w") as f:
        f.write(default_content)

    yield

    # This is an isolated temporary path, so leave deterministic defaults.
    with open(setlist_path, "w") as f:
        f.write(default_content)
