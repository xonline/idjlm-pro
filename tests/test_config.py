"""App creation and route registration tests."""
import pytest

from app import create_app


def test_create_app_does_not_raise():
    """create_app() returns a Flask instance without raising."""
    app = create_app()
    assert app is not None
    assert app.config is not None


def test_expected_blueprint_routes_registered():
    """All expected API prefixes are present in the URL map."""
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    # Every registered blueprint should contribute at least one route
    expected_routes = [
        "/api/import",
        "/api/tracks",
        "/api/review/approve",
        "/api/taxonomy",
        "/api/settings",
        "/api/audio",
        "/api/session/exists",
        "/api/watch/status",
        "/api/export/m3u",
        "/api/duplicates/scan",
        "/api/progress/",           # prefix match — has op_id param
        "/api/setlist",
        "/api/setplan/arcs",
        "/api/analyze/latin",
        "/api/library/health",
        "/api/validate/keys",
    ]

    for route in expected_routes:
        assert any(r.startswith(route) for r in rules), (
            f"Expected route starting with '{route}' not found. "
            f"Registered rules: {sorted(rules)}"
        )
