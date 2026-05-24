import pytest

from src.aml_workflow.eval.completeness import check_sar


class TestCheckSar:
    async def test_all_rules_covered(self):
        narrative = "High Value Check flagged this transaction as suspicious"
        result = await check_sar("sar-1", "txn-1", narrative, {
            "r1": "High Value Check",
            "r2": "Offshore Transaction",
        })
        assert result.score == 1.0
        assert len(result.missed_rules) == 0

    async def test_some_rules_missed(self):
        narrative = "This transaction was flagged"
        result = await check_sar("sar-1", "txn-1", narrative, {
            "r1": "High Value Check",
        })
        assert result.score < 1.0
        assert "High Value Check" in result.missed_rules

    async def test_all_rules_missed(self):
        narrative = "Nothing about any rules here"
        result = await check_sar("sar-1", "txn-1", narrative, {
            "r1": "Structuring Threshold",
            "r2": "Watchlist Match",
        })
        assert result.score == 0.0
        assert len(result.covered_rules) == 0

    async def test_no_flag_details(self):
        result = await check_sar("sar-1", "txn-1", "Some narrative", None)
        assert result.score == 1.0
        assert len(result.missed_rules) == 0

    async def test_empty_flag_details(self):
        result = await check_sar("sar-1", "txn-1", "Some narrative", {})
        assert result.score == 1.0

    async def test_short_rule_name_all_words_underscore_three_chars(self):
        narrative = "Nothing about flagged rules here"
        result = await check_sar("sar-1", "txn-1", narrative, {
            "r1": "XYZ Co",
        })
        assert result.score == 0.0
        assert "XYZ Co" in result.missed_rules
