import uuid
from datetime import datetime, UTC

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.bff.database import get_db
from src.core.models.transaction import Transaction


@pytest.fixture
def client(seeded_session):
    app = FastAPI()
    from src.bff.routes.transactions import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_txns(seeded_session):
    now = datetime.now(UTC).isoformat()
    uid = str(uuid.uuid4())
    txns = [
        Transaction(
            id=str(uuid.uuid4()), upload_id=uid,
            account_id="ACC001", customer_id="CUST001",
            amount=100.0, counterparty="Payee_A",
            city="New York", state="NY", country="US",
            date="2026-05-01", source_txn_id="TXN001",
            created_at=now, updated_at=now,
        ),
        Transaction(
            id=str(uuid.uuid4()), upload_id=uid,
            account_id="ACC003", customer_id="CUST002",
            amount=5000.0, counterparty="Payee_B",
            city="Los Angeles", state="CA", country="US",
            date="2026-05-02", source_txn_id="TXN002",
            created_at=now, updated_at=now,
        ),
    ]
    seeded_session.add_all(txns)
    return txns


class TestTransactionsRoutes:
    def test_list_transactions_no_filters(self, client, seeded_txns):
        resp = client.get("/api/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_filter_by_source_txn_id(self, client, seeded_txns):
        resp = client.get("/api/transactions?source_txn_id=TXN001")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["source_txn_id"] == "TXN001"

    def test_filter_by_account_id(self, client, seeded_txns):
        resp = client.get("/api/transactions?account_id=ACC003")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1

    def test_filter_by_customer_id(self, client, seeded_txns):
        resp = client.get("/api/transactions?customer_id=CUST002")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1

    def test_filter_by_amount_min(self, client, seeded_txns):
        resp = client.get("/api/transactions?amount_min=1000")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["source_txn_id"] == "TXN002"

    def test_filter_by_amount_max(self, client, seeded_txns):
        resp = client.get("/api/transactions?amount_max=500")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["source_txn_id"] == "TXN001"

    def test_filter_by_counterparty(self, client, seeded_txns):
        resp = client.get("/api/transactions?counterparty=Payee_B")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1

    def test_filter_by_from_date(self, client, seeded_txns):
        resp = client.get("/api/transactions?from_date=2026-05-02")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1

    def test_filter_by_to_date(self, client, seeded_txns):
        resp = client.get("/api/transactions?to_date=2026-05-01")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1

    def test_pagination(self, client, seeded_txns):
        resp = client.get("/api/transactions?page=1&per_page=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["per_page"] == 1
        assert len(data["items"]) == 1
        assert data["total"] == 2

    def test_no_results(self, client):
        resp = client.get("/api/transactions?source_txn_id=NONEXISTENT")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
