"""Configuration with security defaults."""
import os
import secrets

# ── Mode ──────────────────────────────────────────────────────────────────
# "prod" (default) = API key required, strict CORS (endersonvizc.dev only)
# "dev" = localhost only, permissive CORS
MODE = os.environ.get("YTDLP_DAEMON_MODE", "prod")

# Server
HOST = "127.0.0.1"  # NEVER bind to 0.0.0.0
PORT = int(os.environ.get("YTDLP_DAEMON_PORT", "17171"))

# ── Security ──────────────────────────────────────────────────────────────

# CORS origins
if MODE == "prod":
    ALLOWED_ORIGINS = []
    ALLOWED_ORIGIN_REGEX = r"^https://([a-z0-9-]+\.)?endersonvizc\.dev$"
else:
    ALLOWED_ORIGINS = []
    ALLOWED_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

# Extra origins from env (comma-separated)
_extra_origins = os.environ.get("YTDLP_ALLOWED_ORIGINS", "")
if _extra_origins:
    ALLOWED_ORIGINS.extend(o.strip() for o in _extra_origins.split(",") if o.strip())

# Allowed YouTube domains for video URL validation
ALLOWED_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "music.youtube.com",
}

# Rate limiting
RATE_LIMIT_REQUESTS = int(os.environ.get("YTDLP_RATE_LIMIT", "30"))
RATE_LIMIT_WINDOW = 60  # seconds

# Cache
CACHE_TTL = 7200          # 2 hours
CACHE_MAX_SIZE = 100      # max entries

# Auto-shutdown
IDLE_TIMEOUT = int(os.environ.get("YTDLP_IDLE_TIMEOUT", "0"))

# Shutdown secret (generated per-run, prevents unauthorized shutdown)
SHUTDOWN_SECRET = secrets.token_urlsafe(32)
