# Test Infrastructure Specification

## Purpose

Automated verification of existing prc-tray behavior via pytest. Establishes unit tests for pure functions and FastAPI endpoint validation tests via TestClient. No runtime changes.

## Requirements

### Requirement: Pytest Runner and Directory Structure

The system MUST provide a runnable pytest configuration. `tests/conftest.py` SHALL expose a `TestClient` fixture and mock `yt_dlp` at import to prevent network calls.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| Green run | pytest + pytest-cov in dev deps, all test modules | `uv run python -m pytest tests/ -v` | Exit 0, all pass |
| TestClient fixture | `conftest.py` defines `client = TestClient(app)` | Test requests `client` | Bound TestClient returned |
| yt-dlp import blocked | `conftest.py` mocks `yt_dlp` | Server module imported | No real import, no network |

### Requirement: TTLCache Unit Tests

The system SHALL test `TTLCache` get, set, clear, expiry, and LRU eviction.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| Cache hit | Key `"abc"` → 42 stored | `get("abc")` | Returns 42, key moved to end |
| Cache miss | Empty cache | `get("missing")` | Returns None |
| TTL expiry | Entry with `ttl=0.01` | Wait >0.01s, `get(key)` | Returns None, entry removed |
| Max-size eviction | `max_size=2`, two entries | `set("third", val)` | Oldest evicted, `len == 2` |
| Clear | Three entries | `clear()` | `len == 0` |

### Requirement: Config Constants and URL Validation Tests

The system SHALL test mode detection, `ALLOWED_DOMAINS`, and `validate_video_url` error paths — pure functions, no network.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| Mode default | `YTDLP_DAEMON_MODE` unset | Config loaded | `MODE == "prod"` |
| Allowed domains | Config loaded | Check `ALLOWED_DOMAINS` | Contains `youtube.com`, `youtu.be`, `music.youtube.com` |
| Reject missing URL | `url=""` | `validate_video_url("")` | `HTTPException(400)`, "URL is required" |
| Reject forbidden domain | `url="https://vimeo.com/123"` | `validate_video_url(url)` | `HTTPException(400)`, "Domain not allowed" |
| Accept youtu.be | `url="https://youtu.be/dQw4w9WgXcQ"` | `validate_video_url(url)` | Returns `"dQw4w9WgXcQ"` |
| Accept raw video ID | `url="dQw4w9WgXcQ"` | `validate_video_url(url)` | Returns `"dQw4w9WgXcQ"` |

### Requirement: Version Resolution Tests

The system SHALL test `get_version()`: env var override and hardcoded fallback.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| Env var priority | `PRC_TRAY_VERSION=1.2.3`, no package | `get_version()` | Returns `"1.2.3"` |
| Ultimate fallback | No env var, no package, no toml | `get_version()` | Returns `"0.0.0-dev"` |

### Requirement: FastAPI Health Endpoint via TestClient

The system SHALL test `GET /health` through TestClient.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| Health ok | TestClient fixture | `GET /health` | 200, body: `status: "ok"`, `mode`, `idle_seconds`, `cache_size` |

### Requirement: FastAPI Extract Validation via TestClient

The system SHALL test `/extract` error paths through TestClient — FastAPI param validation and URL rejection, no yt-dlp.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| Missing url param | TestClient fixture | `GET /extract` | 422 — FastAPI validation error |
| Invalid URL chars | TestClient fixture | `GET /extract?url=!!!` | 400, "Invalid URL format" |
| Non-http scheme | TestClient fixture | `GET /extract?url=ftp://youtube.com/v` | 400, "Only http/https URLs allowed" |
| Forbidden domain | TestClient fixture | `GET /extract?url=https://vimeo.com/123` | 400, "Domain not allowed" |
| Whitespace-only | TestClient fixture | `GET /extract?url=%20` | 400, "URL is required" |

### Requirement: Strict TDD Enforcement

The system MUST set `strict_tdd: true` and populate `runner` fields in `openspec/config.yaml` after tests pass. `strict_tdd: true` SHALL gate future `sdd-apply` phases.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| TDD enabled | All tests green, `tests/` exists | Config updated | `strict_tdd: true`, `runner.command: "uv run python -m pytest tests/ -v"`, `runner.framework: pytest` |
| Apply blocked | `strict_tdd: true`, tests failing | `sdd-apply` runs | Blocked until tests pass |
