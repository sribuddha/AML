import json

from src.aml_workflow.validator import (
    _str_cmp,
    _apply_operator,
    evaluate_conditions,
    evaluate_rules,
)


class TestStrCmp:
    def test_strips_dot_zero(self):
        assert _str_cmp(100.0) == "100"

    def test_keeps_plain_string(self):
        assert _str_cmp("hello") == "hello"


class TestApplyOperator:
    def test_eq_matches(self):
        assert _apply_operator("==", 100, 100) is True

    def test_eq_dot_zero(self):
        assert _apply_operator("==", 100.0, "100") is True

    def test_ne(self):
        assert _apply_operator("!=", 100, 200) is True

    def test_is_empty_with_empty_string(self):
        assert _apply_operator("is_empty", "", "") is True

    def test_is_empty_with_nan(self):
        import math
        assert _apply_operator("is_empty", float("nan"), "") is True

    def test_contains(self):
        assert _apply_operator("contains", "Hello World", "world") is True

    def test_in_with_dot_zero(self):
        assert _apply_operator("in", 100.0, [100, 200]) is True

    def test_unknown_operator_returns_false(self):
        assert _apply_operator("bogus", 1, 2) is False

    def test_none_field_is_empty(self):
        assert _apply_operator("is_empty", None, "") is True


class TestEvaluateConditions:
    def test_condition_true(self):
        assert evaluate_conditions({"amount": 1000}, [{"field": "amount", "operator": ">", "value": 500}]) is True

    def test_condition_false(self):
        assert evaluate_conditions({"amount": 100}, [{"field": "amount", "operator": ">", "value": 500}]) is False


class TestEvaluateRules:
    def test_bad_rules_json_skipped(self):
        rules = [{"id": "r1", "name": "Bad", "rules_json": [{"field": "nonexistent", "operator": ">", "value": 0}]}]
        assert evaluate_rules({"amount": 0}, rules) == {}

    def test_bad_rules_json_decode_skipped(self):
        rules = [{"id": "r1", "name": "Bad", "rules_json": "not valid json!!!"}]
        assert evaluate_rules({"amount": 100}, rules) == {}

    def test_valid_rule_matches(self):
        rules = [{
            "id": "r1", "name": "High Amount",
            "rules_json": json.dumps([{"field": "amount", "operator": ">", "value": 500}]),
        }]
        result = evaluate_rules({"amount": 1000}, rules)
        assert result == {"r1": "High Amount"}
