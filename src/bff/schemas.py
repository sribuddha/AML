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
    eval_file: str | None = None
    pending_sar_count: int = 0


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


class RuleStatusUpdate(BaseModel):
    status: str


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
    action: str
    notes: str | None = None


class BatchReviewRequest(BaseModel):
    sar_ids: list[str]
    action: str


class TransactionRowResponse(BaseModel):
    id: str
    source_txn_id: str
    account_id: str
    account_name: str | None = None
    customer_id: str
    amount: float | None = None
    counterparty: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    date: str | None = None


class CustomerSummaryResponse(BaseModel):
    customer_id: str
    first_name: str
    last_name: str
    city: str | None = None
    state: str | None = None


class AccountDetailResponse(BaseModel):
    account_id: str
    name: str | None = None
    bank: str | None = None
    type: str | None = None
    date_opened: str | None = None


class CustomerDetailResponse(BaseModel):
    customer_id: str
    first_name: str
    last_name: str
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    accounts: list[AccountDetailResponse] = []


class AccountResponse(BaseModel):
    account_id: str
    name: str | None = None
    bank: str | None = None
    type: str | None = None
    date_opened: str | None = None
    customer_id: str


class PendingSARResponse(BaseModel):
    sar_id: str
    transaction_id: str
    upload_id: str
    source_txn_id: str | None = None
    account_id: str | None = None
    customer_id: str | None = None
    customer_first_name: str | None = None
    customer_last_name: str | None = None
    amount: float | None = None
    counterparty: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    date: str | None = None
    flag_details: dict | None = None
    risk_level: str | None = None
    triage_reasoning: str | None = None
    llm_confidence: float | None = None
    triage_stage: str | None = None
    enrichment: dict | None = None
    rule_name: str | None = None
    rule_description: str | None = None
    sar_content: str
    sar_status: str
    created_at: str | None = None


class GenerateStep(BaseModel):
    type: str
    count: int = 100
    bad_rate: int = 0

class GenerateRequest(BaseModel):
    steps: list[GenerateStep] = [GenerateStep(type="upload")]
    shuffle: bool = True
    date: str | None = None

class GenerateResponse(BaseModel):
    download_url: str
    filename: str
    eval_url: str | None = None


class EvalEntry(BaseModel):
    source_txn_id: str
    scenario: str = ""
    expected_escalate: bool = True
    ground_truth: str = ""
    reason_hint: str = ""


class PatternMetricsResponse(BaseModel):
    pattern: str
    total: int = 0
    flagged: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0


class HallucinationResultResponse(BaseModel):
    sar_id: str
    transaction_id: str
    hallucinated_facts: list[str] = []
    passed: bool = True


class CompletenessResultResponse(BaseModel):
    sar_id: str
    transaction_id: str
    covered_rules: list[str] = []
    missed_rules: list[str] = []
    score: float = 1.0


class EvalReportResponse(BaseModel):
    upload_id: str
    total_transactions: int = 0
    total_anomalous: int = 0
    total_flagged: int = 0
    pattern_metrics: list[PatternMetricsResponse] = []
    hallucination_results: list[HallucinationResultResponse] = []
    completeness_results: list[CompletenessResultResponse] = []
    overall_precision: float = 0.0
    overall_recall: float = 0.0
    overall_f1: float = 0.0
    hallucination_free_rate: float = 1.0
    avg_completeness: float = 1.0
