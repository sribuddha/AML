"""Hallucination check — verifies every number/entity in a SAR narrative appears in the source evidence."""

from __future__ import annotations

import re
from typing import Any

from src.aml_workflow.eval import HallucinationResult


def _extract_numbers(text: str) -> set[str]:
    """Extract monetary values and decimal numbers from text.

    Only extracts:
    - Values with $ prefix: $15,000.00
    - Values with decimal point: 15000.00
    This avoids matching digit sequences inside entity IDs like TXN001.
    """
    tokens = set()
    for match in re.finditer(r"\$[\d,]+(?:\.\d{2})?|\b[\d,]+\.\d{2}\b", text):
        raw = match.group()
        cleaned = raw.replace("$", "").replace(",", "")
        tokens.add(cleaned)
    return tokens


def _extract_entities(text: str) -> set[str]:
    """Extract entity-like tokens (TXN IDs, account IDs, capitalized words ≥ 4 chars)."""
    tokens = set()
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9_]{3,}\b", text):
        tokens.add(match.group())
    return tokens


def _build_evidence_set(
    transaction: dict[str, Any],
    flag_details: dict[str, str] | None,
    related_transactions: list[dict[str, Any]] | None = None,
) -> set[str]:
    """Build the set of ground-truth values the SAR should contain."""
    evidence = set()
    for key, value in transaction.items():
        if value is not None:
            evidence.add(str(value))
            if isinstance(value, (int, float)):
                evidence.add(f"{value:.2f}")
                evidence.add(f"{value:,.2f}")
                evidence.add(f"{value:.0f}")
                evidence.add(f"{value:,.0f}")
    if flag_details:
        for name in flag_details.values():
            evidence.add(name)
    if related_transactions:
        for rel in related_transactions:
            for key, value in rel.items():
                if value is not None:
                    evidence.add(str(value))
                    if isinstance(value, (int, float)):
                        evidence.add(f"{value:.2f}")
                        evidence.add(f"{value:,.2f}")
                        evidence.add(f"{value:.0f}")
                        evidence.add(f"{value:,.0f}")
    return evidence


async def check_sar(
    sar_id: str,
    transaction_id: str,
    narrative: str,
    transaction: dict[str, Any],
    flag_details: dict[str, str] | None,
    related_transactions: list[dict[str, Any]] | None = None,
) -> HallucinationResult:
    """Check a single SAR narrative for hallucinated facts."""
    narrative_numbers = _extract_numbers(narrative)
    evidence_numbers = _build_evidence_set(transaction, flag_details, related_transactions)

    hallucinated = []
    for num in sorted(narrative_numbers):
        if num not in evidence_numbers:
            # Check if it's a formatted version of a known value
            try:
                val = float(num.replace(",", ""))
                found = False
                for ev in evidence_numbers:
                    try:
                        if abs(float(ev.replace(",", "")) - val) < 0.01:
                            found = True
                            break
                    except (ValueError, AttributeError):
                        continue
                if not found:
                    hallucinated.append(num)
            except ValueError:
                hallucinated.append(num)

    return HallucinationResult(
        sar_id=sar_id,
        transaction_id=transaction_id,
        hallucinated_facts=hallucinated,
        passed=len(hallucinated) == 0,
    )
