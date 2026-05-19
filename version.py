"""Centralized version resolution.

Resolution chain:
  1. _build_version — generated at build time by CI (bundled into PyInstaller)
  2. importlib.metadata — works when installed via pip/uv
  3. PRC_TRAY_VERSION env var — override for CI
  4. Parse pyproject.toml directly — fallback for dev mode
"""
import os


def get_version() -> str:
    try:
        from _build_version import __version__

        return __version__
    except ImportError:
        pass

    try:
        from importlib.metadata import version

        return version("prc-tray")
    except Exception:
        pass

    if v := os.environ.get("PRC_TRAY_VERSION"):
        return v

    try:
        import tomllib

        with open("pyproject.toml", "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        return "0.0.0-dev"


__version__ = get_version()
