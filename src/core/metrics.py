from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any


def compute_velocity_zscore(
    txns: list[dict[str, Any]],
    ref_date: datetime,
    threshold: float = 2.0,
) -> tuple[float | None, list[int]]:
    """Compute velocity z-score for a customer's transactions.

    Returns (zscore | None, weekly_counts) where weekly_counts has 4 buckets
    for the prior 4 weeks (excluding current week).
    """
    one_week_ago = ref_date - timedelta(days=7)
    four_weeks_ago = ref_date - timedelta(days=35)

    this_week_count = sum(
        1 for t in txns
        if t.get("date") and datetime.fromisoformat(t["date"]) >= one_week_ago
    )

    weekly_counts = [0, 0, 0, 0]
    for t in txns:
        d = t.get("date")
        if not d:
            continue
        dt = datetime.fromisoformat(d)
        if dt < one_week_ago and dt >= four_weeks_ago:
            weeks_ago = int((ref_date - dt).days // 7)
            if 1 <= weeks_ago <= 4:
                weekly_counts[weeks_ago - 1] += 1

    avg_weekly = sum(weekly_counts) / 4.0
    if avg_weekly <= 0 or this_week_count <= 0:
        return None, weekly_counts

    variance = sum((c - avg_weekly) ** 2 for c in weekly_counts) / 4.0
    std_weekly = math.sqrt(variance) if variance > 0 else 1.0
    zscore = (this_week_count - avg_weekly) / max(std_weekly, 1.0)
    return zscore, weekly_counts


def compute_structuring_24h_count(
    txns: list[dict[str, Any]],
    ref_date: datetime,
) -> int:
    """Count transactions in [$9K, $10K] within past 24 hours."""
    one_day_ago = ref_date - timedelta(days=1)
    return sum(
        1 for t in txns
        if t.get("date") and datetime.fromisoformat(t["date"]) >= one_day_ago
        and t.get("amount") is not None and 9000 <= t["amount"] <= 10000
    )
