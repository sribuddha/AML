from __future__ import annotations

import json
import re
from typing import Any

from src.bff.logger import logger
from src.bff.config import get_anonymize_llm_data
from src.aml_workflow.types import TriageDecision, SarResult, _DATA_DISCLAIMER, _pick
from src.aml_workflow.fallbacks import _triage_fallback_batch, _sar_fallback_batch, _fmt_location
from src.aml_workflow.prompts.loader import (
    get_triage_stage2_system,
    get_triage_stage3_system,
    render_triage_user,
)


def _mask_sensitive_fields(txn: dict) -> dict:
    masked = dict(txn)
    masked["counterparty"] = "[REDACTED]"
    return masked


def _build_txn_json_block(
    transaction: dict,
    flag_details: dict[str, str],
    rules: list[dict] | None = None,
    recent_txns: list[dict] | None = None,
    enriched_context: dict | None = None,
) -> str:
    if get_anonymize_llm_data():
        transaction = _mask_sensitive_fields(transaction)
        if recent_txns is not None:
            recent_txns = [_mask_sensitive_fields(t) for t in recent_txns]

    data: dict[str, Any] = {
        "transaction": {
            **_pick(transaction, "source_txn_id", "account_id", "customer_id", "counterparty", "date"),
            "amount": transaction.get("amount", 0) or 0,
            "location": _fmt_location(transaction),
        },
        "flagged_rules": [
            {"id": r_id, "name": r_name}
            for r_id, r_name in flag_details.items()
        ],
    }
    if enriched_context:
        data["enriched_context"] = _pick(
            enriched_context,
            "customer_txn_count_30d", "customer_sum_30d", "customer_avg_30d",
            "customer_std_amt_30d", "account_type", "account_age_days",
            "structuring_24h_count", "velocity_zscore", "dormancy_days",
        )
    if recent_txns is not None:
        data["recent_transaction_history"] = [
            {
                **_pick(t, "counterparty", "date"),
                "amount": t.get("amount", 0) or 0,
                "location": _fmt_location(t),
            }
            for t in recent_txns
        ]
    return f"```json\n{json.dumps(data, indent=2)}\n```"


def _build_triage_messages(
    transaction: dict,
    flag_details: dict[str, str],
    rules: list[dict] | None,
    enriched_context: dict | None = None,
) -> tuple[str, str]:
    system_prompt = get_triage_stage2_system()
    user_prompt = (
        render_triage_user()
        + "\n\n" + _DATA_DISCLAIMER + "\n\n"
        + _build_txn_json_block(transaction, flag_details, rules, enriched_context=enriched_context)
    )
    return system_prompt, user_prompt


def _build_triage_stage3_messages(
    transaction: dict,
    flag_details: dict[str, str],
    recent_txns: list[dict],
    rules: list[dict] | None,
) -> tuple[str, str]:
    system_prompt = get_triage_stage3_system()
    user_prompt = (
        render_triage_user()
        + "\n\n" + _DATA_DISCLAIMER + " and recent customer history.\n\n"
        + _build_txn_json_block(transaction, flag_details, rules, recent_txns=recent_txns)
    )
    return system_prompt, user_prompt


def _build_sar_prompt(transaction: dict, flag_details: dict[str, str], triage: TriageDecision) -> str:
    return (
        "Generate a Suspicious Activity Report (SAR) for the transaction below.\n\n"
        + _DATA_DISCLAIMER + "\n\n"
        + _build_txn_json_block(transaction, flag_details)
        + f"\n\nEscalation Reason: {triage.reason}\n"
        f"Flagged Rules: {', '.join(flag_details.values()) if flag_details else 'None'}\n\n"
        "Write a detailed SAR narrative. Mention each flagged rule by name and explain why "
        "the transaction triggered it. Use ONLY the numbers and facts provided above "
        "— do not invent amounts, values, or account numbers."
    )


def _validate_sar_content(sar_result: SarResult, transaction: dict) -> SarResult:
    actual_amount = transaction.get("amount", 0) or 0
    threshold = actual_amount * 2.0

    extracted: set[str] = set()
    for match in re.finditer(r"\$[\d,]+(?:\.\d{2})?", sar_result.content):
        raw = match.group()
        cleaned = raw.replace("$", "").replace(",", "")
        try:
            val = float(cleaned)
            if val > threshold and abs(val - actual_amount) > 0.01:
                extracted.add(raw)
        except ValueError:
            continue

    if extracted:
        warning = (
            f"\n\n[SYSTEM NOTE: SAR contains amounts "
            f"({', '.join(sorted(extracted))}) that exceed 2x the "
            f"actual transaction amount (${actual_amount:,.2f}). "
            f"These may be hallucinated and should be verified.]"
        )
        logger.warning(
            "SAR amount hallucination detected: txn=%s, amounts=%s vs actual=%.2f",
            transaction.get("source_txn_id", "N/A"),
            sorted(extracted),
            actual_amount,
        )
        return SarResult(content=sar_result.content + warning, raw_response=sar_result.raw_response)

    return sar_result


def _chunk(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _build_triage_batch_item(
    idx: int,
    transaction: dict,
    flag_details: dict[str, str],
    enriched_context: dict | None = None,
) -> str:
    parts = [
        f"Transaction {idx}:",
        _DATA_DISCLAIMER,
        _build_txn_json_block(transaction, flag_details, enriched_context=enriched_context),
    ]
    return "\n\n".join(parts)


def _build_triage_stage3_batch_item(
    idx: int,
    transaction: dict,
    flag_details: dict[str, str],
    recent_txns: list[dict],
) -> str:
    parts = [
        f"Transaction {idx}:",
        _DATA_DISCLAIMER + " and recent customer history.",
        _build_txn_json_block(transaction, flag_details, recent_txns=recent_txns),
    ]
    return "\n\n".join(parts)


def _build_triage_batch_messages(
    transactions: list[dict],
    flag_details_list: list[dict],
    rules: list[dict] | None,
    enriched_context_list: list[dict | None] | None,
) -> tuple[str, str]:
    system = get_triage_stage2_system()
    blocks: list[str] = ["Review each flagged transaction below and determine if it requires escalation for manual review.\n"]
    for i, (txn, fd) in enumerate(zip(transactions, flag_details_list), 1):
        ec = enriched_context_list[i - 1] if enriched_context_list else None
        blocks.append(_build_triage_batch_item(i, txn, fd, ec))
    blocks.append(
        '\nRespond with ONLY a valid JSON object containing a "decisions" array '
        'with one entry per transaction in the same order:\n'
        '{"decisions": [{"source_txn_id": "...", "escalate": true, "reason": "...", "confidence": 0.0}, ...]}'
    )
    return system, "\n\n".join(blocks)


def _build_triage_stage3_batch_messages(
    transactions: list[dict],
    flag_details_list: list[dict],
    recent_txns_list: list[list[dict]],
    rules: list[dict] | None,
) -> tuple[str, str]:
    system = get_triage_stage3_system()
    blocks: list[str] = ["Review each escalated transaction below for deeper analysis with recent transaction history.\n"]
    for i, (txn, fd, recent) in enumerate(zip(transactions, flag_details_list, recent_txns_list), 1):
        blocks.append(_build_triage_stage3_batch_item(i, txn, fd, recent))
    blocks.append(
        '\nRespond with ONLY a valid JSON object containing a "decisions" array '
        'with one entry per transaction in the same order:\n'
        '{"decisions": [{"source_txn_id": "...", "escalate": true, "reason": "...", "confidence": 0.0}, ...]}'
    )
    return system, "\n\n".join(blocks)


def _build_sar_batch_prompt(
    transactions: list[dict],
    flag_details_list: list[dict],
    triage_list: list[TriageDecision],
) -> str:
    blocks: list[str] = ["Generate a Suspicious Activity Report for each escalated transaction below.\n"]
    for i, (txn, fd, td) in enumerate(zip(transactions, flag_details_list, triage_list), 1):
        blocks.append(
            f"Transaction {i}:\n\n"
            + _DATA_DISCLAIMER + "\n\n"
            + _build_txn_json_block(txn, fd)
            + f"\n\nEscalation Reason: {td.reason}\n"
            f"Flagged Rules: {', '.join(fd.values()) if fd else 'None'}"
        )
    n = len(transactions)
    blocks.append(
        f'\nYou must generate exactly {n} SAR{"s" if n != 1 else ""} — '
        f'one for each Transaction listed above. '
        f'Respond with ONLY a valid JSON object containing a "sars" array '
        f'with one entry per transaction in the same order:\n'
        f'{{"sars": [{{"source_txn_id": "...", "content": "Full SAR narrative..."}}, ...]}}\n'
        "In each SAR narrative, mention every flagged rule by name and explain why the transaction triggered it. "
        "Use ONLY the numbers and facts provided above for each transaction — do not invent amounts, values, or account numbers."
    )
    return "\n\n".join(blocks)


def _parse_triage_batch_response(raw: str | None, transactions: list[dict]) -> list[TriageDecision]:
    data = json.loads(raw or "{}")
    decisions = data.get("decisions", [])
    if len(decisions) != len(transactions):
        raise ValueError(f"Expected {len(transactions)} decisions, got {len(decisions)}")
    for i, (d, txn) in enumerate(zip(decisions, transactions)):
        if d.get("source_txn_id") != txn.get("source_txn_id"):
            raise ValueError(f"source_txn_id mismatch at index {i}")
        d.pop("source_txn_id", None)
    return [TriageDecision(**d, raw_response=json.dumps(d)) for d in decisions]


def _parse_sar_batch_response(
    raw: str | None,
    transactions: list[dict],
    flag_details_list: list[dict],
    triage_list: list[TriageDecision],
) -> list[SarResult]:
    data = json.loads(raw or "{}")
    sars = data.get("sars", [])
    if len(sars) != len(transactions):
        raise ValueError(f"Expected {len(transactions)} sars, got {len(sars)}")
    for i, (d, txn) in enumerate(zip(sars, transactions)):
        if d.get("source_txn_id") != txn.get("source_txn_id"):
            raise ValueError(f"source_txn_id mismatch at index {i}")
    return [SarResult(content=s.get("content", ""), raw_response=json.dumps(s)) for s in sars]
