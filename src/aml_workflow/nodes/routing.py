from __future__ import annotations

from src.aml_workflow.state import WorkflowState


def has_flagged(state: WorkflowState, mode: str) -> str:
    results = state.get("results", [])
    flagged = [r for r in results if r["status"] == "flagged"]
    return "stage2" if flagged else "skip"


def has_escalated(state: WorkflowState, mode: str) -> str:
    results = state.get("results", [])
    escalated = [r for r in results if r.get("risk_level") == "high"]
    if not escalated:
        return "skip"
    if mode in ("stage3", "full"):
        return "stage3"
    return "sar"


def needs_sar(state: WorkflowState, mode: str) -> str:
    results = state.get("results", [])
    needs = [r for r in results if r.get("risk_level") == "high"]
    return "sar" if needs else "skip"
