"""Regression test for BUG/issue #200: release CI double-fire.

GitHub Actions triggers `.github/workflows/release.yml` AND
`.github/workflows/release-auto.yml` both on `v*` tags, causing two
GitHub Release objects per tag push. The plan resolves this by
scoping one workflow (release-auto.yml) to prereleases only — stable
semver tags like `v4.2.0` must trigger exactly one release workflow.
A prereelease tag like `v4.2.0-rc1` is allowed to trigger both
release.yml (silver) + release-auto.yml (prerelease draft).

This test does NOT need PyYAML (deliberately) — it parses the very
small subset of YAML we emit with a tiny manual parser, so the suite
stays hermetic.
"""
import os
import re

import pytest


WORKFLOWS_DIR = os.path.join(
    os.path.dirname(__file__), "..", ".github", "workflows"
)


def _read(name):
    path = os.path.join(WORKFLOWS_DIR, name)
    if not os.path.exists(path):
        pytest.skip(f"{path} not found")
    with open(path) as f:
        return f.read()


def _parse_tag_globs(text):
    """Extract the list of 'tags:' patterns from an `on.push.tags:` block.

    Supports both list form (- 'v[0-9]*...') and inline string form
    (tags: 'v*'). Returns the raw strings as found in source order.
    """
    tags_match = re.search(r"^\s*tags:\s*([^\n#]+(?:\n[^\n#]+)*)", text, re.MULTILINE)
    if not tags_match:
        return []

    block = tags_match.group(1)

    # List form: subsequent indented lines starting with `-`
    list_items = re.findall(r"-\s*['\"]?([^\s'\"#]+)['\"]?", block)
    if list_items:
        return list_items

    # Scalar form: tags: 'v*' or tags: v*
    scalar = re.search(r"['\"]?([^\s'\"#]+)['\"]?", block)
    return [scalar.group(1)] if scalar else []


# Stable semver vX.Y.Z (no prerelease suffix)
STABLE_TAG = "v4.2.0"
STABLE_TAG_BARE = "v1.0.0"

# Prerelease vX.Y.Z-rcN
PRERELEASE_TAG = "v4.2.0-rc1"

# Non-version tag starting with v
RANDOM_V_TAG = "vfoo"

# Completely unrelated tag
NON_V_TAG = "release-2026-07"


def _matches_any(tag, globs):
    """Lightweight fnmatch-style match.

    Supports GitHub's: `*` (any chars except `/`), `**` (any chars),
    `[0-9]`, `[0-9]*` brackets, and literal characters.
    """
    for g in globs:
        regex = _glob_to_regex(g)
        if re.fullmatch(regex, tag):
            return True
    return False


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


class TestReleaseCIDoubleFire:
    """Issue #200: pushing a stable tag must trigger exactly one release."""

    def test_release_yml_triggers_on_stable_semver_tag(self):
        """release.yml: tags: 'v[0-9]*.[0-9]*.[0-9]*' — must match v4.2.0."""
        globs = _parse_tag_globs(_read("release.yml"))
        assert globs, "release.yml must define tag patterns"
        assert _matches_any(STABLE_TAG, globs), (
            f"release.yml must trigger on stable semver tag {STABLE_TAG}; "
            f"globs={globs}"
        )

    def test_release_auto_yml_does_not_trigger_on_stable_semver_tag(self):
        """release-auto.yml must NOT match v4.2.0 (no double-fire)."""
        globs = _parse_tag_globs(_read("release-auto.yml"))
        assert globs, "release-auto.yml must define tag patterns"
        assert not _matches_any(STABLE_TAG, globs), (
            f"release-auto.yml must NOT trigger on stable tag {STABLE_TAG} "
            f"(that would cause a 2nd GitHub Release). globs={globs}"
        )
        assert not _matches_any(STABLE_TAG_BARE, globs), (
            f"release-auto.yml must NOT trigger on stable tag {STABLE_TAG_BARE}. "
            f"globs={globs}"
        )

    def test_release_auto_yml_still_handles_prereleases_or_other_tags(self):
        """release-auto.yml should still trigger on something useful.

        Two acceptable shapes:
          (a) prerelease tags (anything with '-' before the version suffix), OR
          (b) a narrower stable trigger that won't collide with v*-semver.

        The clean fix is (a). Verify whichever pattern is used, the bare
        stable form does NOT match.
        """
        globs = _parse_tag_globs(_read("release-auto.yml"))
        assert globs

        # If scoped to prereleases, must match v4.2.0-rc1
        if any(_matches_any(PRERELEASE_TAG, [g]) for g in globs):
            return  # acceptable shape (a)

        # Otherwise it should be restricted narrowly enough to not collide
        # with release.yml's stable semver glob.
        # Bare v4.2.0 must not match (already asserted in prior test).
        pytest.fail(
            "release-auto.yml neither matches prereleases (e.g. v4.2.0-rc1) "
            "nor has been removed. Scoping to prereleases is the canonical "
            "fix from the plan. Add '-rc' or '-*' to the tag patterns."
        )

    def test_exactly_one_workflow_triggers_on_stable_tag(self):
        """v4.2.0: count workflows whose tag globs match — must be 1."""
        names = ["release.yml", "release-auto.yml"]
        matches = []
        for name in names:
            globs = _parse_tag_globs(_read(name))
            if globs and _matches_any(STABLE_TAG, globs):
                matches.append(name)
        assert len(matches) == 1, (
            f"Stable tag {STABLE_TAG} triggers {len(matches)} release "
            f"workflows ({matches}); must be exactly 1 — this is the "
            f"double-fire bug from issue #200."
        )
        assert matches == ["release.yml"], (
            f"Expected only release.yml to fire on stable tags, got {matches}. "
            f"The release.yml workflow builds DMG/EXE + creates the proper "
            f"changelog release. release-auto.yml must be scoped away from "
            f"stable semver tags."
        )

    def test_non_v_tag_does_not_trigger_any_release_workflow(self):
        """Sanity: an unrelated tag (e.g. release-2026-07) doesn't release."""
        for name in ("release.yml", "release-auto.yml"):
            globs = _parse_tag_globs(_read(name))
            assert globs
            assert not _matches_any(NON_V_TAG, globs), (
                f"{name} must not match unrelated tag {NON_V_TAG}; globs={globs}"
            )
