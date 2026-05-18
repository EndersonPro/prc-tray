# PRC Tray

Local HTTP server that wraps yt-dlp to extract YouTube streaming URLs. Runs on `127.0.0.1:17171`.

## Quick Start (dev)

```bash
cd prc-tray
uv sync
uv run python main.py --no-tray
```

## Production Mode

```bash
# Generate API key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Run
YTDLP_DAEMON_MODE=prod \
YTDLP_API_KEY=<your-key> \
./prc-tray --no-tray
```

Prod mode:
- CORS locked to `https://music.endersonvizc.dev`
- API key required via `Authorization: Bearer <key>`
- Same localhost-only binding

## Build Standalone Binary

```bash
uv run pyinstaller daemon.spec --noconfirm --clean
# Output: dist/prc-tray/
```

Packaging script (with platform notes):
```bash
uv run bash scripts/package.sh
```

## Tray Mode

```bash
uv run python main.py        # With system tray icon
uv run python main.py --no-tray  # Headless
```

Auto-shuts down after 10 minutes of inactivity.

## API

See [DAEMON.md](DAEMON.md) for full integration guide, endpoints, auth, and error handling.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YTDLP_DAEMON_MODE` | `dev` | `dev` or `prod` |
| `YTDLP_API_KEY` | (empty) | Required in prod. Bearer token |
| `YTDLP_DAEMON_PORT` | `17171` | Server port |
| `YTDLP_ALLOWED_ORIGINS` | (empty) | Extra CORS origins (comma-separated) |
| `YTDLP_RATE_LIMIT` | `30` | Requests per minute |
| `YTDLP_IDLE_TIMEOUT` | `600` | Auto-shutdown seconds (0 = disabled) |
