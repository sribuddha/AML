import pytest

from src.aml_workflow.eval.hallucination import check_sar, _extract_numbers, _extract_entities, _build_evidence_set


_TRANSACTION = {
    "source_txn_id": "TXN001",
    "account_id": "ACC001",
    "amount": 15000.00,
    "counterparty": "Acme Corp",
    "city": "New York", "state": "NY", "country": "US",
    "date": "2026-05-15",
}

_FLAG_DETAILS = {"rule-1": "High Value Check"}


class TestExtractNumbers:
    def test_extracts_dollar_amount(self):
        assert "15000.00" in _extract_numbers("Amount $15,000.00 is high")

    def test_extracts_decimal_number(self):
        assert "100.00" in _extract_numbers("Flagged amount 100.00")

    def test_extracts_multiple_numbers(self):
        result = _extract_numbers("$1,500.00 and $2,000.00 and 300.50")
        assert "1500.00" in result
        assert "2000.00" in result
        assert "300.50" in result

    def test_skips_digits_in_entity_ids(self):
        result = _extract_numbers("Transaction TXN001 from ACC001")
        assert result == set()

    def test_skips_standalone_integers(self):
        result = _extract_numbers("500 transactions processed")
        assert result == set()

    def test_empty_text(self):
        assert _extract_numbers("") == set()

    def test_no_numbers(self):
        assert _extract_numbers("No numbers here") == set()


class TestExtractEntities:
    def test_extracts_entity_ids(self):
        result = _extract_entities("Transaction TXN001 from ACC001")
        assert "TXN001" in result
        assert "ACC001" in result

    def test_skips_short_words(self):
        result = _extract_entities("the cat is a and")
        assert len(result) == 0


class TestBuildEvidenceSet:
    def test_includes_transaction_fields(self):
        evidence = _build_evidence_set(_TRANSACTION, _FLAG_DETAILS)
        assert "TXN001" in evidence
        assert "ACC001" in evidence
        assert "Acme Corp" in evidence

    def test_includes_formatted_amounts(self):
        evidence = _build_evidence_set({"amount": 15000.00}, None)
        assert "15000.00" in evidence

    def test_includes_rule_names(self):
        evidence = _build_evidence_set(_TRANSACTION, _FLAG_DETAILS)
        assert "High Value Check" in evidence

    def test_handles_none_flag_details(self):
        evidence = _build_evidence_set(_TRANSACTION, None)
        assert "High Value Check" not in evidence


class TestCheckSar:
    async def test_passes_on_clean_narrative(self):
        narrative = (
            "Transaction TXN001 from ACC001 Amount $15,000.00 "
            "Counterparty Acme Corp in New York Flagged Rules: High Value Check"
        )
        result = await check_sar("sar-1", "txn-1", narrative, _TRANSACTION, _FLAG_DETAILS)
        assert result.passed
        assert result.hallucinated_facts == []

    async def test_detects_fake_number(self):
        narrative = (
            "Transaction TXN001 from ACC001 Amount $99,999.00 "
            "Counterparty Acme Corp in New York"
        )
        result = await check_sar("sar-1", "txn-1", narrative, _TRANSACTION, None)
        assert not result.passed
        assert any("99999" in f for f in result.hallucinated_facts)

    async def test_skips_digits_in_entity_ids(self):
        narrative = "Transaction TXN001 from ACC001 Amount $15,000.00"
        result = await check_sar("sar-1", "txn-1", narrative, _TRANSACTION, None)
        assert result.passed

    async def test_empty_narrative(self):
        result = await check_sar("sar-1", "txn-1", "", _TRANSACTION, None)
        assert result.passed

    async def test_approximate_number_match_within_tolerance(self):
        """Number in SAR formatted differently from evidence but within 0.01 tolerance."""
        narrative = (
            "Transaction TXN001 from ACC001 Amount $1,000 "
            "Counterparty Acme Corp in New York"
        )
        txn = {"amount": 1000.00}
        result = await check_sar("sar-1", "txn-1", narrative, txn, None)
        assert result.passed

    async def test_malformed_number_triggers_value_error(self):
        """Narrative with '$, ' token exercises except ValueError path."""
        narrative = "Amount $, is suspicious from ACC001 Counterparty Acme Corp"
        txn = {"amount": 500.00, "source_txn_id": "TXN001"}
        result = await check_sar("sar-1", "txn-1", narrative, txn, None)
        assert not result.passed
