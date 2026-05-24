"""Completeness check — verifies each triggered rule's concern is addressed in the SAR narrative."""

from __future__ import annotations

from typing import Any

from src.aml_workflow.eval import CompletenessResult


async def check_sar(
    sar_id: str,
    transaction_id: str,
    narrative: str,
    flag_details: dict[str, str] | None,
) -> CompletenessResult:
    """Check whether a SAR narrative covers all triggered rules.

    For deterministic fallback SARs, the narrative includes a "Flagged Rules:"
    line listing every rule name, so completeness is inherent.

    For LLM-generated SARs, checks if each rule name appears in the narrative.
    """
    narrative_lower = narrative.lower()

    covered: list[str] = []
    missed: list[str] = []

    for rule_id, rule_name in (flag_details or {}).items():
        # Check if the rule name (or a key word from it) appears in the narrative
        name_lower = rule_name.lower()
        words = name_lower.split()
        key_words = [w for w in words if len(w) > 3]
        if not key_words:
            key_words = words

        if any(w in narrative_lower for w in key_words):
            covered.append(rule_name)
        else:
            missed.append(rule_name)

    total = len(covered) + len(missed)
    score = len(covered) / total if total > 0 else 1.0

    return CompletenessResult(
        sar_id=sar_id,
        transaction_id=transaction_id,
        covered_rules=covered,
        missed_rules=missed,
        score=score,
    )
