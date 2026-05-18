"""Configuration with security defaults."""
import os
import secrets

# ── Mode ──────────────────────────────────────────────────────────────────
# "dev" = localhost only, permissive CORS
# "prod" = API key required, strict CORS (music.endersonvizc.dev only)
MODE = os.environ.get("YTDLP_DAEMON_MODE", "dev")

# Server
HOST = "127.0.0.1"  # NEVER bind to 0.0.0.0
PORT = int(os.environ.get("YTDLP_DAEMON_PORT", "17171"))

# ── Security ──────────────────────────────────────────────────────────────

# API key for production. Required in prod mode, ignored in dev.
# Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
API_KEY = os.environ.get("YTDLP_API_KEY", "")

# CORS origins
if MODE == "prod":
    ALLOWED_ORIGINS = [
        "https://music.endersonvizc.dev",
    ]
else:
    ALLOWED_ORIGINS = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

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
CACHE_TTL = 300           # 5 minutes
CACHE_MAX_SIZE = 100      # max entries

# Auto-shutdown
IDLE_TIMEOUT = int(os.environ.get("YTDLP_IDLE_TIMEOUT", "600"))

# Shutdown secret (generated per-run, prevents unauthorized shutdown)
SHUTDOWN_SECRET = secrets.token_urlsafe(32)
