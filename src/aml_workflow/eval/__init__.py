"""Eval harness for AML workflow — measures detection, hallucination, and completeness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PatternMetrics:
    """Detection metrics for a single fraud pattern."""
    pattern: str
    total: int = 0
    flagged: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0


@dataclass
class HallucinationResult:
    """Result of hallucination check on a single SAR."""
    sar_id: str
    transaction_id: str
    hallucinated_facts: list[str] = field(default_factory=list)
    passed: bool = True


@dataclass
class CompletenessResult:
    """Result of completeness check on a single SAR."""
    sar_id: str
    transaction_id: str
    covered_rules: list[str] = field(default_factory=list)
    missed_rules: list[str] = field(default_factory=list)
    score: float = 1.0


@dataclass
class EvalReport:
    """Full evaluation report for one upload run."""
    upload_id: str
    total_transactions: int = 0
    total_anomalous: int = 0
    total_flagged: int = 0
    pattern_metrics: list[PatternMetrics] = field(default_factory=list)
    hallucination_results: list[HallucinationResult] = field(default_factory=list)
    completeness_results: list[CompletenessResult] = field(default_factory=list)
    overall_precision: float = 0.0
    overall_recall: float = 0.0
    overall_f1: float = 0.0
    hallucination_free_rate: float = 1.0
    avg_completeness: float = 1.0

    def summary(self) -> str:
        lines = [
            f"Eval Report — upload {self.upload_id[:8]}...",
            f"  Transactions:     {self.total_transactions}",
            f"  Anomalous:        {self.total_anomalous}",
            f"  Flagged:          {self.total_flagged}",
            f"  Precision:        {self.overall_precision:.1%}",
            f"  Recall:           {self.overall_recall:.1%}",
            f"  F1:               {self.overall_f1:.1%}",
            f"  Hallucination-free: {self.hallucination_free_rate:.1%}",
            f"  Avg completeness: {self.avg_completeness:.1%}",
            "",
        ]
        for pm in self.pattern_metrics:
            lines.append(f"  {pm.pattern:20s}  prec={pm.precision:.1%}  recall={pm.recall:.1%}  f1={pm.f1:.1%}")
        return "\n".join(lines)


def _compute_metrics(total: int, true_positives: int) -> tuple[float, float, float]:
    """Compute precision, recall, and F1 given ground-truth and correctly-flagged counts.

    Args:
        total: Number of ground-truth items (anomalous transactions for a pattern).
        true_positives: Number of ground-truth items that were correctly flagged.
                        Must be <= total.

    Returns:
        (precision, recall, f1). Since the harness tracks only correctly-flagged items
        (not all flagged items), precision equals 1.0 in the common case where
        true_positives <= total — i.e. this is a *coverage* metric, not a
        binary-classification metric. Call it a "detection rate" rather than
        conventional precision/recall.
    """
    if total == 0:
        return 0.0, 0.0, 0.0
    tp = min(true_positives, total)
    fn = total - tp
    fp = true_positives - tp
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1
