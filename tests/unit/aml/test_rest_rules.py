import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.bff.database import get_db


@pytest.fixture
def client(seeded_session):
    app = FastAPI()
    from src.aml_workflow.rest.rules import router
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c


class TestRulesRest:
    def test_list_rules_empty(self, client):
        resp = client.get("/api/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_create_rule(self, client):
        payload = {
            "name": "High Value",
            "description": "Flag > $10k",
            "type": "deterministic",
            "status": "active",
            "rules_json": [{"field": "amount", "operator": ">", "value": 10000}],
        }
        resp = client.post("/api/rules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "High Value"
        assert "id" in data
        assert data["rules_json"] == payload["rules_json"]

    def test_create_rule_defaults(self, client):
        payload = {"name": "Minimal", "rules_json": [{"field": "amount", "operator": ">", "value": 100}]}
        resp = client.post("/api/rules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "deterministic"
        assert data["status"] == "active"

    def test_get_rule(self, client):
        payload = {"name": "Get Test", "rules_json": [{"field": "amount", "operator": ">", "value": 50000}]}
        create_resp = client.post("/api/rules", json=payload)
        rule_id = create_resp.json()["id"]

        resp = client.get(f"/api/rules/{rule_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == rule_id
        assert data["name"] == "Get Test"

    def test_get_rule_not_found(self, client):
        resp = client.get("/api/rules/nonexistent")
        assert resp.status_code == 404
        assert "Rule not found" in resp.json()["detail"]

    def test_update_rule(self, client):
        payload = {"name": "Original", "rules_json": [{"field": "amount", "operator": ">", "value": 100}]}
        create_resp = client.post("/api/rules", json=payload)
        rule_id = create_resp.json()["id"]

        update = {
            "name": "Updated Rule",
            "type": "deterministic",
            "status": "active",
            "rules_json": [{"field": "amount", "operator": ">", "value": 200}],
        }
        resp = client.put(f"/api/rules/{rule_id}", json=update)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Rule"
        assert data["rules_json"] == update["rules_json"]

    def test_update_rule_not_found(self, client):
        update = {"name": "Nope", "type": "deterministic", "status": "active", "rules_json": []}
        resp = client.put("/api/rules/nonexistent", json=update)
        assert resp.status_code == 404

    def test_update_rule_status(self, client):
        payload = {"name": "Status Test", "rules_json": [{"field": "amount", "operator": ">", "value": 100}]}
        create_resp = client.post("/api/rules", json=payload)
        rule_id = create_resp.json()["id"]

        resp = client.patch(f"/api/rules/{rule_id}/status", json={"status": "inactive"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"

    def test_update_rule_status_invalid(self, client):
        payload = {"name": "Bad Status", "rules_json": []}
        create_resp = client.post("/api/rules", json=payload)
        rule_id = create_resp.json()["id"]

        resp = client.patch(f"/api/rules/{rule_id}/status", json={"status": "invalid"})
        assert resp.status_code == 422

    def test_update_rule_status_not_found(self, client):
        resp = client.patch("/api/rules/nonexistent/status", json={"status": "inactive"})
        assert resp.status_code == 404

    def test_delete_rule(self, client):
        payload = {"name": "Delete Me", "rules_json": [{"field": "amount", "operator": ">", "value": 100}]}
        create_resp = client.post("/api/rules", json=payload)
        rule_id = create_resp.json()["id"]

        resp = client.delete(f"/api/rules/{rule_id}")
        assert resp.status_code == 204

    def test_delete_rule_not_found(self, client):
        resp = client.delete("/api/rules/nonexistent")
        assert resp.status_code == 404

    def test_list_rules_filter_by_type(self, client):
        client.post("/api/rules", json={"name": "R1", "type": "llm", "rules_json": []})
        client.post("/api/rules", json={"name": "R2", "type": "deterministic", "rules_json": []})

        resp = client.get("/api/rules?type=llm")
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["type"] == "llm" for r in data["items"])

    def test_list_rules_filter_by_name(self, client):
        client.post("/api/rules", json={"name": "UniqueName", "rules_json": []})

        resp = client.get("/api/rules?name=UniqueName")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 1

    def test_list_rules_show_inactive(self, client):
        client.post("/api/rules", json={"name": "Active", "rules_json": []})
        payload = {"name": "Inactive", "status": "inactive", "rules_json": []}
        client.post("/api/rules", json=payload)

        resp = client.get("/api/rules?status=all")
        assert resp.status_code == 200
        data = resp.json()
        assert any(r["status"] == "inactive" for r in data["items"])
