"""Regression test for issue #200: release CI double-fire.

Historically `.github/workflows/release-auto.yml` (triggered on `v*`
tags) and `.github/workflows/release.yml` (triggered on
`v[0-9]*.[0-9]*.[0-9]*` tags) BOTH called ``softprops/action-gh-release``,
causing two GitHub Release objects per tag push.

The fix (commit 25630ba) deleted ``release-auto.yml``.  These tests
prevent re-introduction of a second release-creating workflow:

1. ``release-auto.yml`` must not exist.
2. Scanning every workflow file, exactly one workflow uses the
   ``gh-release`` / ``create-release`` action — ``release.yml``.
3. ``release.yml``'s tag glob matches stable semver (``vX.Y.Z``)
   but NOT non-semver ``v*`` tags, so an accidental ``v*`` re-add
   won't collide with it.
4. ``tauri-build.yml`` (which legitimately triggers on ``v*``) must
   NOT contain a release-creating action — only ``release.yml`` may.

This test parses the very small subset of YAML we emit with a tiny
manual parser (no PyYAML dependency) so the suite stays hermetic.
"""
import glob
import os
import re

import pytest


WORKFLOWS_DIR = os.path.join(
    os.path.dirname(__file__), "..", ".github", "workflows"
)

# Actions that create a GitHub Release object.
RELEASE_ACTIONS = (
    "softprops/action-gh-release",
    "actions/create-release",
)


def _workflow_files():
    """Return list of (basename, full_path) for every .yml/.yaml workflow."""
    paths = sorted(
        glob.glob(os.path.join(WORKFLOWS_DIR, "*.yml"))
        + glob.glob(os.path.join(WORKFLOWS_DIR, "*.yaml"))
    )
    return [(os.path.basename(p), p) for p in paths]


def _read_path(path):
    with open(path) as f:
        return f.read()


def _read(name):
    return _read_path(os.path.join(WORKFLOWS_DIR, name))


def _parse_tag_globs(text):
    """Extract the list of 'tags:' patterns from an ``on.push.tags:`` block.

    Supports both list form (``- 'v[0-9]*...'``) and inline string form
    (``tags: 'v*'``). Returns the raw strings in source order, or []
    if the workflow has no ``tags:`` key (e.g. branch-only triggers).
    """
    tags_match = re.search(
        r"^\s*tags:\s*([^\n#]*(?:\n\s+-\s*[^\n#]+)*)", text, re.MULTILINE
    )
    if not tags_match:
        return []
    block = tags_match.group(1)
    list_items = re.findall(r"-\s*['\"]?([^\s'\"#]+)['\"]?", block)
    if list_items:
        return list_items
    scalar = re.search(r"['\"]?([^\s'\"#]+)['\"]?", block)
    return [scalar.group(1)] if scalar else []


def _glob_to_regex(glob):
    out = []
    i = 0
    while i < len(glob):
        c = glob[i]
        if c == "*":
            if i + 1 < len(glob) and glob[i + 1] == "*":
                out.append(".*")
                i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif c == "[":
            j = glob.find("]", i)
            if j == -1:
                out.append(re.escape(c))
                i += 1
            else:
                out.append(glob[i:j + 1])
                i = j + 1
        elif c in r".^$+?{}()|\\":
            out.append("\\" + c)
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


def _matches_any(tag, globs):
    for g in globs:
        if re.fullmatch(_glob_to_regex(g), tag):
            return True
    return False


def _uses_release_action(text):
    """True if the workflow text references a release-creating action."""
    return any(act in text for act in RELEASE_ACTIONS)


# Stable semver vX.Y.Z (no prerelease suffix)
STABLE_TAG = "v4.2.0"
STABLE_TAG_BARE = "v1.0.0"
# Prerelease vX.Y.Z-rcN
PRERELEASE_TAG = "v4.2.0-rc1"
# Non-semver tag starting with v
NON_SEMVER_V_TAG = "vfoo"
# Completely unrelated tag
NON_V_TAG = "release-2026-07"


class TestReleaseCIDoubleFire:
    """Issue #200: pushing a stable tag must create exactly one GitHub Release."""

    def test_release_auto_yml_is_absent(self):
        """The buggy release-auto.yml must not exist in the workflows dir.

        This is the core fix from issue #200: release-auto.yml matched
        ``v*`` and called ``softprops/action-gh-release``, double-firing
        with release.yml on every stable tag push. It must stay deleted.
        """
        path = os.path.join(WORKFLOWS_DIR, "release-auto.yml")
        assert not os.path.exists(path), (
            f"{path} exists — re-introducing this file will cause the "
            f"release CI double-fire from issue #200. Delete it or scope "
            f"its tag trigger away from stable semver (vX.Y.Z) AND remove "
            f"any gh-release action from it."
        )

    def test_exactly_one_workflow_creates_release(self):
        """Across every workflow file, only ONE may use a release action.

        Scanning prevents the bug from sneaking back via a renamed or
        new workflow file (not just release-auto.yml).
        """
        creators = []
        for name, path in _workflow_files():
            text = _read_path(path)
            if _uses_release_action(text):
                creators.append(name)
        assert creators == ["release.yml"], (
            f"Exactly one workflow (release.yml) may create a GitHub "
            f"Release; found {len(creators)}: {creators}. The double-fire "
            f"bug from issue #200 returns if more than one workflow calls "
            f"a release-creating action."
        )

    def test_release_yml_triggers_on_stable_semver_tag(self):
        """release.yml: ``v[0-9]*.[0-9]*.[0-9]*`` must match v4.2.0."""
        globs = _parse_tag_globs(_read("release.yml"))
        assert globs, "release.yml must define tag patterns"
        assert _matches_any(STABLE_TAG, globs), (
            f"release.yml must trigger on stable semver tag {STABLE_TAG}; "
            f"globs={globs}"
        )
        assert _matches_any(STABLE_TAG_BARE, globs), (
            f"release.yml must trigger on stable semver tag {STABLE_TAG_BARE}; "
            f"globs={globs}"
        )

    def test_release_yml_does_not_match_non_semver_v_tag(self):
        """release.yml must not match non-semver ``v*`` tags like ``vfoo``.

        This is the scoping that prevents accidental collision with a
        future prerelease workflow (which may legitimately match ``v*``).
        """
        globs = _parse_tag_globs(_read("release.yml"))
        assert not _matches_any(NON_SEMVER_V_TAG, globs), (
            f"release.yml must NOT match non-semver tag {NON_SEMVER_V_TAG}; "
            f"globs={globs}"
        )

    def test_tauri_build_yml_does_not_create_release(self):
        """tauri-build.yml triggers on ``v*`` but must NOT create a release.

        It only uploads build artifacts — that's fine. But if a future
        change adds a release action here, the double-fire bug returns.
        """
        path = os.path.join(WORKFLOWS_DIR, "tauri-build.yml")
        if not os.path.exists(path):
            pytest.skip("tauri-build.yml not present")
        text = _read_path(path)
        assert not _uses_release_action(text), (
            "tauri-build.yml must not contain a release-creating action "
            "(softprops/action-gh-release or actions/create-release). Only "
            "release.yml may create GitHub Releases."
        )

    def test_non_v_tag_does_not_trigger_any_release_workflow(self):
        """Sanity: an unrelated tag (e.g. release-2026-07) doesn't fire releases."""
        globs = _parse_tag_globs(_read("release.yml"))
        assert globs
        assert not _matches_any(NON_V_TAG, globs), (
            f"release.yml must not match unrelated tag {NON_V_TAG}; "
            f"globs={globs}"
        )

    def test_no_workflow_other_than_release_yml_matches_stable_tag_and_creates_release(self):
        """End-to-end: for stable tag v4.2.0, count workflows that BOTH
        match the tag AND create a release. Must be exactly 1 (release.yml).
        """
        stable_matchers_with_release = []
        for name, path in _workflow_files():
            text = _read_path(path)
            if not _uses_release_action(text):
                continue
            globs = _parse_tag_globs(text)
            if globs and _matches_any(STABLE_TAG, globs):
                stable_matchers_with_release.append(name)
        assert stable_matchers_with_release == ["release.yml"], (
            f"Stable tag {STABLE_TAG} triggers {len(stable_matchers_with_release)} "
            f"release-creating workflows ({stable_matchers_with_release}); must "
            f"be exactly 1 (release.yml). This is the double-fire bug from "
            f"issue #200."
        )
