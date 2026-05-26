# Design: Add Pytest Test Baseline

## Technical Approach

Add pytest infra to a zero-test Python 3.13/FastAPI project. Strategy: test pure logic first
(`cache.py`, `config.py`, `version.py`), then endpoint validation paths via `TestClient`,
staying strictly within proposal scope — no network calls, no yt-dlp extraction, no `/play`/`/stream`.

## Architecture Decisions

| # | Decision | Option A | Option B | Chosen | Why |
|---|----------|----------|----------|--------|-----|
| 1 | Config location | `pytest.ini` (separate file) | `[tool.pytest.ini_options]` in `pyproject.toml` | **B** | Single config file; uv-native pattern |
| 2 | TestClient scope | `function` (per-test) | `module` (shared) | **module** | `server.app` is a module-level singleton; recreating per-test wastes time with no isolation gain |
| 3 | yt-dlp in tests | Mock at import boundary in conftest | Deferred — no mock until needed | **Deferred** | `extract_info` does lazy `import yt_dlp` inside function. Validation-error tests never reach it. Add mock only when `/extract` success-path tests arrive. |
| 4 | TDD toggle timing | Set `strict_tdd: true` in this change | Leave false, set in follow-up | **This change** | Runner exists by end of this change; matches constraint "true only once test runner exists" |

## Data Flow

```
tests/conftest.py          tests/test_*.py
┌──────────────┐           ┌──────────────────┐
│ client fix.  │──TestClient──▶│  test_cache.py   │──▶ cache.TTLCache ✓ (no deps)
│ app override │           │  test_config.py   │──▶ config constants ✓
└──────────────┘           │  test_version.py  │──▶ version.get_version ✓
                           │  test_server.py   │──▶ FastAPI app (via client)
                           └──────────────────┘      │
                                              /health ──▶ 200 ✓
                                          /extract?url= ──▶ 400 ✓ (validation)
                                          /extract?url=X ──▶ 400 ✓ (bad domain)
```

No network boundary crossed. `/play` and `/stream` excluded per proposal scope.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `tests/conftest.py` | Create | FastAPI TestClient fixture (module scope), `app` override with `config.MODE="dev"` |
| `tests/test_cache.py` | Create | TTLCache: get/set/expiry/eviction/clear/len |
| `tests/test_config.py` | Create | MODE constants, ALLOWED_DOMAINS membership, rate-limit/env reads |
| `tests/test_version.py` | Create | get_version() chain: env override, metadata fallback, tomllib path |
| `tests/test_server.py` | Create | `/health` 200 + structure, `/extract` validation: missing url=400, invalid url=400, non-YouTube domain=400, raw video ID=200 (cached mock) |
| `pyproject.toml` | Modify | Add `pytest`, `pytest-cov` to `[dependency-groups].dev`; add `[tool.pytest.ini_options]` with `testpaths = ["tests"]` |
| `openspec/config.yaml` | Modify | `strict_tdd: true`, runner populated: `command: "uv run python -m pytest tests/ -v"`, `framework: pytest`, unit/integration layers marked available |

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | `TTLCache` (get, set, eviction, expiry, clear) | Direct instantiation, `time.sleep(0.01)` for micro-TTL |
| Unit | `validate_video_url` (all paths) | Import function, pass strings, assert 400 vs return value |
| Unit | `get_version()` chain | `monkeypatch.setenv`, `sys.modules` manipulation |
| Integration | `/health` endpoint | `TestClient.get("/health")`, assert 200 + JSON shape |
| Integration | `/extract` error paths | `TestClient.get("/extract", params=...)`, assert 400/422 statuses |

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| `import server` triggers module-level `secrets.token_urlsafe()`, `time.time()`, `logging` | All harmless — deterministic or non-blocking. No network I/O at module level. |
| Lazy `import yt_dlp` inside `extract_info()` accidentally triggered | Validation-error tests exit before reaching `extract_info`. Added explicit comment in conftest warning future maintainers. |
| `MODE` env-dependent behavior skews tests | conftest sets `YTDLP_DAEMON_MODE=dev` before `server` import. TestClient sees dev mode consistently. |
| `pytest-cov` conflicts with PyInstaller | Dev-only dep group — PyInstaller reads `[project].dependencies`, not `[dependency-groups].dev`. Zero conflict. |

## Open Questions

None — all decisions resolved.
