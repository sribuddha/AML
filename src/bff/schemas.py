from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    page: int
    per_page: int
    total: int
    items: list[T]


class UploadSummaryResponse(BaseModel):
    id: str
    filename: str
    status: str
    total_rows: int | None = None
    accepted_count: int | None = None
    failed_count: int = 0
    uploaded_at: str | None = None


class TransactionResponse(BaseModel):
    id: str
    account_id: str
    customer_id: str
    amount: float | None = None
    counterparty: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    date: str | None = None


class RejectedRecordResponse(BaseModel):
    id: str
    row_index: int | None = None
    raw_data: dict[str, Any] | None = None
    reasons: list[str] | None = None


class ValidationDayItem(BaseModel):
    upload_id: str
    clean_count: int
    flagged_count: int
    total_count: int


class ValidationSummaryResponse(BaseModel):
    upload_id: str
    clean_count: int
    flagged_count: int
    total_count: int


class ValidationDetailItem(BaseModel):
    source_txn_id: str
    status: str
    flag_details: dict[str, str] | None = None


class ValidationByTransactionResponse(BaseModel):
    upload_id: str
    status: str
    flag_details: dict[str, str] | None = None
    validated_at: str | None = None


class RuleCreate(BaseModel):
    name: str
    description: str | None = None
    type: str = "deterministic"
    status: str = "active"
    rules_json: list[dict[str, Any]]


class RuleUpdate(BaseModel):
    name: str
    description: str | None = None
    type: str = "deterministic"
    status: str = "active"
    rules_json: list[dict[str, Any]]


class RuleResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    type: str
    status: str
    rules_json: list[dict[str, Any]]


class UploadStatusResponse(BaseModel):
    id: str
    upload_id: str
    status: str
    actor: str
    created_at: str


class TransactionStatusResponse(BaseModel):
    id: str
    transaction_id: str
    status: str
    actor: str
    created_at: str


class SARResponse(BaseModel):
    id: str
    transaction_id: str
    upload_id: str
    rule_id: str | None = None
    content: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    reviewed_at: str | None = None
    review_notes: str | None = None


class ReviewRequest(BaseModel):
    action: str  # "approve" | "reject"
    notes: str | None = None
