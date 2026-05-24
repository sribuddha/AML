# AML Transaction Monitoring System

AI-powered anti-money laundering workflow engine built with LangGraph and FastAPI.

## Architecture

```
CSV Upload → File Processor → Rule Engine → LLM Triage → SAR Generation → Human Review
                    │                                    │
              location expand                    enriched context
           (city/state/country)              (30d stats, velocity,
                                               structuring, dormancy)
```

- **BFF** — FastAPI server with REST endpoints for uploads, transactions, rules CRUD, SAR review, and audit
- **File Processor** — CSV ingestion with structural validation, FK checks, location expansion, chunked inserts, and retry with dedup
- **Rule Engine** — Deterministic rules (LangGraph batch node) plus LLM-based triage (two-stage: aggregate + deep-dive)
- **Human Review** — LangGraph `interrupt()` for human-in-the-loop SAR review; graph resumes via `PATCH /api/sar/{id}/review`
- **Eval Harness** — Fraud pattern generators, hallucination/completeness checks, metrics pipeline

## Quick Start

```bash
pip install -e .
python -m scripts.init_db       # create tables (Alembic)
python -m scripts.seed_db       # seed 50 customers + 7 rules
uvicorn src.bff.app:app --reload
```

Set API keys in `.env` for LLM features:
```
AML_OPENAI_API_KEY=sk-...
# or
AML_GEMINI_API_KEY=...
```

## Key Features

- **Location expansion** — CSV `location` column auto-expands to `city`/`state`/`country` at upload; unknown locations rejected
- **Configurable chunking** — `AML_CHUNK_SIZE` env var (default 10000)
- **Two-stage triage** — Stage 2 aggregate LLM analysis with enriched context; Stage 3 deep-dive with customer history
- **HITL review** — LangGraph interrupt/resume with async SQLite checkpointer
- **Eval harness** — 5 fraud patterns, hallucination detection, completeness checks, metrics reports
- **321 tests, 98% coverage**

## Documentation

- `docs/Technical_Spec.md` — full technical specification
- `docs/progress.md` — build status and key decisions
- `docs/runbook.md` — operational commands and configuration reference
- `AGENTS.md` — developer workflow conventions

## License

MIT
