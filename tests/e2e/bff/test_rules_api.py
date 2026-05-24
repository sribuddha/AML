import uuid

import pytest
import pytest_asyncio

from datetime import datetime, UTC
from src.aml_workflow.models.rule import Rule


@pytest_asyncio.fixture
async def seeded_rules(seeded_session):
    now = datetime.now(UTC).isoformat()
    rules = [
        Rule(
            id=str(uuid.uuid4()), name="High Value Check",
            description="Flags > $10k", type="deterministic",
            status="active", rules_json='[{"field":"amount","operator":">","value":10000}]',
            created_at=now, updated_at=now,
        ),
        Rule(
            id=str(uuid.uuid4()), name="Offshore Monitor",
            description="Flags offshore txns", type="deterministic",
            status="active", rules_json='[{"field":"country","operator":"==","value":"KY"}]',
            created_at=now, updated_at=now,
        ),
        Rule(
            id=str(uuid.uuid4()), name="ML Model v2",
            description="ML-based scoring", type="ml",
            status="active", rules_json='[{"model":"v2","threshold":0.8}]',
            created_at=now, updated_at=now,
        ),
    ]
    seeded_session.add_all(rules)
    await seeded_session.commit()
    return rules


class TestRulesAPI:
    async def test_list_rules_with_type_filter(self, client, seeded_rules):
        resp = await client.get("/api/rules?type=ml")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["type"] == "ml"

    async def test_list_rules_with_name_filter(self, client, seeded_rules):
        resp = await client.get("/api/rules?name=High Value Check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["name"] == "High Value Check"

    async def test_get_rule_returns_404(self, client):
        resp = await client.get(f"/api/rules/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_update_rule_returns_404(self, client):
        resp = await client.put(
            f"/api/rules/{uuid.uuid4()}",
            json={"name": "Ghost", "rules_json": [{"field": "x", "operator": ">", "value": 1}]},
        )
        assert resp.status_code == 404

    async def test_delete_rule_returns_404(self, client):
        resp = await client.delete(f"/api/rules/{uuid.uuid4()}")
        assert resp.status_code == 404
