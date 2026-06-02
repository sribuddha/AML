"""Confidence calibration metrics for LLM triage decisions.

Computes decile-binned accuracy vs confidence and Expected Calibration Error (ECE)
to measure how well the LLM's reported confidence matches actual correctness.
"""

from __future__ import annotations

from typing import Any


def compute_calibration(
    sars: list[Any],
    txn_by_id: dict[str, Any],
    vr_map: dict[str, Any],
    expected: dict[str, dict],
) -> list[dict]:
    """Compute decile-binned confidence calibration from SAR results.

    For each SAR with a non-null ``llm_confidence``:

    1. Look up its transaction (via ``sar.transaction_id``) and the corresponding
       eval entry (via ``transaction.source_txn_id``).
    2. Determine correctness by comparing the predicted escalation
       (via ``ValidationResult.risk_level == "high"``) against the ground-truth
       ``expected_escalate``.
    3. Bin the confidence value into deciles [0.0–1.0).

    Returns a list of 10 bin dicts with keys:
        bin_index, bin_label, count, avg_confidence, accuracy.
    """
    bins: dict[int, dict[str, float | int]] = {
        i: {"count": 0, "confidence_sum": 0.0, "correct": 0}
        for i in range(10)
    }

    for sar in sars:
        confidence = getattr(sar, "llm_confidence", None)
        if confidence is None:
            continue
        txn = txn_by_id.get(sar.transaction_id)
        if txn is None:
            continue
        exp = expected.get(txn.source_txn_id)
        if exp is None:
            continue
        vr = vr_map.get(sar.transaction_id)
        if vr is None or getattr(vr, "status", None) != "flagged":
            continue

        predicted_escalate = getattr(vr, "risk_level", None) == "high"
        ground_truth = exp.get("expected_escalate", True)
        correct = predicted_escalate == ground_truth

        bin_idx = min(int(confidence * 10), 9)
        bins[bin_idx]["count"] += 1  # type: ignore[operator]
        bins[bin_idx]["confidence_sum"] += confidence  # type: ignore[operator]
        if correct:
            bins[bin_idx]["correct"] += 1  # type: ignore[operator]

    total_all = sum(b["count"] for b in bins.values())
    results: list[dict] = []
    ece_sum = 0.0

    for i in range(10):
        b = bins[i]
        count = b["count"]
        if count == 0:
            results.append({
                "bin_index": i,
                "bin_label": f"{i / 10:.1f}-{(i + 1) / 10:.1f}",
                "count": 0,
                "avg_confidence": 0.0,
                "accuracy": 0.0,
            })
            continue

        avg_conf = b["confidence_sum"] / count
        accuracy = b["correct"] / count
        bin_midpoint = (i + 0.5) / 10.0
        ece_sum += (count / total_all) * abs(accuracy - bin_midpoint)

        results.append({
            "bin_index": i,
            "bin_label": f"{i / 10:.1f}-{(i + 1) / 10:.1f}",
            "count": count,
            "avg_confidence": round(avg_conf, 4),
            "accuracy": round(accuracy, 4),
        })

    return results
