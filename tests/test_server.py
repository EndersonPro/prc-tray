"""Integration tests for FastAPI endpoints via TestClient.

Tests /health, /extract validation error paths. No yt-dlp calls.
"""

from urllib.parse import quote

import server


class TestHealthEndpoint:
    """Tests for GET /health — returns status, mode, idle_seconds, cache_size."""

    def test_health_returns_200_with_expected_keys(self, client):
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "mode" in data
        assert "idle_seconds" in data
        assert "cache_size" in data

    def test_health_idle_seconds_is_number(self, client):
        response = client.get("/health")
        data = response.json()
        assert isinstance(data["idle_seconds"], (int, float))

    def test_health_cache_size_is_integer(self, client):
        response = client.get("/health")
        data = response.json()
        assert isinstance(data["cache_size"], int)


class TestExtractValidation:
    """Tests for GET /extract validation — FastAPI param checks and URL validation.

    All paths exit before reaching yt-dlp, so no network calls occur.
    """

    def test_missing_url_param_returns_422(self, client):
        response = client.get("/extract")
        assert response.status_code == 422

    def test_invalid_url_chars_returns_400(self, client):
        response = client.get("/extract?url=!!!")
        assert response.status_code == 400
        # Note: urlparse("!!!") produces empty scheme, so the actual error
        # is the scheme check ("Only http/https URLs allowed"), not the
        # urlparse exception ("Invalid URL format"). This reflects current
        # code behavior — the spec's "Invalid URL format" message applies
        # only when urlparse itself raises.
        detail = response.json()["detail"]
        assert detail == "Only http/https URLs allowed"

    def test_non_http_scheme_returns_400(self, client):
        response = client.get("/extract?url=ftp://youtube.com/v")
        assert response.status_code == 400
        assert "Only http/https URLs allowed" == response.json()["detail"]

    def test_forbidden_domain_returns_400(self, client):
        response = client.get("/extract?url=https://vimeo.com/123")
        assert response.status_code == 400
        assert "Domain not allowed" in response.json()["detail"]

    def test_whitespace_only_url_returns_400(self, client):
        response = client.get("/extract?url=%20")
        assert response.status_code == 400
        assert "URL is required" in response.json()["detail"]


class _FakeUpstreamResponse:
    def __init__(self, status_code=206, headers=None, chunks=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.is_success = 200 <= status_code < 300
        self._chunks = chunks or [b"audio-bytes"]

    def iter_bytes(self, chunk_size):
        yield from self._chunks


class _FakeStreamContext:
    def __init__(self, response):
        self.response = response
        self.closed = False

    def __enter__(self):
        return self.response

    def __exit__(self, exc_type, exc, tb):
        self.closed = True


class _FakeHttpxClient:
    last_headers = None

    def __init__(self, *args, **kwargs):
        pass

    def stream(self, method, url, headers):
        _FakeHttpxClient.last_headers = headers
        response = _FakeUpstreamResponse(
            status_code=206,
            headers={
                "content-type": "audio/webm",
                "content-length": "11",
                "content-range": "bytes 100-110/1000",
                "accept-ranges": "bytes",
            },
        )
        return _FakeStreamContext(response)


class TestStreamProxy:
    """Tests for GET /stream range proxy behavior without real network calls."""

    def test_stream_forwards_range_and_returns_206_headers(self, client, monkeypatch):
        monkeypatch.setattr(server.httpx, "Client", _FakeHttpxClient)
        raw_url = quote("https://rr1---sn-test.googlevideo.com/videoplayback?mime=audio", safe="")

        response = client.get(
            f"/stream?url={raw_url}",
            headers={"Range": "bytes=100-110"},
        )

        assert response.status_code == 206
        assert response.content == b"audio-bytes"
        assert response.headers["content-type"] == "audio/webm"
        assert response.headers["content-length"] == "11"
        assert response.headers["content-range"] == "bytes 100-110/1000"
        assert response.headers["accept-ranges"] == "bytes"
        assert response.headers["access-control-expose-headers"] == "Accept-Ranges, Content-Range, Content-Length"
        assert _FakeHttpxClient.last_headers["Range"] == "bytes=100-110"
        assert _FakeHttpxClient.last_headers["Accept"] == "*/*"
        assert _FakeHttpxClient.last_headers["Referer"] == "https://music.youtube.com/"

    def test_stream_defaults_to_open_range_when_browser_omits_range(self, client, monkeypatch):
        monkeypatch.setattr(server.httpx, "Client", _FakeHttpxClient)
        raw_url = quote("https://rr1---sn-test.googlevideo.com/videoplayback?mime=audio", safe="")

        response = client.get(f"/stream?url={raw_url}")

        assert response.status_code == 206
        assert _FakeHttpxClient.last_headers["Range"] == "bytes=0-"
