"""Shared pytest fixtures for prc-tray tests.

Sets MODE=dev before importing server to ensure TestClient sees
consistent dev-mode behavior. Module-scoped TestClient avoids
recreating the FastAPI app per test.

WARNING: yt-dlp is NOT mocked here. The `extract_info()` function
lazy-imports yt_dlp inside its body. Validation-only tests (400/422
error paths) never reach that code. When success-path `/extract`
tests are added later, conftest MUST mock `yt_dlp` before import.
"""

import os
import sys
from pathlib import Path

# ── Project root on sys.path (flat modules: cache.py, config.py, etc.) ─────
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Set MODE=dev before importing server (server imports config at module level) ──
os.environ["YTDLP_DAEMON_MODE"] = "dev"

import pytest
from fastapi.testclient import TestClient
from server import app


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient with app in dev mode. Module-scoped — shared across tests in the same module."""
    with TestClient(app) as tc:
        yield tc
