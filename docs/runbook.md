# Runbook — AML App

## Configuration

All config is driven by environment variables, loaded from a `.env` file via `_ensure_loaded()` on first function access. Every config value is read through a lazy accessor function (`get_*()`) — no `os.getenv()` calls at module level, no side effects on import.

### Quick Start

```bash
# Copy the template and fill in your API keys
cp .env.template .env
# Edit .env — set at least AML_OPENAI_API_KEY or AML_GEMINI_API_KEY
```

### Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `AML_DATA_DIR` | `<project_root>/data` | Root directory for persistent data (lazy: `get_data_dir()`) |
| `AML_UPLOAD_DIR` | `<AML_DATA_DIR>/uploads` | Directory for uploaded CSV files (lazy: `get_upload_dir()`) |
| `AML_DATABASE_URL` | `sqlite+aiosqlite:///<AML_DATA_DIR>/aml.db` | SQLAlchemy database URL (lazy: `get_database_url()`) |
| `AML_LLM_PROVIDER` | `openai` | Provider: `openai` or `gemini` |
| `AML_OPENAI_API_KEY` | `""` | OpenAI API key |
| `AML_GEMINI_API_KEY` | `""` | Gemini API key |
| `AML_LLM_MODEL_TRIAGE` | `gpt-4o-mini` | Model for triage nodes (stage2 + stage3) |
| `AML_LLM_MODEL_SAR` | `gpt-4o` | Model for SAR node |
| `AML_CHUNK_SIZE` | `10000` | Max rows per chunk during upload processing (lazy: `get_chunk_size()`) |

Values in `.env` take precedence over defaults but can still be overridden by shell environment variables.

### Observability (Langfuse)

```bash
# Start Langfuse + Postgres
docker compose up -d

# Open http://localhost:3000, create account, copy API keys
# Add to .env:
#   OBSERVABILITY_PROVIDER=langfuse
#   LANGFUSE_PUBLIC_KEY=pk-...
#   LANGFUSE_SECRET_KEY=sk-...

# Install optional dep
pip install '.[observability]'

# Run workflow as usual — traces appear at http://localhost:3000
```

| Variable | Default | Description |
|----------|---------|-------------|
| `OBSERVABILITY_PROVIDER` | `none` | Backend: `none` or `langfuse` |
| `LANGFUSE_HOST` | `http://localhost:3000` | Langfuse server URL |
| `LANGFUSE_PUBLIC_KEY` | `""` | Langfuse public API key |
| `LANGFUSE_SECRET_KEY` | `""` | Langfuse secret API key |


```bash
# Create all tables (first time or after schema changes)
python -m scripts.init_db

# Rebuild from scratch (required after breaking schema changes like UUID migration)
Remove-Item data/aml.db -Force
python -m scripts.init_db
python -m scripts.seed_db
```

## Seed Data

**Prerequisite:** The workflow reads rules from the `rule` table. You must seed rules before running the server or submitting uploads — otherwise no transactions will be flagged.

```bash
# Default: 50 customers + 7 rules (High Value Check, Negative Amount, Offshore Location,
#          High Risk Jurisdiction, Offshore Counterparty, Threshold Proximity, Round Amount)
python -m scripts.seed_db

# Custom count
python -m scripts.seed_db --customers 100

# Preview without writing
python -m scripts.seed_db --customers 100 --dry-run

# Clear existing data and re-seed
python -m scripts.seed_db --force
```

## Generate Sample CSV

## Workflow Modes

The graph supports four modes, controlled by `DEFAULT_MODE` in `src/aml_workflow/triggers.py`:

| Mode | Enrichment | Stage2 triage | Stage3 deep-dive | SAR | When to use |
|------|------------|---------------|------------------|-----|-------------|
| `stage1` | Skipped | Auto-escalate all (no LLM) | Skipped | Placeholder | Validate human review flow |
| `stage2` | Runs (30d stats, structuring, velocity, dormancy, account profile) | LLM with enriched context + rule evidence | Skipped | Placeholder | Test triage reduces SAR volume |
| `stage3` | Runs | LLM with enriched context | LLM deep-dive with customer history | LLM-generated | Full pipeline with AI analysis |
| `full` | Runs | Same as stage3 | Same as stage3 | LLM-generated | Full pipeline (alias for stage3) |

Confidence thresholds are baked into the LLM prompt instructions (e.g. stage2: "only escalate if confidence ≥ 50%", stage3: "only escalate if confidence > 60%"). Tune by editing the `.txt` prompt files in `src/aml_workflow/prompts/`.

Enrichment context (30d stats, structuring alerts, velocity z-score, dormancy, account profile) is automatically computed for each customer with flagged transactions and appended as an `## Enriched Context` block to the stage2 user prompt — no configuration needed.

To switch, edit `DEFAULT_MODE` in `triggers.py` and restart the server.

```bash
# Example: switch to stage3 for full pipeline
# triggers.py → DEFAULT_MODE = "stage3"
uvicorn src.bff.app:app --reload
```

## Build Upload Dataset

Generate a single CSV for upload with clean transactions, rule-triggering fraud, and random scrambling:

```bash
# 1. Create 1000 clean records + 50 intentionally bad rows (date defaults to yesterday)
python -m scripts.generate_upload_data --count 1000 --bad-rate 50 --output work/upload.csv

# 2. Append 200 stage-1 fraud records (triggers deterministic rules, evenly distributed)
python -m scripts.generate_stage1_fraud_data --count 200 --output work/upload.csv

# 3. Shuffle so flagged rows aren't clustered at the end
python -m scripts.data_scrambler work/upload.csv

# 4. Upload the single file
curl -X POST http://localhost:8000/api/uploads -F "file=@work/upload.csv"
```

### `generate_upload_data`
Creates random transactions for upload testing. Fetches real customers/accounts from DB. 95% use `--date`, 5% use day before.

```bash
python -m scripts.generate_upload_data --count 1000 --bad-rate 0 --output work/upload.csv
python -m scripts.generate_upload_data --count 500 --bad-rate 25 --date 2026-06-15 --output work/upload.csv
```

### `generate_stage1_fraud_data`
Reads all active deterministic rules from the DB and generates transactions guaranteed to trigger them. Distribution is exact (`--count` produces exactly that many rows). Also writes a `.eval` file with expected escalation labels.

```bash
python -m scripts.generate_stage1_fraud_data --count 300 --output work/upload.csv
python -m scripts.generate_stage1_fraud_data --count 100 --date 2026-06-15 --output work/upload.csv
```

### `generate_stage2_fraud_data`
Generates scenario-based transactions for LLM triage evaluation. Uses 9 hardcoded scenarios (both escalate and no-escalate). Distribution is exact. Appends to CSV and appends `.eval` entries.

```bash
python -m scripts.generate_stage2_fraud_data --count 20 --output work/upload.csv
python -m scripts.generate_stage2_fraud_data --count 20 --date 2026-06-15 --output work/upload.csv
```

### `evaluate_stage2`
Compares LLM triage decisions against `.eval` expectations. Queries validation results from the DB and prints pass/fail per scenario.

```bash
python -m scripts.evaluate_stage2 --upload-id <UUID> --eval work/upload.eval
```

### `data_scrambler`
Shuffles all data rows in a CSV in-place (header preserved, rows randomized).

```bash
python -m scripts.data_scrambler work/upload.csv
```

### Legacy test scripts (kept for backwards compat)

```bash
# Old generate_sample — renamed to test_generate_upload_data
python -m scripts.test_generate_upload_data --count 1000 --bad-rate 0.05

# Old generate_fraud_data — renamed to test_generate_fraud_data
python -m scripts.test_generate_fraud_data --count 5000 --seed-rules
```

## Run Server

```bash
uvicorn src.bff.app:app --reload
```

Server runs on `http://127.0.0.1:8000`. Auto-runs pending Alembic migrations on startup.

## Run Tests

```bash
# All tests with coverage (terminal output only — no files created)
python -m pytest tests/ --cov --cov-report=term-missing

# Unit tests only
python -m pytest tests/unit/ -v

# E2E tests only
python -m pytest tests/e2e/ -v

# BFF API tests
python -m pytest tests/e2e/bff/ -v

# AML workflow tests
python -m pytest tests/e2e/aml/ -v

# Eval harness tests
python -m pytest tests/eval/ -v

# Run a specific test
python -m pytest tests/unit/file/test_service.py::test_all_valid_rows_accepted -v

# Run a specific domain (e.g., aml, bff, file)
python -m pytest tests/unit/aml/ tests/e2e/aml/ -v

# Playwright UI E2E tests (requires seeded DB + both servers running)
# Alternatively, Playwright config auto-starts servers via webServer
python -m scripts.seed_db --force  # ensure DB has seed data
cd ui
npx playwright test
```

## Retry Upload

```bash
# Retry a failed upload (creates new upload_id, deduplicates by source_txn_id + account_id)
python -m scripts.retry_upload <upload_id>
```

## Visualize LangGraph

```bash
python scripts/visualize_graph.py
```

Outputs `work/workflow.md` (Mermaid in Markdown) and `work/workflow.png` (image). The Markdown file renders directly on GitHub.

## Run Eval Harness

```bash
# Generate a fraud dataset + run full eval (requires seeded DB)
python -m scripts.test_generate_fraud_data --count 2000 --seed-rules
python -m scripts.run_eval --csv work/fraud_dataset.csv

# One-liner: generate + eval + seed rules
python -m scripts.run_eval --generate --count 2000 --seed-rules
```

The eval report is printed to console and saved as `work/fraud_dataset.eval.json`.

## Triage Testing with Real LLM

`generate_triage_dataset` generates a CSV with clean transactions + rule-triggering fraud on specific customers, uploads via the service layer (no server needed), and runs the full workflow with real LLM calls. Reports flagged/escalated counts, enrichment snapshots, SARs, and rule coverage.

**Prerequisites:** Seeded DB (`python -m scripts.seed_db`), API key configured in `.env`.

```bash
# Basic run: 300 txns (200 fraud + 100 clean), stage3 mode
python -m scripts.generate_triage_dataset --count 300 --clean-count 100 --days 60

# Triage-only (no SAR generation): faster, still calls LLM for stage2+stage3
python -m scripts.generate_triage_dataset --count 300 --clean-count 100 --triage-only

# Custom customer focus
python -m scripts.generate_triage_dataset --count 300 --customers CUST001,CUST002

# Different date window
python -m scripts.generate_triage_dataset --count 300 --days 30

# Custom output paths
python -m scripts.generate_triage_dataset --count 300 --output work/my_test.csv
```

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--count` | 300 | Total transactions to generate |
| `--clean-count` | 100 | Number of clean (non-fraud) transactions |
| `--customers` | `CUST001,CUST002,CUST003` | Comma-separated customer IDs to focus fraud on |
| `--days` | 60 | Date randomization window (days back from today) |
| `--output` | `work/triage.csv` | Output CSV path |
| `--triage-only` | False | Skip SAR generation (stops after stage3) |

Clean transactions are guaranteed safe: they use secure counterparties, safe amounts, and low-risk locations — never trigger any rule. Fraud transactions are distributed across available rules with dates randomized across `--days`.

### Output

- **CSV file** at `--output` path — ready for manual upload
- **`.eval` file** alongside the CSV — contains expected escalation labels
- **Console report** with rule coverage, enrichment snapshot count, and SAR count

## Cleanup

```bash
# Delete an upload and all associated records (8 tables + staging + data dir)
python -m scripts.delete_upload <upload_id>

# Bulk-clean all orphaned upload directories (no DB record)
# Runs as one-off; use with caution
python -c "
import asyncio, shutil
from pathlib import Path
from sqlalchemy import select
from src.bff.config import get_upload_dir
from src.bff.database import async_session_factory
from src.core.models.uploaded_files import UploadedFiles
async def main():
    async with async_session_factory() as s:
        r = await s.execute(select(UploadedFiles.id))
        valid = set(row[0] for row in r)
    upload_dir = get_upload_dir()
    for d in [*upload_dir.iterdir(), *(upload_dir/'staging').iterdir()]:
        if d.is_dir() and d.name not in valid: shutil.rmtree(d)
asyncio.run(main())
"

# Clean coverage artifacts (if they ever appear)
Remove-Item .coverage -Force
Get-ChildItem -Recurse -Filter "*,cover" | Remove-Item -Force
```
