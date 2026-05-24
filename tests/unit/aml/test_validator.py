import json

import pytest

from src.aml_workflow.validator import evaluate_conditions, evaluate_rules


def _tx(**kwargs):
    defaults = {
        "id": "tx-1",
        "account_id": "ACC001",
        "customer_id": "CUST001",
        "amount": 100.00,
        "counterparty": "Acme Corp",
        "city": "New York", "state": "NY", "country": "US",
        "date": "2026-05-01",
        "source_txn_id": "TXN001",
    }
    defaults.update(kwargs)
    return defaults


class TestEvaluateConditions:
    def test_gt_matches(self):
        assert evaluate_conditions(_tx(amount=50000), [{"field": "amount", "operator": ">", "value": 10000}])

    def test_gt_no_match(self):
        assert not evaluate_conditions(_tx(amount=100), [{"field": "amount", "operator": ">", "value": 10000}])

    def test_lt_matches(self):
        assert evaluate_conditions(_tx(amount=-50), [{"field": "amount", "operator": "<", "value": 0}])

    def test_lt_no_match(self):
        assert not evaluate_conditions(_tx(amount=50), [{"field": "amount", "operator": "<", "value": 0}])

    def test_eq_matches(self):
        assert evaluate_conditions(_tx(country="Cayman Islands"), [{"field": "country", "operator": "==", "value": "Cayman Islands"}])

    def test_eq_no_match(self):
        assert not evaluate_conditions(_tx(country="US"), [{"field": "country", "operator": "==", "value": "Cayman Islands"}])

    def test_neq_matches(self):
        assert evaluate_conditions(_tx(country="US"), [{"field": "country", "operator": "!=", "value": "Cayman Islands"}])

    def test_neq_no_match(self):
        assert not evaluate_conditions(_tx(country="Cayman Islands"), [{"field": "country", "operator": "!=", "value": "Cayman Islands"}])

    def test_is_empty_on_none(self):
        assert evaluate_conditions(_tx(counterparty=None), [{"field": "counterparty", "operator": "is_empty"}])

    def test_is_empty_on_empty_string(self):
        assert evaluate_conditions(_tx(counterparty=""), [{"field": "counterparty", "operator": "is_empty"}])

    def test_is_empty_on_whitespace(self):
        assert evaluate_conditions(_tx(counterparty="   "), [{"field": "counterparty", "operator": "is_empty"}])

    def test_is_empty_no_match(self):
        assert not evaluate_conditions(_tx(counterparty="Acme Corp"), [{"field": "counterparty", "operator": "is_empty"}])

    def test_contains_matches(self):
        assert evaluate_conditions(_tx(counterparty="Acme Corp"), [{"field": "counterparty", "operator": "contains", "value": "Acme"}])

    def test_contains_case_insensitive(self):
        assert evaluate_conditions(_tx(counterparty="Acme Corp"), [{"field": "counterparty", "operator": "contains", "value": "acme"}])

    def test_contains_no_match(self):
        assert not evaluate_conditions(_tx(counterparty="Acme Corp"), [{"field": "counterparty", "operator": "contains", "value": "Global"}])

    def test_in_matches(self):
        assert evaluate_conditions(_tx(country="Cayman Islands"), [{"field": "country", "operator": "in", "value": ["Cayman Islands", "Panama"]}])

    def test_in_no_match(self):
        assert not evaluate_conditions(_tx(country="US"), [{"field": "country", "operator": "in", "value": ["Cayman Islands", "Panama"]}])

    def test_in_float_amount_matches(self):
        assert evaluate_conditions(_tx(amount=5000.0), [{"field": "amount", "operator": "in", "value": [1000, 5000, 10000]}])

    def test_in_float_no_match(self):
        assert not evaluate_conditions(_tx(amount=5001.0), [{"field": "amount", "operator": "in", "value": [1000, 5000, 10000]}])

    def test_gte_matches(self):
        assert evaluate_conditions(_tx(amount=10000), [{"field": "amount", "operator": ">=", "value": 10000}])

    def test_gte_no_match(self):
        assert not evaluate_conditions(_tx(amount=9999), [{"field": "amount", "operator": ">=", "value": 10000}])

    def test_lte_matches(self):
        assert evaluate_conditions(_tx(amount=0), [{"field": "amount", "operator": "<=", "value": 0}])

    def test_lte_no_match(self):
        assert not evaluate_conditions(_tx(amount=1), [{"field": "amount", "operator": "<=", "value": 0}])

    def test_any_condition_matches_or_logic(self):
        conditions = [
            {"field": "amount", "operator": ">", "value": 10000},
            {"field": "country", "operator": "==", "value": "Cayman Islands"},
        ]
        assert evaluate_conditions(_tx(amount=50000, country="US"), conditions)
        assert evaluate_conditions(_tx(amount=100, country="Cayman Islands"), conditions)

    def test_none_field_returns_false_for_gt(self):
        assert not evaluate_conditions(_tx(amount=None), [{"field": "amount", "operator": ">", "value": 0}])

    def test_non_numeric_field_returns_false_for_gt(self):
        assert not evaluate_conditions(_tx(amount="abc"), [{"field": "amount", "operator": ">", "value": 100}])

    def test_none_field_returns_true_for_is_empty(self):
        assert evaluate_conditions(_tx(amount=None), [{"field": "amount", "operator": "is_empty"}])

    def test_unknown_operator_returns_false(self):
        assert not evaluate_conditions(_tx(amount=100), [{"field": "amount", "operator": "matches", "value": "pattern"}])


class TestEvaluateRules:
    def test_no_rules_returns_empty(self):
        txn = _tx(amount=50000)
        assert evaluate_rules(txn, []) == {}

    def test_single_rule_matches(self):
        txn = _tx(amount=50000)
        rules = [{"id": "rule-1", "name": "High Value", "rules_json": json.dumps([{"field": "amount", "operator": ">", "value": 10000}])}]
        assert evaluate_rules(txn, rules) == {"rule-1": "High Value"}

    def test_single_rule_no_match(self):
        txn = _tx(amount=100)
        rules = [{"id": "rule-1", "name": "High Value", "rules_json": json.dumps([{"field": "amount", "operator": ">", "value": 10000}])}]
        assert evaluate_rules(txn, rules) == {}

    def test_multiple_rules_some_match(self):
        txn = _tx(amount=50000, country="US")
        rules = [
            {"id": "r1", "name": "High Value", "rules_json": json.dumps([{"field": "amount", "operator": ">", "value": 10000}])},
            {"id": "r2", "name": "Offshore", "rules_json": json.dumps([{"field": "country", "operator": "==", "value": "Cayman Islands"}])},
        ]
        assert evaluate_rules(txn, rules) == {"r1": "High Value"}

    def test_multiple_rules_all_match(self):
        txn = _tx(amount=50000, country="Cayman Islands")
        rules = [
            {"id": "r1", "name": "High Value", "rules_json": json.dumps([{"field": "amount", "operator": ">", "value": 10000}])},
            {"id": "r2", "name": "Offshore", "rules_json": json.dumps([{"field": "country", "operator": "==", "value": "Cayman Islands"}])},
        ]
        assert evaluate_rules(txn, rules) == {"r1": "High Value", "r2": "Offshore"}

    def test_rules_json_already_parsed(self):
        txn = _tx(amount=50000)
        rules = [{"id": "r1", "name": "High Value", "rules_json": [{"field": "amount", "operator": ">", "value": 10000}]}]
        assert evaluate_rules(txn, rules) == {"r1": "High Value"}
