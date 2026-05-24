import pytest
from fastapi.testclient import TestClient

from src.bff.database import get_db
from src.bff.app import app


@pytest.fixture
def client(seeded_session):
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestRulesCrud:
    def test_list_rules(self, client):
        resp = client.get("/api/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_create_rule(self, client):
        payload = {
            "name": "High Value Check",
            "description": "Flag transactions over $10k",
            "type": "deterministic",
            "status": "active",
            "rules_json": [{"field": "amount", "operator": ">", "value": 10000}],
        }
        resp = client.post("/api/rules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["name"] == "High Value Check"
        return data["id"]

    def test_get_rule_by_id(self, client):
        payload = {
            "name": "Get Rule Test",
            "rules_json": [{"field": "amount", "operator": ">", "value": 50000}],
        }
        create_resp = client.post("/api/rules", json=payload)
        rule_id = create_resp.json()["id"]

        resp = client.get(f"/api/rules/{rule_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == rule_id
        assert data["name"] == "Get Rule Test"

    def test_update_rule(self, client):
        payload = {
            "name": "Update Me",
            "rules_json": [{"field": "amount", "operator": ">", "value": 100}],
        }
        create_resp = client.post("/api/rules", json=payload)
        rule_id = create_resp.json()["id"]

        update_payload = {
            "name": "Updated Rule",
            "type": "deterministic",
            "status": "active",
            "rules_json": [{"field": "amount", "operator": ">", "value": 200}],
        }
        resp = client.put(f"/api/rules/{rule_id}", json=update_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Rule"

    def test_delete_rule(self, client):
        payload = {
            "name": "Delete Me",
            "rules_json": [{"field": "amount", "operator": ">", "value": 100}],
        }
        create_resp = client.post("/api/rules", json=payload)
        rule_id = create_resp.json()["id"]

        resp = client.delete(f"/api/rules/{rule_id}")
        assert resp.status_code == 204

    def test_get_deleted_rule_returns_inactive(self, client):
        payload = {
            "name": "Gone Soon",
            "rules_json": [{"field": "amount", "operator": ">", "value": 100}],
        }
        create_resp = client.post("/api/rules", json=payload)
        rule_id = create_resp.json()["id"]

        client.delete(f"/api/rules/{rule_id}")
        resp = client.get(f"/api/rules/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"
