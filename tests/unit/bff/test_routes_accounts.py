import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.bff.database import get_db


@pytest.fixture
def client(seeded_session):
    app = FastAPI()
    from src.bff.routes.accounts import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


class TestAccountsRoutes:
    def test_get_account_found(self, client):
        resp = client.get("/api/accounts/ACC001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["account_id"] == "ACC001"
        assert data["name"] == "Checking"
        assert data["customer_id"] == "CUST001"

    def test_get_account_not_found(self, client):
        resp = client.get("/api/accounts/NONEXISTENT")
        assert resp.status_code == 404
        assert "Account not found" in resp.json()["detail"]
