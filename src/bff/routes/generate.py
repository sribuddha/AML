import asyncio
import csv
import io
import json
from datetime import datetime, UTC, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from src.bff.config import BASE_DIR
from src.core.schemas import EvalEntry, GenerateRequest, GenerateResponse

router = APIRouter()

WORK_DIR = BASE_DIR / "work"
WORK_DIR.mkdir(parents=True, exist_ok=True)

STEP_TYPES = {"upload", "stage1", "stage2", "synthetic"}


async def _run_step(step: dict, date: str, output: Path):
    stype = step["type"]
    count = step["count"]

    if stype == "upload":
        from scripts.generate_upload_data import generate as fn
        bad_rows = step["bad_rate"]
        await fn(count, bad_rows, date, output)

    elif stype == "stage1":
        from scripts.generate_stage1_fraud_data import generate as fn
        await fn(count, date, output)

    elif stype == "stage2":
        from scripts.generate_stage2_fraud_data import generate as fn
        await fn(count, date, output)

    elif stype == "synthetic":
        from scripts.test_generate_fraud_data import generate as fn
        manifest = output.with_suffix(".manifest.json")
        await fn(count, str(output), str(manifest), False)

    else:
        raise HTTPException(status_code=400, detail=f"Unknown step type: {stype}")


@router.post("/api/generate")
async def generate_test_data(body: GenerateRequest):
    if not body.steps:
        raise HTTPException(status_code=400, detail="At least one step required")

    date_raw = body.date or (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")

    types_part = "_".join(s.type for s in body.steps)
    filename = f"{uuid4()}_{types_part}.csv"
    output_path = WORK_DIR / filename

    for step in body.steps:
        await _run_step(step.model_dump(), date_raw, output_path)

    if body.shuffle:
        from scripts.data_scrambler import scramble
        scramble(output_path)

    eval_url = None
    eval_path = output_path.with_suffix(".eval")
    if eval_path.exists():
        eval_url = f"/api/generate/eval/{filename}"

    return GenerateResponse(
        download_url=f"/api/generate/download/{filename}",
        filename=filename,
        eval_url=eval_url,
    )


@router.get("/api/generate/download/{filename}")
async def download_generated_file(filename: str):
    safe_name = Path(filename).name
    file_path = WORK_DIR / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.get("/api/generate/eval/{filename}")
async def get_generated_eval(filename: str):
    safe_name = Path(filename).name
    eval_path = (WORK_DIR / safe_name).with_suffix(".eval")

    if eval_path.exists():
        entries: list[EvalEntry] = []
        with open(eval_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    entries.append(EvalEntry(**data))
        return entries

    manifest_path = (WORK_DIR / safe_name).with_suffix(".manifest.json")
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        return [
            EvalEntry(
                source_txn_id=txn_id,
                scenario=label,
                expected_escalate=True,
                ground_truth=label,
                reason_hint=f"Synthetic pattern: {label}",
            )
            for txn_id, label in manifest.items()
        ]

    raise HTTPException(status_code=404, detail="No eval data found for this file")


@router.get("/api/generate/preview/{filename}")
async def preview_generated_csv(
    filename: str,
    limit: int = Query(50, ge=1, le=500),
):
    safe_name = Path(filename).name
    file_path = WORK_DIR / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    rows: list[dict[str, str]] = []
    with open(file_path, newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= limit:
                break
            rows.append(row)

    fieldnames = list(rows[0].keys()) if rows else []
    return {"fieldnames": fieldnames, "rows": rows}
