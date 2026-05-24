# AML — Anti-Money Laundering Transaction Validation System

**Author:** Srikanth Buddha(AI-assisted)  
**Date:** 2026-05-20  
**Status:** Draft

---

## 1. Overview / Summary

A single-process AML transaction validation system. Users upload CSV transaction files through a FastAPI BFF; the backend parses, validates, and inserts accepted rows, then triggers a LangGraph workflow that applies deterministic rules and optionally uses an LLM (OpenAI or Gemini) for triage and SAR narrative generation. An eval harness measures detection precision/recall, hallucination rates, and rule completeness. No external queues, no auth — designed for local single-user operation.

### How It Works — End to End

**1. Upload** — A user uploads a CSV of bank transactions via `POST /api/uploads`. The system validates each row structurally (required fields, data types, FK lookups against customer/account tables) and rejects bad rows with reasons. Accepted rows are inserted into the `transaction` table. A background LangGraph workflow is triggered via `asyncio.create_task`.

**2. Rule Engine** — The workflow loads active deterministic rules from the DB (e.g. `amount > 10000`, `counterparty contains 'Offshore'`, `location = 'Cayman'`) and evaluates every transaction against every rule. Flagged rows get `status = "flagged"` with `flag_details` mapping rule IDs to rule names. Clean rows get `status = "clean"`. Results are persisted to `validation_result` with audit log entries.

**3. Enrichment** — For each customer with flagged transactions, the system computes customer-level context: 30-day stats (count, sum, avg, std dev), structuring alerts (txns in [$9K, $10K] within 24h), velocity z-score (this-week vs prior 4 weeks), dormancy (days since last transaction), and account profile (type, age). This context is frozen to the `enrichment_snapshot` table for eval audit and passed in-memory to the next stage via workflow state.

**4. LLM Triage (Stage 2)** — A Large Language Model (OpenAI or Gemini) reviews each flagged transaction along with the enriched context and rule evidence, and decides to either clear it (`escalate: false`) or escalate it (`escalate: true, reason, confidence`). The LLM must meet a confidence threshold baked into the prompt instructions.

**5. LLM Deep-Dive (Stage 3)** — If escalated, a second LLM pass reviews the transaction alongside its recent transaction history (same customer, last ~20 txns) and makes a final escalation decision. This catches cases where stage 2's aggregate stats miss recurring patterns (e.g. a $45K payment looks anomalous against a $8K average, but the history shows it's a normal weekly payment).

**6. SAR Generation** — Escalated transactions get a Suspicious Activity Report narrative (LLM-generated or placeholder depending on workflow mode), stored in the `sar` table with `status = "pending_review"`. The upload status is updated to `"pending_human"`.

**7. Human Review** — The workflow pauses via LangGraph's `interrupt()` and persists a checkpoint. A human reviews SARs via `PATCH /api/sar/{id}/review` (approve or reject). When all SARs for the upload are resolved, the workflow resumes via `Command(resume="all_reviewed")`, the `finalize` node sets `upload.status = "complete"`, and the graph ends.

---

## 2. Goals & Non-Goals

### Goals

- **G-01:** Accept CSV uploads, structurally validate each row, and persist accepted transactions + rejected reasons
- **G-02:** Run a deterministic rule engine over every (transaction × rule) pair to flag suspicious activity
- **G-03:** Use LLM triage (OpenAI or Gemini) to reduce false-positive SAR volumes and generate human-readable Suspicious Activity Reports
- **G-04:** Provide REST API for uploads, validation results, rules CRUD, SAR review, and audit trails
- **G-05:** Provide an eval harness with synthetic fraud patterns to measure detection metrics, hallucination rates, and SAR completeness

### Non-Goals

- User authentication / authorization (no login, roles, or API keys)
- Multi-user or multi-tenant support
- Docker / containerization or cloud deployment
- External message queues (Redis, Celery, SQS)
- LLM-based anomaly detection (ML models for transaction scoring)
- CI/CD pipeline or pre-commit hooks
- File content dedup via SHA256
- Audit log retention / data purging policies

---

## 3. Background / Context

Financial institutions must file Suspicious Activity Reports (SARs) for transactions that may indicate money laundering. Manual review of every flagged transaction is expensive and slow. This system automates the detection pipeline: deterministic rules filter obvious cases, an LLM triages borderline ones, and only high-risk transactions get SAR narratives generated — reducing human review workload while maintaining auditability.

---

## 4. Requirements

### Functional Requirements

| Requirement ID | Description | Priority |
|---|---|---|
| FR-001 | Upload CSV files, parse rows, reject structurally invalid rows with reasons | High |
| FR-002 | Insert valid rows into the transaction table; support large CSVs via chunked insertion | High |
| FR-003 | Apply deterministic rules (JSON conditions: `>`, `<`, `>=`, `<=`, `==`, `!=`, `is_empty`, `contains`, `in`) to flag suspicious transactions | High |
| FR-004 | Route flagged transactions through LLM triage (OpenAI or Gemini) to decide escalation | Medium |
| FR-005 | Generate SAR narratives for escalated transactions (LLM-generated or placeholder) | Medium |
| FR-006 | Support workflow modes: `stage1` (no LLM, all flagged → escalated), `stage2` (LLM triage with aggregate context, confidence threshold in prompt), `stage3` (LLM deep-dive with customer history, confidence threshold in prompt), `full` (stage2 + LLM SAR generation) | Medium |
| FR-007 | CRUD for rules (soft-delete insert-only pattern) | High |
| FR-008 | Retrieve validation results by upload (summary + paginated flagged details), by date, and by source_txn_id | High |
| FR-009 | Human review of pending SARs (approve/reject); auto-complete upload when all SARs resolved | Medium |
| FR-010 | Reprocess failed/stale workflows with heartbeat detection (10-minute stale window) | Medium |
| FR-011 | Event-sourced audit trail logging every entity status transition (transaction, upload) | Medium |
| FR-012 | Retry failed uploads using `.val` staging files with source_txn_id dedup | Medium |
| FR-013 | Eval harness with synthetic fraud patterns (structuring, velocity, impossible travel, round-trip, watchlist) and ground-truth labels | Low |

### Non-Functional Requirements

| Requirement ID | Description | Target |
|---|---|---|
| NFR-001 | Response time for upload endpoint (no background workflow) | < 5s for 10K rows |
| NFR-002 | Chunked insertion for large CSVs | 10,000 rows per chunk |
| NFR-003 | Maximum rejected rows returned in preview | 10 rows |
| NFR-004 | Pagination on all list endpoints | 50 per page (max 100) |
| NFR-005 | Workflow node retries on transient errors | 3 attempts, exponential backoff (2^attempt seconds) |
| NFR-006 | LLM triage must always fall back to deterministic rules when API keys are absent | Fallback on any API error |
| NFR-007 | Test coverage | ≥ 90% (verified via `pytest --cov`) |
| NFR-008 | Idempotent retry — `source_txn_id` deduplication prevents double-insert | No duplicate transactions |

---

## 5. High Level Architecture

Single FastAPI server that handles all backend concerns (file processing, rules management, BFF endpoints). The **AML_Workflow** runs as a background LangGraph workflow triggered via `asyncio.create_task`. SQLite is the single database. The React UI (future build) communicates exclusively through the BFF.

### Architecture Diagram

```
┌──────────┐     ┌──────────┐     ┌───────────────┐
│    UI    │────▶│    BFF   │────▶│ AML_Workflow  │
│ (React)  │     │(FastAPI) │     │  (LangGraph)  │
└──────────┘     └────┬─────┘     └───────────────┘
                      │
                 ┌────▼─────┐
                 │  SQLite   │
                 └──────────┘
```

### Key Components

- **UI (React):** File upload, dashboard, rule editor (future build — not yet implemented).

- **BFF (FastAPI):** Single backend — file processing (CSV parse, structural validation, accepted/rejected routing), rules CRUD, BFF endpoints for UI consumption, and orchestration of AML_Workflow trigger. 19 REST endpoints under `/api`.

- **AML_Workflow (LangGraph):** Background state machine. Loads un-validated transactions + active deterministic rules → evaluates every (transaction × rule) pair → persists `validation_result` and updates `transaction.status` → optional two-stage LLM triage (stage2: aggregate analysis, stage3: deep-dive with customer history) → SAR creation → human review interrupt → finalize. Every status transition is recorded in `audit_log`.

- **Eval Harness (`src/aml_workflow/eval/`):** Post-workflow evaluation. Measures detection metrics (precision/recall/F1 per fraud pattern), SAR hallucination rates (number/entity verification against source evidence), and rule completeness coverage in generated narratives. Runnable standalone via `scripts/run_eval.py`.

- **SQLite:** Single-file database — 9 tables (customer, account, uploaded_files, rejected_record, transaction, rule, validation_result, sar, audit_log).

### Detailed Flow (Implemented)

```
┌──────────────────────────────────────────────────────────────────┐
│                     BFF (FastAPI) — Upload Path                    │
│                                                                   │
│  CSV ──► POST /api/uploads ──► validate/split ──► SQLite         │
│                                       │                           │
│                              accepted  │  rejected                │
│                                  │     │     │                    │
│                            ┌─────▼─────▼─────┐                    │
│                            │  Transaction    │  RejectedRecord    │
│                            │  (accepted)     │  (rejected)        │
│                            └─────────┬───────┘                    │
│                                      │                            │
│               asyncio.create_task(run_validation(upload_id))      │
└──────────────────────────────────────┼────────────────────────────┘
                                        │
┌──────────────────────────────────────▼────────────────────────────┐
│              AML_Workflow (LangGraph StateGraph)                   │
│                                                                    │
 │  ┌──────────────┐   ┌────────────────────┐   ┌──────────────────┐ │
 │  │  load_data   │──▶│  rule_engine_batch │──▶│   enrich_node    │ │
 │  │              │   │                    │   │                  │ │
 │  │ Queries DB   │   │ Evaluates every    │   │ Customer-level   │ │
 │  │ • accepted   │   │ (txn × rule)       │   │ aggregations:    │ │
 │  │   txns       │   │ condition pair     │   │ • 30d stats      │ │
 │  │ • active     │   │ OR logic across    │   │ • structuring    │ │
 │  │   rules      │   │ conditions         │   │ • velocity z     │ │
 │  └──────────────┘   │ Updates txn.status │   │ • dormancy       │ │
 │                     └────────┬───────────┘   │ • account prof.  │ │
 │                              │               └────────┬─────────┘ │
 │                              ▼                        ▼           │
 │                     persist results          stage2_triage         │
 │                     + audit events               │                 │
 │                              │            flagged→clean            │
 │                              │            flagged→escalated        │
 │                              │                  │                  │
 │                              │                  ▼                  │
 │                              │            stage3_triage            │
 │                              │                  |                  │
 │                              │            escalated→clean          │
 │                              │            escalated→pending_review │
 │                              │                  |                  │
 │                              │                  ▼                  │
 │                              │              sar_node               │
 │                              │                  |                  │
 │                              │            create SAR row           │
 │                              │           upload→pending_human      │
 │                              │                  |                  │
 │                              │            human_review             │
 │                              │                  |                  │
 │                              │            [INTERRUPT]              │
 │                              │                  |                  │
 │                              │            (resume after            │
 │                              │             human PATCH)            │
 │                              │                  |                  │
 │                              │             finalize                │
 │                              │                  |                  │
 │                              │           upload→complete           │
 │                              └──────────────── END ────────────────┘
 │                                                                    │
 │  Clean path (no flags):                                            │
 │   rule_engine_batch → persist results → finalize → END            │
 │                                                                    │
 │  Flagged path (all modes):                                         │
 │   rule_engine_batch → persist → enrich_node → stage2_triage → ... │
 │                                                                    │
 │  Full path (stage3 deep-dive):                                     │
 │   ... → stage2_triage → stage3_triage → sar_node → …              │
└──────────────────────────────────────────────────────────────────┘

| Mode | LLM Usage | Pipeline Depth |
|------|-----------|----------------|
| `stage1` | None — all flagged → escalated | Rules → SAR |
| `stage2` | Stage2 triage only (with enriched context) | Rules → Enrich → Stage2 → SAR |
| `stage3` | Stage2 + Stage3 triage + SAR generation | Rules → Enrich → Stage2 → Stage3 → SAR |
| `full` | Same as stage3 | Same as stage3 |

See §6 (Detailed Design — Workflow) for the full mode table with per-node behavior.
```

Transaction status state machine:

```
loaded → clean                    (no rules fired)
       → flagged ──→ clean         (stage2 triage cleared it)
                  └─→ escalated ──→ clean               (stage3 deep-dive cleared it)
                                 └─→ pending_review ──→ clean      (human approved)
                                                      └─→ dismissed (human rejected)
```

Upload status state machine:

```
uploaded → processing → pending_human → complete
                                      ↘ failed
```

---

## 6. Detailed Design

### BFF

**File:** `src/bff/`

FastAPI application (`app.py`) serving all REST endpoints under `/api`. Routes are registered across dedicated modules for uploads (`upload.py`, `read.py`, `reprocess.py`), rules (`rules.py`), SARs (`sar.py`), audit logs (`audit.py`), and validation results (`validation.py`). Auto-migration runs on startup via the application lifespan handler. Pydantic schemas in `schemas.py` define request/response models.

### FileProcessor

**File:** `src/file_processor/service.py`

Handles CSV ingestion, structural validation, and insertion.

#### Upload — Validation & Insertion

Every CSV upload follows this workflow in `process_upload`:

1. **Generate UUID** — Router generates `upload_id` (`uuid.uuid4()`) before any DB or disk operation.
2. **Parse & normalize** — CSV bytes parsed via `BytesIO` + pandas. Column names normalized via `HEADER_ALIASES` dict (maps e.g. "acct" → "account_id", "amt" → "amount", "cp" → "counterparty", "loc" → "location", "txn_date" → "date"). Missing required columns (`account_id`, `customer_id`, `amount`, `counterparty`, `location`, `date`) return HTTP 400. The `source_txn_id` column is preserved if present; otherwise auto-generated as `TXN-{index:06d}`.
3. **Save original** — Raw bytes written to `{UPLOAD_DIR}/staging/{upload_id}/{filename}.orig`.
4. **Validate each row** — For every row:
   - NaN check on all 6 required fields → `{field} is required`
   - Missing/blank `account_id` or `customer_id` → `Missing {field}`
   - Missing amount → `Missing amount`; non-numeric amount → `Amount is not numeric`
   - Invalid date format (not `YYYY-MM-DD`) → `not a valid date`
   - FK lookup against `Account` and `Customer` tables → `{field}_id not found`
   - Rejected rows (max 10) returned in `rejected_preview` with key `"row"`, `"raw_data"` (NaN values cleaned to `null`), and `"reasons"` array.
5. **Insert accepted rows** — Two paths based on accepted count vs `CHUNK_SIZE` (10,000):

   **Small CSV (accepted <= 10,000):**
   - Write accepted rows to `staging/{upload_id}/0.val` (CSV)
   - Insert all accepted rows to `transaction` table
   - Rename `0.val` → `0.val.db`

   **Large CSV (accepted > 10,000):**
   - No `.val` files created
   - Insert accepted rows to `transaction` table in chunks of 10,000
   - For each chunk, create an `UploadedFiles` row with `upload_chunk=N`, `filename={original}.N`, `status="committed"`

6. **Write rejected rows** — Insert `RejectedRecord` rows to DB and write `staging/{upload_id}/0.fail` (JSON Lines).
7. **Complete** — `UploadedFiles` row marked `status="completed"` and committed.
8. **Background workflow** — `asyncio.create_task(run_validation(upload_id))` triggers the LangGraph workflow (creates own DB session).

**Output files in staging dir:**
- `{filename}.orig` — raw CSV backup
- `0.val` → `0.val.db` — accepted rows (small CSV only, renamed after successful insert)
- `0.fail` — rejected rows as JSON Lines (permanent audit)

#### Retry Upload

**Purpose:** Re-process a failed upload using `.val` files from its staging directory.

**Flow:**
1. Look up the failed upload by `upload_id` — its staging directory must exist with `.val` files.
2. Collect `.val` + `.dbfail` files from the staging directory.
3. For each chunk, read rows, skip duplicates by `source_txn_id` and `account_id`, and insert remaining rows.
4. If bulk INSERT fails, fall back to individual inserts; individual failures written to `.dbfail`.
5. Update upload's `accepted_count` / `failed_count` and mark `completed`.

**Idempotency key:** `source_txn_id` — if a row with the same key was already committed, it is skipped.

### Workflow

**File:** `src/aml_workflow/`

Background LangGraph state machine that processes uploaded transactions through rule evaluation, optional LLM triage, SAR generation, and human review.

#### LLM Client

**File:** `src/aml_workflow/llm.py`

- **Class:** `LLMClient` — abstraction over OpenAI (via `openai.AsyncOpenAI`) and Google Gemini (via `google.genai.Client`).
- **Provider selection:** Controlled by `AML_LLM_PROVIDER` env var (`"openai"` default, or `"gemini"`).
- **Model config:** `AML_LLM_MODEL_TRIAGE` (default `"gpt-4o-mini"`) for triage; `AML_LLM_MODEL_SAR` (default `"gpt-4o"`) for SAR generation.
- **API keys:** `AML_OPENAI_API_KEY` and `AML_GEMINI_API_KEY` — if neither set, all methods fall through to deterministic fallback rules.
- **Prompt files:** Prompts are stored as standalone `.txt` files in `src/aml_workflow/prompts/`:
  - `triage_stage2_system.txt` — stage2 aggregate triage (confidence threshold baked into instructions)
  - `triage_stage3_system.txt` — stage3 deep-dive triage with customer history (confidence threshold baked into instructions)
  - `triage_user.txt` — shared user prompt template for both stages
  - `triage_system.txt` — legacy (superseded by stage2/stage3 prompts)
- **Two-stage triage:**
  - `triage()` — stage2: LLM receives transaction details + rule evidence + optional enriched context. Confidence threshold is instructed in the prompt. Returns `TriageDecision{escalate, reason, confidence}`.
  - `triage_stage3()` — stage3: LLM receives transaction details + rule evidence + recent transaction history for the same customer. Confidence threshold is instructed in the prompt. Returns `TriageDecision{escalate, reason, confidence}`.
- **Rules context:** Both `triage()` and `triage_stage3()` accept a `rules: list[dict] | None` parameter. When provided, rule names and descriptions are included in the prompt to ground the LLM's escalation decision in the deterministic rules that triggered.
- **Enriched context:** `triage()` accepts an optional `enriched_context: dict | None` parameter. When provided, customer-level aggregations (30d stats, structuring alerts, velocity z-score, dormancy, account profile) are appended as an `## Enriched Context` block to the existing user prompt — same pattern as stage3 appends "Recent customer history".
- **Provider-specific formatting:** OpenAI receives system/user messages; Gemini uses `system_instruction` in the config dict.
- **Triage structured output:** OpenAI uses `response_format` with `json_schema`; Gemini uses `response_mime_type: application/json` + `response_schema`. Both request `{escalate: bool, reason: string, confidence: float}`.
- **Fallback:** `_triage_fallback` escalates if amount > $50,000 (confidence scales with excess). `_sar_fallback` generates plain-text SAR with all fields.

#### Validator

**File:** `src/aml_workflow/validator.py`

- **9 operators:** `>`, `<`, `>=`, `<=`, `==`, `!=`, `is_empty`, `contains`, `in`
- **OR logic:** Any matching condition triggers the rule.
- **Rules are loaded** with `status='active'` and `type='deterministic'`.

#### Workflow Mode

The graph accepts a `mode` parameter that controls LLM usage and pipeline depth:

| Mode | `enrich_node` | `stage2_triage` | `stage3_triage` | `sar_node` | Use case |
|------|--------------|----------------|----------------|-----------|----------|
| `stage1` | Skipped | Auto-escalate all flagged (no LLM) | Skipped | Placeholder SAR | Test human review flow without LLM |
| `stage2` | Runs | LLM triage with enriched context + rule evidence | Skipped | Placeholder SAR | Test triage filter reduces SAR volume |
| `stage3` | Runs | LLM triage with enriched context + rule evidence | LLM deep-dive with customer history | LLM-generated SAR | Full pipeline with AI analysis |
| `full` | Runs | Same as stage3 | Same as stage3 | LLM-generated SAR | Full pipeline (alias for stage3) |

Default: `DEFAULT_MODE = "stage2"` in `src/aml_workflow/triggers.py:13`. Change the constant to switch modes.

#### Human-in-the-Loop (Interrupt)

After `sar_node` creates SARs with `status = "pending_review"`, the graph updates the upload to `pending_human` and routes through a `human_review` node that calls `interrupt()` if any pending SARs remain. This pauses execution, persists the checkpoint to `<DATA_DIR>/checkpoints.db` via `AsyncSqliteSaver`, and raises a `GraphInterrupt` exception (handled silently by `_run_node` — no error logging).

**Resume flow:**

1. Human reviews SARs via `PATCH /api/sar/{sar_id}/review` (sets `sar.status` to `confirmed`/`dismissed`, updates `transaction.status` to `clean`/`dismissed`, writes audit log).
2. When the last pending SAR for the upload is resolved, the PATCH handler resumes the graph with `Command(resume="all_reviewed")`.
3. The `human_review` node re-checks pending count: if zero, returns `{"human_review_complete": True}`.
4. The `finalize` node sets `upload.status = "complete"` and the graph ends.

**Configuration:**

| Concern | Detail |
|---------|--------|
| Checkpointer | `AsyncSqliteSaver` wrapping `<DATA_DIR>/checkpoints.db` |
| Thread ID | Upload UUID (`configurable.thread_id` in `config`) |
| Resume signal | `Command(resume="all_reviewed")` |
| GraphInterrupt | Re-raised through `_run_node` without logging or audit (normal flow) |

Without a checkpointer, `interrupt()` still pauses but cannot resume — the graph stops at the interrupt point permanently.

### Eval

**File:** `src/aml_workflow/eval/`

- **5 fraud patterns:** structuring, velocity, impossible_travel, round_trip, watchlist
- **Detection metrics:** precision, recall, F1 per pattern (via `_compute_metrics` — uses total/flagged counts with tp = min(flagged, total))
- **Hallucination check (`hallucination.py`):** Extracts `$`-prefixed numbers and capitalized entities from SAR narrative; verifies against evidence set (transaction fields + formatted amounts + rule names). 0.01 tolerance for numeric comparisons.
- **Completeness check (`completeness.py`):** For each triggered rule, checks if key words (>3 chars) from the rule name appear in the SAR narrative.
- **EvalReport:** Includes overall metrics, hallucination-free rate, average completeness, per-pattern breakdown.

---

## 7. Infrastructure

| Concern | Detail |
|---------|--------|
| Compute | Single local process: `uvicorn src.bff.app:app --reload`. Python >= 3.14. |
| Database | SQLite via `sqlite+aiosqlite` at `<AML_DATA_DIR>/aml.db`. Alembic migrations auto-run on startup via `app.py` lifespan. Each background task creates its own `AsyncSession`. |
| Orchestration | LangGraph `StateGraph` — 8 nodes: load_data, rule_engine_batch, persist_results, enrich_node, stage2_triage, stage3_triage, sar_node, human_review, finalize. Single-threaded asyncio. Checkpoints to `<DATA_DIR>/checkpoints.db` via `AsyncSqliteSaver` for interrupt/resume. Node retry: 3 attempts, exponential backoff (`2^attempt` s), non-transient → immediate fail. |
| Queues | None. Workflow triggered via `asyncio.create_task(run_validation(upload_id))` after upload. No external message brokers. |
| LLM Providers | OpenAI (`AsyncOpenAI`) and Gemini (`genai.Client`). Provider + model names via env vars (see `.env.template`). No API keys → deterministic fallback. |
| Caching | None. Every request queries SQLite directly. No Redis or in-memory cache. |
| Configuration | Env vars in `.env.template`. Hardcoded constants: chunk_size=10K, pagination=50/100, retry=3, backoff=2^attempt s, heartbeat=10min. |

---

## 8. API Design

### External API

All endpoints are served from the BFF under `/api`. The UI communicates exclusively with these endpoints. Authentication is not scoped for initial build.

**Upload**

| Method | Path | Request | Response | Description |
|--------|------|---------|----------|-------------|
| `POST` | `/api/uploads` | `multipart/form-data` — field `file` (CSV) | `200` — UploadReceipt | Upload a CSV transaction file |
| `POST` | `/api/uploads/{id}/retry` | — | `201` — UploadReceipt | Retry a failed upload — re-inserts rows from staging `.val` files |
| `POST` | `/api/uploads/{id}/reprocess` | — | `202` — `{"message": "..."}` | Re-run the workflow for crash recovery. Idempotent — checks status and heartbeat before re-running. |

**Reprocess logic:**
1. Fetch upload — 404 if not found.
2. Check `review_status`:
   - `NULL` → re-run immediately
   - `PROGRESS` → check heartbeat via `MAX(updated_at)` on `validation_result` where `status IN ('clean', 'flagged')`:
     - recent (<10 minutes) → `202 {"message": "Workflow already in progress"}` (no action)
     - old (≥10 minutes) or no rows → reset `review_status = NULL`, re-run
   - `PENDING_HUMAN` → graph is paused via `interrupt()`; resume via `PATCH /api/sar/{id}/review`. Reprocess returns `400 {"detail": "Human review in progress"}`.
   - `COMPLETE` → `400 {"detail": "Workflow already complete"}`
   - otherwise → `400 {"detail": "Unknown review_status: ..."}`

```json
// Response 200/201 — UploadReceipt
{
  "upload_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "transactions.csv",
  "total_rows": 500,
  "accepted_count": 480,
  "failed_count": 20,
  "rejected_preview": [
    { "row": 12, "raw_data": {"account_id": "ACC999", "amount": 500.0}, "reasons": ["account_id 'ACC999' not found"] },
    { "row": 45, "raw_data": {"amount": "abc"}, "reasons": ["Amount is not numeric"] }
  ]
}
```

**Uploads & Transactions**

| Method | Path | Response | Description |
|--------|------|----------|-------------|
| `GET` | `/api/uploads?page=&per_page=` | `200` — PaginatedResponse[UploadSummary] | List all uploads (paginated, ordered by uploaded_at desc) |
| `GET` | `/api/uploads/{id}` | `200` — UploadSummary | Status and stats for one upload |
| `GET` | `/api/uploads/{id}/transactions?page=&per_page=` | `200` — PaginatedResponse[Transaction] | Accepted transactions (paginated, ordered by source_txn_id) |
| `GET` | `/api/transactions/{id}` | `200` — Transaction | Single transaction by UUID |
| `GET` | `/api/uploads/{id}/rejected?page=&per_page=` | `200` — PaginatedResponse[RejectedRecord] | Rejected rows with reasons |

```json
// Response 200 — UploadSummary
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "transactions.csv",
  "status": "completed",
  "total_rows": 500,
  "accepted_count": 480,
  "failed_count": 20,
  "uploaded_at": "2026-05-19T12:00:00Z"
}

// Response 200 — PaginatedResponse[Transaction]
{
  "page": 1,
  "per_page": 50,
  "total": 480,
  "items": [
    {
      "id": "uuid-here",
      "account_id": "ACC001",
      "customer_id": "CUST001",
      "amount": 1500.00,
      "counterparty": "Acme Corp",
      "location": "New York",
      "date": "2026-05-01"
    }
  ]
}

// Response 200 — PaginatedResponse[RejectedRecord]
{
  "page": 1,
  "per_page": 50,
  "total": 20,
  "items": [
    {
      "id": "uuid-here",
      "row_index": 12,
      "raw_data": {"account_id": "ACC999", "amount": "500"},
      "reasons": ["account_id 'ACC999' not found in account table"]
    }
  ]
}
```

**Validation Results**

| Method | Path | Response | Description |
|--------|------|----------|-------------|
| `GET` | `/api/uploads/{id}/validation` | `200` — ValidationSummary | clean/flagged/total counts for one upload (summary mode — no `?status=` filter) |
| `GET` | `/api/uploads/{id}/validation?status=flagged&page=&per_page=` | `200` — PaginatedResponse[ValidationDetail] | Flagged-only rows with source_txn_id and flag_details |
| `GET` | `/api/validation/date/{date}` | `200` — list[ValidationDayItem] | All uploads validated on YYYY-MM-DD with clean/flagged counts |
| `GET` | `/api/validation/transaction/{source_txn_id}` | `200` — ValidationByTransaction | Single latest validation result across all uploads |

```json
// Response 200 — ValidationDayItem
{
  "upload_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "clean_count": 450,
  "flagged_count": 30,
  "total_count": 480
}

// Response 200 — ValidationSummary
{
  "upload_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "clean_count": 450,
  "flagged_count": 30,
  "total_count": 480
}

// Response 200 — ValidationDetail
{
  "source_txn_id": "TXN002",
  "status": "flagged",
  "flag_details": {
    "rule-uuid-here": "High Value Check"
  }
}

// Response 200 — ValidationByTransaction
{
  "upload_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "flagged",
  "flag_details": { "rule-uuid": "rule-name" },
  "validated_at": "2026-05-20T12:00:00Z"
}
```

**Rules (CRUD)**

| Method | Path | Request Body | Response | Description |
|--------|------|-------------|----------|-------------|
| `GET` | `/api/rules?name=&type=&status=&page=&per_page=` | — | `200` — PaginatedResponse[Rule] | List rules; defaults to `status=active`. Optional filters: `?name=X&type=Y&status=all\|active\|inactive&page=&per_page=` |
| `GET` | `/api/rules/{id}` | — | `200` — Rule | Get rule by UUID |
| `POST` | `/api/rules` | `RuleCreate` | `201` — Rule | Create a new rule |
| `PUT` | `/api/rules/{id}` | `RuleUpdate` | `200` — Rule | Soft-deletes old rule (status→inactive), creates new rule with updated payload (new UUID) |
| `DELETE` | `/api/rules/{id}` | — | `204` — no content | Soft-delete rule (status→inactive) |

Rules are insert-only. No records are physically deleted.

```json
// Request body — RuleCreate / RuleUpdate
{
  "name": "High-Value & Negative Checks",
  "description": "Flags large or negative transactions",
  "type": "deterministic",
  "status": "active",
  "rules_json": [
    { "field": "amount", "operator": ">", "value": 10000 },
    { "field": "amount", "operator": "<", "value": 0 },
    { "field": "counterparty", "operator": "is_empty" }
  ]
}

// Response 200/201 — Rule
{
  "id": "uuid-here",
  "name": "High-Value & Negative Checks",
  "description": "Flags large or negative transactions",
  "type": "deterministic",
  "status": "active",
  "rules_json": [ ... ]
}
```

**SAR — Suspicious Activity Reports**

| Method | Path | Body | Response | Description |
|--------|------|------|----------|-------------|
| `GET` | `/api/sar/{id}` | — | `200` — SAR | Get single SAR by UUID |
| `PATCH` | `/api/sar/{id}/review` | `{action, notes}` | `200` — SAR | Approve or reject a pending SAR. If all SARs for the upload are resolved, resumes the paused LangGraph via `Command(resume="all_reviewed")` to complete the workflow. |
| `GET` | `/api/sar?upload_id=&status=&page=&per_page=` | — | `200` — PaginatedResponse[SAR] | List SARs with optional filters. |

```json
// Request body — PATCH /api/sar/{sar_id}/review
{
  "action": "approve",
  "notes": "Reviewed by compliance officer — no further action needed."
}

// Response 200 — SAR
{
  "id": "uuid-here",
  "transaction_id": "uuid-here",
  "upload_id": "uuid-here",
  "rule_id": "uuid-here",
  "content": "Suspicious Activity Report text...",
  "status": "approved",
  "created_at": "2026-05-20T12:00:00Z",
  "reviewed_at": "2026-05-21T09:00:00Z",
  "review_notes": "Reviewed by compliance officer — no further action needed."
}
```

**Audit Log**

| Method | Path | Response | Description |
|--------|------|----------|-------------|
| `GET` | `/api/uploads/{id}/audit?page=&per_page=` | `200` — PaginatedResponse[AuditLog] | Per-transaction event-sourced audit trail — every workflow step, validation write, and SAR review logged |

```json
// Response 200 — AuditLog
{
  "id": "uuid-here",
  "event_type": "transaction.validated",
  "entity_type": "transaction",
  "entity_id": "uuid-here",
  "upload_id": "uuid-here",
  "payload": {
    "status": "flagged"
  },
  "actor": "system",
  "created_at": "2026-05-20T12:00:00Z"
}
```

**Reference Data**

| Method | Path | Response | Description |
|--------|------|----------|-------------|
| `GET` | `/api/customers?page=&per_page=` | `200` — PaginatedResponse[Customer] | List seeded customers (not yet implemented — route not registered) |
| `GET` | `/api/accounts?page=&per_page=` | `200` — PaginatedResponse[Account] | List seeded accounts (not yet implemented — route not registered) |

### Internal API

No service-to-service HTTP calls. Internal communication is in-process:

| Caller | Callee | Mechanism | Payload |
|--------|--------|-----------|---------|
| BFF — upload route | AML_Workflow trigger | `asyncio.create_task(run_validation(upload_id))` | `upload_id: str` |
| BFF — reprocess route | AML_Workflow trigger | `asyncio.create_task(run_validation(upload_id))` | `upload_id: str` |
| AML_Workflow — load_data | database layer | Direct SQLAlchemy async query | `upload_id` → `[txn dicts]` + `[active deterministic rules]` |
| AML_Workflow — rule_engine_batch | validator.evaluate_rules | Function call | `(txn: dict, rules: [Rule]) → {status, flag_details}` |
| AML_Workflow — enrich_node | enrichment.enrich_transactions | Async function call | `(db, flagged_txns, upload_id) → {customer_id: dict}` |
| AML_Workflow — stage2_triage | LLMClient.triage | Method call | `(txn, flag_details, rules, enriched_context) → TriageDecision` |
| AML_Workflow — sar_node | LLMClient.generate_sar | Method call | `(txn: dict, flag_details: dict, triage: TriageDecision) → SAR content` |

---

## 9. Persistence

### Database

**Database Type:** RDBMS (SQLite via `sqlite+aiosqlite`)

#### RDBMS Schema

| Table Name | Purpose |
|---|---|
| `customer` | Seeded reference data — 50 synthetic customers |
| `account` | Seeded reference data — 1-2 per customer |
| `uploaded_files` | Tracks each CSV upload and its processing status |
| `rejected_record` | Rows that failed structural validation during upload |
| `transaction` | Accepted rows from CSV uploads |
| `rule` | User-defined validation rules (JSON conditions) |
| `validation_result` | Per-transaction results from LangGraph validation (deterministic rules + optional LLM triage) |
| `sar` | Suspicious Activity Reports generated by LLM, awaiting human review |
| `audit_log` | Event-sourced audit trail — every workflow step, validation write, and SAR review logged with event_type, entity, payload, actor |
| `enrichment_snapshot` | Eval audit trail — per-customer enrichment context frozen at `enrich_node` time, keyed by `(upload_id, customer_id)` |

##### `customer` Schema

| Field | Datatype | Constraints |
|---|---|---|
| customer_id | TEXT | PRIMARY KEY |
| first_name | TEXT | NOT NULL |
| last_name | TEXT | NOT NULL |
| address_line | TEXT | |
| city | TEXT | |
| state | TEXT | |
| zip | TEXT | |
| created_at | TEXT | ISO datetime |
| updated_at | TEXT | ISO datetime |

##### `account` Schema

| Field | Datatype | Constraints |
|---|---|---|
| id | TEXT | PRIMARY KEY (UUID) |
| account_id | TEXT | NOT NULL, UNIQUE — natural key |
| customer_id | TEXT | NOT NULL, FOREIGN KEY → customer(customer_id) |
| name | TEXT | nullable |
| bank | TEXT | nullable |
| location | TEXT | nullable |
| date_opened | TEXT | ISO date string |
| type | TEXT | e.g. checking, savings, credit |
| created_at | TEXT | ISO datetime |
| updated_at | TEXT | ISO datetime |

##### `uploaded_files` Schema

| Field | Datatype | Constraints |
|---|---|---|
| id | TEXT | PRIMARY KEY (UUID) |
| filename | TEXT | NOT NULL |
| upload_chunk | INTEGER | nullable — NULL for parent row, chunk index for chunk tracking rows |
| status | TEXT | NOT NULL — `uploaded`, `processing`, `pending_human`, `complete`, `failed`, `committed` (chunk rows only) |
| total_rows | INTEGER | |
| accepted_count | INTEGER | |
| failed_count | INTEGER | with default=0 |
| failed_db_count | INTEGER | with server_default='0' |
| uploaded_at | TEXT | ISO datetime |
| created_at | TEXT | ISO datetime |
| updated_at | TEXT | ISO datetime |

> **Migration note:** `review_status` column was merged into `status` (v2). Old values: NULL → `uploaded`, PROGRESS → `processing`, PENDING_HUMAN → `pending_human`, COMPLETE → `complete`.

##### `rejected_record` Schema

| Field | Datatype | Constraints |
|---|---|---|
| id | TEXT | PRIMARY KEY (UUID) |
| upload_id | TEXT | NOT NULL, FOREIGN KEY → uploaded_files(id) |
| row_index | INTEGER | |
| raw_data | TEXT | JSON — original CSV row as dict |
| reasons | TEXT | JSON array of strings |
| created_at | TEXT | ISO datetime |
| updated_at | TEXT | ISO datetime |

##### `transaction` Schema

| Field | Datatype | Constraints |
|---|---|---|
| id | TEXT | PRIMARY KEY (UUID) |
| upload_id | TEXT | NOT NULL, FOREIGN KEY → uploaded_files(id) |
| account_id | TEXT | NOT NULL — FK reference, validated at upload |
| customer_id | TEXT | NOT NULL — FK reference, validated at upload |
| amount | REAL | |
| counterparty | TEXT | |
| location | TEXT | |
| date | TEXT | ISO date string |
| source_txn_id | TEXT | NOT NULL — source system transaction ID |
| status | TEXT | NOT NULL, default `loaded` — `loaded`, `clean`, `flagged`, `escalated`, `pending_review`, `dismissed` |
| ground_truth | TEXT | nullable — fraud pattern label for eval datasets (`structuring`, `velocity`, `impossible_travel`, `round_trip`, `watchlist`, or NULL for clean) |
| created_at | TEXT | ISO datetime |
| updated_at | TEXT | ISO datetime |

##### `rule` Schema

| Field | Datatype | Constraints |
|---|---|---|
| id | TEXT | PRIMARY KEY (UUID) |
| name | TEXT | NOT NULL |
| description | TEXT | |
| type | TEXT | NOT NULL, server_default='deterministic' — `deterministic` or `llm` |
| status | TEXT | NOT NULL, server_default='active' — active, inactive, draft |
| rules_json | TEXT | NOT NULL — JSON array of condition objects (deterministic) or prompt/guidelines (llm) |
| created_at | TEXT | ISO datetime |
| updated_at | TEXT | ISO datetime |

##### `validation_result` Schema

| Field | Datatype | Constraints |
|---|---|---|
| id | TEXT | PRIMARY KEY (UUID) |
| upload_id | TEXT | NOT NULL, FOREIGN KEY → uploaded_files(id) |
| transaction_id | TEXT | NOT NULL, FOREIGN KEY → transaction(id) |
| status | TEXT | NOT NULL — clean or flagged |
| flag_details | JSON | DB column `details`; `null` for clean, `{"rule-uuid": "rule-name"}` for flagged |
| risk_level | TEXT | nullable — `high` or `auto_reviewed` (set by triage_node) |
| category | TEXT | nullable — not currently used |
| triage_reasoning | TEXT | nullable — reason from triage decision |
| raw_llm_response | TEXT | nullable — raw JSON/text returned by the LLM API (triage response) for debugging |
| validated_at | TEXT | ISO datetime |
| created_at | TEXT | ISO datetime |
| updated_at | TEXT | ISO datetime |

```json
// flag_details — clean (SQL NULL)
null

// flag_details — flagged
{"a1b2c3d4-...": "High Value Check", "e5f6g7h8-...": "Offshore Transaction"}
```

##### `sar` Schema

| Field | Datatype | Constraints |
|---|---|---|
| id | TEXT | PRIMARY KEY (UUID) |
| transaction_id | TEXT | NOT NULL, FOREIGN KEY → transaction(id) |
| upload_id | TEXT | NOT NULL, FOREIGN KEY → uploaded_files(id) |
| rule_id | TEXT | nullable, FOREIGN KEY → rule(id) |
| content | TEXT | NOT NULL — SAR narrative (LLM-generated or placeholder); for stage3 includes deep-dive analysis reasoning |
| raw_llm_response | TEXT | nullable — raw JSON/text returned by the LLM API (SAR response) for debugging |
| status | TEXT | NOT NULL, default `pending_review` — `pending_review`, `confirmed`, `dismissed` |
| created_at | TEXT | ISO datetime |
| updated_at | TEXT | ISO datetime |
| reviewed_at | TEXT | nullable — ISO datetime of human review |
| review_notes | TEXT | nullable — human reviewer notes |

##### `audit_log` Schema (event-sourcing v2)

| Field | Datatype | Constraints |
|---|---|---|
| id | TEXT | PRIMARY KEY (UUID) |
| event_type | TEXT | NOT NULL — entity status transitions: `transaction.created`, `transaction.validated`, `transaction.triaged`, `transaction.escalated`, `transaction.reviewed`, `upload.created`, `upload.processing`, `upload.pending_human`, `upload.completed`, `upload.failed` |
| entity_type | TEXT | NOT NULL — `transaction`, `upload` |
| entity_id | TEXT | NOT NULL — UUID of the entity |
| upload_id | TEXT | nullable, FOREIGN KEY → uploaded_files(id) |
| payload | TEXT | NOT NULL — JSON dict with status transition context: `{"status": "flagged"}` or `{"from": "processing", "to": "pending_human"}` |
| actor | TEXT | NOT NULL, server_default='system' — `system` or `human` |
| created_at | TEXT | NOT NULL — ISO datetime |

##### `enrichment_snapshot` Schema

| Field | Datatype | Constraints |
|---|---|---|
| upload_id | TEXT | PRIMARY KEY, FOREIGN KEY → uploaded_files(id) |
| customer_id | TEXT | PRIMARY KEY |
| ref_date | TEXT | ISO datetime — `max(Transaction.date)` for the upload |
| customer_txn_count_30d | INTEGER | |
| customer_sum_30d | REAL | |
| customer_avg_30d | REAL | |
| customer_std_amt_30d | REAL | nullable |
| account_type | TEXT | nullable |
| account_age_days | INTEGER | nullable |
| structuring_24h_count | INTEGER | |
| velocity_zscore | REAL | nullable |
| dormancy_days | INTEGER | nullable |
| created_at | TEXT | ISO datetime |

**Relationships:**
- `account` → `customer` (many-to-one via customer_id)
- `uploaded_files` ← `rejected_record` (one-to-many via upload_id)
- `uploaded_files` ← `transaction` (one-to-many via upload_id)
- `uploaded_files` ← `validation_result` (one-to-many via upload_id)
- `uploaded_files` ← `sar` (one-to-many via upload_id)
- `uploaded_files` ← `audit_log` (one-to-many via upload_id)
- `uploaded_files` ← `enrichment_snapshot` (one-to-many via upload_id)
- `transaction` ← `validation_result` (one-to-one per validation run via transaction_id)
- `transaction` ← `sar` (one-to-one per escalation via transaction_id)
- `rule` ← `sar` (one-to-many via rule_id)

**Indexes:**
- `idx_upload_status` on `uploaded_files(status)`
- `idx_rejected_upload` on `rejected_record(upload_id)`
- `idx_transaction_upload` on `transaction(upload_id)`
- `idx_validation_upload` on `validation_result(upload_id)`
- `idx_validation_tx` on `validation_result(transaction_id)`
- `idx_audit_log_upload` on `audit_log(upload_id)`
- `idx_audit_log_event` on `audit_log(event_type)`
- `idx_audit_log_entity` on `audit_log(entity_type, entity_id)`

### Async Protocols

No external async messaging. The only async pattern is:

- **FastAPI** — `asyncio.create_task(run_validation(upload_id))` after a successful upload.
- AML_Workflow runs as a LangGraph state machine within the async task. No queues, no message brokers.
- Each background task creates its own `AsyncSession` from `async_session_factory` to avoid sharing sessions with the request handler.

---

## 10. Dependencies

### External

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | >=0.115.0 | Web framework |
| `uvicorn[standard]` | >=0.34.0 | ASGI server |
| `sqlalchemy[asyncio]` | >=2.0.0 | ORM + async engine |
| `aiosqlite` | >=0.20.0 | Async SQLite driver |
| `python-multipart` | >=0.0.20 | File upload parsing |
| `pandas` | >=2.2.0 | CSV parsing & DataFrame operations |
| `faker` | >=33.0.0 | Synthetic data generation (seed_db, test scripts) |
| `alembic` | >=1.14.0 | Database migrations |
| `langgraph` | >=1.2.0 | State machine / workflow graph |
| `langgraph-checkpoint-sqlite` | >=3.0.0 | SQLite checkpointer for interrupt/resume |

**Runtime-only imports (not in pyproject.toml):**
- `openai` — for `AsyncOpenAI` client (imported lazily in `llm.py`)
- `google-genai` (>=2.5.0) — for Gemini client (imported lazily in `llm.py`). `system_instruction` is passed in config dict, not as a top-level kwarg.

**Test-only:**
| Package | Version |
|---------|---------|
| `pytest` | >=8.0.0 |
| `pytest-asyncio` | >=0.24.0 |
| `pytest-cov` | >=5.0.0 |
| `httpx` | >=0.28.0 |

### Internal

None. No internal company packages are consumed.

---

## 11. Security Considerations

- **No authentication:** The application has no login, no API keys, no JWT, no bearer tokens, and no role-based access. Every endpoint is fully open. Explicitly deferred to v2.
- **CORS:** Wildcard CORS (`allow_origins=["*"]`, all methods, all headers) — acceptable for local single-user use, but would need tightening for any multi-user or network-exposed deployment.
- **LLM API keys:** `AML_OPENAI_API_KEY` and `AML_GEMINI_API_KEY` are passed directly to the respective SDKs. They are read from environment variables / `.env` file and never logged.
- **SQL injection:** No raw SQL. All queries use SQLAlchemy ORM with parameterized queries.
- **Input validation:** File extension check (`.csv` only), column presence check, row-level structural validation (required fields, types, FK lookups). No executable content is accepted.
- **Data protection:** All data is stored in a single local SQLite file. No encryption at rest. No TLS (local HTTP only).
- **Audit trail:** Every write to validation_result, every workflow step, and every SAR review is logged to the immutable `audit_log` table with actor, timestamp, and payload — providing non-repudiation.

---

## 12. Performance & Scalability

- **Upload throughput:** CSV rows are parsed via pandas (vectorized). Small CSVs (≤10K rows) are inserted in a single batch. Large CSVs are inserted in chunks of 10,000 rows per chunk with per-chunk tracking rows.
- **Workflow throughput:** Rule evaluation is O(txn × rules) with OR-short-circuit per rule. 1000 transactions × 10 rules ≈ 10,000 condition evaluations — completes in <1s.
- **LLM calls:** Only escalated transactions generate LLM calls. With `stage1` mode, no LLM calls are made. With `stage3` or `full` mode, flagged transactions produce stage2 triage calls and escalated transactions produce stage3 deep-dive triage calls + SAR generation calls (sequential per-node, async per-call).
- **Pagination:** All list endpoints default to 50 items per page, max 100. Uses SQL `LIMIT/OFFSET`.
- **Connection pooling:** SQLAlchemy default async pool settings (`pool_size=5`, `max_overflow=10`). Single-file SQLite limits concurrent write concurrency.
- **Retries:** Workflow nodes retry up to 3 times on transient errors (timeouts, connection errors, rate limits, operational errors) with exponential backoff (2^attempt seconds). Non-transient errors fail immediately.
- **No caching layer:** Every request queries SQLite directly. No Redis, no in-memory cache.
- **Scaling limitations:** Single-process, single-threaded (asyncio), single-file SQLite. Horizontal scaling would require switching to PostgreSQL and adding an external queue. This is a local-only tool.

---

## 13. Logs

### Logging Setup

**File:** `src/bff/logger.py`

- **Output destination:** `stdout` (no log files)
- **Default level:** `INFO` (can be overridden via `AML_LOG_LEVEL`)
- **Format:** `%(asctime)s  %(levelname)-8s  %(name)s  %(message)s` with ISO date format (`%Y-%m-%d %H:%M:%S`)
- **Logger name:** `aml_workflow`

### What Is Logged

| Component | Event | Level |
|-----------|-------|-------|
| Workflow | Started, completed | `info` |
| Workflow | Failed with exception type + message + traceback | `error` |
| Graph — load_data | Loaded N transactions and M rules for upload X | `info` |
| Graph — set_progress | Set review_status=PROGRESS for upload X | `info` |
| Graph — rule_engine_batch | N flagged, M clean out of T | `info` |
| Graph — triage_node | N escalated, M auto-reviewed out of T flagged | `info` |
| Graph — sar_node | Created N SARs for upload X | `info` |
| Graph — write_results | Wrote N validation results and M audit logs | `info` |
| Graph — set_review_status | Upload X review_status: OLD → NEW | `info` |
| Graph — node retry | Node failed (attempt N/M): ErrorType: message | `warning` |
| Graph — node permanent failure | Node failed permanently with exc_info | `error` |

### Audit Trail

Every entity status transition is recorded in the `audit_log` table:
- `event_type`: entity status transition (e.g. `transaction.validated`, `upload.completed`)
- `entity_type` + `entity_id`: the entity that changed state
- `payload`: JSON with destination status: `{"status": "flagged"}` or `{"from": "processing", "to": "pending_human"}`
- `actor`: `"system"` or `"human"`
- `created_at`: ISO timestamp

Step-level workflow events (e.g. `load_data.started`) are NOT written to the audit log — they are captured in application logging only (`logger.info`). Audit log tracks only business entity transitions.

No log rotation, no JSON logging, no structured logging framework. No external log aggregation.

---

## 14. Open Questions

- [ ] **LLM packages not in pyproject.toml:** `openai` and `google-genai` are imported lazily at runtime but not declared as dependencies. Expected to be installed manually by the user. Should they be added as optional dependencies?
- [ ] **Reference data endpoints for customers/accounts:** The API spec lists `GET /api/customers` and `GET /api/accounts` but no router registers these routes (only `sar.py`, `rules.py`, `audit.py`, `validation.py`, `upload.py`, `read.py`, `reprocess.py` are registered in `app.py`).
- [ ] **Gemini `google-genai` package name:** The actual PyPI package for Gemini is `google-genai` (not `google-generativeai`). Verifying correct package name in docs.
- [ ] **HRM (Human Review Mode):** The `category` column on `validation_result` is never written — should it be populated during triage?
- [ ] **Eval metrics precision formula:** `_compute_metrics` uses `tp = min(flagged, total)` — this assumes all flagged positives are from the anomalous set, which may overstate precision when non-anomalous transactions are also flagged. Is this the intended approximation?

---

## 15. References / Appendix

- **Documents:** `docs/progress.md`, `docs/runbook.md`
- **LangGraph:** https://langchain-ai.github.io/langgraph/
- **FastAPI:** https://fastapi.tiangolo.com/
- **SQLAlchemy async:** https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

---

## 16. Out of Scope (v1)

The following are explicitly out of scope for the initial build and deferred to future iterations:

- **`content_hash` dedup** — detecting and rejecting duplicate file uploads via SHA256 content hash
- **Transformers / LLM-based validation** — using ML models for anomaly detection or natural language rule parsing
- **External message queues** — Redis, Celery, SQS, or any async broker (BackgroundTasks suffice for single-process)
- **User authentication / authorization** — no login, roles, or API keys
- **Audit logging / data retention policies** — no structured audit trail or automated data purging
- **Docker / containerization** — no Dockerfile, docker-compose, or cloud deployment config
- **CI/CD pipeline** — no GitHub Actions, pre-commit hooks, or automated deployment
- **Multi-user / multi-tenant support** — single-user local app
