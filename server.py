"""FastAPI server with security hardening."""
import re
import time
import hmac
import logging
from urllib.parse import urlparse
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
from cache import cache
from version import __version__

logger = logging.getLogger("prc-tray")

# ── Rate limiter (in-memory, per-IP) ──────────────────────────────────────

class RateLimiter:
    def __init__(self, max_requests: int, window: int):
        self._max = max_requests
        self._window = window
        self._hits: dict[str, list[float]] = {}

    def check(self, ip: str) -> bool:
        now = time.time()
        hits = self._hits.setdefault(ip, [])
        self._hits[ip] = [t for t in hits if now - t < self._window]
        if len(self._hits[ip]) >= self._max:
            return False
        self._hits[ip].append(now)
        return True


rate_limiter = RateLimiter(config.RATE_LIMIT_REQUESTS, config.RATE_LIMIT_WINDOW)

# ── Idle tracking ─────────────────────────────────────────────────────────

_last_request_time = time.time()
_shutdown_callback = None


def get_idle_seconds() -> float:
    return time.time() - _last_request_time


def set_shutdown_callback(cb):
    global _shutdown_callback
    _shutdown_callback = cb


def _touch():
    global _last_request_time
    _last_request_time = time.time()


# ── API key validation ────────────────────────────────────────────────────

def _verify_api_key(authorization: str | None) -> None:
    """In prod mode, require Bearer token. In dev mode, skip."""
    if config.MODE != "prod":
        return
    if not config.API_KEY:
        raise HTTPException(status_code=500, detail="Server misconfigured: YTDLP_API_KEY not set")
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header. Use: Bearer <api_key>")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization format. Use: Bearer <api_key>")
    if not hmac.compare_digest(parts[1], config.API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")


# ── URL validation ────────────────────────────────────────────────────────

_VIDEO_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{11}$')


def validate_video_url(url: str) -> str:
    """Validate and extract video ID. Returns the ID or raises HTTPException."""
    url = url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    if _VIDEO_ID_RE.match(url):
        return url

    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL format")

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https URLs allowed")

    hostname = (parsed.hostname or "").lower()
    if hostname not in config.ALLOWED_DOMAINS:
        raise HTTPException(
            status_code=400,
            detail=f"Domain not allowed: {hostname}. Allowed: {', '.join(sorted(config.ALLOWED_DOMAINS))}"
        )

    if hostname == "youtu.be":
        vid = parsed.path.lstrip("/")
        if _VIDEO_ID_RE.match(vid):
            return vid
        raise HTTPException(status_code=400, detail="Could not extract video ID from youtu.be URL")

    from urllib.parse import parse_qs
    qs = parse_qs(parsed.query)
    vid = qs.get("v", [None])[0]
    if vid and _VIDEO_ID_RE.match(vid):
        return vid

    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) >= 2 and path_parts[0] in ("embed", "v", "shorts"):
        candidate = path_parts[1]
        if _VIDEO_ID_RE.match(candidate):
            return candidate

    raise HTTPException(status_code=400, detail="Could not extract video ID from URL")


# ── yt-dlp extraction ────────────────────────────────────────────────────

def extract_info(video_id: str) -> dict:
    """Extract video info using yt-dlp. Pure Python, no subprocess."""
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "simulate": True,
        "nocheckcertificate": True,
        "socket_timeout": 15,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=422, detail=f"Extraction failed: {e}")
    except Exception as e:
        logger.exception("Unexpected error during extraction")
        raise HTTPException(status_code=500, detail="Internal extraction error")

    if not info:
        raise HTTPException(status_code=422, detail="No info returned")

    formats = []
    for fmt in (info.get("formats") or []):
        entry = {
            "format_id": fmt.get("format_id"),
            "ext": fmt.get("ext"),
            "resolution": fmt.get("resolution") or f"{fmt.get('width', '?')}x{fmt.get('height', '?')}",
            "fps": fmt.get("fps"),
            "vcodec": fmt.get("vcodec"),
            "acodec": fmt.get("acodec"),
            "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
            "tbr": fmt.get("tbr"),
            "url": fmt.get("url"),
        }
        if entry["url"]:
            formats.append(entry)

    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "description": (info.get("description") or "")[:500],
        "uploader": info.get("uploader"),
        "duration": info.get("duration"),
        "view_count": info.get("view_count"),
        "upload_date": info.get("upload_date"),
        "thumbnail": info.get("thumbnail"),
        "formats": formats,
    }


# ── Middleware ─────────────────────────────────────────────────────────────

def _get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ── App lifecycle ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Mode: {config.MODE}")
    logger.info(f"Daemon starting on {config.HOST}:{config.PORT}")
    if config.MODE == "prod":
        logger.info(f"CORS origins: {config.ALLOWED_ORIGINS}")
        logger.info("API key required for /extract")
    else:
        logger.info(f"Shutdown secret: {config.SHUTDOWN_SECRET}")
    yield
    logger.info("Daemon shutting down")


# ── FastAPI app ───────────────────────────────────────────────────────────

app = FastAPI(
    title="PRC Tray",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=False,
    max_age=600,
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Global security: localhost enforcement, rate limiting, idle tracking."""
    client_ip = _get_client_ip(request)

    # In dev mode, enforce localhost only
    if config.MODE == "dev" and client_ip not in ("127.0.0.1", "::1", "localhost"):
        return JSONResponse(status_code=403, content={"detail": "Only localhost connections allowed"})

    # Rate limiting
    if not rate_limiter.check(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

    _touch()
    response = await call_next(request)
    return response


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Health check. Returns daemon status and mode."""
    return {
        "status": "ok",
        "mode": config.MODE,
        "idle_seconds": round(get_idle_seconds(), 1),
        "cache_size": len(cache),
    }


@app.get("/extract")
def extract(
    request: Request,
    url: str = Query(..., description="YouTube URL or video ID", max_length=500),
    authorization: str | None = Header(None),
):
    """Extract streaming URLs for a YouTube video.

    In prod mode: requires Authorization: Bearer <api_key>
    In dev mode: no auth needed (localhost only).
    """
    _verify_api_key(authorization)

    video_id = validate_video_url(url)

    cached = cache.get(video_id)
    if cached:
        logger.info(f"Cache hit: {video_id}")
        cached["_cached"] = True
        return cached

    logger.info(f"Extracting: {video_id}")
    result = extract_info(video_id)
    cache.set(video_id, result)
    return result


@app.post("/shutdown")
def shutdown(request: Request, secret: str = Query(...)):
    """Graceful shutdown. Requires the secret token printed at startup."""
    if secret != config.SHUTDOWN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid shutdown secret")

    logger.info("Shutdown requested via API")
    if _shutdown_callback:
        _shutdown_callback()
    return {"status": "shutting_down"}
