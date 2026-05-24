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
        c._gemini_client.models.generate_content = MagicMock(return_value=mock_resp)

        result = await c._triage_gemini(_TXN, _FLAG)
        assert isinstance(result, TriageDecision)
        assert result.escalate is True
        assert result.reason == "Flagged by rules"
        assert result.confidence == 0.92

    async def test_triage_gemini_fallback_on_error(self):
        c = _make_gemini_client()
        c._gemini_client.models.generate_content = MagicMock(side_effect=Exception("API error"))

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
        c._gemini_client.models.generate_content = MagicMock(return_value=mock_resp)

        result = await c._triage_stage3_gemini(_TXN, _FLAG, [])
        assert isinstance(result, TriageDecision)
        assert result.escalate is False
        assert result.reason == "Routine transaction"

    async def test_stage3_gemini_fallback_on_error(self):
        c = _make_gemini_client()
        c._gemini_client.models.generate_content = MagicMock(side_effect=Exception("API error"))

        result = await c._triage_stage3_gemini(_TXN, _FLAG, [])
        assert isinstance(result, TriageDecision)
        assert result.escalate is True


class TestGeminiSar:
    async def test_sar_gemini_returns_result(self):
        c = _make_gemini_client()
        mock_resp = MagicMock()
        mock_resp.text = "Gemini generated SAR report"
        c._gemini_client.models.generate_content = MagicMock(return_value=mock_resp)

        triage = TriageDecision(escalate=True, reason="High risk", confidence=0.9)
        result = await c._sar_gemini(_TXN, _FLAG, triage)
        assert isinstance(result, SarResult)
        assert "Gemini generated SAR report" in result.content
        assert result.raw_response == "Gemini generated SAR report"

    async def test_sar_gemini_fallback_on_error(self):
        c = _make_gemini_client()
        c._gemini_client.models.generate_content = MagicMock(side_effect=Exception("API error"))

        triage = TriageDecision(escalate=True, reason="High risk", confidence=0.9)
        result = await c._sar_gemini(_TXN, _FLAG, triage)
        assert isinstance(result, SarResult)
        assert "TXN001" in result.content
        assert "Offshore Transaction" in result.content
