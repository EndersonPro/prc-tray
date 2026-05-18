# PRC Tray — Integration Guide

## What It Is

A local HTTP server that wraps yt-dlp to extract YouTube streaming URLs. Runs on the user's machine at `127.0.0.1:17171`. Your frontend calls it to get direct video/audio stream URLs without managing a backend server.

## Architecture

```
┌──────────────────────┐         ┌─────────────────────────┐
│  Frontend             │  HTTP   │  Daemon (user's machine) │
│  music.endersonvizc.dev│ ─────→ │  127.0.0.1:17171        │
│                       │         │  Python + yt-dlp         │
└──────────────────────┘         └─────────────────────────┘
```

The daemon runs locally on each user's machine. There is no central server to manage. Users install the binary and run it.

## Two Modes

| Mode | Env Var | Auth | CORS | Use Case |
|------|---------|------|------|----------|
| `dev` | `YTDLP_DAEMON_MODE=dev` (default) | None | localhost only | Local development |
| `prod` | `YTDLP_DAEMON_MODE=prod` | API key required | `https://music.endersonvizc.dev` only | Production |

## API Endpoints

### `GET /health`

No auth required. Check if daemon is running.

**Response:**
```json
{
  "status": "ok",
  "mode": "dev",
  "idle_seconds": 42.1,
  "cache_size": 3
}
```

### `GET /extract?url=<youtube_url_or_id>`

Extract streaming URLs for a video.

**Auth (prod mode only):**
```
Authorization: Bearer <api_key>
```

**Parameters:**
- `url` (required): YouTube URL or 11-char video ID
  - Accepted: `https://www.youtube.com/watch?v=ID`, `https://youtu.be/ID`, `ID` (bare)
  - Max length: 500 chars

**Response (200):**
```json
{
  "id": "dQw4w9WgXcQ",
  "title": "Video Title",
  "description": "First 500 chars...",
  "uploader": "Channel Name",
  "duration": 213,
  "view_count": 1773113788,
  "upload_date": "20091025",
  "thumbnail": "https://...",
  "formats": [
    {
      "format_id": "22",
      "ext": "mp4",
      "resolution": "1280x720",
      "fps": 30,
      "vcodec": "avc1.64001F",
      "acodec": "mp4a.40.2",
      "filesize": null,
      "tbr": 1024,
      "url": "https://rr3---sn-xxx.googlevideo.com/videoplayback?..."
    }
  ],
  "_cached": true
}
```

**Error responses:**
- `400`: Invalid URL or non-YouTube domain
- `401`: Missing Authorization header (prod mode)
- `403`: Invalid API key (prod mode)
- `422`: yt-dlp extraction failed (video private, deleted, etc.)
- `429`: Rate limit exceeded (30 req/min)
- `500`: Internal error

**Notes on `formats`:**
- Each entry has a direct `url` to a googlevideo.com stream
- URLs expire after ~6 hours (YouTube rotates them)
- `vcodec: "none"` = audio-only format
- `acodec: "none"` = video-only format
- Progressive formats (both video+audio) are typically 720p max
- Adaptive formats (separate video/audio) go up to 4K

### `POST /shutdown?secret=<token>`

Stop the daemon. Token is printed at startup logs.

## Frontend Integration (prod mode)

```javascript
const DAEMON = "http://127.0.0.1:17171";
const API_KEY = "your-api-key-here"; // Set via env or config

async function extractVideo(url) {
  const res = await fetch(`${DAEMON}/extract?url=${encodeURIComponent(url)}`, {
    headers: {
      "Authorization": `Bearer ${API_KEY}`
    }
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail);
  }

  return await res.json();
}

// Health check (no auth needed)
async function isDaemonRunning() {
  try {
    const res = await fetch(`${DAEMON}/health`, {
      signal: AbortSignal.timeout(3000)
    });
    return res.ok;
  } catch {
    return false;
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YTDLP_DAEMON_MODE` | `dev` | `dev` or `prod` |
| `YTDLP_API_KEY` | (empty) | Required in prod mode. Bearer token for auth |
| `YTDLP_DAEMON_PORT` | `17171` | Server port |
| `YTDLP_ALLOWED_ORIGINS` | (empty) | Extra CORS origins (comma-separated) |
| `YTDLP_RATE_LIMIT` | `30` | Requests per minute |
| `YTDLP_IDLE_TIMEOUT` | `600` | Seconds before auto-shutdown (0 = disabled) |

## Production Deployment (per user)

```bash
# 1. Generate API key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Run in prod mode
YTDLP_DAEMON_MODE=prod \
YTDLP_API_KEY=<generated-key> \
./prc-tray --no-tray
```

The daemon binds to `127.0.0.1` only. It is NOT exposed to the internet. The browser on the same machine connects to it via `fetch("http://127.0.0.1:17171/...")`.

## Security Model

| Layer | Dev Mode | Prod Mode |
|-------|----------|-----------|
| Bind address | `127.0.0.1` | `127.0.0.1` |
| CORS | localhost origins | `https://music.endersonvizc.dev` only |
| Auth | None | Bearer token required |
| Rate limit | 30 req/min | 30 req/min |
| URL validation | YouTube domains only | YouTube domains only |
| Middleware | Rejects non-localhost IPs | CORS handles origin restriction |
| Shutdown | Secret token required | Secret token required |

## Cache Behavior

- Results cached per video ID for 5 minutes
- Max 100 entries in cache (LRU eviction)
- `_cached: true` field in response indicates cache hit
- URLs in cached responses may be stale if near expiration

## Error Handling for Frontend

```javascript
async function extractWithRetry(url, retries = 2) {
  for (let i = 0; i <= retries; i++) {
    try {
      const data = await extractVideo(url);
      return data;
    } catch (err) {
      if (i === retries) throw err;
      // Wait before retry (exponential backoff)
      await new Promise(r => setTimeout(r, 1000 * (i + 1)));
    }
  }
}
```

## Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| "Daemon offline" | Daemon not running | Start it: `./prc-tray --no-tray` |
| "401 Missing Authorization" | Prod mode, no header | Add `Authorization: Bearer <key>` |
| "403 Invalid API key" | Wrong key | Check `YTDLP_API_KEY` matches |
| "422 Extraction failed" | Video unavailable | Check video is public, not age-gated |
| "429 Rate limit" | Too many requests | Wait 60 seconds |
| Stale URLs in cache | Cache TTL not expired | Wait 5 min or video URLs rotated |
