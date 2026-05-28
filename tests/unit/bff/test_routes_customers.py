import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.bff.database import get_db


@pytest.fixture
def client(seeded_session):
    app = FastAPI()
    from src.bff.routes.customers import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


class TestCustomersRoutes:
    def test_list_customers(self, client):
        resp = client.get("/api/customers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_customers_paginated(self, client):
        resp = client.get("/api/customers?page=1&per_page=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["per_page"] == 2
        assert len(data["items"]) == 2

    def test_list_customers_filter_first_name(self, client):
        resp = client.get("/api/customers?first_name=John")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["first_name"] == "John"

    def test_list_customers_filter_last_name(self, client):
        resp = client.get("/api/customers?last_name=Smith")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["last_name"] == "Smith"

    def test_get_customer_found(self, client):
        resp = client.get("/api/customers/CUST001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["customer_id"] == "CUST001"
        assert data["first_name"] == "John"
        assert len(data["accounts"]) == 2

    def test_get_customer_not_found(self, client):
        resp = client.get("/api/customers/NONEXISTENT")
        assert resp.status_code == 404
        assert "Customer not found" in resp.json()["detail"]
