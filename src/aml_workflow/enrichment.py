from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.enrichment_snapshot import EnrichmentSnapshot
from src.core.utils import now as _now
from src.core.metrics import compute_velocity_zscore
from src.core.models.account import Account
from src.core.models.transaction import Transaction


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
    if not customer_ids:
        return {}

    # Precompute customer->accounts map from flagged txns (avoids per-customer queries)
    flagged_accounts_by_customer: dict[str, set[str]] = {}
    for t in flagged:
        cid = t.get("customer_id")
        aid = t.get("account_id")
        if cid and aid:
            flagged_accounts_by_customer.setdefault(cid, set()).add(aid)

    all_account_ids: set[str] = set()
    for aids in flagged_accounts_by_customer.values():
        all_account_ids.update(aids)

    # ── Batch query 1: Account profiles ────────────────────────
    account_rows = await db.execute(
        select(Account).where(Account.customer_id.in_(customer_ids))
    )
    accounts_by_cid: dict[str, Account] = {}
    for a in account_rows.scalars().all():
        if a.customer_id not in accounts_by_cid:
            accounts_by_cid[a.customer_id] = a

    # ── Batch query 2: Dormancy (last txn date per account) ────
    last_txn_by_account: dict[str, str] = {}
    if all_account_ids:
        last_txn_rows = await db.execute(
            select(Transaction.account_id, func.max(Transaction.date))
            .where(Transaction.account_id.in_(list(all_account_ids)))
            .group_by(Transaction.account_id)
        )
        last_txn_by_account = dict(last_txn_rows.fetchall())

    # ── Batch query 3: 30-day amounts list per customer ────────
    thirty_days_ago = (ref_date - timedelta(days=30)).isoformat()
    window_end = ref_date.isoformat()
    txn_amount_rows = await db.execute(
        select(Transaction.customer_id, Transaction.amount)
        .where(
            Transaction.customer_id.in_(customer_ids),
            Transaction.date >= thirty_days_ago,
            Transaction.date <= window_end,
        )
    )
    amounts_by_customer: dict[str, list[float]] = {}
    for cid, amt in txn_amount_rows:
        if cid not in amounts_by_customer:
            amounts_by_customer[cid] = []
        if amt is not None:
            amounts_by_customer[cid].append(amt)

    # ── Batch query 4: Structuring 24h per customer ────────────
    one_day_ago = (ref_date - timedelta(days=1)).isoformat()
    structuring_rows = await db.execute(
        select(Transaction.customer_id, func.count())
        .select_from(Transaction)
        .where(
            Transaction.customer_id.in_(customer_ids),
            Transaction.amount >= 9000,
            Transaction.amount <= 10000,
            Transaction.date >= one_day_ago,
            Transaction.date <= window_end,
        )
        .group_by(Transaction.customer_id)
    )
    structuring_counts = dict(structuring_rows.fetchall())

    # ── Batch query 5: Velocity data (dates for this_week + prior_4wk) ──
    four_weeks_ago = (ref_date - timedelta(days=35)).isoformat()
    date_rows = await db.execute(
        select(Transaction.customer_id, Transaction.date)
        .where(
            Transaction.customer_id.in_(customer_ids),
            Transaction.date >= four_weeks_ago,
            Transaction.date <= window_end,
        )
    )
    dates_by_customer: dict[str, list[str]] = {}
    for cid, d in date_rows:
        dates_by_customer.setdefault(cid, []).append(d)

    # ── Assemble results per customer ──────────────────────────
    results: dict[str, dict] = {}
    for cid in customer_ids:
        context = EnrichedContext()

        account = accounts_by_cid.get(cid)
        if account:
            context.account_type = account.type
            opened = _parse_date(account.date_opened)
            if opened:
                context.account_age_days = (ref_date.date() - opened.date()).days

        flagged_accounts = flagged_accounts_by_customer.get(cid, set())
        max_txn_date: str | None = None
        for aid in flagged_accounts:
            d = last_txn_by_account.get(aid)
            if d and (max_txn_date is None or d > max_txn_date):
                max_txn_date = d
        last_txn_date = _parse_date(max_txn_date)
        if last_txn_date:
            context.dormancy_days = (ref_date.date() - last_txn_date.date()).days

        amounts = amounts_by_customer.get(cid, [])
        if amounts:
            context.customer_txn_count_30d = len(amounts)
            context.customer_sum_30d = sum(amounts)
            context.customer_avg_30d = sum(amounts) / len(amounts)
            context.customer_std_amt_30d = _compute_std(amounts)

        context.structuring_24h_count = structuring_counts.get(cid, 0) or 0

        # Velocity z-score
        all_dates = dates_by_customer.get(cid, [])
        context.velocity_zscore = compute_velocity_zscore(all_dates, ref_date)

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
        now = _now()
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
