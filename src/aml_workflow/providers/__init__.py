from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from src.bff.logger import logger

from src.aml_workflow.types import TriageDecision, SarResult
from src.aml_workflow.prompts.builders import (
    _build_triage_messages,
    _build_triage_stage3_messages,
    _build_sar_prompt,
    _build_triage_batch_messages,
    _build_triage_stage3_batch_messages,
    _build_sar_batch_prompt,
    _parse_triage_batch_response,
    _parse_sar_batch_response,
    _validate_sar_content,
)
from src.aml_workflow.fallbacks import (
    _triage_fallback,
    _sar_fallback,
    _triage_fallback_batch,
    _sar_fallback_batch,
)
from src.bff.config import get_llm_timeout, get_llm_budget


class LLMProvider(ABC):
    @abstractmethod
    async def triage(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        rules: list[dict] | None = None,
        enriched_context: dict | None = None,
    ) -> TriageDecision: ...

    @abstractmethod
    async def triage_stage3(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        recent_txns: list[dict],
        rules: list[dict] | None = None,
        enriched_context: dict | None = None,
    ) -> TriageDecision: ...

    @abstractmethod
    async def generate_sar(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        triage: TriageDecision,
        enriched_context: dict | None = None,
    ) -> SarResult: ...

    @abstractmethod
    async def triage_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        rules: list[dict] | None = None,
        enriched_context_list: list[dict | None] | None = None,
    ) -> list[TriageDecision]: ...

    @abstractmethod
    async def triage_stage3_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        recent_txns_list: list[list[dict]],
        rules: list[dict] | None = None,
        enriched_context_list: list[dict | None] | None = None,
    ) -> list[TriageDecision]: ...

    @abstractmethod
    async def generate_sar_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        triage_list: list[TriageDecision],
        enriched_context_list: list[dict | None] | None = None,
    ) -> list[SarResult]: ...


class FallbackProvider(LLMProvider):
    async def triage(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        rules: list[dict] | None = None,
        enriched_context: dict | None = None,
    ) -> TriageDecision:
        logger.warning("LLM not configured — using fallback triage")
        return _triage_fallback(transaction, flag_details, rules, enriched_context)

    async def triage_stage3(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        recent_txns: list[dict],
        rules: list[dict] | None = None,
        enriched_context: dict | None = None,
    ) -> TriageDecision:
        logger.warning("LLM not configured — using fallback triage stage3")
        return _triage_fallback(transaction, flag_details, rules)

    async def generate_sar(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        triage: TriageDecision,
        enriched_context: dict | None = None,
    ) -> SarResult:
        logger.warning("LLM not configured — using fallback SAR")
        return _sar_fallback(transaction, flag_details, triage)

    async def triage_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        rules: list[dict] | None = None,
        enriched_context_list: list[dict | None] | None = None,
    ) -> list[TriageDecision]:
        logger.warning("LLM not configured — using fallback triage batch")
        return _triage_fallback_batch(transactions, flag_details_list, rules, enriched_context_list)

    async def triage_stage3_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        recent_txns_list: list[list[dict]],
        rules: list[dict] | None = None,
        enriched_context_list: list[dict | None] | None = None,
    ) -> list[TriageDecision]:
        logger.warning("LLM not configured — using fallback stage3 batch")
        return _triage_fallback_batch(transactions, flag_details_list, rules)

    async def generate_sar_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        triage_list: list[TriageDecision],
        enriched_context_list: list[dict | None] | None = None,
    ) -> list[SarResult]:
        logger.warning("LLM not configured — using fallback SAR batch")
        return _sar_fallback_batch(transactions, flag_details_list, triage_list)


from .openai import OpenAIProvider  # noqa: E402
from .gemini import GeminiProvider  # noqa: E402
