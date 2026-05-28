"""Query DB and print summary report for an upload.

Usage:
    python -m scripts.report_upload --upload-id <uuid>
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select

from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles
from src.core.models.validation_result import ValidationResult
from src.core.models.sar import SAR
from src.core.models.enrichment_snapshot import EnrichmentSnapshot
from src.bff.database import async_session_factory


async def report(upload_id: str):
    async with async_session_factory() as session:
        txn_result = await session.execute(
            select(Transaction).where(Transaction.upload_id == upload_id)
        )
        txns = txn_result.scalars().all()

        vr_result = await session.execute(
            select(ValidationResult).where(ValidationResult.upload_id == upload_id)
        )
        vrs = vr_result.scalars().all()

        sar_result = await session.execute(
            select(SAR).where(SAR.upload_id == upload_id)
        )
        sars = sar_result.scalars().all()

        snap_result = await session.execute(
            select(EnrichmentSnapshot).where(EnrichmentSnapshot.upload_id == upload_id)
        )
        snaps = snap_result.scalars().all()

        flagged = sum(1 for v in vrs if v.status == "flagged")
        escalated = sum(1 for v in vrs if v.risk_level == "high")
        auto_reviewed = sum(1 for v in vrs if v.risk_level == "auto_reviewed")
        no_risk = sum(1 for v in vrs if v.risk_level is None)

        rule_counts: Counter[str] = Counter()
        for v in vrs:
            if v.flag_details:
                for rule_name in v.flag_details.values():
                    rule_counts[rule_name] += 1

        upload_rec = await session.get(UploadedFiles, upload_id)

    print()
    print("=== Upload Report ===")
    print(f"  Upload ID:           {upload_id}")
    print(f"  Total transactions:  {len(txns)}")
    print(f"  Validation results:  {len(vrs)}")
    print(f"    Flagged:           {flagged}")
    print(f"    Escalated (high):  {escalated}")
    print(f"    Auto-reviewed:     {auto_reviewed}")
    if no_risk:
        print(f"    No risk_level:     {no_risk}")
    print(f"  Enrichment snapshots: {len(snaps)} customers")
    print(f"  SARs created:        {len(sars)}")
    if upload_rec:
        print(f"  Upload status:       {upload_rec.status}")
    print()

    if rule_counts:
        print("  Rule coverage:")
        for rule_name, count in sorted(rule_counts.items()):
            print(f"    {rule_name:30s} {count} flagged")
        print()


def main():
    parser = argparse.ArgumentParser(description="Query DB and print summary report for an upload")
    parser.add_argument("--upload-id", required=True, help="Upload UUID")
    args = parser.parse_args()

    import asyncio
    asyncio.run(report(args.upload_id))


if __name__ == "__main__":
    main()
