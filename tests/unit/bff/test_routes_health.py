import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    async def test_health_returns_ok(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["version"] == "0.1.0"
        assert body["db"] in ("connected", "disconnected")

    async def test_health_bypasses_auth(self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AML_API_KEY", "secret-key")
        resp = await client.get("/api/health", headers={"Authorization": "Bearer wrong-key"})
        assert resp.status_code == 200

    async def test_health_without_auth_header(self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AML_API_KEY", "secret-key")
        resp = await client.get("/api/health")
        assert resp.status_code == 200
