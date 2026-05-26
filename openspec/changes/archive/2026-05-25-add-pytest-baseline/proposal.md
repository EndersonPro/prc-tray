# Proposal: Add Pytest Test Baseline

## Intent

prc-tray has zero tests. `strict_tdd` is `false` because no test runner exists. This change adds pytest infrastructure and unit tests for existing behavior without altering runtime functionality, then enables TDD enforcement.

## Scope

### In Scope
- Add `pytest` and `pytest-cov` to `[dependency-groups].dev` in `pyproject.toml`
- Create `tests/` with `conftest.py` and `pytest.ini` (or `pyproject.toml` tool section)
- Unit tests for pure functions: `cache.py` (TTLCache), `config.py` (mode constants, URL validation), `version.py` (get_version resolution chain)
- FastAPI endpoint tests via `TestClient`: `/health`, `/extract` validation paths and error cases
- Update `openspec/config.yaml`: set `strict_tdd: true`, populate test runner fields

### Out of Scope
- Integration tests requiring real yt-dlp network calls (extraction)
- Tray icon tests (GUI, pystray)
- `/play` and `/stream` endpoint tests (require network mock complexity deferred to follow-up)
- Coverage thresholds — baseline first, quality gates later
- CI pipeline changes

## Capabilities

### New Capabilities
- `test-infrastructure`: pytest runner, `conftest.py`, test directory structure, FastAPI `TestClient` fixtures

### Modified Capabilities
None — no existing specs in `openspec/specs/`.

## Approach

1. Add `pytest`, `pytest-cov`, and `httpx` to dev dependencies (httpx already in main deps for stream proxy, reused for TestClient)
2. Create `tests/conftest.py` with FastAPI `TestClient` fixture and mock helpers
3. Write `test_cache.py`, `test_config.py`, `test_version.py` for pure-function coverage
4. Write `test_server.py` exercising `/health` and `/extract` error paths (invalid URLs, missing params, forbidden domains)
5. Update `openspec/config.yaml` testing section with valid runner config and `strict_tdd: true`
6. Verify `uv run python -m pytest tests/ -v` passes green

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `pyproject.toml` | Modified | Add pytest, pytest-cov to dev deps |
| `tests/` | New | Test root with conftest and test modules |
| `openspec/config.yaml` | Modified | strict_tdd=true, runner.command populated |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Test deps conflict with PyInstaller build | Low | Dev-only group, excluded from release builds |
| yt-dlp import fails in test env | Low | Mock yt-dlp at import boundary in conftest |

## Rollback Plan

Remove `tests/` directory. Revert `pyproject.toml` dev deps. Set `strict_tdd` back to `false` and clear runner fields in `openspec/config.yaml`.

## Dependencies

- `pytest>=8.0` (new dev dep)
- `pytest-cov>=5.0` (new dev dep)
- `httpx` (already in main deps, reused for TestClient)

## Success Criteria

- [ ] `uv run python -m pytest tests/ -v` exits 0 with all tests passing
- [ ] `openspec/config.yaml` has `strict_tdd: true` and valid `runner.command`
- [ ] No source files outside `tests/` and `pyproject.toml` changed, except `openspec/config.yaml`
- [ ] `uv run python main.py --no-tray` still starts normally (smoke)
