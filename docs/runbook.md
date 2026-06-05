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
| `AML_API_KEY` | `""` | API key for `Authorization: Bearer` authentication. All `/api/*` routes require this. Empty = no auth (dev mode). |
| `AML_CORS_ORIGINS` | `http://localhost:5173,http://localhost:8000` | Comma-separated allowed CORS origins. Set to `*` for wide open (not recommended in production). |
| `AML_ANONYMIZE_LLM_DATA` | `false` | When `true`, counterparty names are masked before sending to LLM APIs. |
| `AML_LLM_TIMEOUT` | `120` | Per-call LLM timeout in seconds (lazy: `get_llm_timeout()`) |
| `AML_LLM_BUDGET` | `0` | Max LLM spend per upload in USD. `0` = unlimited. (lazy: `get_llm_budget()`) |

Values in `.env` take precedence over defaults but can still be overridden by shell environment variables.

### LLM Safety Controls

- **Per-call timeout**: `AML_LLM_TIMEOUT` (default 120s) passed to every OpenAI/Gemini SDK call. Timeout exceptions caught by existing API error handlers → rule-based fallback.
- **Per-upload budget**: `AML_LLM_BUDGET` (default 0 = unlimited). `LLMClient` estimates cost per call via `_estimate_call_cost()` (model-aware pricing). If budget exceeded, LLM calls skipped entirely — rule-based defaults used instead.
- **Cost estimation**: Uses `_MODEL_PRICING` dict in `llm.py` (covers gpt-4o-mini, gpt-4o, gemini-2.0-flash). Estimates input tokens as chars/3.5, output tokens per call type. Conservative overestimate for safety.

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
# Default: 50 customers + 7 rules with severity (High Value Check, Negative Amount, Offshore Location,
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

Confidence thresholds are baked into the LLM prompt instructions (stage2: range-based guidance where 0.5+ indicates moderate confidence, stage3: "only escalate if confidence > 60%"). Tune by editing the `.txt` prompt files in `src/aml_workflow/prompts/`.

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
Reads all active deterministic rules from the DB and generates transactions guaranteed to trigger them. Distribution is exact (`--count` produces exactly that many rows). Also writes a `.eval` file with expected escalation labels. Each `.eval` entry includes a `"stage": "stage1"` field for per-stage metric grouping.

```bash
python -m scripts.generate_stage1_fraud_data --count 300 --output work/upload.csv
python -m scripts.generate_stage1_fraud_data --count 100 --date 2026-06-15 --output work/upload.csv
```

### `generate_stage2_fraud_data`
Generates scenario-based transactions for LLM triage evaluation. Uses 9 hardcoded scenarios (both escalate and no-escalate). Distribution is exact. Appends to CSV and appends `.eval` entries. Each `.eval` entry includes a `"stage": "stage2"` field for per-stage metric grouping.

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

## Production Deployment

The app can be deployed via Docker Compose with nginx as the entry point.

### Prerequisites

- Docker + Docker Compose
- `.env` file configured with API keys (copy from `.env.template`)
- LLM API keys for at least one provider (OpenAI or Gemini)

### Quick Start

```bash
# Build images and start all services
docker compose build
docker compose up -d

# Check health
curl http://localhost/api/health

# Open app at http://localhost
```

### Services

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| `app` | `aml-app` | 8000 | FastAPI backend (Alembic migrations, SPA serving) |
| `nginx` | `aml-nginx` | 80 | Reverse proxy + static frontend serving |
| (Langfuse stack) | — | 3000 | Observability (optional, requires config) |

### Architecture

```
Browser → nginx:80 → /api/* → app:8000 (FastAPI)
                  → /*      → nginx serves frontend (SPA)
                  → /api/health → app:8000 (bypasses API key auth)
```

- **nginx** handles SSL termination (add your certs to enable HTTPS), rate limiting, and static file caching
- **Backend** runs Alembic migrations on startup, serves the SPA at `/` for non-API routes when `ui/dist` is present (already mounted in the Docker image)
- **Health endpoint** at `/api/health` returns `{"status":"ok","version":"0.1.0","db":"connected|disconnected"}` and bypasses `Authorization: Bearer` middleware

### Environment Variables

Same as development (see [Configuration](#configuration)). Key production considerations:

| Variable | Production Note |
|----------|-----------------|
| `AML_API_KEY` | **Must** be set in production — auth is bypassed when empty |
| `AML_CORS_ORIGINS` | Set to your domain, never `*` with credentials |
| `AML_DATABASE_URL` | SQLite default — for production load, migrate to PostgreSQL (see Note below) |
| `AML_LLM_TIMEOUT` | Default 120s — lower if you prefer faster fallbacks |
| `AML_LLM_BUDGET` | Set a USD cap per upload to control costs |
| `AML_ANONYMIZE_LLM_DATA` | `true` recommended for production to mask counterparty names |

### API Key Management (UI)

The Settings page (`/settings`) allows entering the `AML_API_KEY` at runtime. On first load, the app calls `/api/sar` — if it gets a 401, the UI shows a locked state (only Settings + API Docs nav) with a prompt to enter the key. The key is validated against the backend before being saved to `localStorage`.

This means:
- **Development**: No `VITE_AML_API_KEY` build-time env var needed — enter the key once in Settings
- **Docker/production**: Set `AML_API_KEY` in `.env`; first-time users enter it via Settings page
- **Key change**: Navigate to Settings, enter the new key, Save — old key is replaced

### SSL / HTTPS

The nginx config listens on port 80 and is ready for SSL. To enable HTTPS:

1. Place your certificate files at e.g. `./certs/fullchain.pem` and `./certs/privkey.pem`
2. Mount them in the nginx service:
```yaml
volumes:
  - ./certs:/etc/nginx/certs:ro
```
3. Update `nginx.conf` to listen on 443 and proxy_pass to the backend:
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ...
}
```

### Data Persistence

App data (SQLite databases, uploads) is stored in a named Docker volume `app-data` mounted at `/app/data`. This survives container restarts and rebuilds:

```bash
# Inspect volume
docker volume inspect aml_app-data

# Backup
docker run --rm -v app-data:/data -v .:/backup alpine tar czf /backup/app-data-$(date +%Y%m%d).tar.gz -C /data .
```

### Production Note: SQLite

The current default database is SQLite (`data/aml.db`), which is adequate for single-instance deployments with moderate throughput. For higher concurrency or HA, migrate to PostgreSQL by:

1. Adding a `postgres` service to `docker-compose.yml`
2. Setting `AML_DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/aml`
3. Adding `asyncpg` to `pyproject.toml` dependencies

This is deferred to a future phase — SQLite is sufficient for the current workload profile.

### Viewing Logs

```bash
# Backend logs
docker compose logs -f app

# Nginx logs
docker compose logs -f nginx

# All services
docker compose logs -f
```

## Run Tests

Activate the venv first (otherwise system Python is used and local packages like `aml-observability` won't be found):

```bash
.venv\Scripts\activate
```

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

# If venv not activated, call venv pytest directly:
.venv\Scripts\pytest tests/unit/ -v

# Playwright UI E2E tests (requires seeded DB + both servers running)
# Alternatively, Playwright config auto-starts servers via webServer
python -m scripts.seed_db --force  # ensure DB has seed data
cd ui
npx playwright test
```

## Vulnerability Scanning

```bash
# Python dependency CVE scan (against uv.lock)
uv run pip-audit

# Python SAST scan (code-level issues)
uv run bandit -r src/

# Frontend dependency CVE scan
cd ui
npm audit
```

All three scans should report zero findings on a clean project. Bandit skips test files and generated data by design — it only scans `src/`.

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

The eval report is printed to console and saved as `work/fraud_dataset.eval.json`. The report includes `pattern_metrics` (per-fraud-pattern precision/recall/F1), `stage_metrics` (per-stage breakdown with rule_catch_rate, llm_clear_rate, llm_escalate_rate), and the `mode` the upload was processed in.

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

## Pre-commit Hooks

The project uses `pre-commit` to run secret scanning and code quality checks on every commit.

### Setup (one-time)

```bash
# Install pre-commit if not already installed
uv sync  # or: pip install pre-commit

# Install git hooks
pre-commit install
```

### What runs on commit

| Hook | Purpose |
|------|---------|
| `detect-private-key` | Flags staged PEM private keys (built-in) |
| `mixed-line-ending` | Normalizes line endings to LF |
| `end-of-file-fixer` | Ensures files end with a newline |
| `scan-for-secrets` | Scans for OpenAI keys (`sk-...`), Gemini keys (`AIza...`), AWS keys, and generic secret assignments |

### Manual scan

```bash
# Check all files in the repo (not just staged)
python scripts/scan_for_secrets.py
```

## Key Rotation

API keys are stored in `.env` (gitignored). To rotate a key:

1. **Generate a new key** via the provider's console (OpenAI, Google AI Studio, etc.)
2. **Update `.env`** with the new key value
3. **Restart the server** (`Ctrl+C` + `uvicorn src.bff.app:app --reload`)
4. **If the old key was ever committed**, rotate it immediately at the provider and revoke the exposed key — the pre-commit hook prevents this but manual mistakes happen.
5. **Optional:** Delete old key references from shell history (`Get-Content (Get-PSReadlineOption).HistorySavePath` on Windows, `history -c` on Linux).

| Key | Location | Rotation Trigger |
|-----|----------|-----------------|
| `AML_OPENAI_API_KEY` | `.env` | Every 90 days or on suspected exposure |
| `AML_GEMINI_API_KEY` | `.env` | Every 90 days or on suspected exposure |
| `AML_API_KEY` | `.env` | On suspected exposure |
