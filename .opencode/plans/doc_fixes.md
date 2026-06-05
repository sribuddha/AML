# Documentation Remediation Plan

## README.md (2 changes)

### Fix 1 — Python badge (line 5)
```
![Python](https://img.shields.io/badge/python-3.12-blue)
→
![Python](https://img.shields.io/badge/python-3.14-blue)
```

### Fix 2 — Python prerequisite text (line 89)
```
- Python 3.12+
→
- Python 3.14+
```

---

## Technical_Spec.md (5 changes)

### Fix 1 — Endpoint count (line 120)
```
19 REST endpoints under `/api`
→
35 REST endpoints under `/api`
```

### Fix 2 — Table count (line 128)
```
10 tables (customer, account, uploaded_files, rejected_record, transaction, rule, validation_result, sar, audit_log, enrichment_snapshot)
→
12 tables (customer, account, uploaded_files, rejected_record, transaction, rule, validation_result, sar, audit_log, enrichment_snapshot, transaction_status, upload_status)
```

### Fix 3 — Node list in orchestration table (line 384)
Remove `persist_results` from the node list. Change:
```
8 nodes: load_data, rule_engine_batch, persist_results, enrich_node, stage2_triage, stage3_triage, sar_node, human_review, finalize
→
8 nodes: load_data, rule_engine_batch, enrich_node, stage2_triage, stage3_triage, sar_node, human_review, finalize
```

### Fix 4 — Stage2 confidence threshold (lines 308–309, 313)
Replace claims about baked-in confidence thresholds for stage2 with description of range-based guidance. The stage2 prompt uses confidence ranges (0.8-1.0/0.5-0.7/0.2-0.4/0.0-0.1) and rule-based escalation criteria — no hard 50% threshold.

Change line 308:
```
  - `triage_stage2_system.txt` — stage2 aggregate triage (confidence threshold baked into instructions)
→
  - `triage_stage2_system.txt` — stage2 aggregate triage with range-based confidence guidance
```

Change line 313:
```
   - `triage()` — stage2: LLM receives transaction details + rule evidence + optional enriched context. Confidence threshold is instructed in the prompt. Returns `TriageDecision{escalate, reason, confidence}`.
→
   - `triage()` — stage2: LLM receives transaction details + rule evidence + optional enriched context. Confidence ranges (0.8-1.0 strong, 0.5-0.7 moderate, 0.2-0.4 weak, 0.0-0.1 clear) guide escalation decisions. Returns `TriageDecision{escalate, reason, confidence}`.
```

### Fix 5 — Stage2 threshold in FR-006 (line 72)
```
`stage2` (LLM triage with aggregate context, confidence threshold in prompt),
→
`stage2` (LLM triage with aggregate context, confidence ranges in prompt),
```

---

## runbook.md (1 change)

### Fix 1 — Stage2 threshold description (line 110)
```
Confidence thresholds are baked into the LLM prompt instructions (e.g. stage2: "only escalate if confidence ≥ 50%", stage3: "only escalate if confidence > 60%").
→
Confidence thresholds are baked into the LLM prompt instructions (e.g. stage2: range-based guidance with 0.5+ moderate confidence flags for escalation, stage3: "only escalate if confidence > 60%").
```

---

## progress.md (2 changes)

### Fix 1 — Location map count (line 134)
```
`_LOCATION_MAP` in `service.py` with ~25 entries covering all known CSV location values
→
`_LOCATION_MAP` in `service.py` with 30 entries covering all known CSV location values
```

### Fix 2 — Add current-state block at top (between line 1 and line 3)
```
## Build Status

| Module | Component | Status |
…
```
Insert a current-state summary block at the very top (after line 1 `# Progress — AML App`, before `## Build Status`):

```
*Current: 551 Python tests at 97% coverage. Full-stack app: React 19 frontend + FastAPI BFF + LangGraph workflow + SQLite. See history below for milestone details.*
```

---

## UI_Technical_Spec.md (1 change)

### Fix 1 — Prototype label (section 1 overview, around line 10)
Replace any "prototype" or "Phase 1" characterization. If the document labels the system as a prototype, change to "production" or "full-stack application."

The document currently says "Status: Draft" at line 7, which is fine. No other "prototype" labels were found. No changes needed unless a line like "Phase 1 prototype" exists.

---

## Verification Step

After applying all changes, run:
```bash
python -m pytest tests/ --cov --cov-report=term-missing
```
to verify the actual coverage number (claimed as both 97% and 98% in different spots) and adjust the README/progress.md accordingly.
