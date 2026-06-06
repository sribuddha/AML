from __future__ import annotations

import asyncio

from src.bff.logger import logger
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
    get_llm_budget,
)
from src.aml_workflow.types import TriageDecision, SarResult
from src.aml_workflow.prompts.builders import (
    _build_triage_messages,
    _build_triage_stage3_messages,
    _build_sar_prompt,
    _build_triage_batch_messages,
    _build_triage_stage3_batch_messages,
    _build_sar_batch_prompt,
    _chunk,
)
from src.aml_workflow.fallbacks import (
    _triage_fallback,
    _sar_fallback,
    _triage_fallback_batch,
    _sar_fallback_batch,
)


# ── Cost estimation ───────────────────────────────────────────

_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
}

_OUTPUT_ESTIMATES: dict[str, int] = {
    "triage": 100,
    "stage3": 100,
    "sar": 400,
    "triage_batch": 50,
    "stage3_batch": 50,
    "sar_batch": 300,
}


def _estimate_call_cost(
    model: str,
    input_chars: int,
    call_type: str,
    n_items: int = 1,
) -> float:
    pricing = _MODEL_PRICING.get(model, {"input": 2.50, "output": 10.00})
    input_tokens = input_chars / 3.5
    per_item_output = _OUTPUT_ESTIMATES.get(call_type, 200)
    output_tokens = per_item_output * n_items
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


# ── LLM Client ────────────────────────────────────────────────


class LLMClient:
    def __init__(self) -> None:
        self.provider = get_llm_provider()
        self.triage_model = get_llm_model_triage()
        self.sar_model = get_llm_model_sar()
        self._budget = get_llm_budget()
        self._total_cost = 0.0
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
            from src.core.observability import wrap_gemini_client
            return GeminiProvider(
                model_triage=self.triage_model,
                model_sar=self.sar_model,
                gemini_client=wrap_gemini_client(genai.Client(api_key=gemini_key)),
            )

        logger.warning(
            "No LLM client initialized — provider=%s, openai_key=%s, gemini_key=%s",
            self.provider,
            "set" if openai_key else "missing",
            "set" if gemini_key else "missing",
        )
        return FallbackProvider()

    def _check_budget(self, estimated_cost: float) -> bool:
        if self._budget <= 0:
            return True
        return (self._total_cost + estimated_cost) <= self._budget

    async def triage(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        rules: list[dict] | None = None,
        enriched_context: dict | None = None,
    ) -> TriageDecision:
        system, user = _build_triage_messages(transaction, flag_details, rules, enriched_context)
        estimated = _estimate_call_cost(self.triage_model, len(system) + len(user), "triage")
        if not self._check_budget(estimated):
            logger.warning("LLM budget exceeded for triage — using fallback")
            return _triage_fallback(transaction, flag_details, rules, enriched_context)
        result = await self._provider.triage(transaction, flag_details, rules, enriched_context)
        self._total_cost += estimated
        return result

    async def triage_stage3(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        recent_txns: list[dict],
        rules: list[dict] | None = None,
    ) -> TriageDecision:
        system, user = _build_triage_stage3_messages(transaction, flag_details, recent_txns, rules)
        estimated = _estimate_call_cost(self.triage_model, len(system) + len(user), "stage3")
        if not self._check_budget(estimated):
            logger.warning("LLM budget exceeded for stage3 — using fallback")
            return _triage_fallback(transaction, flag_details, rules)
        result = await self._provider.triage_stage3(transaction, flag_details, recent_txns, rules)
        self._total_cost += estimated
        return result

    async def generate_sar(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        triage: TriageDecision,
    ) -> SarResult:
        prompt = _build_sar_prompt(transaction, flag_details, triage)
        estimated = _estimate_call_cost(self.sar_model, len(prompt), "sar")
        if not self._check_budget(estimated):
            logger.warning("LLM budget exceeded for SAR — using fallback")
            return _sar_fallback(transaction, flag_details, triage)
        result = await self._provider.generate_sar(transaction, flag_details, triage)
        self._total_cost += estimated
        return result

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
                system, user = _build_triage_batch_messages(
                    list(txns), list(flags), rules, list(enrichments),
                )
                estimated = _estimate_call_cost(
                    self.triage_model,
                    len(system) + len(user),
                    "triage_batch",
                    n_items=len(txns),
                )
                if not self._check_budget(estimated):
                    logger.warning("LLM budget exceeded for triage batch — using fallback")
                    return _triage_fallback_batch(list(txns), list(flags), rules, list(enrichments))
                decisions = await self._provider.triage_batch(
                    list(txns), list(flags), rules, list(enrichments),
                )
                self._total_cost += estimated
                return decisions

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
                system, user = _build_triage_stage3_batch_messages(
                    list(txns), list(flags), list(recent), rules,
                )
                estimated = _estimate_call_cost(
                    self.triage_model,
                    len(system) + len(user),
                    "stage3_batch",
                    n_items=len(txns),
                )
                if not self._check_budget(estimated):
                    logger.warning("LLM budget exceeded for stage3 batch — using fallback")
                    return _triage_fallback_batch(list(txns), list(flags), rules)
                decisions = await self._provider.triage_stage3_batch(
                    list(txns), list(flags), list(recent), rules,
                )
                self._total_cost += estimated
                return decisions

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
                prompt = _build_sar_batch_prompt(list(txns), list(flags), list(triages))
                estimated = _estimate_call_cost(
                    self.sar_model,
                    len(prompt),
                    "sar_batch",
                    n_items=len(txns),
                )
                if not self._check_budget(estimated):
                    logger.warning("LLM budget exceeded for SAR batch — using fallback")
                    return _sar_fallback_batch(list(txns), list(flags), list(triages))
                results = await self._provider.generate_sar_batch(
                    list(txns), list(flags), list(triages),
                )
                self._total_cost += estimated
                return results

        for chunk in chunks:
            results = await _run_chunk(chunk)
            all_results.extend(results)
        return all_results
