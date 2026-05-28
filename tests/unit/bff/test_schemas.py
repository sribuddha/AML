import json

import pytest
from pydantic import ValidationError

from src.core.schemas import (
    PaginatedResponse,
    RejectedRecordResponse,
    RuleCreate,
    RuleResponse,
    RuleUpdate,
    TransactionResponse,
    UploadSummaryResponse,
    ValidationByTransactionResponse,
    ValidationDayItem,
    ValidationDetailItem,
    ValidationSummaryResponse,
)


class TestPaginatedResponse:
    def test_serialization(self):
        obj = PaginatedResponse[int](page=1, per_page=10, total=25, items=[1, 2, 3])
        data = obj.model_dump()
        assert data["page"] == 1
        assert data["per_page"] == 10
        assert data["total"] == 25
        assert data["items"] == [1, 2, 3]

    def test_empty_items(self):
        obj = PaginatedResponse(page=1, per_page=50, total=0, items=[])
        assert obj.total == 0


class TestUploadSummaryResponse:
    def test_full_fields(self):
        obj = UploadSummaryResponse(
            id="abc-123",
            filename="test.csv",
            status="completed",
            total_rows=100,
            accepted_count=95,
            failed_count=5,
            uploaded_at="2026-05-20T12:00:00Z",
        )
        data = obj.model_dump()
        assert data["id"] == "abc-123"
        assert data["failed_count"] == 5

    def test_minimal_fields(self):
        obj = UploadSummaryResponse(id="x", filename="x.csv", status="processing")
        assert obj.total_rows is None
        assert obj.accepted_count is None
        assert obj.failed_count == 0
        assert obj.uploaded_at is None


class TestTransactionResponse:
    def test_omits_internal_fields(self):
        obj = TransactionResponse(
            id="uuid-1",
            account_id="ACC001",
            customer_id="CUST001",
            amount=1500.00,
            counterparty="Acme",
            city="New York",
            state="NY",
            country="US",
            date="2026-05-01",
        )
        data = obj.model_dump()
        assert "source_txn_id" not in data
        assert "upload_id" not in data
        assert "created_at" not in data
        assert "updated_at" not in data

    def test_nullable_fields(self):
        obj = TransactionResponse(
            id="uuid-2",
            account_id="ACC002",
            customer_id="CUST002",
        )
        assert obj.amount is None
        assert obj.counterparty is None


class TestRejectedRecordResponse:
    def test_with_parsed_data(self):
        obj = RejectedRecordResponse(
            id="r-1",
            row_index=12,
            raw_data={"account_id": "ACC999"},
            reasons=["not found"],
        )
        assert obj.raw_data == {"account_id": "ACC999"}
        assert obj.reasons == ["not found"]

    def test_minimal(self):
        obj = RejectedRecordResponse(id="r-2")
        assert obj.row_index is None
        assert obj.raw_data is None
        assert obj.reasons is None


class TestValidationDayItem:
    def test_full(self):
        obj = ValidationDayItem(upload_id="u-1", clean_count=10, flagged_count=2, total_count=12)
        assert obj.total_count == obj.clean_count + obj.flagged_count


class TestValidationSummaryResponse:
    def test_full(self):
        obj = ValidationSummaryResponse(upload_id="u-1", clean_count=50, flagged_count=5, total_count=55)
        assert obj.model_dump() == {
            "upload_id": "u-1",
            "clean_count": 50,
            "flagged_count": 5,
            "total_count": 55,
        }


class TestValidationDetailItem:
    def test_flagged(self):
        obj = ValidationDetailItem(
            source_txn_id="TXN002",
            status="flagged",
            flag_details={"rule-1": "High Value"},
        )
        assert obj.flag_details == {"rule-1": "High Value"}

    def test_no_flag_details(self):
        obj = ValidationDetailItem(source_txn_id="TXN001", status="clean", flag_details=None)
        assert obj.flag_details is None


class TestValidationByTransactionResponse:
    def test_full(self):
        obj = ValidationByTransactionResponse(
            upload_id="u-1",
            status="flagged",
            flag_details={"r-1": "Rule"},
            validated_at="2026-05-20T12:00:00Z",
        )
        assert obj.validated_at is not None

    def test_clean(self):
        obj = ValidationByTransactionResponse(
            upload_id="u-1",
            status="clean",
            flag_details=None,
            validated_at=None,
        )
        assert obj.flag_details is None
        assert obj.validated_at is None


class TestRuleCreate:
    def test_full_payload(self):
        body = RuleCreate(
            name="Test Rule",
            description="Desc",
            type="llm",
            status="draft",
            rules_json=[{"field": "amount", "operator": ">", "value": 100}],
        )
        assert body.name == "Test Rule"
        assert body.type == "llm"

    def test_defaults(self):
        body = RuleCreate(
            name="Default Rule",
            rules_json=[{"field": "amount", "operator": ">", "value": 100}],
        )
        assert body.type == "deterministic"
        assert body.status == "active"
        assert body.description is None

    def test_required_name(self):
        with pytest.raises(ValidationError):
            RuleCreate(rules_json=[])

    def test_required_rules_json(self):
        with pytest.raises(ValidationError):
            RuleCreate(name="Bad")


class TestRuleUpdate:
    def test_full(self):
        body = RuleUpdate(
            name="Updated",
            type="deterministic",
            status="active",
            rules_json=[{"field": "country", "operator": "==", "value": "Cayman Islands"}],
        )
        assert body.name == "Updated"

    def test_defaults(self):
        body = RuleUpdate(name="U", rules_json=[])
        assert body.type == "deterministic"
        assert body.status == "active"


class TestRuleResponse:
    def test_full(self):
        obj = RuleResponse(
            id="r-1",
            name="My Rule",
            description="Desc",
            type="deterministic",
            status="active",
            rules_json=[{"field": "amount", "operator": ">", "value": 100}],
        )
        data = obj.model_dump()
        assert data["id"] == "r-1"
        assert len(data["rules_json"]) == 1

    def test_minimal(self):
        obj = RuleResponse(
            id="r-2",
            name="Minimal",
            type="llm",
            status="draft",
            rules_json=[],
        )
        assert obj.description is None
