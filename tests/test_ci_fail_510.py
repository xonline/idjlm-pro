"""Intentional CI failure test for issue #510 verification."""
import pytest


def test_intentional_failure_for_issue_510():
    """This test is designed to fail to verify CI webhook auto-filing."""
    assert False, "INTENTIONAL FAILURE: This test verifies CI webhook auto-files xonline/jobs issue #510"
