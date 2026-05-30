from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai.errors import APIError

from src.aml_workflow.llm import (
    LLMClient,
    TriageDecision,
    SarResult,
    _triage_fallback,
    _sar_fallback,
    _build_rule_evidence,
    _build_triage_messages,
    _build_triage_stage3_messages,
    _build_sar_prompt,
    _triage_fallback_batch,
    _sar_fallback_batch,
)


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


class TestTriageFallback:
    def test_escalates_with_flag_details(self):
        txn = {**_TXN, "amount": 100}
        result = _triage_fallback(txn, _FLAG)
        assert isinstance(result, TriageDecision)
        assert result.escalate is True
        assert result.confidence == 0.7
        assert "High Value Check" in result.reason

    def test_escalates_with_single_flag(self):
        result = _triage_fallback(_TXN, {"rule-1": "Round Amount"})
        assert result.escalate is True
        assert result.confidence == 0.7
        assert "Round Amount" in result.reason

    def test_no_escalate_when_no_flag_details(self):
        result = _triage_fallback(_TXN, {})
        assert result.escalate is False
        assert result.confidence == 0.1
        assert "No rules" in result.reason

    def test_no_escalate_when_none_flag_details(self):
        txn = {**_TXN, "amount": 75000}
        result = _triage_fallback(txn, {})
        assert result.escalate is False

    def test_confidence_between_0_and_1(self):
        txn = {**_TXN, "amount": 75000}
        result = _triage_fallback(txn, _FLAG)
        assert 0.0 <= result.confidence <= 1.0


class TestSarFallback:
    def test_contains_all_fields(self):
        triage = TriageDecision(escalate=True, reason="Exceeds threshold", confidence=0.9)
        result = _sar_fallback(_TXN, _FLAG, triage)
        assert "TXN001" in result.content
        assert "ACC001" in result.content
        assert "$15,000" in result.content
        assert "Global Trading" in result.content
        assert "London" in result.content
        assert "escalated" in result.content.lower()
        assert "Exceeds threshold" in result.content
        assert "High Value Check" in result.content
        assert "Offshore Transaction" in result.content

    def test_handles_missing_fields(self):
        txn = {**_TXN, "amount": None, "source_txn_id": None}
        triage = TriageDecision(escalate=False, reason="Normal", confidence=0.5)
        result = _sar_fallback(txn, {}, triage)
        assert "$0" in result.content


class TestBuildTriagePrompt:
    def test_build_rule_evidence(self):
        rules = [
            {"id": "rule-1", "name": "High Value Check", "rules_json": '[{"field": "amount", "operator": ">", "value": 10000}]'},
            {"id": "rule-2", "name": "Offshore Transaction", "rules_json": '[{"field": "country", "operator": "==", "value": "Cayman Islands"}]'},
        ]
        evidence = _build_rule_evidence(_FLAG, rules)
        assert "High Value Check" in evidence
        assert "Offshore Transaction" in evidence
        assert "amount" in evidence or "Cayman" in evidence

    def test_build_rule_evidence_without_rules(self):
        evidence = _build_rule_evidence(_FLAG, None)
        assert "High Value Check" in evidence
        assert "Offshore Transaction" in evidence

    def test_empty_flag_details(self):
        evidence = _build_rule_evidence({}, [])
        assert "None" in evidence

    def test_build_triage_messages_includes_fields(self):
        system, user = _build_triage_messages(_TXN, _FLAG, None)
        assert "TXN001" in user
        assert "ACC001" in user
        assert "CUST001" in user
        assert "$15,000" in user
        assert "Global Trading" in user
        assert "London" in user
        assert "2026-05-15" in user
        assert "High Value Check" in user
        assert "Offshore Transaction" in user
        assert "escalate" in system.lower()

    def test_build_triage_messages_includes_enriched_context(self):
        enriched = {
            "customer_txn_count_30d": 5,
            "customer_sum_30d": 25000.0,
            "customer_avg_30d": 5000.0,
            "account_type": "checking",
        }
        _, user = _build_triage_messages(_TXN, _FLAG, None, enriched)
        assert "## Enriched Context" in user or "Customer enrichment" in user
        assert "5 txns" in user
        assert "checking" in user

    def test_build_triage_messages_no_enriched_context(self):
        _, user = _build_triage_messages(_TXN, _FLAG, None, None)
        assert "## Enriched Context" not in user
        assert "Customer enrichment" not in user


class TestBuildSarPrompt:
    def test_includes_triage_decision(self):
        triage = TriageDecision(escalate=True, reason="High value to high-risk jurisdiction", confidence=0.9)
        prompt = _build_sar_prompt(_TXN, _FLAG, triage)
        assert "high" in prompt.lower() or "High value" in prompt
        assert "High value to high-risk jurisdiction" in prompt

    def test_includes_transaction_and_rules(self):
        triage = TriageDecision(escalate=True, reason="Large amount", confidence=0.8)
        prompt = _build_sar_prompt(_TXN, _FLAG, triage)
        assert "TXN001" in prompt
        assert "High Value Check" in prompt


class TestTriageDefaultFallback:
    @staticmethod
    def _make_fallback_client() -> LLMClient:
        from src.aml_workflow.providers import FallbackProvider
        c = LLMClient()
        c._provider = FallbackProvider()
        return c

    async def test_triage_without_api_key_uses_fallback(self):
        client = self._make_fallback_client()
        txn = {**_TXN, "amount": 60000}
        result = await client.triage(txn, _FLAG)
        assert isinstance(result, TriageDecision)
        assert result.escalate is True

    async def test_triage_escalates_when_flagged(self):
        client = self._make_fallback_client()
        txn = {**_TXN, "amount": 100}
        result = await client.triage(txn, _FLAG)
        assert isinstance(result, TriageDecision)
        assert result.escalate is True

    async def test_triage_stage3_without_api_key_uses_fallback(self):
        client = self._make_fallback_client()
        txn = {**_TXN, "amount": 60000}
        result = await client.triage_stage3(txn, _FLAG, [])
        assert isinstance(result, TriageDecision)
        assert result.escalate is True

    async def test_triage_stage3_escalates_when_flagged(self):
        client = self._make_fallback_client()
        txn = {**_TXN, "amount": 100}
        result = await client.triage_stage3(txn, _FLAG, [])
        assert isinstance(result, TriageDecision)
        assert result.escalate is True


class TestGenerateSarDefaultFallback:
    async def test_sar_without_api_key_uses_fallback(self):
        from src.aml_workflow.providers import FallbackProvider
        client = LLMClient()
        client._provider = FallbackProvider()
        triage = TriageDecision(escalate=True, reason="Over 50k", confidence=0.9)
        result = await client.generate_sar(_TXN, _FLAG, triage)
        assert isinstance(result, SarResult)
        assert "TXN001" in result.content
        assert result.raw_response is not None


class TestBuildTriageStage3Messages:
    def test_includes_recent_history(self):
        recent = [
            {"amount": 500.0, "counterparty": "Local Shop", "city": "Boston", "state": "MA", "country": "US", "date": "2026-05-01"},
            {"amount": 25000.0, "counterparty": "Global Trading", "city": "London", "country": "GB", "date": "2026-05-02"},
        ]
        system, user = _build_triage_stage3_messages(_TXN, _FLAG, recent, None)
        assert "Local Shop" in user
        assert "Global Trading" in user
        assert "$500" in user
        assert "$25,000" in user
        assert "escalate" in system.lower()

    def test_empty_recent_history(self):
        system, user = _build_triage_stage3_messages(_TXN, _FLAG, [], None)
        assert "No recent transactions" in user
        assert "escalate" in system.lower()

    def test_single_recent_txn(self):
        recent = [{"amount": 100.0, "counterparty": "Test", "city": "New York", "state": "NY", "country": "US", "date": "2026-05-10"}]
        system, user = _build_triage_stage3_messages(_TXN, _FLAG, recent, None)
        assert "$100" in user
        assert "Test" in user


class TestGeminiHappyPath:
    @pytest.fixture
    def provider(self):
        from src.aml_workflow.providers import GeminiProvider
        model = "gemini-2.0-flash"
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = '{"escalate": true, "reason": "High risk flagged", "confidence": 0.88}'
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        return GeminiProvider(model_triage=model, model_sar=model, gemini_client=mock_client)

    async def test_triage_returns_decision(self, provider):
        result = await provider.triage(_TXN, _FLAG)
        assert isinstance(result, TriageDecision)
        assert result.escalate is True
        assert result.reason == "High risk flagged"
        assert result.confidence == 0.88

    async def test_stage3_returns_decision(self, provider):
        result = await provider.triage_stage3(_TXN, _FLAG, [])
        assert isinstance(result, TriageDecision)
        assert result.escalate is True
        assert result.reason == "High risk flagged"

    async def test_sar_returns_string(self, provider):
        triage = TriageDecision(escalate=True, reason="Over 50k", confidence=0.9)
        result = await provider.generate_sar(_TXN, _FLAG, triage)
        assert isinstance(result, SarResult)
        assert result.content == '{"escalate": true, "reason": "High risk flagged", "confidence": 0.88}'
        assert result.raw_response == '{"escalate": true, "reason": "High risk flagged", "confidence": 0.88}'


class TestGeminiFallback:
    @pytest.fixture
    def provider(self):
        from src.aml_workflow.providers import GeminiProvider
        model = "gemini-2.0-flash"
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(side_effect=APIError(code=500, response_json={"error": "API error"}))
        return GeminiProvider(model_triage=model, model_sar=model, gemini_client=mock_client)

    async def test_triage_fallback_on_error(self, provider):
        txn = {**_TXN, "amount": 60000}
        result = await provider.triage(txn, _FLAG)
        assert isinstance(result, TriageDecision)
        assert result.escalate is True
        assert "High Value Check" in result.reason

    async def test_stage3_fallback_on_error(self, provider):
        txn = {**_TXN, "amount": 60000}
        result = await provider.triage_stage3(txn, _FLAG, [])
        assert isinstance(result, TriageDecision)
        assert result.escalate is True
        assert "High Value Check" in result.reason

    async def test_sar_fallback_on_error(self, provider):
        triage = TriageDecision(escalate=True, reason="Over 50k", confidence=0.9)
        result = await provider.generate_sar(_TXN, _FLAG, triage)
        assert isinstance(result, SarResult)
        assert "TXN001" in result.content
        assert result.raw_response is not None
