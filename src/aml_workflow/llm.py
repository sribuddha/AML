from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from src.bff.logger import logger

from src.aml_workflow.prompts.loader import get_triage_stage2_system, get_triage_stage3_system, render_triage_user
from src.bff.config import (
    get_llm_provider,
    get_openai_api_key,
    get_gemini_api_key,
    get_llm_model_triage,
    get_llm_model_sar,
    get_stage2_batch_size,
    get_stage3_batch_size,
    get_sar_batch_size,
    get_stage2_concurrency,
    get_stage3_concurrency,
    get_sar_concurrency,
)


def _fmt_location(txn: dict) -> str:
    city = txn.get("city") or ""
    state = txn.get("state") or ""
    country = txn.get("country") or ""
    parts = [p for p in [city, state, country] if p]
    return ", ".join(parts) if parts else "N/A"


@dataclass
class TriageDecision:
    escalate: bool
    reason: str
    confidence: float
    raw_response: str | None = None


@dataclass
class SarResult:
    content: str
    raw_response: str | None = None


# ── Prompt builders ──────────────────────────────────────────────

def _build_rule_evidence(flag_details: dict[str, str], rules: list[dict] | None) -> str:
    if not flag_details:
        return "None"
    lines: list[str] = []
    for rule_id, rule_name in flag_details.items():
        condition = ""
        if rules:
            rule_def = next((r for r in rules if r["id"] == rule_id), None)
            if rule_def and rule_def.get("rules_json"):
                condition = f" — {rule_def['rules_json']}"
        lines.append(f"- {rule_name}{condition}")
    return "\n".join(lines)


def _build_triage_messages(
    transaction: dict,
    flag_details: dict[str, str],
    rules: list[dict] | None,
    enriched_context: dict | None = None,
) -> tuple[str, str]:
    rule_evidence = _build_rule_evidence(flag_details, rules)
    system_prompt = get_triage_stage2_system()
    user_prompt = render_triage_user(
        source_txn_id=transaction.get("source_txn_id", "N/A"),
        account_id=transaction.get("account_id", "N/A"),
        customer_id=transaction.get("customer_id", "N/A"),
        amount=transaction.get("amount", 0) or 0,
        counterparty=transaction.get("counterparty", "N/A"),
        location=_fmt_location(transaction),
        date=transaction.get("date", "N/A"),
        rules_flagged=len(flag_details),
        rule_evidence=rule_evidence,
    )
    if enriched_context:
        from src.aml_workflow.enrichment import EnrichedContext, _format_context
        ctx = EnrichedContext(**enriched_context)
        user_prompt += f"\n\nCustomer enrichment:\n{_format_context(ctx)}"
    return system_prompt, user_prompt


def _build_triage_stage3_messages(
    transaction: dict,
    flag_details: dict[str, str],
    recent_txns: list[dict],
    rules: list[dict] | None,
) -> tuple[str, str]:
    rule_evidence = _build_rule_evidence(flag_details, rules)
    system_prompt = get_triage_stage3_system()

    history_lines = []
    for t in recent_txns:
        history_lines.append(
            f"- ${t.get('amount', 0):,.2f} | {t.get('counterparty', 'N/A')} | "
            f"{_fmt_location(t)} | {t.get('date', 'N/A')}"
        )
    history_text = "\n".join(history_lines) if history_lines else "No recent transactions found."

    user_prompt = render_triage_user(
        source_txn_id=transaction.get("source_txn_id", "N/A"),
        account_id=transaction.get("account_id", "N/A"),
        customer_id=transaction.get("customer_id", "N/A"),
        amount=transaction.get("amount", 0) or 0,
        counterparty=transaction.get("counterparty", "N/A"),
        location=_fmt_location(transaction),
        date=transaction.get("date", "N/A"),
        rules_flagged=len(flag_details),
        rule_evidence=rule_evidence,
    )
    user_prompt += f"\n\nRecent customer history:\n{history_text}"
    return system_prompt, user_prompt


def _build_sar_prompt(transaction: dict, flag_details: dict[str, str], triage: TriageDecision) -> str:
    return (
        f"Generate a Suspicious Activity Report for:\n"
        f"- Source TXN ID: {transaction.get('source_txn_id', 'N/A')}\n"
        f"- Account: {transaction.get('account_id', 'N/A')}\n"
        f"- Customer: {transaction.get('customer_id', 'N/A')}\n"
        f"- Amount: ${(transaction.get('amount') or 0):,.2f}\n"
        f"- Counterparty: {transaction.get('counterparty', 'N/A')}\n"
        f"- Location: {_fmt_location(transaction)}\n"
        f"- Date: {transaction.get('date', 'N/A')}\n"
        f"\nEscalation Reason: {triage.reason}\n"
        f"Flagged Rules: {', '.join(flag_details.values()) if flag_details else 'None'}\n"
        f"\nWrite a detailed SAR narrative. Use ONLY the numbers and facts provided above — do not invent amounts, values, or account numbers."
    )


# ── Batch builders ───────────────────────────────────────────────

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
        f"  Source TXN ID: {transaction.get('source_txn_id', 'N/A')}",
        f"  Account: {transaction.get('account_id', 'N/A')}",
        f"  Customer: {transaction.get('customer_id', 'N/A')}",
        f"  Amount: ${(transaction.get('amount') or 0):,.2f}",
        f"  Counterparty: {transaction.get('counterparty', 'N/A')}",
        f"  Location: {_fmt_location(transaction)}",
        f"  Date: {transaction.get('date', 'N/A')}",
        "  Flagged Rules:",
    ]
    if flag_details:
        for _, name in flag_details.items():
            parts.append(f"    - {name}")
    else:
        parts.append("    - None")
    if enriched_context:
        parts.append("  Customer Enrichment:")
        from src.aml_workflow.enrichment import EnrichedContext, _format_context
        ctx = EnrichedContext(**enriched_context)
        parts.append(f"    {_format_context(ctx).replace(chr(10), chr(10) + '    ')}")
    return "\n".join(parts)


def _build_triage_stage3_batch_item(
    idx: int,
    transaction: dict,
    flag_details: dict[str, str],
    recent_txns: list[dict],
) -> str:
    base = _build_triage_batch_item(idx, transaction, flag_details)
    history_lines = ["  Recent Transaction History:"]
    if recent_txns:
        for t in recent_txns:
            history_lines.append(
                f"    ${t.get('amount', 0):,.2f} | {t.get('counterparty', 'N/A')} | "
                f"{_fmt_location(t)} | {t.get('date', 'N/A')}"
            )
    else:
        history_lines.append("    No recent transactions found.")
    return base + "\n" + "\n".join(history_lines)


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
        fd_block = "".join(f"    - {name}\n" for _, name in fd.items()) if fd else "    - None\n"
        blocks.append(
            f"Transaction {i}:\n"
            f"  Source TXN ID: {txn.get('source_txn_id', 'N/A')}\n"
            f"  Account: {txn.get('account_id', 'N/A')}\n"
            f"  Customer: {txn.get('customer_id', 'N/A')}\n"
            f"  Amount: ${(txn.get('amount') or 0):,.2f}\n"
            f"  Counterparty: {txn.get('counterparty', 'N/A')}\n"
            f"  Location: {_fmt_location(txn)}\n"
            f"  Date: {txn.get('date', 'N/A')}\n"
            f"  Escalation Reason: {td.reason}\n"
            "  Flagged Rules:\n"
            f"{fd_block}"
        )
    blocks.append(
        '\nRespond with ONLY a valid JSON object containing a "sars" array '
        'with one entry per transaction in the same order:\n'
        '{"sars": [{"source_txn_id": "...", "content": "Full SAR narrative..."}, ...]}\n'
        "Use ONLY the numbers and facts provided above for each transaction — do not invent amounts, values, or account numbers."
    )
    return "\n\n".join(blocks)


# ── Batch response parsing ───────────────────────────────────────

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


# ── Fallbacks ────────────────────────────────────────────────────

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
    content = (
        f"Suspicious Activity Report\n"
        f"Transaction: {transaction.get('source_txn_id', 'N/A')}\n"
        f"Account: {transaction.get('account_id', 'N/A')}\n"
        f"Amount: ${(transaction.get('amount') or 0):,.2f}\n"
        f"Counterparty: {transaction.get('counterparty', 'N/A')}\n"
        f"Location: {_fmt_location(transaction)}\n"
        f"Risk Level: {'escalated' if triage.escalate else 'auto_reviewed'}\n"
        f"Reason: {triage.reason}\n"
        f"Confidence: {triage.confidence:.2f}\n"
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


class LLMClient:
    """Abstraction over OpenAI / Gemini for triage and SAR generation.

    Falls back to rule-based defaults when no API key is configured.
    """

    def __init__(self) -> None:
        self.provider = get_llm_provider()
        self.triage_model = get_llm_model_triage()
        self.sar_model = get_llm_model_sar()
        self._provider = self._init_provider()

    def _init_provider(self):
        from src.aml_workflow.providers import OpenAIProvider, GeminiProvider, FallbackProvider

        openai_key = get_openai_api_key()
        gemini_key = get_gemini_api_key()

        if self.provider == "openai" and openai_key:
            from openai import AsyncOpenAI
            raw_client = AsyncOpenAI(api_key=openai_key)
            from src.core.observability import wrap_openai_client
            return OpenAIProvider(
                model_triage=self.triage_model,
                model_sar=self.sar_model,
                openai_client=wrap_openai_client(raw_client),
            )

        if self.provider == "gemini" and gemini_key:
            from google import genai
            return GeminiProvider(
                model_triage=self.triage_model,
                model_sar=self.sar_model,
                gemini_client=genai.Client(api_key=gemini_key),
            )

        logger.warning(
            "No LLM client initialized — provider=%s, openai_key=%s, gemini_key=%s",
            self.provider,
            "set" if openai_key else "missing",
            "set" if gemini_key else "missing",
        )
        return FallbackProvider()

    async def triage(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        rules: list[dict] | None = None,
        enriched_context: dict | None = None,
    ) -> TriageDecision:
        return await self._provider.triage(transaction, flag_details, rules, enriched_context)

    async def triage_stage3(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        recent_txns: list[dict],
        rules: list[dict] | None = None,
    ) -> TriageDecision:
        return await self._provider.triage_stage3(transaction, flag_details, recent_txns, rules)

    async def generate_sar(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        triage: TriageDecision,
    ) -> SarResult:
        return await self._provider.generate_sar(transaction, flag_details, triage)

    async def triage_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        rules: list[dict] | None = None,
        enriched_context_list: list[dict | None] | None = None,
    ) -> list[TriageDecision]:
        chunks = _chunk(
            list(zip(transactions, flag_details_list,
                     enriched_context_list or [None] * len(transactions))),
            get_stage2_batch_size(),
        )
        sem = asyncio.Semaphore(get_stage2_concurrency())
        all_decisions: list[TriageDecision] = []

        async def _run_chunk(chunk: list[tuple]) -> list[TriageDecision]:
            async with sem:
                txns, flags, enrichments = zip(*chunk)
                return await self._provider.triage_batch(
                    list(txns), list(flags), rules, list(enrichments),
                )

        for chunk in chunks:
            decisions = await _run_chunk(chunk)
            all_decisions.extend(decisions)
        return all_decisions

    async def triage_stage3_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        recent_txns_list: list[list[dict]],
        rules: list[dict] | None = None,
    ) -> list[TriageDecision]:
        chunks = _chunk(
            list(zip(transactions, flag_details_list, recent_txns_list)),
            get_stage3_batch_size(),
        )
        sem = asyncio.Semaphore(get_stage3_concurrency())
        all_decisions: list[TriageDecision] = []

        async def _run_chunk(chunk: list[tuple]) -> list[TriageDecision]:
            async with sem:
                txns, flags, recent = zip(*chunk)
                return await self._provider.triage_stage3_batch(
                    list(txns), list(flags), list(recent), rules,
                )

        for chunk in chunks:
            decisions = await _run_chunk(chunk)
            all_decisions.extend(decisions)
        return all_decisions

    async def generate_sar_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        triage_list: list[TriageDecision],
    ) -> list[SarResult]:
        chunks = _chunk(
            list(zip(transactions, flag_details_list, triage_list)),
            get_sar_batch_size(),
        )
        sem = asyncio.Semaphore(get_sar_concurrency())
        all_results: list[SarResult] = []

        async def _run_chunk(chunk: list[tuple]) -> list[SarResult]:
            async with sem:
                txns, flags, triages = zip(*chunk)
                return await self._provider.generate_sar_batch(
                    list(txns), list(flags), list(triages),
                )

        for chunk in chunks:
            results = await _run_chunk(chunk)
            all_results.extend(results)
        return all_results
