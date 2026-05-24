from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.models.enrichment_snapshot import EnrichmentSnapshot
from src.bff.models.account import Account
from src.file_processor.models import Transaction


@dataclass
class EnrichedContext:
    customer_txn_count_30d: int = 0
    customer_sum_30d: float = 0.0
    customer_avg_30d: float = 0.0
    customer_std_amt_30d: float | None = None
    account_type: str | None = None
    account_age_days: int | None = None
    structuring_24h_count: int = 0
    velocity_zscore: float | None = None
    dormancy_days: int | None = None


def _compute_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return statistics.stdev(values)


def _parse_date(d: str | None) -> datetime | None:
    if not d:
        return None
    try:
        return datetime.fromisoformat(d)
    except (ValueError, TypeError):
        return None


def _format_context(ctx: EnrichedContext) -> str:
    lines: list[str] = []
    if ctx.customer_txn_count_30d:
        lines.append(f"- Customer activity (30d): {ctx.customer_txn_count_30d} txns, "
                     f"${ctx.customer_sum_30d:,.0f} total, ${ctx.customer_avg_30d:,.0f} avg")
        if ctx.customer_std_amt_30d is not None:
            lines.append(f"  - Std dev: ${ctx.customer_std_amt_30d:,.0f}")
    if ctx.structuring_24h_count:
        lines.append(f"- Structuring alert: {ctx.structuring_24h_count} txns near $10K threshold in past 24h")
    if ctx.velocity_zscore is not None:
        alert = " — anomalous" if abs(ctx.velocity_zscore) > 2 else ""
        lines.append(f"- Velocity z-score: {ctx.velocity_zscore:.1f}{alert}")
    if ctx.dormancy_days is not None:
        lines.append(f"- Dormancy: {ctx.dormancy_days} days since last transaction")
    if ctx.account_type:
        age = f", opened {ctx.account_age_days} days ago" if ctx.account_age_days is not None else ""
        lines.append(f"- Account: {ctx.account_type}{age}")
    if not lines:
        return ""
    return "## Enriched Context\n" + "\n".join(lines)


async def enrich_transactions(
    db: AsyncSession,
    transactions: list[dict],
    upload_id: str,
) -> dict[str, dict]:
    flagged = [t for t in transactions if t.get("status") == "flagged"]
    if not flagged:
        return {}

    # Get upload's max date as reference time
    upload_max_date_row = await db.execute(
        select(func.max(Transaction.date)).where(Transaction.upload_id == upload_id)
    )
    upload_max_date = upload_max_date_row.scalar()
    ref_date = _parse_date(upload_max_date) or datetime.now(UTC)

    # Collect unique customer_ids from flagged txns
    customer_ids = list({t["customer_id"] for t in flagged if t.get("customer_id")})

    # Batch-fetch enrichment data per customer
    results: dict[str, dict] = {}

    for cid in customer_ids:
        context = EnrichedContext()

        # Customer account profile
        account_row = await db.execute(
            select(Account).where(Account.customer_id == cid).limit(1)
        )
        account = account_row.scalar_one_or_none()
        if account:
            context.account_type = account.type
            opened = _parse_date(account.date_opened)
            if opened:
                context.account_age_days = (ref_date.date() - opened.date()).days

        # Dormancy: days since last txn for any account this customer uses
        # We need the account_ids for this customer's flagged txns
        flagged_accounts = list({t["account_id"] for t in flagged
                                if t.get("customer_id") == cid and t.get("account_id")})
        if flagged_accounts:
            last_txn_row = await db.execute(
                select(func.max(Transaction.date))
                .where(Transaction.account_id.in_(flagged_accounts))
            )
            last_txn = last_txn_row.scalar()
            last_txn_date = _parse_date(last_txn)
            if last_txn_date:
                context.dormancy_days = (ref_date.date() - last_txn_date.date()).days

        # 30-day window statistics
        thirty_days_ago = (ref_date - timedelta(days=30)).isoformat()
        txn_rows = await db.execute(
            select(Transaction.amount)
            .where(
                Transaction.customer_id == cid,
                Transaction.date >= thirty_days_ago,
                Transaction.date <= ref_date.isoformat(),
            )
        )
        amounts = [r[0] for r in txn_rows if r[0] is not None]
        if amounts:
            context.customer_txn_count_30d = len(amounts)
            context.customer_sum_30d = sum(amounts)
            context.customer_avg_30d = sum(amounts) / len(amounts)
            context.customer_std_amt_30d = _compute_std(amounts)

        # Structuring 24h: count txns in [$9K, $10K] for same customer
        one_day_ago = (ref_date - timedelta(days=1)).isoformat()
        structuring_row = await db.execute(
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.customer_id == cid,
                Transaction.amount >= 9000,
                Transaction.amount <= 10000,
                Transaction.date >= one_day_ago,
                Transaction.date <= ref_date.isoformat(),
            )
        )
        context.structuring_24h_count = structuring_row.scalar() or 0

        # Velocity z-score: this week vs prior 4 weeks
        one_week_ago = (ref_date - timedelta(days=7)).isoformat()
        four_weeks_ago = (ref_date - timedelta(days=35)).isoformat()
        week_prior_start = (ref_date - timedelta(days=7)).isoformat()
        week_prior_end = ref_date.isoformat()
        four_week_prior_start = (ref_date - timedelta(days=35)).isoformat()
        four_week_prior_end = (ref_date - timedelta(days=7)).isoformat()

        this_week_row = await db.execute(
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.customer_id == cid,
                Transaction.date >= one_week_ago,
                Transaction.date <= ref_date.isoformat(),
            )
        )
        this_week_count = this_week_row.scalar() or 0

        prior_4wk_rows = await db.execute(
            select(Transaction.date)
            .where(
                Transaction.customer_id == cid,
                Transaction.date >= four_weeks_ago,
                Transaction.date < one_week_ago,
            )
            .order_by(Transaction.date)
        )
        prior_dates = prior_4wk_rows.scalars().all()

        # Bucket into 4 weekly bins
        weekly_counts = [0, 0, 0, 0]
        for d in prior_dates:
            dt = _parse_date(d)
            if dt is None:
                continue
            weeks_ago = (ref_date - dt).days // 7
            if 1 <= weeks_ago <= 4:
                weekly_counts[weeks_ago - 1] += 1

        avg_weekly = sum(weekly_counts) / max(len(weekly_counts), 1)
        if avg_weekly > 0 and this_week_count > 0:
            variance = sum((c - avg_weekly) ** 2 for c in weekly_counts) / max(len(weekly_counts), 1)
            std_weekly = math.sqrt(variance) if variance > 0 else 1.0
            context.velocity_zscore = (this_week_count - avg_weekly) / max(std_weekly, 1.0)

        # Serialize to dict
        results[cid] = {
            "customer_txn_count_30d": context.customer_txn_count_30d,
            "customer_sum_30d": context.customer_sum_30d,
            "customer_avg_30d": context.customer_avg_30d,
            "customer_std_amt_30d": context.customer_std_amt_30d,
            "account_type": context.account_type,
            "account_age_days": context.account_age_days,
            "structuring_24h_count": context.structuring_24h_count,
            "velocity_zscore": context.velocity_zscore,
            "dormancy_days": context.dormancy_days,
        }

    # Write enrichment snapshots for eval audit trail
    if results:
        now = datetime.now(UTC).isoformat()
        snapshots = [
            EnrichmentSnapshot(
                upload_id=upload_id,
                customer_id=cid,
                ref_date=ref_date.isoformat(),
                customer_txn_count_30d=ctx["customer_txn_count_30d"],
                customer_sum_30d=ctx["customer_sum_30d"],
                customer_avg_30d=ctx["customer_avg_30d"],
                customer_std_amt_30d=ctx["customer_std_amt_30d"],
                account_type=ctx["account_type"],
                account_age_days=ctx["account_age_days"],
                structuring_24h_count=ctx["structuring_24h_count"],
                velocity_zscore=ctx["velocity_zscore"],
                dormancy_days=ctx["dormancy_days"],
                created_at=now,
            )
            for cid, ctx in results.items()
        ]
        db.add_all(snapshots)
        await db.commit()

    return results
