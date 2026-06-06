from __future__ import annotations

import json
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
from src.bff.config import get_llm_timeout

from . import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        model_triage: str,
        model_sar: str,
        openai_client: Any,
    ) -> None:
        self._triage_model = model_triage
        self._sar_model = model_sar
        self._openai = openai_client

    async def triage(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        rules: list[dict] | None = None,
        enriched_context: dict | None = None,
    ) -> TriageDecision:
        from openai import APIError

        system, user = _build_triage_messages(transaction, flag_details, rules, enriched_context)
        logger.info("OpenAI triage: model=%s, txn=%s", self._triage_model, transaction.get("source_txn_id", "N/A"))
        try:
            resp = await self._openai.chat.completions.create(
                model=self._triage_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "triage",
                        "strict": True,
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
                timeout=get_llm_timeout(),
            )
            raw = resp.choices[0].message.content
            data = json.loads(raw)
            return TriageDecision(**data, raw_response=raw)
        except (APIError, json.JSONDecodeError, KeyError) as e:
            logger.error("OpenAI triage failed: %s", e)
            return _triage_fallback(transaction, flag_details, rules)

    async def triage_stage3(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        recent_txns: list[dict],
        rules: list[dict] | None = None,
    ) -> TriageDecision:
        from openai import APIError

        system, user = _build_triage_stage3_messages(transaction, flag_details, recent_txns, rules)
        logger.info("OpenAI stage3: model=%s, txn=%s", self._triage_model, transaction.get("source_txn_id", "N/A"))
        try:
            resp = await self._openai.chat.completions.create(
                model=self._triage_model,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "triage",
                        "strict": True,
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
                timeout=get_llm_timeout(),
            )
            raw = resp.choices[0].message.content
            data = json.loads(raw)
            return TriageDecision(**data, raw_response=raw)
        except (APIError, json.JSONDecodeError, KeyError) as e:
            logger.error("OpenAI stage3 failed: %s", e)
            return _triage_fallback(transaction, flag_details, rules)

    async def generate_sar(
        self,
        transaction: dict,
        flag_details: dict[str, str],
        triage: TriageDecision,
    ) -> SarResult:
        from openai import APIError

        prompt = _build_sar_prompt(transaction, flag_details, triage)
        logger.info("OpenAI SAR: model=%s, txn=%s", self._sar_model, transaction.get("source_txn_id", "N/A"))
        try:
            resp = await self._openai.chat.completions.create(
                model=self._sar_model,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
                timeout=get_llm_timeout(),
            )
            content = resp.choices[0].message.content or ""
            result = SarResult(content=content, raw_response=content)
            return _validate_sar_content(result, transaction)
        except APIError as e:
            logger.error("OpenAI SAR generation failed: %s", e)
            return _sar_fallback(transaction, flag_details, triage)

    async def triage_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        rules: list[dict] | None = None,
        enriched_context_list: list[dict | None] | None = None,
    ) -> list[TriageDecision]:
        from openai import APIError
        system, user = _build_triage_batch_messages(transactions, flag_details_list, rules, enriched_context_list)
        logger.info("OpenAI triage batch: model=%s, n=%d", self._triage_model, len(transactions))
        try:
            resp = await self._openai.chat.completions.create(
                model=self._triage_model,
                temperature=0,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "triage_batch",
                        "strict": True,
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
                timeout=get_llm_timeout(),
            )
            return _parse_triage_batch_response(resp.choices[0].message.content, transactions)
        except (APIError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("OpenAI triage batch failed: %s", e)
            return _triage_fallback_batch(transactions, flag_details_list, rules, enriched_context_list)

    async def triage_stage3_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        recent_txns_list: list[list[dict]],
        rules: list[dict] | None = None,
    ) -> list[TriageDecision]:
        from openai import APIError
        system, user = _build_triage_stage3_batch_messages(transactions, flag_details_list, recent_txns_list, rules)
        logger.info("OpenAI stage3 batch: model=%s, n=%d", self._triage_model, len(transactions))
        try:
            resp = await self._openai.chat.completions.create(
                model=self._triage_model,
                temperature=0,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "triage_stage3_batch",
                        "strict": True,
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
                timeout=get_llm_timeout(),
            )
            return _parse_triage_batch_response(resp.choices[0].message.content, transactions)
        except (APIError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("OpenAI stage3 triage batch failed: %s", e)
            return _triage_fallback_batch(transactions, flag_details_list, rules)

    async def generate_sar_batch(
        self,
        transactions: list[dict],
        flag_details_list: list[dict],
        triage_list: list[TriageDecision],
    ) -> list[SarResult]:
        from openai import APIError
        prompt = _build_sar_batch_prompt(transactions, flag_details_list, triage_list)
        logger.info("OpenAI SAR batch: model=%s, n=%d", self._sar_model, len(transactions))
        try:
            resp = await self._openai.chat.completions.create(
                model=self._sar_model,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "sar_batch",
                        "strict": True,
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
                timeout=get_llm_timeout(),
            )
            results = _parse_sar_batch_response(resp.choices[0].message.content, transactions, flag_details_list, triage_list)
            return [_validate_sar_content(r, t) for r, t in zip(results, transactions)]
        except (APIError, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("OpenAI SAR batch failed: %s", e)
            return _sar_fallback_batch(transactions, flag_details_list, triage_list)
