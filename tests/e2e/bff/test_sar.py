import uuid
from datetime import datetime, UTC

import pytest
from fastapi.testclient import TestClient

from src.bff.database import get_db
from src.bff.app import app
from src.aml_workflow.models.sar import SAR


@pytest.fixture
def client(seeded_session):
    app.dependency_overrides[get_db] = lambda: seeded_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_sar(seeded_session):
    now = datetime.now(UTC).isoformat()
    sar = SAR(
        id=str(uuid.uuid4()),
        transaction_id=str(uuid.uuid4()),
        upload_id=str(uuid.uuid4()),
        rule_id=str(uuid.uuid4()),
        content="Suspicious transaction detected: high-value transfer to offshore account.",
        status="pending_review",
        created_at=now,
        updated_at=now,
    )
    seeded_session.add(sar)
    seeded_session.commit()
    return sar


class TestSar:
    def test_list_sar_reports(self, client, seeded_sar):
        resp = client.get("/api/sar")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) >= 1

    def test_get_sar_report_by_id(self, client, seeded_sar):
        resp = client.get(f"/api/sar/{seeded_sar.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == seeded_sar.id
        assert "content" in data
        assert "status" in data
