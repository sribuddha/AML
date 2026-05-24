from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from src.aml_workflow.prompts.loader import get_triage_stage2_system, get_triage_stage3_system, render_triage_user
from src.bff.config import (
    LLM_PROVIDER,
    OPENAI_API_KEY,
    GEMINI_API_KEY,
    LLM_MODEL_TRIAGE,
    LLM_MODEL_SAR,
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

    async def triage(self, transaction: dict, flag_details: dict[str, str], rules: list[dict] | None = None, enriched_context: dict | None = None) -> TriageDecision:
        if self._openai_client:
            return await self._triage_openai(transaction, flag_details, rules, enriched_context)
        if self._gemini_client:
            return await self._triage_gemini(transaction, flag_details, rules, enriched_context)
        return self._triage_fallback(transaction, flag_details, rules, enriched_context)

    async def triage_stage3(self, transaction: dict, flag_details: dict[str, str], recent_txns: list[dict], rules: list[dict] | None = None) -> TriageDecision:
        if self._openai_client:
            return await self._triage_stage3_openai(transaction, flag_details, recent_txns, rules)
        if self._gemini_client:
            return await self._triage_stage3_gemini(transaction, flag_details, recent_txns, rules)
        return self._triage_fallback(transaction, flag_details, rules)

    async def generate_sar(self, transaction: dict, flag_details: dict[str, str], triage: TriageDecision) -> SarResult:
        if self._openai_client:
            return await self._sar_openai(transaction, flag_details, triage)
        if self._gemini_client:
            return await self._sar_gemini(transaction, flag_details, triage)
        return self._sar_fallback(transaction, flag_details, triage)

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
        try:
            resp = await self._openai_client.chat.completions.create(
                model=self.triage_model,
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
        except (APIError, json.JSONDecodeError, KeyError):
            return self._triage_fallback(transaction, flag_details, rules)

    async def _triage_openai(self, transaction: dict, flag_details: dict[str, str], rules: list[dict] | None = None, enriched_context: dict | None = None) -> TriageDecision:
        from openai import APIError

        system, user = self._build_triage_messages(transaction, flag_details, rules, enriched_context)
        try:
            resp = await self._openai_client.chat.completions.create(
                model=self.triage_model,
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
        except (APIError, json.JSONDecodeError, KeyError):
            return self._triage_fallback(transaction, flag_details, rules)

    async def _sar_openai(self, transaction: dict, flag_details: dict[str, str], triage: TriageDecision) -> SarResult:
        from openai import APIError

        prompt = self._build_sar_prompt(transaction, flag_details, triage)
        try:
            resp = await self._openai_client.chat.completions.create(
                model=self.sar_model,
                messages=[{"role": "user", "content": prompt}],
            )
            content = resp.choices[0].message.content or ""
            return SarResult(content=content, raw_response=content)
        except APIError:
            return self._sar_fallback(transaction, flag_details, triage)

    # ── Gemini ────────────────────────────────────────────────────

    async def _triage_stage3_gemini(self, transaction: dict, flag_details: dict[str, str], recent_txns: list[dict], rules: list[dict] | None = None) -> TriageDecision:
        system, user = self._build_triage_stage3_messages(transaction, flag_details, recent_txns, rules)
        try:
            from google.genai import types
            resp = self._gemini_client.models.generate_content(
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
        except Exception:
            return self._triage_fallback(transaction, flag_details, rules)

    async def _triage_gemini(self, transaction: dict, flag_details: dict[str, str], rules: list[dict] | None = None, enriched_context: dict | None = None) -> TriageDecision:
        system, user = self._build_triage_messages(transaction, flag_details, rules, enriched_context)
        try:
            from google.genai import types
            resp = self._gemini_client.models.generate_content(
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
        except Exception:
            return self._triage_fallback(transaction, flag_details, rules)

    async def _sar_gemini(self, transaction: dict, flag_details: dict[str, str], triage: TriageDecision) -> SarResult:
        prompt = self._build_sar_prompt(transaction, flag_details, triage)
        try:
            resp = self._gemini_client.models.generate_content(
                model=self.sar_model,
                contents=prompt,
            )
            content = resp.text or ""
            return SarResult(content=content, raw_response=resp.text)
        except Exception:
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
            f"Confidence: {triage.confidence:.2f}\n"
            f"Flagged Rules: {', '.join(flag_details.values()) if flag_details else 'None'}\n"
            f"\nProvide a detailed SAR describing the suspicious activity."
        )
