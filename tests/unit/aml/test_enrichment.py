from __future__ import annotations

import uuid
from datetime import datetime, timedelta, UTC

from sqlalchemy import select

import pytest

from src.aml_workflow.enrichment import (
    EnrichedContext,
    _compute_std,
    _format_context,
    _parse_date,
    enrich_transactions,
)
from src.bff.models.account import Account
from src.file_processor.models import Transaction, UploadedFiles


class TestEnrichedContext:
    def test_defaults(self):
        ctx = EnrichedContext()
        assert ctx.customer_txn_count_30d == 0
        assert ctx.customer_sum_30d == 0.0
        assert ctx.customer_avg_30d == 0.0
        assert ctx.customer_std_amt_30d is None
        assert ctx.account_type is None
        assert ctx.account_age_days is None
        assert ctx.structuring_24h_count == 0
        assert ctx.velocity_zscore is None
        assert ctx.dormancy_days is None


class TestParseDate:
    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_empty_returns_none(self):
        assert _parse_date("") is None

    def test_invalid_returns_none(self):
        assert _parse_date("not-a-date") is None

    def test_valid_iso(self):
        result = _parse_date("2026-05-01T12:00:00")
        assert result is not None
        assert result.year == 2026
        assert result.month == 5


class TestComputeStd:
    def test_none_for_single_value(self):
        assert _compute_std([100.0]) is None

    def test_none_for_empty(self):
        assert _compute_std([]) is None

    def test_computes_std(self):
        result = _compute_std([100.0, 200.0, 300.0])
        assert result is not None
        assert result == pytest.approx(100.0, rel=0.1)


class TestFormatContext:
    def test_empty_context(self):
        assert _format_context(EnrichedContext()) == ""

    def test_30d_stats(self):
        ctx = EnrichedContext(
            customer_txn_count_30d=5,
            customer_sum_30d=25000.0,
            customer_avg_30d=5000.0,
            customer_std_amt_30d=2000.0,
        )
        result = _format_context(ctx)
        assert "## Enriched Context" in result
        assert "5 txns" in result
        assert "$25,000 total" in result
        assert "$5,000 avg" in result
        assert "$2,000" in result

    def test_30d_no_std(self):
        ctx = EnrichedContext(
            customer_txn_count_30d=1,
            customer_sum_30d=5000.0,
            customer_avg_30d=5000.0,
        )
        result = _format_context(ctx)
        assert "Std dev" not in result

    def test_structuring(self):
        ctx = EnrichedContext(structuring_24h_count=3)
        result = _format_context(ctx)
        assert "Structuring alert" in result
        assert "3 txns" in result

    def test_velocity_normal(self):
        ctx = EnrichedContext(velocity_zscore=1.2)
        result = _format_context(ctx)
        assert "z-score: 1.2" in result
        assert "anomalous" not in result

    def test_velocity_anomalous(self):
        ctx = EnrichedContext(velocity_zscore=3.5)
        result = _format_context(ctx)
        assert "z-score: 3.5" in result
        assert "anomalous" in result

    def test_dormancy(self):
        ctx = EnrichedContext(dormancy_days=90)
        result = _format_context(ctx)
        assert "Dormancy: 90 days" in result

    def test_account_profile(self):
        ctx = EnrichedContext(account_type="checking", account_age_days=365)
        result = _format_context(ctx)
        assert "Account: checking" in result
        assert "opened 365 days ago" in result

    def test_account_profile_no_age(self):
        ctx = EnrichedContext(account_type="savings")
        result = _format_context(ctx)
        assert "Account: savings" in result
        assert "days ago" not in result


@pytest.mark.asyncio
async def test_enrich_no_flagged_txns(seeded_session):
    txns = [{"customer_id": "CUST001", "status": "loaded"}]
    result = await enrich_transactions(seeded_session, txns, "upload-1")
    assert result == {}


@pytest.mark.asyncio
async def test_enrich_empty_txns(seeded_session):
    result = await enrich_transactions(seeded_session, [], "upload-1")
    assert result == {}


@pytest.mark.asyncio
async def test_enrich_single_flagged_txn(seeded_session):
    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(id="u1", filename="test.csv", status="completed", created_at=now, updated_at=now)
    seeded_session.add(upload)
    seeded_session.add(Account(account_id="ACC100", customer_id="CUST100", type="checking", date_opened="2024-01-01", created_at=now, updated_at=now))
    seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u1", account_id="ACC100", customer_id="CUST100",
                                   amount=15000.0, counterparty="X", city="New York", state="NY", country="US", date=now,
                                   source_txn_id="T1", created_at=now, updated_at=now))
    await seeded_session.commit()

    txns = [{"customer_id": "CUST100", "account_id": "ACC100", "status": "flagged"}]
    result = await enrich_transactions(seeded_session, txns, "u1")
    assert "CUST100" in result
    ctx = result["CUST100"]
    assert ctx["account_type"] == "checking"
    assert ctx["account_age_days"] is not None
    assert ctx["customer_txn_count_30d"] == 1


@pytest.mark.asyncio
async def test_enrich_structuring_detected(seeded_session):
    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(id="u2", filename="test.csv", status="completed", created_at=now, updated_at=now)
    seeded_session.add(upload)
    for i in range(3):
        seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u2", account_id="ACC200", customer_id="CUST200",
                                       amount=9500.0, counterparty="Y", state="CA", country="US", date=now,
                                       source_txn_id=f"T{i}", created_at=now, updated_at=now))
    await seeded_session.commit()

    txns = [{"customer_id": "CUST200", "account_id": "ACC200", "status": "flagged"}]
    result = await enrich_transactions(seeded_session, txns, "u2")
    ctx = result["CUST200"]
    assert ctx["structuring_24h_count"] == 3


@pytest.mark.asyncio
async def test_enrich_multi_customer(seeded_session):
    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(id="u3", filename="test.csv", status="completed", created_at=now, updated_at=now)
    seeded_session.add(upload)
    seeded_session.add(Account(account_id="ACC300", customer_id="CUST300", type="checking", date_opened="2023-01-01", created_at=now, updated_at=now))
    seeded_session.add(Account(account_id="ACC301", customer_id="CUST301", type="savings", date_opened="2024-06-01", created_at=now, updated_at=now))
    seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u3", account_id="ACC300", customer_id="CUST300",
                                   amount=50000.0, counterparty="A", city="New York", state="NY", country="US", date=now,
                                   source_txn_id="T1", created_at=now, updated_at=now))
    seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u3", account_id="ACC301", customer_id="CUST301",
                                   amount=2000.0, counterparty="B", state="MA", country="US", date=now,
                                   source_txn_id="T2", created_at=now, updated_at=now))
    await seeded_session.commit()

    txns = [
        {"customer_id": "CUST300", "account_id": "ACC300", "status": "flagged"},
        {"customer_id": "CUST301", "account_id": "ACC301", "status": "flagged"},
    ]
    result = await enrich_transactions(seeded_session, txns, "u3")
    assert len(result) == 2
    assert result["CUST300"]["account_type"] == "checking"
    assert result["CUST301"]["account_type"] == "savings"
    assert result["CUST300"]["customer_txn_count_30d"] == 1
    assert result["CUST301"]["customer_txn_count_30d"] == 1


@pytest.mark.asyncio
async def test_enrich_no_account_record(seeded_session):
    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(id="u4", filename="test.csv", status="completed", created_at=now, updated_at=now)
    seeded_session.add(upload)
    seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u4", account_id="ACC400", customer_id="CUST400",
                                   amount=1000.0, counterparty="C", state="TX", country="US", date=now,
                                   source_txn_id="T1", created_at=now, updated_at=now))
    await seeded_session.commit()

    txns = [{"customer_id": "CUST400", "account_id": "ACC400", "status": "flagged"}]
    result = await enrich_transactions(seeded_session, txns, "u4")
    ctx = result["CUST400"]
    assert ctx["account_type"] is None
    assert ctx["account_age_days"] is None
    assert ctx["customer_txn_count_30d"] == 1


@pytest.mark.asyncio
async def test_enrich_no_transactions_for_upload(seeded_session):
    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(id="u5", filename="test.csv", status="completed", created_at=now, updated_at=now)
    seeded_session.add(upload)
    await seeded_session.commit()

    txns = [{"customer_id": "CUST500", "account_id": "ACC500", "status": "flagged"}]
    result = await enrich_transactions(seeded_session, txns, "u5")
    ctx = result["CUST500"]
    assert ctx["customer_txn_count_30d"] == 0
    assert ctx["account_type"] is None


@pytest.mark.asyncio
async def test_enrich_velocity_zscore(seeded_session):
    now = datetime.now(UTC)
    upload = UploadedFiles(id="u6", filename="test.csv", status="completed", created_at=now.isoformat(), updated_at=now.isoformat())
    seeded_session.add(upload)
    # Create prior historical data: 1 txn each week for 4 weeks prior
    for weeks_ago in range(1, 5):
        txn_date = (now - timedelta(weeks=weeks_ago, days=1)).isoformat()
        seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u6", account_id="ACC600", customer_id="CUST600",
                                       amount=5000.0, counterparty="D", state="TX", country="US", date=txn_date,
                                       source_txn_id=f"T{weeks_ago}", created_at=now.isoformat(), updated_at=now.isoformat()))
    # Create high this-week count (5 txns vs avg ~1) for anomalous z-score
    for i in range(5):
        recent_date = (now - timedelta(hours=i)).isoformat()
        seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u6", account_id="ACC600", customer_id="CUST600",
                                       amount=1000.0, counterparty="E", city="New York", state="NY", country="US", date=recent_date,
                                       source_txn_id=f"Tr{i}", created_at=now.isoformat(), updated_at=now.isoformat()))
    await seeded_session.commit()

    txns = [{"customer_id": "CUST600", "account_id": "ACC600", "status": "flagged"}]
    result = await enrich_transactions(seeded_session, txns, "u6")
    ctx = result["CUST600"]
    assert ctx["velocity_zscore"] is not None
    assert ctx["velocity_zscore"] > 2  # anomalous


@pytest.mark.asyncio
async def test_enrich_dormancy_detected(seeded_session):
    now = datetime.now(UTC).isoformat()
    recent = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    old_date = (datetime.now(UTC) - timedelta(days=180)).isoformat()
    upload = UploadedFiles(id="u7", filename="test.csv", status="completed", created_at=now, updated_at=now)
    seeded_session.add(upload)
    # A recent transaction sets ref_date; the flagged account has only old transactions
    seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u7", account_id="ACC_UNUSED", customer_id="OTHER",
                                   amount=100.0, counterparty="X", country="", date=recent,
                                   source_txn_id="T_ref", created_at=now, updated_at=now))
    seeded_session.add(Account(account_id="ACC700", customer_id="CUST700", type="savings", date_opened="2023-01-01", created_at=now, updated_at=now))
    seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u7", account_id="ACC700", customer_id="CUST700",
                                   amount=500.0, counterparty="F", state="CA", country="US", date=old_date,
                                   source_txn_id="T1", created_at=now, updated_at=now))
    await seeded_session.commit()

    txns = [{"customer_id": "CUST700", "account_id": "ACC700", "status": "flagged"}]
    result = await enrich_transactions(seeded_session, txns, "u7")
    ctx = result["CUST700"]
    assert ctx["dormancy_days"] is not None
    assert ctx["dormancy_days"] >= 170


@pytest.mark.asyncio
async def test_enrichment_snapshot_created(seeded_session):
    from src.aml_workflow.models.enrichment_snapshot import EnrichmentSnapshot

    now = datetime.now(UTC).isoformat()
    upload = UploadedFiles(id="u_snap", filename="test.csv", status="completed", created_at=now, updated_at=now)
    seeded_session.add(upload)
    seeded_session.add(Account(account_id="ACC_SNAP", customer_id="CUST_SNAP", type="checking", date_opened="2024-01-01", created_at=now, updated_at=now))
    seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u_snap", account_id="ACC_SNAP", customer_id="CUST_SNAP",
                                   amount=50000.0, counterparty="X", city="New York", state="NY", country="US", date=now,
                                   source_txn_id="T1", created_at=now, updated_at=now))
    await seeded_session.commit()

    txns = [{"customer_id": "CUST_SNAP", "account_id": "ACC_SNAP", "status": "flagged"}]
    result = await enrich_transactions(seeded_session, txns, "u_snap")

    snap = await seeded_session.get(EnrichmentSnapshot, ("u_snap", "CUST_SNAP"))
    assert snap is not None
    assert snap.customer_txn_count_30d == result["CUST_SNAP"]["customer_txn_count_30d"]
    assert snap.customer_sum_30d == result["CUST_SNAP"]["customer_sum_30d"]
    assert snap.customer_avg_30d == result["CUST_SNAP"]["customer_avg_30d"]
    assert snap.structuring_24h_count == result["CUST_SNAP"]["structuring_24h_count"]
    assert snap.account_type == "checking"
    assert snap.upload_id == "u_snap"
    assert snap.customer_id == "CUST_SNAP"


@pytest.mark.asyncio
async def test_enrich_velocity_skips_bad_dates(seeded_session):
    now = datetime.now(UTC)
    ref_str = now.isoformat()
    upload = UploadedFiles(id="u_baddate", filename="test.csv", status="completed",
                           created_at=ref_str, updated_at=ref_str)
    seeded_session.add(upload)
    seeded_session.add(Account(account_id="ACC_BAD", customer_id="CUST_BAD", type="checking",
                               date_opened="2023-01-01", created_at=ref_str,
                               updated_at=ref_str))
    # Good recent txn to set ref_date
    seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u_baddate",
                                   account_id="ACC_BAD", customer_id="CUST_BAD",
                                   amount=100.0, counterparty="X", city="New York", state="NY", country="US",
                                   date=ref_str, source_txn_id="T_ref",
                                   created_at=ref_str,
                                   updated_at=ref_str))
    # Prior-period txns for velocity window: one good, one with unparseable date
    prior_str = (now - timedelta(days=14)).isoformat()
    seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u_baddate",
                                   account_id="ACC_BAD", customer_id="CUST_BAD",
                                   amount=500.0, counterparty="Prior", state="TX", country="US",
                                   date=prior_str, source_txn_id="T_prior",
                                   created_at=ref_str,
                                   updated_at=ref_str))
    # Bad date — ISO-like with trailing X so fromisoformat fails but sorts within range
    seeded_session.add(Transaction(id=str(uuid.uuid4()), upload_id="u_baddate",
                                   account_id="ACC_BAD", customer_id="CUST_BAD",
                                   amount=1000.0, counterparty="Bad", state="CA", country="US",
                                   date=prior_str[:19] + "X", source_txn_id="T_bad",
                                   created_at=ref_str,
                                   updated_at=ref_str))
    await seeded_session.commit()

    txns = [{"customer_id": "CUST_BAD", "account_id": "ACC_BAD", "status": "flagged"}]
    result = await enrich_transactions(seeded_session, txns, "u_baddate")
    ctx = result["CUST_BAD"]
    # 3 txns in 30d window (ref + prior + bad-date); bad-date amount still counted
    # but its parse failure is skipped in velocity z-score bucket
    assert ctx["customer_txn_count_30d"] == 3
    assert ctx["velocity_zscore"] is None or isinstance(ctx["velocity_zscore"], float)


@pytest.mark.asyncio
async def test_enrichment_snapshot_not_created_for_clean(seeded_session):
    from src.aml_workflow.models.enrichment_snapshot import EnrichmentSnapshot

    txns = [{"customer_id": "CUST001", "status": "loaded"}]
    await enrich_transactions(seeded_session, txns, "upload-x")

    result = await seeded_session.execute(
        select(EnrichmentSnapshot).where(EnrichmentSnapshot.upload_id == "upload-x")
    )
    assert result.scalar_one_or_none() is None
