from __future__ import annotations

from typing import Any

from src.aml_workflow.types import TriageDecision, SarResult, _pick


def _fmt_location(txn: dict) -> str:
    city = txn.get("city") or ""
    state = txn.get("state") or ""
    country = txn.get("country") or ""
    parts = [p for p in [city, state, country] if p]
    return ", ".join(parts) if parts else "N/A"


def _build_rule_evidence(flag_details: dict[str, str], rules: list[dict] | None) -> str:
    if not flag_details:
        return "None"
    lines: list[str] = []
    for rule_id, rule_name in flag_details.items():
        severity = "medium"
        condition = ""
        if rules:
            rule_def = next((r for r in rules if r["id"] == rule_id), None)
            if rule_def:
                severity = rule_def.get("severity", "medium")
                if rule_def.get("rules_json"):
                    condition = f" — {rule_def['rules_json']}"
        lines.append(f"- {rule_name} (severity: {severity.upper()}){condition}")
    return "\n".join(lines)


def _triage_fallback(
    transaction: dict,
    flag_details: dict[str, str],
    rules: list[dict] | None = None,
    enriched_context: dict | None = None,
) -> TriageDecision:
    if flag_details:
        rule_names = ", ".join(flag_details.values())
        return TriageDecision(
            escalate=True,
            reason=f"Flagged by rule(s): {rule_names}",
            confidence=0.7,
            raw_response=f"FALLBACK: escalated by rule(s): {rule_names}",
        )
    return TriageDecision(
        escalate=False,
        reason="No rules triggered",
        confidence=0.1,
        raw_response="FALLBACK: no rules triggered",
    )


def _sar_fallback(transaction: dict, flag_details: dict[str, str], triage: TriageDecision) -> SarResult:
    t = _pick(transaction, "source_txn_id", "account_id", "counterparty", default="N/A")
    content = (
        f"Suspicious Activity Report\n"
        f"Transaction: {t['source_txn_id']}\n"
        f"Account: {t['account_id']}\n"
        f"Amount: ${(transaction.get('amount') or 0):,.2f}\n"
        f"Counterparty: {t['counterparty']}\n"
        f"Location: {_fmt_location(transaction)}\n"
        f"Risk Level: {'escalated' if triage.escalate else 'auto_reviewed'}\n"
        f"Reason: {triage.reason}\n"
        f"Confidence: {triage.confidence * 100:.0f}%\n"
        f"Flagged Rules: {', '.join(flag_details.values())}\n"
    )
    return SarResult(content=content, raw_response="FALLBACK: " + content[:100])


def _triage_fallback_batch(
    transactions: list[dict],
    flag_details_list: list[dict],
    rules: list[dict] | None = None,
    enriched_context_list: list[dict | None] | None = None,
) -> list[TriageDecision]:
    return [_triage_fallback(txn, fd, rules, ec)
            for txn, fd, ec in zip(transactions, flag_details_list,
                                   enriched_context_list or [None] * len(transactions))]


def _sar_fallback_batch(
    transactions: list[dict],
    flag_details_list: list[dict],
    triage_list: list[TriageDecision],
) -> list[SarResult]:
    return [_sar_fallback(txn, fd, td)
            for txn, fd, td in zip(transactions, flag_details_list, triage_list)]
