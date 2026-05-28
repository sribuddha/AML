import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.aml_workflow.llm import LLMClient, TriageDecision, SarResult


_TXN = {
    "id": "txn-001",
    "account_id": "ACC001",
    "customer_id": "CUST001",
    "amount": 15000.00,
    "counterparty": "Global Trading",
    "city": "London", "country": "GB",
    "date": "2026-05-15",
    "source_txn_id": "TXN001",
}

_FLAG = {"rule-1": "High Value Check", "rule-2": "Offshore Transaction"}


def _make_openai_client() -> LLMClient:
    c = LLMClient()
    c._openai_client = MagicMock()
    c._gemini_client = None
    return c


def _make_gemini_client() -> LLMClient:
    c = LLMClient()
    c._gemini_client = MagicMock()
    c._openai_client = None
    return c


# Set up mock for the openai module so that
# ``from openai import APIError`` inside the methods succeeds.
_MOCKED_API_ERROR = type("APIError", (Exception,), {})
_MOCK_OPENAI = MagicMock()
_MOCK_OPENAI.APIError = _MOCKED_API_ERROR


class TestOpenAITriage:
    _TRIAGE_RESP = json.dumps({"escalate": True, "reason": "High risk", "confidence": 0.88})

    @patch.dict("sys.modules", {"openai": _MOCK_OPENAI})
    async def test_triage_openai_returns_decision(self):
        c = _make_openai_client()
        mock_msg = MagicMock()
        mock_msg.content = self._TRIAGE_RESP
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        c._openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await c._triage_openai(_TXN, _FLAG)
        assert isinstance(result, TriageDecision)
        assert result.escalate is True
        assert result.reason == "High risk"
        assert result.confidence == 0.88
        assert result.raw_response == self._TRIAGE_RESP

    @patch.dict("sys.modules", {"openai": _MOCK_OPENAI})
    async def test_triage_openai_fallback_on_error(self):
        c = _make_openai_client()
        c._openai_client.chat.completions.create = AsyncMock(side_effect=_MOCKED_API_ERROR("API error"))

        result = await c._triage_openai(_TXN, _FLAG)
        assert isinstance(result, TriageDecision)
        assert result.escalate is True
        assert "High Value Check" in result.reason

    @patch.dict("sys.modules", {"openai": _MOCK_OPENAI})
    async def test_triage_openai_fallback_on_bad_json(self):
        c = _make_openai_client()
        mock_msg = MagicMock()
        mock_msg.content = "not valid json"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        c._openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await c._triage_openai(_TXN, _FLAG)
        assert isinstance(result, TriageDecision)
        assert result.escalate is True


class TestOpenAITriageStage3:
    _TRIAGE_RESP = json.dumps({"escalate": False, "reason": "Normal pattern", "confidence": 0.95})

    @patch.dict("sys.modules", {"openai": _MOCK_OPENAI})
    async def test_stage3_openai_returns_decision(self):
        c = _make_openai_client()
        mock_msg = MagicMock()
        mock_msg.content = self._TRIAGE_RESP
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        c._openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await c._triage_stage3_openai(_TXN, _FLAG, [])
        assert isinstance(result, TriageDecision)
        assert result.escalate is False
        assert result.reason == "Normal pattern"
        assert result.confidence == 0.95

    @patch.dict("sys.modules", {"openai": _MOCK_OPENAI})
    async def test_stage3_openai_fallback_on_error(self):
        c = _make_openai_client()
        c._openai_client.chat.completions.create = AsyncMock(side_effect=_MOCKED_API_ERROR("API error"))

        result = await c._triage_stage3_openai(_TXN, _FLAG, [])
        assert isinstance(result, TriageDecision)
        assert result.escalate is True


class TestOpenAISar:
    @patch.dict("sys.modules", {"openai": _MOCK_OPENAI})
    async def test_sar_openai_returns_result(self):
        c = _make_openai_client()
        mock_msg = MagicMock()
        mock_msg.content = "Generated SAR content here"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        c._openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        triage = TriageDecision(escalate=True, reason="Over 50k", confidence=0.9)
        result = await c._sar_openai(_TXN, _FLAG, triage)
        assert isinstance(result, SarResult)
        assert "Generated SAR content" in result.content
        assert result.raw_response == result.content

    @patch.dict("sys.modules", {"openai": _MOCK_OPENAI})
    async def test_sar_openai_fallback_on_error(self):
        c = _make_openai_client()
        c._openai_client.chat.completions.create = AsyncMock(side_effect=_MOCKED_API_ERROR("API error"))

        triage = TriageDecision(escalate=True, reason="Over 50k", confidence=0.9)
        result = await c._sar_openai(_TXN, _FLAG, triage)
        assert isinstance(result, SarResult)
        assert "TXN001" in result.content
        assert "Offshore Transaction" in result.content


class TestGeminiTriage:
    _TRIAGE_RESP = '{"escalate": true, "reason": "Flagged by rules", "confidence": 0.92}'

    async def test_triage_gemini_returns_decision(self):
        c = _make_gemini_client()
        mock_resp = MagicMock()
        mock_resp.text = self._TRIAGE_RESP
        c._gemini_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

        result = await c._triage_gemini(_TXN, _FLAG)
        assert isinstance(result, TriageDecision)
        assert result.escalate is True
        assert result.reason == "Flagged by rules"
        assert result.confidence == 0.92

    async def test_triage_gemini_fallback_on_error(self):
        c = _make_gemini_client()
        c._gemini_client.aio.models.generate_content = AsyncMock(side_effect=Exception("API error"))

        result = await c._triage_gemini(_TXN, _FLAG)
        assert isinstance(result, TriageDecision)
        assert result.escalate is True
        assert "High Value Check" in result.reason


class TestGeminiTriageStage3:
    _TRIAGE_RESP = '{"escalate": false, "reason": "Routine transaction", "confidence": 0.80}'

    async def test_stage3_gemini_returns_decision(self):
        c = _make_gemini_client()
        mock_resp = MagicMock()
        mock_resp.text = self._TRIAGE_RESP
        c._gemini_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

        result = await c._triage_stage3_gemini(_TXN, _FLAG, [])
        assert isinstance(result, TriageDecision)
        assert result.escalate is False
        assert result.reason == "Routine transaction"

    async def test_stage3_gemini_fallback_on_error(self):
        c = _make_gemini_client()
        c._gemini_client.aio.models.generate_content = AsyncMock(side_effect=Exception("API error"))

        result = await c._triage_stage3_gemini(_TXN, _FLAG, [])
        assert isinstance(result, TriageDecision)
        assert result.escalate is True


class TestGeminiSar:
    async def test_sar_gemini_returns_result(self):
        c = _make_gemini_client()
        mock_resp = MagicMock()
        mock_resp.text = "Gemini generated SAR report"
        c._gemini_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

        triage = TriageDecision(escalate=True, reason="High risk", confidence=0.9)
        result = await c._sar_gemini(_TXN, _FLAG, triage)
        assert isinstance(result, SarResult)
        assert "Gemini generated SAR report" in result.content
        assert result.raw_response == "Gemini generated SAR report"

    async def test_sar_gemini_fallback_on_error(self):
        c = _make_gemini_client()
        c._gemini_client.aio.models.generate_content = AsyncMock(side_effect=Exception("API error"))

        triage = TriageDecision(escalate=True, reason="High risk", confidence=0.9)
        result = await c._sar_gemini(_TXN, _FLAG, triage)
        assert isinstance(result, SarResult)
        assert "TXN001" in result.content
        assert "Offshore Transaction" in result.content


# ── Batch method helpers ────────────────────────────────────────


class TestChunk:
    def test_chunk_even(self):
        c = LLMClient()
        chunks = c._chunk([1, 2, 3, 4], 2)
        assert chunks == [[1, 2], [3, 4]]

    def test_chunk_uneven(self):
        c = LLMClient()
        chunks = c._chunk([1, 2, 3, 4, 5], 2)
        assert chunks == [[1, 2], [3, 4], [5]]

    def test_chunk_empty(self):
        c = LLMClient()
        chunks = c._chunk([], 2)
        assert chunks == []


class TestBuildTriageBatchItem:
    def test_build_item_all_fields(self):
        c = LLMClient()
        result = c._build_triage_batch_item(1, _TXN, _FLAG)
        assert "Transaction 1:" in result
        assert "TXN001" in result
        assert "ACC001" in result
        assert "CUST001" in result
        assert "15,000" in result
        assert "Global Trading" in result
        assert "London" in result
        assert "High Value Check" in result
        assert "Offshore Transaction" in result

    def test_build_item_empty_flags(self):
        c = LLMClient()
        result = c._build_triage_batch_item(1, _TXN, {})
        assert "None" in result

    def test_build_item_with_enriched_context(self):
        c = LLMClient()
        ec = {"customer_txn_count_30d": 5, "customer_sum_30d": 25000.0,
              "customer_avg_30d": 5000.0, "account_type": "checking"}
        result = c._build_triage_batch_item(1, _TXN, _FLAG, ec)
        assert "Customer Enrichment" in result
        assert "checking" in result
        assert "5 txns" in result


class TestBuildTriageStage3BatchItem:
    def test_build_item_with_history(self):
        c = LLMClient()
        recent = [
            {"amount": 500.0, "counterparty": "Local Shop", "city": "Boston", "state": "MA", "country": "US", "date": "2026-05-01"},
        ]
        result = c._build_triage_stage3_batch_item(1, _TXN, _FLAG, recent)
        assert "Transaction 1" in result
        assert "Recent Transaction History" in result
        assert "Local Shop" in result
        assert "$500" in result

    def test_build_item_no_history(self):
        c = LLMClient()
        result = c._build_triage_stage3_batch_item(1, _TXN, _FLAG, [])
        assert "No recent transactions found" in result


class TestBuildBatchMessages:
    def test_triage_batch_messages(self):
        c = LLMClient()
        system, user = c._build_triage_batch_messages([_TXN], [_FLAG], None, [None])
        assert "Transaction 1" in user
        assert "TXN001" in user
        assert "HIGH_VALUE" in system or "escalate" in system

    def test_triage_stage3_batch_messages(self):
        c = LLMClient()
        system, user = c._build_triage_stage3_batch_messages([_TXN], [_FLAG], [[]], None)
        assert "Transaction 1" in user
        assert "TXN001" in user

    def test_sar_batch_prompt(self):
        c = LLMClient()
        triage = TriageDecision(escalate=True, reason="High risk", confidence=0.9)
        prompt = c._build_sar_batch_prompt([_TXN], [_FLAG], [triage])
        assert "Transaction 1" in prompt
        assert "TXN001" in prompt
        assert "High risk" in prompt


# ── Provider dispatch ────────────────────────────────────────────

class TestBatchProviderDispatch:
    @patch.dict("sys.modules", {"openai": _MOCK_OPENAI})
    async def test_triage_batch_provider_openai(self):
        c = _make_openai_client()
        mock_msg = MagicMock()
        mock_msg.content = json.dumps({"decisions": [{"source_txn_id": "TXN001", "escalate": True, "reason": "High", "confidence": 0.9}]})
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        c._openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)

        result = await c._triage_batch_provider([_TXN], [_FLAG], None, [None])
        assert len(result) == 1
        assert result[0].escalate is True

    async def test_triage_batch_provider_fallback(self):
        c = _make_openai_client()
        c._openai_client = None  # Force fallback
        result = await c._triage_batch_provider([_TXN], [_FLAG], None, [None])
        assert len(result) == 1
        assert result[0].escalate is True

    async def test_sar_batch_provider_fallback(self):
        c = _make_openai_client()
        c._openai_client = None
        triage = TriageDecision(escalate=True, reason="High", confidence=0.9)
        result = await c._sar_batch_provider([_TXN], [_FLAG], [triage])
        assert len(result) == 1
        assert "TXN001" in result[0].content

    async def test_triage_stage3_batch_provider_fallback(self):
        c = _make_openai_client()
        c._openai_client = None
        result = await c._triage_stage3_batch_provider([_TXN], [_FLAG], [[]], None)
        assert len(result) == 1
        assert result[0].escalate is True


class TestParseBatchResponse:
    def test_parse_triage_batch_success(self):
        raw = json.dumps({"decisions": [{"source_txn_id": "TXN001", "escalate": True, "reason": "R1", "confidence": 0.9}]})
        result = LLMClient._parse_triage_batch_response(raw, [_TXN])
        assert len(result) == 1
        assert result[0].escalate is True
        assert result[0].reason == "R1"

    def test_parse_triage_batch_empty(self):
        with pytest.raises((ValueError, KeyError)):
            LLMClient._parse_triage_batch_response(None, [_TXN])

    def test_parse_triage_batch_mismatch(self):
        raw = json.dumps({"decisions": [{"source_txn_id": "WRONG", "escalate": True, "reason": "R", "confidence": 0.5}]})
        with pytest.raises(ValueError, match="source_txn_id mismatch"):
            LLMClient._parse_triage_batch_response(raw, [_TXN])

    def test_parse_sar_batch_success(self):
        triage = TriageDecision(escalate=True, reason="R", confidence=0.5)
        raw = json.dumps({"sars": [{"source_txn_id": "TXN001", "content": "SAR narrative"}]})
        result = LLMClient._parse_sar_batch_response(raw, [_TXN], [_FLAG], [triage])
        assert len(result) == 1
        assert "SAR narrative" in result[0].content

    def test_parse_sar_batch_mismatch(self):
        triage = TriageDecision(escalate=True, reason="R", confidence=0.5)
        raw = json.dumps({"sars": [{"source_txn_id": "WRONG", "content": "SAR"}]})
        with pytest.raises(ValueError, match="source_txn_id mismatch"):
            LLMClient._parse_sar_batch_response(raw, [_TXN], [_FLAG], [triage])

    def test_parse_sar_batch_empty(self):
        triage = TriageDecision(escalate=True, reason="R", confidence=0.5)
        with pytest.raises((ValueError, KeyError)):
            LLMClient._parse_sar_batch_response(None, [_TXN], [_FLAG], [triage])


class TestFallbackBatch:
    def test_triage_fallback_batch(self):
        c = LLMClient()
        result = c._triage_fallback_batch([_TXN], [_FLAG], None, [None])
        assert len(result) == 1
        assert result[0].escalate is True

    def test_sar_fallback_batch(self):
        c = LLMClient()
        triage = TriageDecision(escalate=True, reason="R", confidence=0.5)
        result = c._sar_fallback_batch([_TXN], [_FLAG], [triage])
        assert len(result) == 1
        assert "TXN001" in result[0].content


class TestInitClient:
    def test_init_no_keys(self):
        c = LLMClient()
        c._init_client()
        assert c._openai_client is None
        assert c._gemini_client is None
