<p align="center">
  <img src="assets/logo.png" alt="PRC Tray" width="128">
</p>

<h1 align="center">PRC Tray</h1>

<p align="center">
  Local daemon that extracts YouTube streaming URLs via yt-dlp.<br>
  Runs on <code>127.0.0.1:17171</code> — fast, private, no server costs.
</p>

---

## Architecture

PRC Tray is a **local daemon** designed to work alongside a web frontend. It runs on the user's machine, extracts YouTube streaming URLs using yt-dlp, and serves them over HTTP with CORS headers.

```
┌─────────────────┐     http://127.0.0.1:17171     ┌──────────────┐
│  Web Frontend   │ ──────────────────────────────→ │   PRC Tray   │
│  (HTTPS site)   │ ←────────────────────────────── │   (Daemon)   │
└─────────────────┘     JSON + stream URLs          └──────┬───────┘
                                                           │
                                                    ┌──────▼───────┐
                                                    │    yt-dlp    │
                                                    │  (extraction)│
                                                    └──────────────┘
```

**Why local?**
- **Speed**: no round-trip to a server — extraction happens on the user's machine
- **Privacy**: YouTube URLs are signed with the user's IP — a server-side proxy would get 403 errors
- **Zero cost**: no server infrastructure needed for extraction

### Components

| File | Purpose |
|------|---------|
| `main.py` | Entry point — CLI args, signal handling, tray integration |
| `server.py` | FastAPI server — all endpoints, CORS, rate limiting |
| `config.py` | Configuration from env vars |
| `cache.py` | In-memory LRU cache with TTL |
| `tray.py` | System tray icon (pystray) with controls |
| `version.py` | Centralized version resolution |
| `daemon.spec` | PyInstaller build config (single-file binary) |

---

## Security

### Network isolation

The daemon binds **exclusively to `127.0.0.1`** — it is never exposed to the network. Only processes on the same machine can reach it.

### CORS

| Mode | Allowed Origins |
|------|----------------|
| `dev` | Any `localhost` / `127.0.0.1` port (regex) |
| `prod` | `https://music.endersonvizc.dev` only |

### PNA (Private Network Access)

The daemon includes `Access-Control-Allow-Private-Network: true` in CORS responses. This allows an HTTPS frontend to fetch from the local daemon — required by Chrome's PNA policy since 2024.

### Rate limiting

30 requests per minute per IP (configurable via `YTDLP_RATE_LIMIT`).

### No API key

Security is achieved through localhost binding + CORS — no API key needed. The origin restriction is the authentication boundary.

---

## API Endpoints

### `GET /health`

Daemon status check. No auth required.

```json
{ "status": "ok", "mode": "prod", "idle_seconds": 42.1, "cache_size": 3 }
```

### `GET /play?url=<video_id_or_url>`

**Primary endpoint.** Extracts video info and returns sorted audio/video arrays with stream URLs.

```bash
curl "http://127.0.0.1:17171/play?url=dQw4w9WgXcQ"
```

Response:
```json
{
  "id": "dQw4w9WgXcQ",
  "title": "Video Title",
  "thumbnail": "https://i.ytimg.com/vi/...",
  "duration": 213,
  "audio": [
    {
      "url": "http://127.0.0.1:17171/stream?url=...",
      "raw_url": "https://rr8---sn-*.googlevideo.com/...",
      "ext": "m4a",
      "bitrate": 129.5,
      "codec": "mp4a.40.2"
    }
  ],
  "video": [
    {
      "url": "http://127.0.0.1:17171/stream?url=...",
      "raw_url": "https://rr8---sn-*.googlevideo.com/...",
      "ext": "webm",
      "resolution": "3840x2160",
      "height": 2160,
      "fps": 25,
      "codec": "vp9",
      "bitrate": 5500
    }
  ],
  "combined": [...]
}
```

- `audio[]` — sorted by bitrate (best first), audio-only formats
- `video[]` — sorted by resolution + fps (best first), video-only formats
- `combined[]` — audio+video in single stream (fallback, typically 640x360 max)
- `url` — proxied through daemon's `/stream` (for local use)
- `raw_url` — direct googlevideo.com URL (for backend proxy if needed)

### `GET /extract?url=<video_id_or_url>`

Raw yt-dlp extraction. Returns all 30+ formats without filtering.

### `GET /stream?url=<encoded_googlevideo_url>`

Proxies a googlevideo.com stream. Used internally by `/play` URLs.

```bash
curl "http://127.0.0.1:17171/stream?url=https%3A%2F%2Frr8---sn-*.googlevideo.com%2F..."
```

- Streams bytes progressively (no full buffering)
- `Content-Type` auto-detected from mime param
- CORS headers included

### `POST /shutdown?secret=<token>`

Graceful shutdown. The secret is printed in logs at startup.

---

## Installation

### macOS

```bash
# Download DMG from releases
open PRC-Tray-1.0.0-macos.dmg
# Drag PRC Tray to Applications
# Double-click to run — daemon starts in background (no terminal)
```

The `.app` runs as a daemon with `LSUIElement=true` — no Dock icon, no terminal window. Access the tray menu from the menu bar for health check, logs, and shutdown.

### Linux (Debian/Ubuntu)

```bash
sudo dpkg -i PRC-Tray-1.0.0-linux-amd64.deb
prc-tray --no-tray
```

### Windows

Run `PRC-Tray-1.0.0-windows-setup.exe` and follow the installer.

### From source

```bash
git clone https://github.com/endersonvizc/prc-tray.git
cd prc-tray
uv sync
uv run python main.py --no-tray
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `YTDLP_DAEMON_MODE` | `dev` | `dev` or `prod` |
| `YTDLP_DAEMON_PORT` | `17171` | Server port |
| `YTDLP_DAEMON_HOST` | `127.0.0.1` | Bind address |
| `YTDLP_RATE_LIMIT` | `30` | Requests per minute per IP |
| `YTDLP_IDLE_TIMEOUT` | `0` | Auto-shutdown seconds (0 = disabled) |
| `YTDLP_CACHE_TTL` | `7200` | Cache TTL in seconds (2 hours) |
| `YTDLP_CACHE_MAX_SIZE` | `128` | Max cached entries |

---

## Build

### Binary

```bash
# Generate version file
echo '__version__ = "1.0.0"' > _build_version.py

# Build single-file binary
uv run pyinstaller daemon.spec --noconfirm --clean
# Output: dist/prc-tray
```

### Installers

```bash
# macOS DMG (prod mode)
bash installers/install-macos.sh --non-interactive

# macOS DMG (dev mode)
bash installers/install-macos.sh --non-interactive --dev

# macOS PKG (with LaunchAgent auto-start)
bash installers/install-macos.sh --non-interactive --pkg

# Linux .deb
bash installers/install-linux.sh --deb
```

---

## CI/CD

Releases are triggered by pushing a `v*` tag:

```bash
git tag v1.0.0
git push --tags
```

The GitHub Actions workflow:
1. Extracts version from tag (`v1.0.0` → `1.0.0`)
2. Generates `_build_version.py` with the version
3. Builds on macOS, Linux, and Windows
4. Creates installers with version in filenames
5. Creates a GitHub Release with all artifacts

---

## Frontend Integration

### Detect daemon

```js
const DAEMON = "http://127.0.0.1:17171";

async function isDaemonRunning() {
  try {
    const res = await fetch(`${DAEMON}/health`, { signal: AbortSignal.timeout(2000) });
    return res.ok;
  } catch {
    return false;
  }
}
```

### Play audio

```js
const data = await fetch(`${DAEMON}/play?url=VIDEO_ID`).then(r => r.json());

// Best quality audio — stream directly (no fetch + blob)
const audio = new Audio(data.audio[0].url);
audio.play();
```

### HTTPS frontend (Mixed Content)

The daemon runs on HTTP. An HTTPS frontend cannot fetch directly due to browser security. Solutions:

1. **Audio element**: `new Audio(url)` works — browsers allow media from HTTP localhost
2. **PNA header**: The daemon sends `Access-Control-Allow-Private-Network: true`, enabling `fetch()` from HTTPS pages in Chrome
3. **Backend proxy**: Use `raw_url` from `/play` response and proxy through your HTTPS backend

---

## Tray Menu

When running with the system tray icon:

| Item | Action |
|------|--------|
| PRC Tray v1.0.0 (dev/prod) | Version and mode display |
| Health Check | Opens `/health` in browser |
| Copy Shutdown Secret | Copies token to clipboard |
| Open Logs | Opens `/tmp/prc-tray.log` |
| Quit | Graceful shutdown |

---

## Logs

- **macOS/Linux**: `/tmp/prc-tray.log`
- **Windows**: `%TEMP%\prc-tray.log`

Logs are written to both file and stderr simultaneously.
