from __future__ import annotations

import json
from typing import Any

from src.bff.logger import logger

from google.genai import types
from google.genai.errors import APIError

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
from src.bff.config import get_llm_timeout

from . import LLMProvider


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        model_triage: str,
        model_sar: str,
        gemini_client: Any,
    ) -> None:
        self._triage_model = model_triage
        self._sar_model = model_sar
        self._gemini = gemini_client

    async def triage(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        rules: list[dict] | None = None,
        enriched_context: dict | None = None,
    ) -> TriageDecision:
        system, user = _build_triage_messages(transaction, flag_details, rules, enriched_context)
        logger.info("Gemini triage: model=%s, txn=%s", self._triage_model, transaction.get("source_txn_id", "N/A"))
        try:
            resp = await self._gemini.aio.models.generate_content(
                model=self._triage_model,
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
                timeout=get_llm_timeout(),
            )
        except APIError as e:
            logger.error("Gemini triage API call failed: %s", e)
            return _triage_fallback(transaction, flag_details, rules)
        try:
            data = json.loads(resp.text)
            return TriageDecision(**data, raw_response=resp.text)
        except (json.JSONDecodeError, AttributeError, KeyError, TypeError, ValueError) as e:
            logger.error("Gemini triage parsing failed: %s", e)
            return _triage_fallback(transaction, flag_details, rules)

    async def triage_stage3(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        recent_txns: list[dict],
        rules: list[dict] | None = None,
        enriched_context: dict | None = None,
    ) -> TriageDecision:
        system, user = _build_triage_stage3_messages(transaction, flag_details, recent_txns, rules, enriched_context)
        logger.info("Gemini stage3: model=%s, txn=%s", self._triage_model, transaction.get("source_txn_id", "N/A"))
        try:
            resp = await self._gemini.aio.models.generate_content(
                model=self._triage_model,
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
                timeout=get_llm_timeout(),
            )
        except APIError as e:
            logger.error("Gemini stage3 API call failed: %s", e)
            return _triage_fallback(transaction, flag_details, rules)
        try:
            data = json.loads(resp.text)
            return TriageDecision(**data, raw_response=resp.text)
        except (json.JSONDecodeError, AttributeError, KeyError, TypeError, ValueError) as e:
            logger.error("Gemini stage3 triage parsing failed: %s", e)
            return _triage_fallback(transaction, flag_details, rules)

    async def generate_sar(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        triage: TriageDecision,
        enriched_context: dict | None = None,
    ) -> SarResult:
        prompt = _build_sar_prompt(transaction, flag_details, triage, enriched_context)
        logger.info("Gemini SAR: model=%s, txn=%s", self._sar_model, transaction.get("source_txn_id", "N/A"))
        try:
            resp = await self._gemini.aio.models.generate_content(
                model=self._sar_model,
                contents=prompt,
                timeout=get_llm_timeout(),
            )
        except APIError as e:
            logger.error("Gemini SAR API call failed: %s", e)
            return _sar_fallback(transaction, flag_details, triage)
        content = resp.text or ""
        result = SarResult(content=content, raw_response=resp.text)
        return _validate_sar_content(result, transaction)

    async def triage_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        rules: list[dict] | None = None,
        enriched_context_list: list[dict | None] | None = None,
    ) -> list[TriageDecision]:
        system, user = _build_triage_batch_messages(transactions, flag_details_list, rules, enriched_context_list)
        logger.info("Gemini triage batch: model=%s, n=%d", self._triage_model, len(transactions))
        try:
            resp = await self._gemini.aio.models.generate_content(
                model=self._triage_model,
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
                timeout=get_llm_timeout(),
            )
            return _parse_triage_batch_response(resp.text, transactions)
        except (APIError, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.error("Gemini triage batch failed: %s", e)
            return _triage_fallback_batch(transactions, flag_details_list, rules, enriched_context_list)

    async def triage_stage3_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        recent_txns_list: list[list[dict]],
        rules: list[dict] | None = None,
        enriched_context_list: list[dict | None] | None = None,
    ) -> list[TriageDecision]:
        system, user = _build_triage_stage3_batch_messages(transactions, flag_details_list, recent_txns_list, rules, enriched_context_list)
        logger.info("Gemini stage3 batch: model=%s, n=%d", self._triage_model, len(transactions))
        try:
            resp = await self._gemini.aio.models.generate_content(
                model=self._triage_model,
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
                timeout=get_llm_timeout(),
            )
            return _parse_triage_batch_response(resp.text, transactions)
        except (APIError, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.error("Gemini stage3 triage batch failed: %s", e)
            return _triage_fallback_batch(transactions, flag_details_list, rules)

    async def generate_sar_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        triage_list: list[TriageDecision],
        enriched_context_list: list[dict | None] | None = None,
    ) -> list[SarResult]:
        prompt = _build_sar_batch_prompt(transactions, flag_details_list, triage_list, enriched_context_list)
        logger.info("Gemini SAR batch: model=%s, n=%d", self._sar_model, len(transactions))
        try:
            resp = await self._gemini.aio.models.generate_content(
                model=self._sar_model,
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
                timeout=get_llm_timeout(),
            )
            results = _parse_sar_batch_response(resp.text, transactions, flag_details_list, triage_list)
            return [_validate_sar_content(r, t) for r, t in zip(results, transactions)]
        except (APIError, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.error("Gemini SAR batch failed: %s", e)
            return _sar_fallback_batch(transactions, flag_details_list, triage_list)
