import argparse
import asyncio
import shutil

from sqlalchemy import delete, select

from src.aml_workflow.models.audit_log import AuditLog
from src.core.models.enrichment_snapshot import EnrichmentSnapshot
from src.core.models.sar import SAR
from src.core.models.validation_result import ValidationResult
from src.bff.config import UPLOAD_DIR
from src.bff.database import async_session_factory
from src.file_processor.models import RejectedRecord
from src.core.models.transaction import Transaction
from src.core.models.uploaded_files import UploadedFiles


async def delete_upload(upload_id: str):
    async with async_session_factory() as session:
        # Check upload exists
        result = await session.execute(
            select(UploadedFiles).where(UploadedFiles.id == upload_id)
        )
        upload = result.scalar_one_or_none()
        if not upload:
            print(f"Upload {upload_id} not found.")
            return

        # Delete in FK-safe order: children before parents

        # ValidationResult references both transaction + uploaded_files
        result_vr = await session.execute(
            delete(ValidationResult)
            .where(ValidationResult.upload_id == upload_id)
            .returning(ValidationResult.id)
        )
        vr_count = len(result_vr.fetchall())

        # Sar references transaction + uploaded_files (rule_id is nullable)
        result_sar = await session.execute(
            delete(SAR).where(SAR.upload_id == upload_id).returning(SAR.id)
        )
        sar_count = len(result_sar.fetchall())

        # AuditLog has nullable FK to uploaded_files
        result_al = await session.execute(
            delete(AuditLog)
            .where(AuditLog.upload_id == upload_id)
            .returning(AuditLog.id)
        )
        al_count = len(result_al.fetchall())

        # EnrichmentSnapshot references uploaded_files only
        result_es = await session.execute(
            delete(EnrichmentSnapshot)
            .where(EnrichmentSnapshot.upload_id == upload_id)
            .returning(EnrichmentSnapshot.customer_id)
        )
        es_count = len(result_es.fetchall())

        result_tx = await session.execute(
            delete(Transaction)
            .where(Transaction.upload_id == upload_id)
            .returning(Transaction.id)
        )
        tx_count = len(result_tx.fetchall())

        result_rj = await session.execute(
            delete(RejectedRecord)
            .where(RejectedRecord.upload_id == upload_id)
            .returning(RejectedRecord.id)
        )
        rj_count = len(result_rj.fetchall())

        # Delete chunk rows belonging to this upload
        result_chunks = await session.execute(
            delete(UploadedFiles).where(
                UploadedFiles.filename.like(f"{upload.filename}.%"),
                UploadedFiles.upload_chunk.isnot(None),
            ).returning(UploadedFiles.id)
        )
        chunk_count = len(result_chunks.fetchall())

        await session.delete(upload)
        await session.commit()

        # Remove staging directory from disk
        staging_dir = UPLOAD_DIR / "staging" / upload_id
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
            print(f"  Staging directory removed: {staging_dir}")
        else:
            print(f"  Staging directory not found: {staging_dir}")

        # Remove upload data directory (contains data.csv copy)
        upload_dir = UPLOAD_DIR / upload_id
        if upload_dir.exists():
            shutil.rmtree(upload_dir)
            print(f"  Upload data directory removed: {upload_dir}")
        else:
            print(f"  Upload data directory not found: {upload_dir}")

        print(f"Deleted upload {upload_id} ({upload.filename}):")
        print(f"  Validation results removed: {vr_count}")
        print(f"  SARs removed:               {sar_count}")
        print(f"  Audit log entries removed:  {al_count}")
        print(f"  Enrichment snapshots removed:{es_count}")
        print(f"  Transactions removed:       {tx_count}")
        print(f"  Rejected records removed:   {rj_count}")
        print(f"  Chunk rows removed:         {chunk_count}")


def run():
    parser = argparse.ArgumentParser(description="Delete an upload and all associated records")
    parser.add_argument("upload_id", type=str, help="ID of the upload to delete")
    args = parser.parse_args()
    asyncio.run(delete_upload(args.upload_id))


if __name__ == "__main__":
    run()
