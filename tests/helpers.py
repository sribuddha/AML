import uuid as _uuid
from io import BytesIO

import pandas as pd

from src.file_processor.service import (
    HEADER_ALIASES,
    REQUIRED_FIELDS,
    process_upload,
)


async def upload_csv(session, csv_path, filename="txns.csv"):
    """Upload a CSV through the service layer — no background task triggered."""
    content = csv_path.read_bytes()
    df = pd.read_csv(BytesIO(content))

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

    upload_id = str(_uuid.uuid4())
    result = await process_upload(df, filename, upload_id, session, content)
    return result["upload_id"]
