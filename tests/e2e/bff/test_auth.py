from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestAPIKeyAuth:
    """Tests for API key authentication middleware.

    These tests set AML_API_KEY via monkeypatch so the middleware
    enforces auth. All other tests in the suite leave the key empty
    (no auth required).
    """

    async def test_returns_401_when_no_auth_header(self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AML_API_KEY", "test-key-123")
        resp = await client.post("/api/uploads", files={"file": ("test.csv", b"a,b\n1,2", "text/csv")})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Unauthorized"

    async def test_returns_401_with_wrong_key(self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AML_API_KEY", "test-key-123")
        resp = await client.post(
            "/api/uploads",
            files={"file": ("test.csv", b"a,b\n1,2", "text/csv")},
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 401

    async def test_returns_401_with_bad_scheme(self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AML_API_KEY", "test-key-123")
        resp = await client.post(
            "/api/uploads",
            files={"file": ("test.csv", b"a,b\n1,2", "text/csv")},
            headers={"Authorization": "Basic dGVzdDpwYXNz"},
        )
        assert resp.status_code == 401

    async def test_allows_valid_key(self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AML_API_KEY", "test-key-123")
        resp = await client.post(
            "/api/uploads",
            files={"file": ("test.csv", b"a,b\n1,2", "text/csv")},
            headers={"Authorization": "Bearer test-key-123"},
        )
        assert resp.status_code != 401

    async def test_options_passthrough(self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AML_API_KEY", "test-key-123")
        resp = await client.options("/api/uploads")
        assert resp.status_code != 401

    async def test_non_api_routes_passthrough(self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AML_API_KEY", "test-key-123")
        resp = await client.get("/")
        assert resp.status_code != 401

    async def test_no_auth_when_key_empty(self, client: AsyncClient) -> None:
        resp = await client.post("/api/uploads", files={"file": ("test.csv", b"a,b\n1,2", "text/csv")})
        assert resp.status_code != 401
