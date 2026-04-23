"""
Pytest configuration and shared fixtures.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def set_test_env() -> None:
    """Force APP_ENV=test for all tests."""
    os.environ["APP_ENV"] = "test"
