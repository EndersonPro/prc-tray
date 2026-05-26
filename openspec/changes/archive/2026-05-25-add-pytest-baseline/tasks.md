# Tasks: Add Pytest Test Baseline

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~230 (6 new files, 2 modified) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Delivery strategy | ask-always |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

No work-unit split needed — fits comfortably in one PR.

## Phase 1: Infrastructure — Dependencies & Test Runner

- [x] 1.1 Add `pytest>=8.0` and `pytest-cov>=5.0` to `[dependency-groups].dev` in `pyproject.toml`
- [x] 1.2 Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]` to `pyproject.toml`
- [x] 1.3 Create `tests/conftest.py` — module-scoped `client` fixture importing `server.app`, setting `config.MODE="dev"` before import

## Phase 2: Unit Tests — Pure Logic (no network)

- [x] 2.1 Create `tests/test_cache.py` — `TTLCache`: get hit/miss, TTL expiry (`time.sleep(0.01)`), LRU eviction at `max_size`, `clear()`, `len()`
- [x] 2.2 Create `tests/test_config.py` — MODE default ("prod"), ALLOWED_DOMAINS membership, `validate_video_url`: empty URL→400, forbidden domain→400, valid youtu.be→video ID, raw video ID→accepted
- [x] 2.3 Create `tests/test_version.py` — `get_version()`: `PRC_TRAY_VERSION` env override via `monkeypatch.setenv`, ultimate fallback returns `"0.0.0-dev"`

## Phase 3: Integration Tests — FastAPI Endpoints via TestClient

- [x] 3.1 Create `tests/test_server.py` — `GET /health` returns 200 + `status`, `mode`, `idle_seconds`, `cache_size` keys
- [x] 3.2 Add `/extract` error paths: missing url→422, invalid chars ("!!!")→400, non-http scheme (`ftp://`)→400, forbidden domain (`vimeo.com`)→400, whitespace-only (`%20`)→400

## Phase 4: TDD Enforcement

- [x] 4.1 Update `openspec/config.yaml` — `testing.strict_tdd: true`, `testing.runner.command: "uv run python -m pytest tests/ -v"`, `testing.runner.framework: pytest`, set `unit.available: true` and `integration.available: true` with tool `pytest`
