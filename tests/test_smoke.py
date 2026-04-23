"""
Sentinel — Smoke tests (Phase 1)
These tests verify the repo skeleton is correctly set up.
"""

from __future__ import annotations


def test_config_loads() -> None:
    """Settings should load without errors even with empty env."""
    from packages.common.config import get_settings
    settings = get_settings()
    assert settings.app_env in ("development", "test", "production")


def test_ingest_script_importable() -> None:
    """Ingest CLI should be importable without errors."""
    import importlib
    mod = importlib.import_module("scripts.ingest")
    assert hasattr(mod, "app")
