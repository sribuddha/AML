# AML Transaction Monitoring System

An anti-money laundering workflow engine that automates Suspicious Activity Report (SAR) generation from CSV transaction uploads. Combines deterministic rules with optional LLM-based triage, enrichment analytics, and human-in-the-loop review.

![Python](https://img.shields.io/badge/python-3.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-009688) ![React](https://img.shields.io/badge/React-19-61DAFB) ![SQLite](https://img.shields.io/badge/SQLite-003B57) ![Docker](https://img.shields.io/badge/Docker-2496ED)

---

## User Flow

**Step 1**: Upload a CSV file containing transaction records (amount, account, customer, location, counterparty, date). Rows with unknown location strings or invalid references are rejected individually. Accepted rows are validated and inserted in configurable chunks of 10,000 rows.

**Step 2**: The file processor ingests the CSV and triggers the AML workflow. Each transaction is evaluated against the rule engine. Progress is visible in the operations dashboard.

**Step 3**: Flagged transactions appear in the compliance view with enrichment context (30-day stats, velocity z-score, structuring patterns) and LLM triage results.

**Step 4**: SARs pending human review show in the compliance queue. Review the evidence and approve or dismiss each SAR.

**Step 5**: Once all SARs for an upload are resolved, the workflow completes. Status updates across the dashboard and transaction views.

---

## Architecture

```
[React Frontend] ──HTTP──→ [FastAPI BFF]
                                │
                     [File Processor] → [SQLite DB] ← [AML Workflow (LangGraph)]
                                                            │
                                                     ├─ Rule Engine (stage 1)
                                                     ├─ LLM Triage (stage 2)
                                                     ├─ LLM Deep-Dive (stage 3)
                                                     └─ Human Review (stage 4)
```

The file processor and AML workflow are decoupled through the database. Ingestion writes accepted transactions, the workflow picks them up asynchronously through a status field. The frontend communicates through the same REST API available to scripts and tooling.

## System Components

### AML Workflow

Processes flagged transactions through a cascading series of stages. At each stage, only the most suspicious cases escalate to the next, reducing false positives early and reserving LLM calls and human review for genuinely high-risk activity.

| Stage | Description |
|-------|-------------|
| 1. Rule Engine | Deterministic rules flag transactions that exceed defined thresholds. Fast, zero LLM cost. |
| 2. LLM Triage | Quick LLM eval on flagged transactions using enriched customer context (30d stats, velocity, structuring, dormancy, computed in 5 batch queries). Filters false positives before deeper investigation. |
| 3. LLM Deep-Dive | Detailed LLM eval on escalated transactions using full recent transaction history. Generates structured SAR narratives. |
| 4. Human Review | LangGraph `interrupt()` pauses for compliance officer sign-off. Checkpoints survive restarts; system never auto-files. |

### File Uploader
Accepts CSV uploads with varying column names, validates row structure, expands free-text locations into city/state/country, inserts accepted rows in configurable chunks, rejects bad rows individually, and supports retry with dedup.

### UI
Dashboard and workflows for compliance officers to review SARs, manage rules, and monitor uploads without a terminal.

### BFF
REST API consumed by the frontend and scripts; also contains global modules for auth, CORS, audit logging, and configuration.

### Data Generator
CLI scripts and API endpoints that generate CSV transaction files for development and testing. Four generation types are available: clean uploads (standard transactions), stage 1 fraud (triggers specific deterministic rules), stage 2 triage (tests LLM escalation decisions), and synthetic fraud (embedded patterns like structuring, velocity, impossible travel, round-trip, and watchlist). Each produces a companion `.eval` file with ground-truth labels used by the Detection Quality Pipeline.

### Detection Quality Pipeline (Eval Harness)
Synthetic fraud generators for 5 patterns (structuring, velocity, impossible travel, round-trip, watchlist). Measures precision/recall/F1 per pattern and per stage. Includes hallucination detection, completeness checks, and confidence calibration (ECE).

---

## Testing Philosophy

- **551 Python tests (98% coverage)**: rules, enrichment, LLM fallbacks, file processor edge cases, workflow routing, API endpoints
- **302 Vitest tests (97% coverage)**: React component behavior
- **7 Playwright E2E specs**: critical upload to review to completion path
- **Detection Quality Pipeline**: validates the system actually catches bad actors, not just that code paths execute

---

## Documentation

1. **`docs/Technical_Spec.md`**: architecture, API design, persistence, OWASP LLM Top 10 conventions
2. **`docs/runbook.md`**: operational commands, env var reference, Docker deployment, LLM safety controls
3. **`docs/progress.md`**: 50+ design decisions with rationale, build status, testing conventions
4. **`docs/UI_Technical_Spec.md`**: frontend architecture, component API docs
5. **`AGENTS.md`**: developer workflow conventions

---

## Prerequisites

- Python 3.12+
- Node.js 18+ (for frontend development)
- Docker (for containerized deployment)

## Quick Start

```bash
pip install -e .
python -m scripts.init_db
python -m scripts.seed_db
uvicorn src.bff.app:app --reload
```

Set `AML_OPENAI_API_KEY` or `AML_GEMINI_API_KEY` in `.env` for LLM features. See `docs/runbook.md` for full configuration and deployment options.

---

## Project Evolution

1. File processor with CSV validation, location expansion, and chunked insert.
2. Deterministic rule engine that can be customized with inbuilt operators
3. LangGraph workflow with enrichment, two-stage LLM triage, human-in-the-loop review, and SAR generation.
4. Batching - each stages have different batch sizes
5. FastAPI server with SQLAlchemy models and Alembic migrations.
6. React frontend scaffold with dashboard and paginated views.
7. Eval Harness (detection quality pipeline): synthetic fraud generators and metrics.
8. Langfuse observability: LLM call tracing with LangGraph instrumentation.
9. Codebase refactoring for modularity and performance.
10. UI design system with layout, toast notifications, and component consistency.
11. Docker containerization, OWASP LLM Top 10 security controls, health endpoint, confidence calibration, and LLM budget/timeout management.

---

## License

MIT. See `LICENSE`.
