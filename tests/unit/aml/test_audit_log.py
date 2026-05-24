import uuid
from datetime import datetime, UTC

import pytest

from src.aml_workflow.models.audit_log import AuditLog


class TestAuditLog:
    async def test_create_audit_log(self, seeded_session):
        now = datetime.now(UTC).isoformat()
        al = AuditLog(
            event_type="test_event",
            entity_type="transaction",
            entity_id=str(uuid.uuid4()),
            payload='{"key": "value"}',
            created_at=now,
        )
        seeded_session.add(al)
        await seeded_session.commit()
        await seeded_session.refresh(al)

        assert al.id is not None
        assert len(al.id) == 36
        assert al.event_type == "test_event"
        assert al.entity_type == "transaction"
        assert al.payload == '{"key": "value"}'
        assert al.created_at == now

    async def test_auto_generates_id(self, seeded_session):
        now = datetime.now(UTC).isoformat()
        al1 = AuditLog(
            event_type="e1", entity_type="txn",
            entity_id=str(uuid.uuid4()),
            payload="{}", created_at=now,
        )
        al2 = AuditLog(
            event_type="e2", entity_type="txn",
            entity_id=str(uuid.uuid4()),
            payload="{}", created_at=now,
        )
        seeded_session.add_all([al1, al2])
        await seeded_session.commit()
        assert al1.id != al2.id

    async def test_nullable_upload_id(self, seeded_session):
        now = datetime.now(UTC).isoformat()
        al = AuditLog(
            event_type="no_upload",
            entity_type="system",
            entity_id=str(uuid.uuid4()),
            payload="{}",
            created_at=now,
        )
        seeded_session.add(al)
        await seeded_session.commit()
        await seeded_session.refresh(al)
        assert al.upload_id is None

    async def test_default_actor_is_system(self, seeded_session):
        now = datetime.now(UTC).isoformat()
        al = AuditLog(
            event_type="default_actor",
            entity_type="rule",
            entity_id=str(uuid.uuid4()),
            payload="{}",
            created_at=now,
        )
        seeded_session.add(al)
        await seeded_session.commit()
        await seeded_session.refresh(al)
        assert al.actor == "system"
