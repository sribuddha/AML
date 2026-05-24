from __future__ import annotations

from typing import Any, TypedDict


class WorkflowState(TypedDict):
    upload_id: str
    transactions: list[dict[str, Any]]
    rules: list[dict[str, Any]]
    results: list[dict[str, Any]]
    validated_at: str
    triage_results: dict[str, dict[str, str | bool | float]]  # {transaction_id: {escalate, reason, confidence}}
    enriched_data: dict[str, dict[str, Any]]  # {customer_id: EnrichedContext-as-dict}
    sars: list[dict[str, Any]]  # sar records to insert
    human_review_complete: bool  # set True after human review passes
