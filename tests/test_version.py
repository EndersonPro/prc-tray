"""Unit tests for get_version() — env var override and ultimate fallback."""

import builtins
import importlib
import sys

import pytest

# Ensure _build_version (CI artifact) is not present during tests
sys.modules.pop("_build_version", None)
import version


class TestGetVersion:
    """Tests version.get_version() resolution chain."""

    def test_env_var_override_takes_priority(self, monkeypatch):
        """PRC_TRAY_VERSION env var overrides importlib.metadata."""
        # Block importlib.metadata so resolution reaches the env check
        monkeypatch.setattr(importlib.metadata, "version", _raise_exception)
        monkeypatch.setenv("PRC_TRAY_VERSION", "1.2.3")
        assert version.get_version() == "1.2.3"

    def test_ultimate_fallback_returns_dev(self, monkeypatch):
        """When ALL resolution methods fail, return '0.0.0-dev'."""
        real_open = builtins.open

        monkeypatch.setattr(importlib.metadata, "version", _raise_exception)
        monkeypatch.delenv("PRC_TRAY_VERSION", raising=False)

        # Mock open so tomllib.parse("pyproject.toml") fails
        def mock_open(file, *args, **kwargs):
            if isinstance(file, str) and "pyproject.toml" in file:
                raise FileNotFoundError("mock: no pyproject.toml")
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", mock_open)
        assert version.get_version() == "0.0.0-dev"


def _raise_exception(*args, **kwargs):
    """Helper that always raises — used to block importlib.metadata.version."""
    raise Exception("mock failure")
