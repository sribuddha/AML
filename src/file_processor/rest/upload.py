import asyncio
import uuid
from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.bff.config import UPLOAD_DIR
from src.bff.database import get_db
from src.file_processor.service import REQUIRED_FIELDS, HEADER_ALIASES, process_upload, retry_upload

router = APIRouter()


@router.post("/api/uploads")
async def upload_file(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    upload_id = str(uuid.uuid4())
    content = await file.read()

    try:
        df = pd.read_csv(BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    actual_cols = set(df.columns.str.strip().str.lower())
    expected_cols = set(HEADER_ALIASES.keys())

    missing = [c for c in expected_cols if not actual_cols.intersection(HEADER_ALIASES[c])]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {missing}",
        )

    col_map = {}
    for col in df.columns:
        stripped = col.strip().lower()
        for canonical, aliases in HEADER_ALIASES.items():
            if stripped in aliases:
                col_map[col] = canonical
                break
    df = df.rename(columns=col_map)
    keep_cols = list(REQUIRED_FIELDS)
    if "source_txn_id" in df.columns:
        keep_cols.append("source_txn_id")
    df = df[keep_cols]

    result = await process_upload(df, file.filename, upload_id, db, content)

    async def _trigger_workflow():
        from src.bff.database import async_session_factory
        async with async_session_factory() as workflow_db:
            from src.aml_workflow.triggers import run_validation
            await run_validation(upload_id, workflow_db)

    asyncio.create_task(_trigger_workflow())

    return result


@router.post("/api/uploads/{upload_id}/retry", status_code=201)
async def retry_upload_endpoint(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await retry_upload(upload_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result
