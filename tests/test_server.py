"""Integration tests for FastAPI endpoints via TestClient.

Tests /health, /extract validation error paths. No yt-dlp calls.
"""


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
