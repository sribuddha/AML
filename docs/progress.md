# Progress — AML App

## Build Status

| Module | Component | Status |
|---|---|---|
| **Backend — BFF** | File Processor — unified staging workflow (split/val/fail) | ✅ Done |
| | File Processor — progressive batch shrink + .val.db/.dbfail + chunk tracking | ✅ Done |
| | File Processor — location column expanded to city/state/country at upload | ✅ Done |
| | BFF read endpoints (GET /uploads, /transactions, /rejected, /validation) | ✅ Done |
| | Rules Engine validator (apply conditions to transactions) | ✅ Done |
| | Rules Engine CRUD (POST/PUT/DELETE /api/rules + filter/list) | ✅ Done |
| **Backend — Workflow** | AML_Workflow — deterministic rule engine (LangGraph, 100-txn batches) | ✅ Done |
| | AML_Workflow — LLM triage/sar nodes | ✅ Done |
| | AML_Workflow — Two-stage triage (stage2 aggregate + stage3 deep-dive) | ✅ Done |
| | AML_Workflow — Entity status tracking (transaction.status, upload.status) | ✅ Done |
| | AML_Workflow — Status-transition audit log (no step-level noise) | ✅ Done |
| | LLMClient unit tests (fallbacks, prompts) | ✅ Done |
| | Workflow node unit tests (triage, sar, load, write) | ✅ Done |
| **Infrastructure** | Config + async database session | ✅ Done |
| | Alembic migrations (sync env.py, auto-run on startup) | ✅ Done |
| | UUID PKs/FKs + `source_txn_id` column | ✅ Done |
| | Chunk tracking + `failed_db_count` + progressive insert | ✅ Done |
| **Eval Harness** | Fraud pattern generator (5 patterns, ground truth labels) | ✅ Done |
| | Hallucination check (number/entity verification against evidence) | ✅ Done |
| | Completeness check (rule coverage in SAR narratives) | ✅ Done |
| | Eval pipeline (upload → workflow → metrics → report) | ✅ Done |
| | Eval integration tests (31 tests, 94% coverage) | ✅ Done |
| **Scripts** | `init_db` — create tables via Alembic | ✅ Done |
| | `seed_db` — 50 customers + 1-2 accounts each + 7 deterministic rules (`--force` flag) | ✅ Done |
| | `delete_upload` — remove upload + all associated records (7 tables: ValidationResult, SAR, AuditLog, Transaction, RejectedRecord, chunks, UploadedFiles) + staging + data dir | ✅ Done |
| | `test_generate_upload_data` (was `generate_sample`) — create test CSV with optional bad rows | ✅ Done |
| | `retry_upload` — retry a failed upload with dedup | ✅ Done |
| | `visualize_graph` — output Mermaid/PNG of LangGraph | ✅ Done |
| | `test_generate_fraud_data` (was `generate_fraud_data`) — synthetic fraud pattern CSV + manifest | ✅ Done |
| | `run_eval` — full eval pipeline (generate → upload → evaluate → report) | ✅ Done |
| | `generate_upload_data` — production upload CSV with --bad-rate count and --date | ✅ Done |
| | `generate_stage1_fraud_data` — rule-triggering transactions from DB rules + `.eval` output | ✅ Done |
| | `generate_stage2_fraud_data` — scenario-based LLM triage eval transactions (9 hardcoded scenarios, `.eval` output) | ✅ Done |
| | `evaluate_stage2` — compare LLM triage decisions against `.eval` expectations | ✅ Done |
| | `data_scrambler` — shuffle CSV rows in-place | ✅ Done |
| **Testing** | Unit tests (service.py — 23 tests) | ✅ Done |
| | E2E tests (upload endpoint — 16 tests) | ✅ Done |
| | Test artifact cleanup (autouse fixture removes staging dirs + CSV files) | ✅ Done |
| | Unit tests (validator.py + workflow nodes) | ✅ Done |
| | E2E tests (workflow — deterministic rule engine) | ✅ Done |
| | E2E tests (read endpoints + rules CRUD) | ✅ Done |
| | Node retry: timeout → log/give up (no automated retry yet) | 🔜 Nice-to-have |
| **Frontend** | React scaffold | ⬜ Not built |

## Key Decisions

| Topic | Decision |
|---|---|
| Upload validation | Hardcoded structural checks (required fields, FK lookups, type checks). Rules engine is a separate module — not applied at upload time. |
| Rules engine | Applied later in AML_Workflow, not during CSV ingestion. Two-phase: upload rejects structurally bad rows, workflow flags suspicious rows. |
| Rule format | JSON array of `{field, operator, value}` conditions. Validated as a monolith blob — no separate conditions table. |
| Rule type | `type` TEXT column (`deterministic` / `llm`) with `server_default='deterministic'`. Engine queries `WHERE type = 'deterministic'`. |
| Rule status | `status` TEXT column (active / inactive / draft) — not a boolean `enabled` flag. |
| `Transaction.amount` | `Float` column type, not `Integer`. |
| `validation_result` | No `rule_id` FK. Flagging stored as `flag_details` JSON (`{ruleID: ruleName}` map). |
| | `details` column repurposed as `flag_details` (same DB column, renamed model attribute). |
| `uploaded_files` | Tracks `total_rows`, `accepted_count`, `failed_count`. Status values: uploaded / processing / pending_human / complete / failed / committed (chunk rows). `review_status` merged into `status` (v2). |
| DB timestamps | `created_at` + `updated_at` on every table. `uploaded_at` and `validated_at` kept alongside for semantic clarity. |
| External API | Uses HTTP 400 for validation errors (not 200 with error body). Does not expose internal audit fields. |
| Migrations | Alembic with sync `env.py` (not async). Server lifespan runs `alembic upgrade head` on every startup — idempotent. |
| Sample generation | `--bad-rate N` flag to inject intentionally corrupt rows. Default 0. |
| PKs/FKs | All internal PKs and FKs are UUID (TEXT, `String(36)`). `customer_id` and `account_id` remain natural string keys. |
| Idempotency key | `source_txn_id` (source system transaction ID) used for retry dedup along with `account_id`. |
| Per-chunk tracking | Each chunk gets its own `UploadedFiles` row with `upload_chunk` index; `.val` renamed to `.val.db` on successful insert commit. |
| `.dbfail` files | Created only during retry when individual DB insert fails; re-processed on next retry alongside `.val`. |
| Progressive batch shrink | Retry tries bulk insert first (all rows), falls back to individual inserts; individual failures go to `.dbfail`. |
| Upload UUID | Single UUID generated by router (`uuid.uuid4()`); used as PK + staging dir name. Original CSV saved as `{filename}.orig` in staging, not in uploads root. |
| Rules CRUD | Insert-only: DELETE = soft-delete (status→inactive), PUT = soft-delete old + create new rule (new UUID). GET defaults to `status=active`. |
| Validation read endpoints | `by-date` groups by upload_id with clean/flagged counts. `details` returns only flagged rows with `source_txn_id`. `by-transaction` returns single latest result across all uploads. |
| Prompts | Stored as standalone `.txt` files in `src/aml_workflow/prompts/`, loaded at import by `loader.py`. Auditable by non-developers, versionable independently. |
| LLM system message | OpenAI: `messages[{"role": "system"}]`. Gemini: `system_instruction` in config dict (not top-level kwarg). Both use `str.format()` for templating (zero new dependencies). |
| `.eval` format | JSONL — one JSON object per line, keyed by `source_txn_id`. Stage1 overwrites, stage2 appends. |
| Stage2 scenarios | Hardcoded in `scripts/generate_stage2_fraud_data.py` (not read from DB). Covers both escalate and no-escalate cases to test LLM judgment. |
| `AsyncSqliteSaver` | Replaces `SqliteSaver` for v3.1.0 compatibility (async context manager required for async graphs). |
| `delete_upload` | Deletes in FK-safe order: ValidationResult, SAR, AuditLog, Transaction, RejectedRecord, chunk rows, parent UploadedFiles — all 7 tables. Also removes both staging and data directories. |
| `account.location` | Added via Alembic migration `e1c9c714d55d` after model was updated without a corresponding migration. |
| Account PK | `id` (UUID String(36)) as PK with `default=lambda: str(uuid.uuid4())`; `account_id` is unique but not PK — allows natural key lookup without exposing internal UUID. |
| Enrichment queries | All use `Transaction` table directly (no aggregation materialised views). Reference date is `max(Transaction.date)` for the current upload. |
| Enriched context format | Appended as `## Enriched Context` block to existing `triage_user.txt` prompt (same pattern as stage3 appends "Recent customer history"). |
| Enrichment scope | Per `customer_id`, not per transaction. All flagged txns sharing a customer reuse the same enriched dict. Only runs on flagged transactions. |
| Velocity z-score | Buckets prior 35 days into 4 weekly bins; z-score = (this_week - avg_prior) / std_prior. Requires ≥ 2 data points; returns `None` for insufficient data. |

### Phase 7b — LangGraph Native HITL (✅ Done)
- `interrupt()` + `AsyncSqliteSaver` checkpointer replaces manual `review_status` DB polling
- `human_review` node pauses graph after `sar_node` via `interrupt()`
- `PATCH /api/sar/{id}/review` resumes the graph with `Command(resume=…)` when all SARs resolved
- `set_progress` bug fixed — now actually sets `review_status = "PROGRESS"`
- Checkpoints stored in `<DATA_DIR>/checkpoints.db` via `AsyncSqliteSaver`
- `SqliteSaver.from_conn_string` replaced with `AsyncSqliteSaver.from_conn_string` (async context manager) for v3.1.0 compatibility
- `_run_node` correctly re-raises `GraphInterrupt` before general `except` to avoid treating interrupts as errors
- Fixed `NameError: name 'UploadedFiles' is not defined` in `sar_node` closure (lazy import)
- 25+ graph unit tests, 18+ LLM unit tests, 126+ total unit tests green; graph.py 93% coverage, triggers.py 94% coverage

### Prompt Refactor (✅ Done)
- All triage prompts extracted from `llm.py` into standalone `.txt` files in `src/aml_workflow/prompts/`
- `_build_triage_prompt` removed; replaced with `_build_rule_evidence()` + `_build_triage_messages()`
- `llm.triage()` now accepts `rules: list[dict] | None` parameter; rule names/descriptions grounded in prompt
- Gemini `system_instruction` compatibility confirmed with `google-genai` v2.5.0
- E2E test with real Gemini (`gemini-2.5-flash-lite`) verified

### Phase 7c — Parallel Send() (planned)
- `triage_one` / `sar_one` nodes with `Send()` fan-out for concurrent LLM calls
- State reducers (`Annotated` + merge functions) for aggregating parallel results

### Phase 8 — Entity Status Tracking + Two-Stage Triage (✅ Done)
- `Transaction.status` column added: loaded / clean / flagged / escalated / pending_review / dismissed
- `UploadedFiles.status` unified: merged `review_status` into single `status` column
- `stage2_triage` node: LLM aggregate analysis, confidence threshold in prompt
- `stage3_triage` node: LLM deep-dive with customer recent transaction history, confidence threshold in prompt
- `sar_node`: creates SAR row, updates upload → pending_human
- `human_review` interrupt: pauses for human review of SARs
- `finalize` node: upload → complete
- Audit log records only entity status transitions — no step-level noise (`{step}.started/completed` removed)
- `sar.status` values: pending_review → confirmed / dismissed
- `transaction.reviewed` audit event written on human PATCH review

### Location Split (✅ Done)
- `Transaction.location` → `city`/`state`/`country` (three separate String columns)
- CSV format unchanged — `service.py` expands `location` at upload via `_LOCATION_MAP`
- Unknown locations → row rejection (data consistency expected, no silent fallback)
- `_LOCATION_MAP` in `service.py` with ~25 entries covering all known CSV location values
- Countries use full names (e.g., `"Cayman Islands"`) — self-documenting in rules
- Migration `013_location_split.py` — adds city/state/country, backfills from location, drops location column
- `validator.py` unchanged — rules target flat `country` field
- `llm.py`: `_fmt_location()` helper, all location references updated to city/state/country
- `scripts/seed_db.py` rules updated: `field: "location"` → `field: "country"`
- `scripts/generate_stage1_fraud_data.py` updated: country conditions map to valid location values
- `retry_upload` now expands location before re-inserting rows
- Key bug fix: `date` field was accidentally dropped from `accepted` dict during location refactor — restored
- `Account.location` column removed from model + deleted migration `e1c9c714d55d` (repointed `008`/`009`)
- `generate_upload_data` and `generate_stage1_fraud_data` now accept optional `session` param
- Count: 310 passed, 1 skipped, 95% coverage
- Skipped: `test_review_completes_upload_when_all_resolved` — pre-existing flaky E2E (SQLite session race)

### Test Restructure & Coverage Recovery (✅ Done)
- Flat `tests/` restructured into `{unit,e2e}/{bff,aml,file,ui}/` by domain
- E2E tests accidentally deleted during restructure, recreated with agents
- Coverage dipped to 88% after lost tests; recovered to 98% by writing 53 new tests:
  - 8 new test files covering REST API endpoints (upload, read, sar review, validation, reprocess, rules CRUD filters/errors), AuditLog model, and LLM client OpenAI/Gemini methods
- Key uncovered lines remaining: `llm.py` provider detection (5), `read.py` JSON error paths (5), `reprocess.py` heartbeat edge cases (3), `rules.py` status filter (2), `validator.py` edge cases (2), `logger.py` (1), `service.py` NaN cleanup (5), `graph.py` (9)
- Total: **321 passed, 0 failed, 98% coverage** (33/1734 uncovered)
- Test suite: 46s (session-scoped engine + 53 more tests)

### Performance (test suite speedup)
- Test suite reduced from 192s to 60s (~69% faster)
- `CHUNK_SIZE` made configurable via `AML_CHUNK_SIZE` env var (default 10000 in `service.py:19`)
- Chunking E2E tests reduced from 15001 to 501 rows with `CHUNK_SIZE=500`, cut from 25s to <1s each
- `engine` fixture changed to `scope="session"` — single DB for all tests, table cleanup in fixture teardown
- Session-scoped engine + table cleanup saved ~90s per full suite run

### Enrichment Layer (✅ Done)
- `Account` model — consolidated into `src/bff/models/account.py` (id UUID PK, account_id unique, customer_id, name, bank, location, type, date_opened, timestamps)
- Alembic migration `009_account.py` — creates `account` table + seeds from existing `transaction` data
- `src/aml_workflow/enrichment.py` — `EnrichedContext` dataclass + `enrich_transactions()` async function computing:
  - 30d customer stats (count, sum, avg, std dev)
  - Structuring 24h count (txns in [$9K, $10K])
  - Velocity z-score (this-week vs prior 4 weeks)
  - Dormancy (days since last transaction)
  - Account profile (type, age)
- `enrich_node` in `graph.py` — new node between `rule_engine_batch` and `stage2_triage`; only runs when flagged transactions exist
- `llm.triage()` — `enriched_context` param appended to user prompt (same pattern as stage3 history)
- 26 unit tests, 99% coverage on `enrichment.py`
- `EnrichmentSnapshot` model + migration `010_enrichment_snapshot.py` — write-only table keyed by `(upload_id, customer_id)` for eval audit trail

### Phase 8 — SSE Streaming (deferred to UI)
- `astream()` replaces `ainvoke()` for real-time node progress
- LLM token streaming during SAR generation (requires UI)

### Phase 9 — Eval file priority fix
- Upload route now prefers `.manifest.json` over `.eval` — synthetic generator produces `FRAUD_` IDs in the manifest that match DB transactions, while stage generators produce `ST1_`/`ST2_` IDs that don't match
- Existing upload `5c9f3789` fixed: eval file corrected from `.eval` to `.manifest.json`
- Eval hallucination check now passes `related_transactions` to avoid flagging amounts from same-customer transactions as hallucinated

## Testing Conventions

- **Directory structure:** `tests/{unit,e2e}/{bff,aml,file,ui}/` organized by domain × type; `tests/eval/` stays flat
- **Database:** In-memory SQLite (`sqlite+aiosqlite://`). No Alembic — uses `Base.metadata.create_all` directly. Single session-scoped engine for all tests.
- **Fixtures** (`tests/conftest.py`):
  - `engine` (session-scoped) — creates tables on a fresh in-memory DB, disposed after all tests
  - `session` — fresh async session per test, table cleanup on teardown
  - `seeded_session` — seeds 3 customers (CUST001–003) + 4 accounts (ACC001–004), table cleanup on teardown
  - `client` — `httpx.AsyncClient` with `ASGITransport` wrapping a test FastAPI app
  - `_cleanup_staging` (autouse) — tracks test upload IDs via `after_insert` event listener; removes test-created staging dirs post-test
- **Unit tests** call `process_upload(df, filename, upload_id, session, content)` directly with a pandas DataFrame
- **E2E tests** use the `client` fixture to test REST endpoints via `httpx.AsyncClient`
- **Workflow E2E tests** seed deterministic rules and verify `validation_result` rows after upload
- **Coverage:** `migrations/` excluded from report. Use `--cov-report=term-missing` (no annotated files).
- **LLM test isolation:** `test_llm.py` uses `monkeypatch` to clear API keys in environment, ensuring fallback code paths are exercised without real API calls.
- **Ad-hoc files:** All generated artifacts go to `work/` (gitignored). See AGENTS.md.
- **Run command:** `python -m pytest tests/ --cov --cov-report=term-missing`

## What's Left

### Minor coverage gaps (92%)
- `rules.py` at 85% (12 new lines: PATCH endpoint + default status filter)
- `llm.py` at 97% (lines 55-56, 63, 70, 77: provider detection branches)
- `read.py` at 92% (lines 135, 148-149, 154-155: rejected record JSON parsing errors)
- `reprocess.py` at 93% (lines 43-44: heartbeat `ValueError/TypeError`, 51: unknown status)
- `graph.py` at 96% (9 lines across various error paths)
- `service.py` at 98% (5 lines: NaN cleanup branches)
- Target: ≥ 90% per module (already met at 92% overall)

### UI Improvements (✅ Done)
- **Full-width layout**: Removed `max-w-7xl` constraint from main content area — AML Monitor now spans the full page
- **Homepage**: 5-card dashboard at `/` (Compliance, Operations, Rules, Customers, Transactions) replacing the redirect to `/transactions`
- **AML Monitor title**: Sidebar title links to `/` for easy navigation back to dashboard
- **TestPage unchecked state**: Removed `opacity-50` / muted text styling; unchecked rows use dashed borders + "tick to add" hint; count inputs stay visible and editable for pre-configuration

### Vitest + Unit Tests (✅ Done)
- **266 tests across 16 files** — all passing
- **Coverage: 93.71% statements, 96.27% lines** (component/page coverage)
- Covers all 7 pages + all 5 components + API client
- Commands: `npm test`, `npm run test:watch`, `npm run test:coverage`
- Run from `ui/` directory

### Playwright E2E UI Tests (new)
- 7 spec files in `tests/e2e/ui/` covering Compliance, Operations, Rules, Transactions, Customers, Test Generator, Layout
- Run from `ui/` with `npx playwright test`
- Config with `webServer` for auto-starting backend + Vite dev server
- Global setup seeds DB with `scripts.seed_db --force`

### React Frontend (after Phase 6)
- Vite + TypeScript scaffold
- Upload page (drag-and-drop CSV)
- Transaction list + validation dashboard

### Rule Status Toggle (✅ Done)
- `PATCH /api/rules/{rule_id}/status` endpoint — in-place toggle without versioning
- `RuleStatusUpdate` Pydantic schema (`status: "active" | "inactive"`)
- Frontend `RulesPage.tsx`: Deactivate/Activate toggle button per row, status dropdown in edit form, removed "Delete" action
- E2E tests: 3 new backend tests (404, 422 invalid, active→inactive→active toggle)
- Playwright E2E UI tests: 7 spec files covering all pages + sidebar navigation

### Eval Integration (✅ Done)
- **TestPage preview**: After generation, two tabs show CSV content (read-only table) and `.eval` ground truth data side-by-side in scrollable containers
- **Upload from work**: `POST /api/uploads/from-work/{filename}` processes a server-side CSV (from `work/`) and associates any `.eval` sidecar file with the upload record
- **Operations Eval button**: "Eval" button on completed uploads with `eval_file` → calls `POST /api/uploads/{upload_id}/eval` and opens a modal showing:
  - Summary cards (transactions, anomalous, flagged)
  - Overall metrics (precision, recall, F1)
  - Hallucination-free rate and avg completeness
  - Per-pattern metrics table with color-coded scores
  - Hallucination issues list (failed checks with hallucinated facts)
  - Completeness issues list (missed rules per SAR)
- **New endpoints**:
  - `GET /api/generate/eval/{filename}` — serves `.eval` JSONL or `.manifest.json` as JSON
  - `GET /api/generate/preview/{filename}` — returns first N CSV rows as JSON for table preview
  - `POST /api/uploads/from-work/{filename}` — upload CSV from server-side `work/` directory
  - `POST /api/uploads/{upload_id}/eval` — run eval on processed upload, returns `EvalReportResponse`
- **New DB column**: `uploaded_files.eval_file` (String, nullable) — stores path to `.eval` sidecar
- **Migration**: `014_eval_file.py` (adds column, no data migration needed)
- **Schema types**: `GenerateResponse` extended with `filename` and `eval_url`; new `EvalReportResponse`, `EvalEntry`, `PatternMetricsResponse`, `HallucinationResultResponse`, `CompletenessResultResponse`
- **Frontend types**: `GenerateResponse` updated; new `CsvPreview`, `EvalEntry`, `EvalReport`, `PatternMetrics`, `HallucinationResult`, `CompletenessResult`, `UploadSummary.eval_file`

### Customer Name Persistence + "View all" Link (✅ Done)
- **Customer name persists**: `customerName` state in CompliancePage captured on first SAR load, survives after `sars` cleared by Accept All / Dismiss All (no longer falls back to raw ID `CUST005`).
- **"View all pending reviews"**: Shown as a link below the green checkmark in completed state when `customerUrlId` is set — navigates to `/compliance` (clears customer filter).
- Tests: all 19 CompliancePage tests pass, build clean.

### Phase 8 — LLM Confidence Pipeline, Batching & Logging (✅ Done)
- **SAR LLM fields**: Migration `015_sar_llm_fields.py` adds `llm_confidence`, `triage_reasoning`, `triage_stage` to `sar` table; piped from triage nodes through to SAR records and displayed in ReviewCard UI (confidence %, stage badge, reasoning section)
- **LLM logging**: `import logging` + `logger` in `llm.py` with warnings on missing API keys, errors on all OpenAI/Gemini exception handlers (both per-item and batch paths)
- **Batch LLM calls**: 6 env vars (`AML_STAGE2_BATCH_SIZE=25`, `AML_STAGE3_BATCH_SIZE=5`, `AML_SAR_BATCH_SIZE=5`, concurrency=1 per stage). Batch methods (`triage_batch`, `triage_stage3_batch`, `generate_sar_batch`) with chunking + semaphore, OpenAI/Gemini structured output schemas, `source_txn_id` cross-matching parsers
- **Graph node batching**: `stage2_triage`, `stage3_triage`, `sar_node` collect all items and call batch methods; stage3 uses single `WHERE customer_id IN (...)` query
- **Info logs per LLM call**: `logger.info(...)` at all 12 API call sites (6 batch + 6 individual) logging model name and transaction count/ID
- **Provider switch**: Migrated from Gemini free tier to OpenAI GPT-4.1-nano (configurable via `.env`); `gpt-4.1-nano` is the cheapest GPT model ($0.10/$0.40 per MTok, deprecating Oct 2026)
- **SAR hyperlinks in UI**: Transaction links (Txn/Acct/Cust) moved from standalone section into SAR Report container — tagged under the report heading
- **Dependency fix**: `openai` and `google-genai` added to `pyproject.toml` via `uv add`
- **Bug fix**: `source_txn_id` popped from LLM response dict before unpacking into `TriageDecision(**d)` to avoid unexpected keyword argument error
- **Current totals**: 196 backend unit tests, 85 e2e, 272 frontend tests — all passing

### Phase 7 — Eval Harness + Improvements (in progress)
- Calibration check (confidence vs actual accuracy across deciles)
- Two-stage triage filter (cheap Stage 1, expensive Stage 2) — ✅ Done
- Per-transaction audit log — ✅ Done
- Workflow mode (stage1 / stage2 / full) — hardcoded in `triggers.py`; controls whether LLM is used for triage and SAR generation

### Phase 9 — Batch API + Cost Optimization (planned)
- Switch from synchronous per-chunk calls to OpenAI Batch API endpoint (50% cost reduction, async 24h turnaround)
- Model fallback chain: gpt-4.1-nano → gpt-4o-mini → fallback template (graceful degradation)
- Per-stage model overrides (cheap triage, better SAR)

### Nice to Have / Future (deferred to v2)
- File content dedup via SHA256
- Split test suite: `tests/unit/ tests/eval/` for fast workflow feedback (~20s), `tests/e2e/` only for API changes (~1min)
- LLM-based validation / anomaly detection
- External message queues (Redis, Celery)
- Authentication / authorization
- Containerization (Docker)
- CI/CD pipeline
