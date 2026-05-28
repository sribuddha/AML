import json
import math
from typing import Any


def _get_field_value(txn: dict[str, Any], field: str) -> Any:
    val = txn.get(field)
    if isinstance(val, str):
        val = val.strip()
    return val


def _str_cmp(val: Any) -> str:
    s = str(val)
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _apply_operator(operator: str, field_val: Any, condition_val: Any) -> bool:
    if field_val is None:
        return operator == "is_empty"

    if operator in (">", "<", ">=", "<="):
        try:
            fv = float(field_val)
            cv = float(condition_val)
        except (ValueError, TypeError):
            return False
        if operator == ">":
            return fv > cv
        elif operator == "<":
            return fv < cv
        elif operator == ">=":
            return fv >= cv
        elif operator == "<=":
            return fv <= cv

    elif operator == "==":
        return _str_cmp(field_val) == _str_cmp(condition_val)
    elif operator == "!=":
        return _str_cmp(field_val) != _str_cmp(condition_val)
    elif operator == "is_empty":
        return field_val == "" or (isinstance(field_val, float) and math.isnan(field_val))
    elif operator == "contains":
        return isinstance(field_val, str) and str(condition_val).lower() in field_val.lower()
    elif operator == "in":
        fv_str = str(field_val)
        if fv_str.endswith(".0"):
            fv_str = fv_str[:-2]
        cv_list = []
        for v in (condition_val or []):
            cv_str = str(v)
            if cv_str.endswith(".0"):
                cv_str = cv_str[:-2]
            cv_list.append(cv_str)
        return fv_str in cv_list

    return False


def evaluate_conditions(txn: dict[str, Any], conditions: list[dict[str, Any]]) -> bool:
    for cond in conditions:
        op = cond.get("operator", "==")
        field = cond.get("field", "")
        val = cond.get("value")
        field_val = _get_field_value(txn, field)
        if _apply_operator(op, field_val, val):
            return True
    return False


def evaluate_rules(txn: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for rule_dict in rules:
        rj = rule_dict["rules_json"]
        try:
            conditions = json.loads(rj) if isinstance(rj, str) else rj
        except (json.JSONDecodeError, TypeError):
            continue
        if evaluate_conditions(txn, conditions):
            result[rule_dict["id"]] = rule_dict["name"]
    return result
