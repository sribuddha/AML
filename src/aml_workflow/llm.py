from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from src.bff.logger import logger

from src.aml_workflow.prompts.loader import get_triage_stage2_system, get_triage_stage3_system, render_triage_user
from src.bff.config import (
    LLM_PROVIDER,
    OPENAI_API_KEY,
    GEMINI_API_KEY,
    LLM_MODEL_TRIAGE,
    LLM_MODEL_SAR,
    STAGE2_BATCH_SIZE,
    STAGE3_BATCH_SIZE,
    SAR_BATCH_SIZE,
    STAGE2_CONCURRENCY,
    STAGE3_CONCURRENCY,
    SAR_CONCURRENCY,
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


class LLMClient:
    """Abstraction over OpenAI / Gemini for triage and SAR generation.

    Falls back to rule-based defaults when no API key is configured.
    """

    def __init__(self) -> None:
        self.provider = LLM_PROVIDER
        self.triage_model = LLM_MODEL_TRIAGE
        self.sar_model = LLM_MODEL_SAR
        self._openai_client = None
        self._gemini_client = None
        self._init_client()

    def _init_client(self) -> None:
        if self.provider == "openai" and OPENAI_API_KEY:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        elif self.provider == "gemini" and GEMINI_API_KEY:
            from google import genai
            self._gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        if not self._openai_client and not self._gemini_client:
            logger.warning(
                "No LLM client initialized — provider=%s, openai_key=%s, gemini_key=%s",
                self.provider,
                "set" if OPENAI_API_KEY else "missing",
                "set" if GEMINI_API_KEY else "missing",
            )

    async def triage(self, transaction: dict, flag_details: dict[str, str], rules: list[dict] | None = None, enriched_context: dict | None = None) -> TriageDecision:
        if self._openai_client:
            return await self._triage_openai(transaction, flag_details, rules, enriched_context)
        if self._gemini_client:
            return await self._triage_gemini(transaction, flag_details, rules, enriched_context)
        logger.warning("LLM not configured — using fallback triage")
        return self._triage_fallback(transaction, flag_details, rules, enriched_context)

    async def triage_stage3(self, transaction: dict, flag_details: dict[str, str], recent_txns: list[dict], rules: list[dict] | None = None) -> TriageDecision:
        if self._openai_client:
            return await self._triage_stage3_openai(transaction, flag_details, recent_txns, rules)
        if self._gemini_client:
            return await self._triage_stage3_gemini(transaction, flag_details, recent_txns, rules)
        logger.warning("LLM not configured — using fallback triage stage3")
        return self._triage_fallback(transaction, flag_details, rules)

    async def generate_sar(self, transaction: dict, flag_details: dict[str, str], triage: TriageDecision) -> SarResult:
        if self._openai_client:
            return await self._sar_openai(transaction, flag_details, triage)
        if self._gemini_client:
            return await self._sar_gemini(transaction, flag_details, triage)
        logger.warning("LLM not configured — using fallback SAR")
        return self._sar_fallback(transaction, flag_details, triage)

    # ── Batch helpers ─────────────────────────────────────────────

    @staticmethod
    def _chunk(items: list, size: int) -> list[list]:
        return [items[i:i + size] for i in range(0, len(items), size)]

    def _build_triage_batch_item(self, idx: int, transaction: dict, flag_details: dict[str, str], enriched_context: dict | None = None) -> str:
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

    def _build_triage_stage3_batch_item(self, idx: int, transaction: dict, flag_details: dict[str, str], recent_txns: list[dict]) -> str:
        base = self._build_triage_batch_item(idx, transaction, flag_details)
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

    def _build_triage_batch_messages(self, transactions: list[dict], flag_details_list: list[dict], rules: list[dict] | None, enriched_context_list: list[dict | None] | None) -> tuple[str, str]:
        system = get_triage_stage2_system()
        blocks: list[str] = ["Review each flagged transaction below and determine if it requires escalation for manual review.\n"]
        for i, (txn, fd) in enumerate(zip(transactions, flag_details_list), 1):
            ec = enriched_context_list[i - 1] if enriched_context_list else None
            blocks.append(self._build_triage_batch_item(i, txn, fd, ec))
        blocks.append(
            '\nRespond with ONLY a valid JSON object containing a "decisions" array '
            'with one entry per transaction in the same order:\n'
            '{"decisions": [{"source_txn_id": "...", "escalate": true, "reason": "...", "confidence": 0.0}, ...]}'
        )
        return system, "\n\n".join(blocks)

    def _build_triage_stage3_batch_messages(self, transactions: list[dict], flag_details_list: list[dict], recent_txns_list: list[list[dict]], rules: list[dict] | None) -> tuple[str, str]:
        system = get_triage_stage3_system()
        blocks: list[str] = ["Review each escalated transaction below for deeper analysis with recent transaction history.\n"]
        for i, (txn, fd, recent) in enumerate(zip(transactions, flag_details_list, recent_txns_list), 1):
            blocks.append(self._build_triage_stage3_batch_item(i, txn, fd, recent))
        blocks.append(
            '\nRespond with ONLY a valid JSON object containing a "decisions" array '
            'with one entry per transaction in the same order:\n'
            '{"decisions": [{"source_txn_id": "...", "escalate": true, "reason": "...", "confidence": 0.0}, ...]}'
        )
        return system, "\n\n".join(blocks)

    def _build_sar_batch_prompt(self, transactions: list[dict], flag_details_list: list[dict], triage_list: list[TriageDecision]) -> str:
        blocks: list[str] = ["Generate a Suspicious Activity Report for each escalated transaction below.\n"]
        for i, (txn, fd, td) in enumerate(zip(transactions, flag_details_list, triage_list), 1):
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
                + "".join(f"    - {name}\n" for _, name in fd.items()) if fd else "    - None\n"
            )
        blocks.append(
            '\nRespond with ONLY a valid JSON object containing a "sars" array '
            'with one entry per transaction in the same order:\n'
            '{"sars": [{"source_txn_id": "...", "content": "Full SAR narrative..."}, ...]}\n'
            "Use ONLY the numbers and facts provided above for each transaction — do not invent amounts, values, or account numbers."
        )
        return "\n\n".join(blocks)

    # ── Public batch methods ──────────────────────────────────────

    async def triage_batch(self, transactions: list[dict], flag_details_list: list[dict], rules: list[dict] | None = None, enriched_context_list: list[dict | None] | None = None) -> list[TriageDecision]:
        chunks = self._chunk(list(zip(transactions, flag_details_list, enriched_context_list or [None] * len(transactions))), STAGE2_BATCH_SIZE)
        sem = asyncio.Semaphore(STAGE2_CONCURRENCY)
        all_decisions: list[TriageDecision] = []

        async def _run_chunk(chunk: list[tuple]) -> list[TriageDecision]:
            async with sem:
                txns, flags, enrichments = zip(*chunk)
                return await self._triage_batch_provider(list(txns), list(flags), rules, list(enrichments))

        for chunk in chunks:
            decisions = await _run_chunk(chunk)
            all_decisions.extend(decisions)
        return all_decisions

    async def triage_stage3_batch(self, transactions: list[dict], flag_details_list: list[dict], recent_txns_list: list[list[dict]], rules: list[dict] | None = None) -> list[TriageDecision]:
        chunks = self._chunk(list(zip(transactions, flag_details_list, recent_txns_list)), STAGE3_BATCH_SIZE)
        sem = asyncio.Semaphore(STAGE3_CONCURRENCY)
        all_decisions: list[TriageDecision] = []

        async def _run_chunk(chunk: list[tuple]) -> list[TriageDecision]:
            async with sem:
                txns, flags, recent = zip(*chunk)
                return await self._triage_stage3_batch_provider(list(txns), list(flags), list(recent), rules)

        for chunk in chunks:
            decisions = await _run_chunk(chunk)
            all_decisions.extend(decisions)
        return all_decisions

    async def generate_sar_batch(self, transactions: list[dict], flag_details_list: list[dict], triage_list: list[TriageDecision]) -> list[SarResult]:
        chunks = self._chunk(list(zip(transactions, flag_details_list, triage_list)), SAR_BATCH_SIZE)
        sem = asyncio.Semaphore(SAR_CONCURRENCY)
        all_results: list[SarResult] = []

        async def _run_chunk(chunk: list[tuple]) -> list[SarResult]:
            async with sem:
                txns, flags, triages = zip(*chunk)
                return await self._sar_batch_provider(list(txns), list(flags), list(triages))

        for chunk in chunks:
            results = await _run_chunk(chunk)
            all_results.extend(results)
        return all_results

    # ── Batch provider dispatch ───────────────────────────────────

    async def _triage_batch_provider(self, transactions: list[dict], flag_details_list: list[dict], rules: list[dict] | None, enriched_context_list: list[dict | None]) -> list[TriageDecision]:
        if self._openai_client:
            return await self._triage_openai_batch(transactions, flag_details_list, rules, enriched_context_list)
        if self._gemini_client:
            return await self._triage_gemini_batch(transactions, flag_details_list, rules, enriched_context_list)
        return self._triage_fallback_batch(transactions, flag_details_list, rules, enriched_context_list)

    async def _triage_stage3_batch_provider(self, transactions: list[dict], flag_details_list: list[dict], recent_txns_list: list[list[dict]], rules: list[dict] | None) -> list[TriageDecision]:
        if self._openai_client:
            return await self._triage_stage3_openai_batch(transactions, flag_details_list, recent_txns_list, rules)
        if self._gemini_client:
            return await self._triage_stage3_gemini_batch(transactions, flag_details_list, recent_txns_list, rules)
        return self._triage_fallback_batch(transactions, flag_details_list, rules)

    async def _sar_batch_provider(self, transactions: list[dict], flag_details_list: list[dict], triage_list: list[TriageDecision]) -> list[SarResult]:
        if self._openai_client:
            return await self._sar_openai_batch(transactions, flag_details_list, triage_list)
        if self._gemini_client:
            return await self._sar_gemini_batch(transactions, flag_details_list, triage_list)
        return self._sar_fallback_batch(transactions, flag_details_list, triage_list)

    # ── OpenAI batch ──────────────────────────────────────────────

    async def _triage_openai_batch(self, transactions: list[dict], flag_details_list: list[dict], rules: list[dict] | None, enriched_context_list: list[dict | None]) -> list[TriageDecision]:
        from openai import APIError
        system, user = self._build_triage_batch_messages(transactions, flag_details_list, rules, enriched_context_list)
        logger.info("OpenAI triage batch: model=%s, n=%d", self.triage_model, len(transactions))
        try:
            resp = await self._openai_client.chat.completions.create(
                model=self.triage_model,
                temperature=0,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "triage_batch",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "decisions": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "source_txn_id": {"type": "string"},
                                            "escalate": {"type": "boolean"},
                                            "reason": {"type": "string"},
                                            "confidence": {"type": "number"},
                                        },
                                        "required": ["source_txn_id", "escalate", "reason", "confidence"],
                                    },
                                },
                            },
                            "required": ["decisions"],
                        },
                    },
                },
            )
            return self._parse_triage_batch_response(resp.choices[0].message.content, transactions)
        except (APIError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("OpenAI triage batch failed: %s", e)
            return self._triage_fallback_batch(transactions, flag_details_list, rules, enriched_context_list)

    async def _triage_stage3_openai_batch(self, transactions: list[dict], flag_details_list: list[dict], recent_txns_list: list[list[dict]], rules: list[dict] | None) -> list[TriageDecision]:
        from openai import APIError
        system, user = self._build_triage_stage3_batch_messages(transactions, flag_details_list, recent_txns_list, rules)
        logger.info("OpenAI stage3 batch: model=%s, n=%d", self.triage_model, len(transactions))
        try:
            resp = await self._openai_client.chat.completions.create(
                model=self.triage_model,
                temperature=0,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "triage_stage3_batch",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "decisions": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "source_txn_id": {"type": "string"},
                                            "escalate": {"type": "boolean"},
                                            "reason": {"type": "string"},
                                            "confidence": {"type": "number"},
                                        },
                                        "required": ["source_txn_id", "escalate", "reason", "confidence"],
                                    },
                                },
                            },
                            "required": ["decisions"],
                        },
                    },
                },
            )
            return self._parse_triage_batch_response(resp.choices[0].message.content, transactions)
        except (APIError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("OpenAI stage3 triage batch failed: %s", e)
            return self._triage_fallback_batch(transactions, flag_details_list, rules)

    async def _sar_openai_batch(self, transactions: list[dict], flag_details_list: list[dict], triage_list: list[TriageDecision]) -> list[SarResult]:
        from openai import APIError
        prompt = self._build_sar_batch_prompt(transactions, flag_details_list, triage_list)
        logger.info("OpenAI SAR batch: model=%s, n=%d", self.sar_model, len(transactions))
        try:
            resp = await self._openai_client.chat.completions.create(
                model=self.sar_model,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "sar_batch",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "sars": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "source_txn_id": {"type": "string"},
                                            "content": {"type": "string"},
                                        },
                                        "required": ["source_txn_id", "content"],
                                    },
                                },
                            },
                            "required": ["sars"],
                        },
                    },
                },
            )
            return self._parse_sar_batch_response(resp.choices[0].message.content, transactions, flag_details_list, triage_list)
        except (APIError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("OpenAI SAR batch failed: %s", e)
            return self._sar_fallback_batch(transactions, flag_details_list, triage_list)

    # ── Gemini batch ──────────────────────────────────────────────

    async def _triage_gemini_batch(self, transactions: list[dict], flag_details_list: list[dict], rules: list[dict] | None, enriched_context_list: list[dict | None]) -> list[TriageDecision]:
        system, user = self._build_triage_batch_messages(transactions, flag_details_list, rules, enriched_context_list)
        logger.info("Gemini triage batch: model=%s, n=%d", self.triage_model, len(transactions))
        try:
            from google.genai import types
            resp = await self._gemini_client.aio.models.generate_content(
                model=self.triage_model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=types.Schema(
                        type="object",
                        properties={
                            "decisions": types.Schema(
                                type="array",
                                items=types.Schema(
                                    type="object",
                                    properties={
                                        "source_txn_id": types.Schema(type="string"),
                                        "escalate": types.Schema(type="boolean"),
                                        "reason": types.Schema(type="string"),
                                        "confidence": types.Schema(type="number"),
                                    },
                                    required=["source_txn_id", "escalate", "reason", "confidence"],
                                ),
                            ),
                        },
                        required=["decisions"],
                    ),
                ),
            )
            return self._parse_triage_batch_response(resp.text, transactions)
        except Exception as e:
            logger.error("Gemini triage batch failed: %s", e)
            return self._triage_fallback_batch(transactions, flag_details_list, rules, enriched_context_list)

    async def _triage_stage3_gemini_batch(self, transactions: list[dict], flag_details_list: list[dict], recent_txns_list: list[list[dict]], rules: list[dict] | None) -> list[TriageDecision]:
        system, user = self._build_triage_stage3_batch_messages(transactions, flag_details_list, recent_txns_list, rules)
        logger.info("Gemini stage3 batch: model=%s, n=%d", self.triage_model, len(transactions))
        try:
            from google.genai import types
            resp = await self._gemini_client.aio.models.generate_content(
                model=self.triage_model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=types.Schema(
                        type="object",
                        properties={
                            "decisions": types.Schema(
                                type="array",
                                items=types.Schema(
                                    type="object",
                                    properties={
                                        "source_txn_id": types.Schema(type="string"),
                                        "escalate": types.Schema(type="boolean"),
                                        "reason": types.Schema(type="string"),
                                        "confidence": types.Schema(type="number"),
                                    },
                                    required=["source_txn_id", "escalate", "reason", "confidence"],
                                ),
                            ),
                        },
                        required=["decisions"],
                    ),
                ),
            )
            return self._parse_triage_batch_response(resp.text, transactions)
        except Exception as e:
            logger.error("Gemini stage3 triage batch failed: %s", e)
            return self._triage_fallback_batch(transactions, flag_details_list, rules)

    async def _sar_gemini_batch(self, transactions: list[dict], flag_details_list: list[dict], triage_list: list[TriageDecision]) -> list[SarResult]:
        prompt = self._build_sar_batch_prompt(transactions, flag_details_list, triage_list)
        logger.info("Gemini SAR batch: model=%s, n=%d", self.sar_model, len(transactions))
        try:
            from google.genai import types
            resp = await self._gemini_client.aio.models.generate_content(
                model=self.sar_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=types.Schema(
                        type="object",
                        properties={
                            "sars": types.Schema(
                                type="array",
                                items=types.Schema(
                                    type="object",
                                    properties={
                                        "source_txn_id": types.Schema(type="string"),
                                        "content": types.Schema(type="string"),
                                    },
                                    required=["source_txn_id", "content"],
                                ),
                            ),
                        },
                        required=["sars"],
                    ),
                ),
            )
            return self._parse_sar_batch_response(resp.text, transactions, flag_details_list, triage_list)
        except Exception as e:
            logger.error("Gemini SAR batch failed: %s", e)
            return self._sar_fallback_batch(transactions, flag_details_list, triage_list)

    # ── Batch response parsing ────────────────────────────────────

    @staticmethod
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

    @staticmethod
    def _parse_sar_batch_response(raw: str | None, transactions: list[dict], flag_details_list: list[dict], triage_list: list[TriageDecision]) -> list[SarResult]:
        data = json.loads(raw or "{}")
        sars = data.get("sars", [])
        if len(sars) != len(transactions):
            raise ValueError(f"Expected {len(transactions)} sars, got {len(sars)}")
        for i, (d, txn) in enumerate(zip(sars, transactions)):
            if d.get("source_txn_id") != txn.get("source_txn_id"):
                raise ValueError(f"source_txn_id mismatch at index {i}")
        return [SarResult(content=s.get("content", ""), raw_response=json.dumps(s)) for s in sars]

    # ── Batch fallback ────────────────────────────────────────────

    def _triage_fallback_batch(self, transactions: list[dict], flag_details_list: list[dict], rules: list[dict] | None = None, enriched_context_list: list[dict | None] | None = None) -> list[TriageDecision]:
        return [self._triage_fallback(txn, fd, rules, ec) for txn, fd, ec in zip(transactions, flag_details_list, enriched_context_list or [None] * len(transactions))]

    def _sar_fallback_batch(self, transactions: list[dict], flag_details_list: list[dict], triage_list: list[TriageDecision]) -> list[SarResult]:
        return [self._sar_fallback(txn, fd, td) for txn, fd, td in zip(transactions, flag_details_list, triage_list)]

    # ── Prompt helpers ────────────────────────────────────────────

    def _build_rule_evidence(self, flag_details: dict[str, str], rules: list[dict] | None) -> str:
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

    def _build_triage_messages(self, transaction: dict, flag_details: dict[str, str], rules: list[dict] | None, enriched_context: dict | None = None) -> tuple[str, str]:
        rule_evidence = self._build_rule_evidence(flag_details, rules)
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

    def _build_triage_stage3_messages(self, transaction: dict, flag_details: dict[str, str], recent_txns: list[dict], rules: list[dict] | None) -> tuple[str, str]:
        rule_evidence = self._build_rule_evidence(flag_details, rules)
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

    # ── OpenAI ────────────────────────────────────────────────────

    async def _triage_stage3_openai(self, transaction: dict, flag_details: dict[str, str], recent_txns: list[dict], rules: list[dict] | None = None) -> TriageDecision:
        from openai import APIError

        system, user = self._build_triage_stage3_messages(transaction, flag_details, recent_txns, rules)
        logger.info("OpenAI stage3: model=%s, txn=%s", self.triage_model, transaction.get("source_txn_id", "N/A"))
        try:
            resp = await self._openai_client.chat.completions.create(
                model=self.triage_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "triage",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "escalate": {"type": "boolean"},
                                "reason": {"type": "string"},
                                "confidence": {"type": "number"},
                            },
                            "required": ["escalate", "reason", "confidence"],
                        },
                    },
                },
            )
            raw = resp.choices[0].message.content
            data = json.loads(raw)
            return TriageDecision(**data, raw_response=raw)
        except (APIError, json.JSONDecodeError, KeyError) as e:
            logger.error("OpenAI stage3 triage failed: %s", e)
            return self._triage_fallback(transaction, flag_details, rules)

    async def _triage_openai(self, transaction: dict, flag_details: dict[str, str], rules: list[dict] | None = None, enriched_context: dict | None = None) -> TriageDecision:
        from openai import APIError

        system, user = self._build_triage_messages(transaction, flag_details, rules, enriched_context)
        logger.info("OpenAI triage: model=%s, txn=%s", self.triage_model, transaction.get("source_txn_id", "N/A"))
        try:
            resp = await self._openai_client.chat.completions.create(
                model=self.triage_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "triage",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "escalate": {"type": "boolean"},
                                "reason": {"type": "string"},
                                "confidence": {"type": "number"},
                            },
                            "required": ["escalate", "reason", "confidence"],
                        },
                    },
                },
            )
            raw = resp.choices[0].message.content
            data = json.loads(raw)
            return TriageDecision(**data, raw_response=raw)
        except (APIError, json.JSONDecodeError, KeyError) as e:
            logger.error("OpenAI triage failed: %s", e)
            return self._triage_fallback(transaction, flag_details, rules)

    async def _sar_openai(self, transaction: dict, flag_details: dict[str, str], triage: TriageDecision) -> SarResult:
        from openai import APIError

        prompt = self._build_sar_prompt(transaction, flag_details, triage)
        logger.info("OpenAI SAR: model=%s, txn=%s", self.sar_model, transaction.get("source_txn_id", "N/A"))
        try:
            resp = await self._openai_client.chat.completions.create(
                model=self.sar_model,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            content = resp.choices[0].message.content or ""
            return SarResult(content=content, raw_response=content)
        except APIError as e:
            logger.error("OpenAI SAR generation failed: %s", e)
            return self._sar_fallback(transaction, flag_details, triage)

    # ── Gemini ────────────────────────────────────────────────────

    async def _triage_stage3_gemini(self, transaction: dict, flag_details: dict[str, str], recent_txns: list[dict], rules: list[dict] | None = None) -> TriageDecision:
        system, user = self._build_triage_stage3_messages(transaction, flag_details, recent_txns, rules)
        logger.info("Gemini stage3: model=%s, txn=%s", self.triage_model, transaction.get("source_txn_id", "N/A"))
        try:
            from google.genai import types
            resp = await self._gemini_client.aio.models.generate_content(
                model=self.triage_model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=types.Schema(
                        type="object",
                        properties={
                            "escalate": types.Schema(type="boolean"),
                            "reason": types.Schema(type="string"),
                            "confidence": types.Schema(type="number"),
                        },
                        required=["escalate", "reason", "confidence"],
                    ),
                ),
            )
            data = json.loads(resp.text)
            return TriageDecision(**data, raw_response=resp.text)
        except Exception as e:
            logger.error("Gemini stage3 triage failed: %s", e)
            return self._triage_fallback(transaction, flag_details, rules)

    async def _triage_gemini(self, transaction: dict, flag_details: dict[str, str], rules: list[dict] | None = None, enriched_context: dict | None = None) -> TriageDecision:
        system, user = self._build_triage_messages(transaction, flag_details, rules, enriched_context)
        logger.info("Gemini triage: model=%s, txn=%s", self.triage_model, transaction.get("source_txn_id", "N/A"))
        try:
            from google.genai import types
            resp = await self._gemini_client.aio.models.generate_content(
                model=self.triage_model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=types.Schema(
                        type="object",
                        properties={
                            "escalate": types.Schema(type="boolean"),
                            "reason": types.Schema(type="string"),
                            "confidence": types.Schema(type="number"),
                        },
                        required=["escalate", "reason", "confidence"],
                    ),
                ),
            )
            data = json.loads(resp.text)
            return TriageDecision(**data, raw_response=resp.text)
        except Exception as e:
            logger.error("Gemini triage failed: %s", e)
            return self._triage_fallback(transaction, flag_details, rules)

    async def _sar_gemini(self, transaction: dict, flag_details: dict[str, str], triage: TriageDecision) -> SarResult:
        prompt = self._build_sar_prompt(transaction, flag_details, triage)
        logger.info("Gemini SAR: model=%s, txn=%s", self.sar_model, transaction.get("source_txn_id", "N/A"))
        try:
            resp = await self._gemini_client.aio.models.generate_content(
                model=self.sar_model,
                contents=prompt,
            )
            content = resp.text or ""
            return SarResult(content=content, raw_response=resp.text)
        except Exception as e:
            logger.error("Gemini SAR generation failed: %s", e)
            return self._sar_fallback(transaction, flag_details, triage)

    # ── Fallbacks ─────────────────────────────────────────────────

    def _triage_fallback(self, transaction: dict, flag_details: dict[str, str], rules: list[dict] | None = None, enriched_context: dict | None = None) -> TriageDecision:
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

    def _sar_fallback(self, transaction: dict, flag_details: dict[str, str], triage: TriageDecision) -> SarResult:
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

    # ── Prompt builders ───────────────────────────────────────────

    def _build_sar_prompt(self, transaction: dict, flag_details: dict[str, str], triage: TriageDecision) -> str:
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
