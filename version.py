"""Centralized version resolution.

Resolution chain:
  1. importlib.metadata — works when installed via pip/uv
  2. PRC_TRAY_VERSION env var — override for PyInstaller bundles / CI
  3. Parse pyproject.toml directly — fallback for dev mode
"""
import os


def get_version() -> str:
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
