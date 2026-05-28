"""FastAPI server with security hardening."""
import re
import time
import logging
from urllib.parse import urlparse
from contextlib import asynccontextmanager

import httpx

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

import config
from cache import cache
from version import __version__

logger = logging.getLogger("prc-tray")
logging.getLogger("httpx").setLevel(logging.WARNING)

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
    allow_origin_regex=config.ALLOWED_ORIGIN_REGEX,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=False,
    allow_private_network=True,
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


@app.get("/play")
def play(
    request: Request,
    url: str = Query(..., description="YouTube URL or video ID", max_length=500),
):
    """Extract video info with ready-to-stream audio and video URLs.

    Returns sorted arrays (best quality first) with proxied stream URLs.
    Frontend can use audio[0] and video[0] directly.
    """
    from urllib.parse import quote

    video_id = validate_video_url(url)
    base = f"http://{config.HOST}:{config.PORT}"

    cached = cache.get(f"play:{video_id}")
    if cached:
        logger.info(f"Cache hit (play): {video_id}")
        return cached

    logger.info(f"Extracting (play): {video_id}")
    info = extract_info(video_id)

    def _proxy_url(raw_url: str) -> str:
        return f"{base}/stream?url={quote(raw_url, safe='')}"

    def _parse_resolution(res: str) -> int:
        if not res or "x" not in str(res):
            return 0
        try:
            return int(str(res).split("x")[1])
        except (ValueError, IndexError):
            return 0

    # Filter and sort audio-only formats (best bitrate first)
    audio_formats = []
    for f in info["formats"]:
        if f.get("acodec") and f["acodec"] != "none" and (not f.get("vcodec") or f["vcodec"] == "none"):
            audio_formats.append({
                "url": _proxy_url(f["url"]),
                "raw_url": f["url"],
                "ext": f["ext"],
                "bitrate": f.get("tbr") or 0,
                "codec": f["acodec"],
            })
    audio_formats.sort(key=lambda x: x["bitrate"], reverse=True)

    # Filter and sort video-only formats (best resolution first, then fps)
    video_formats = []
    for f in info["formats"]:
        if f.get("vcodec") and f["vcodec"] != "none" and (not f.get("acodec") or f["acodec"] == "none"):
            video_formats.append({
                "url": _proxy_url(f["url"]),
                "raw_url": f["url"],
                "ext": f["ext"],
                "resolution": f.get("resolution") or f"{f.get('width', '?')}x{f.get('height', '?')}",
                "height": _parse_resolution(f.get("resolution")),
                "fps": f.get("fps") or 0,
                "codec": f["vcodec"],
                "bitrate": f.get("tbr") or 0,
            })
    video_formats.sort(key=lambda x: (x["height"], x["fps"]), reverse=True)

    # Also include combined format (audio+video) as fallback
    combined = []
    for f in info["formats"]:
        if (f.get("vcodec") and f["vcodec"] != "none" and
                f.get("acodec") and f["acodec"] != "none"):
            combined.append({
                "url": _proxy_url(f["url"]),
                "raw_url": f["url"],
                "ext": f["ext"],
                "resolution": f.get("resolution") or f"{f.get('width', '?')}x{f.get('height', '?')}",
                "height": _parse_resolution(f.get("resolution")),
                "fps": f.get("fps") or 0,
            })
    combined.sort(key=lambda x: x["height"], reverse=True)

    result = {
        "id": info["id"],
        "title": info["title"],
        "thumbnail": info["thumbnail"],
        "duration": info["duration"],
        "audio": audio_formats,
        "video": video_formats,
        "combined": combined,
    }

    cache.set(f"play:{video_id}", result)
    return result


@app.get("/extract")
def extract(
    request: Request,
    url: str = Query(..., description="YouTube URL or video ID", max_length=500),
):
    """Extract streaming URLs for a YouTube video.

    Security: localhost-only binding + CORS restricts to allowed origins.
    """
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


@app.get("/stream")
def stream(
    request: Request,
    url: str = Query(..., description="googlevideo.com stream URL", max_length=2000),
):
    """Proxy a YouTube audio/video stream.

    Fetches the stream server-side (no CORS restrictions) and relays it
    to the browser with permissive CORS headers.
    """
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    if not hostname.endswith(".googlevideo.com"):
        raise HTTPException(status_code=400, detail="Only googlevideo.com URLs allowed")

    content_type = "application/octet-stream"
    url_lower = url.lower()
    if "mime=audio" in url_lower:
        content_type = "audio/webm"
    elif "mime=video" in url_lower:
        content_type = "video/webm"

    range_header = request.headers.get("range") or "bytes=0-"
    upstream_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Referer": "https://music.youtube.com/",
        "Range": range_header,
    }
    logger.info(
        "Stream request: host=%s browser_range=%s upstream_range=%s url_length=%d",
        hostname,
        request.headers.get("range") or "<missing>",
        upstream_headers["Range"],
        len(url),
    )

    client = httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(connect=10, read=300, write=10, pool=10),
    )
    upstream = client.stream("GET", url, headers=upstream_headers)
    upstream_resp = upstream.__enter__()
    logger.info(
        "Stream upstream response: status=%s content_type=%s content_length=%s content_range=%s accept_ranges=%s",
        upstream_resp.status_code,
        upstream_resp.headers.get("content-type") or "<missing>",
        upstream_resp.headers.get("content-length") or "<missing>",
        upstream_resp.headers.get("content-range") or "<missing>",
        upstream_resp.headers.get("accept-ranges") or "<missing>",
    )

    if not upstream_resp.is_success:
        upstream.__exit__(None, None, None)
        logger.warning(
            "Stream upstream failed: status=%s browser_range=%s upstream_range=%s",
            upstream_resp.status_code,
            request.headers.get("range") or "<missing>",
            upstream_headers["Range"],
        )
        raise HTTPException(
            status_code=upstream_resp.status_code,
            detail="Upstream stream fetch failed",
        )

    upstream_content_type = upstream_resp.headers.get("content-type")
    if upstream_content_type:
        content_type = upstream_content_type

    response_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Expose-Headers": "Accept-Ranges, Content-Range, Content-Length",
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-cache",
    }

    content_length = upstream_resp.headers.get("content-length")
    content_range = upstream_resp.headers.get("content-range")
    accept_ranges = upstream_resp.headers.get("accept-ranges")

    if content_length:
        response_headers["Content-Length"] = content_length
    if content_range:
        response_headers["Content-Range"] = content_range
    if accept_ranges:
        response_headers["Accept-Ranges"] = accept_ranges

    response_status = 206 if upstream_resp.status_code == 206 else 200
    logger.info(
        "Stream daemon response: status=%s content_type=%s content_length=%s content_range=%s accept_ranges=%s",
        response_status,
        content_type,
        response_headers.get("Content-Length") or "<missing>",
        response_headers.get("Content-Range") or "<missing>",
        response_headers.get("Accept-Ranges") or "<missing>",
    )

    def _generate():
        try:
            for chunk in upstream_resp.iter_bytes(65536):
                yield chunk
        finally:
            upstream.__exit__(None, None, None)

    return StreamingResponse(
        _generate(),
        status_code=response_status,
        media_type=content_type,
        headers=response_headers,
    )


@app.post("/shutdown")
def shutdown(request: Request, secret: str = Query(...)):
    """Graceful shutdown. Requires the secret token printed at startup."""
    if secret != config.SHUTDOWN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid shutdown secret")

    logger.info("Shutdown requested via API")
    if _shutdown_callback:
        _shutdown_callback()
    return {"status": "shutting_down"}
