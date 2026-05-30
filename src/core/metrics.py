from __future__ import annotations

import math
from datetime import datetime, timedelta


def compute_velocity_zscore(
    date_strings: list[str],
    ref_date: datetime,
) -> float | None:
    """Compute velocity z-score from ISO date strings.

    Returns z-score or None if insufficient data.
    """
    this_week_count = 0
    weekly_counts = [0, 0, 0, 0]
    one_week_ago = ref_date - timedelta(days=7)
    four_weeks_ago = ref_date - timedelta(days=35)

    for d in date_strings:
        try:
            dt = datetime.fromisoformat(d)
        except (ValueError, TypeError):
            continue
        days_ago = (ref_date - dt).days
        if 0 <= days_ago <= 7:
            this_week_count += 1
        else:
            weeks_ago = days_ago // 7
            if 1 <= weeks_ago <= 4:
                weekly_counts[weeks_ago - 1] += 1

    avg_weekly = sum(weekly_counts) / 4.0
    if avg_weekly <= 0 or this_week_count <= 0:
        return None

    variance = sum((c - avg_weekly) ** 2 for c in weekly_counts) / 4.0
    std_weekly = math.sqrt(variance) if variance > 0 else 1.0
    return (this_week_count - avg_weekly) / max(std_weekly, 1.0)


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
