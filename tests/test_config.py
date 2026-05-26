"""Unit tests for config constants and validate_video_url error paths."""

import importlib

import pytest
from fastapi import HTTPException

from server import validate_video_url


class TestConfig:
    """Tests for config module constants — pure functions, no network."""

    def test_mode_defaults_to_prod(self, monkeypatch):
        """MODE is 'prod' when YTDLP_DAEMON_MODE env var is unset."""
        monkeypatch.delenv("YTDLP_DAEMON_MODE", raising=False)
        import config as cfg
        importlib.reload(cfg)
        assert cfg.MODE == "prod"

    def test_allowed_domains_contains_expected(self):
        """ALLOWED_DOMAINS includes youtube.com, youtu.be, music.youtube.com."""
        import config as cfg
        assert "youtube.com" in cfg.ALLOWED_DOMAINS
        assert "youtu.be" in cfg.ALLOWED_DOMAINS
        assert "music.youtube.com" in cfg.ALLOWED_DOMAINS

    def test_rate_limit_and_cache_defaults(self):
        """Rate limit and cache configs have sensible defaults."""
        import config as cfg
        assert cfg.RATE_LIMIT_REQUESTS >= 1
        assert cfg.RATE_LIMIT_WINDOW == 60
        assert cfg.CACHE_TTL == 7200
        assert cfg.CACHE_MAX_SIZE == 100


class TestValidateVideoUrl:
    """Pure-function tests for validate_video_url — no FastAPI, no network."""

    def test_empty_url_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            validate_video_url("")
        assert exc.value.status_code == 400
        assert "URL is required" in str(exc.value.detail)

    def test_whitespace_only_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            validate_video_url("   \t  ")
        assert exc.value.status_code == 400
        assert "URL is required" in str(exc.value.detail)

    def test_forbidden_domain_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            validate_video_url("https://vimeo.com/123")
        assert exc.value.status_code == 400
        assert "Domain not allowed" in str(exc.value.detail)

    def test_valid_youtu_be_returns_video_id(self):
        assert validate_video_url("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_raw_video_id_accepted(self):
        assert validate_video_url("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
