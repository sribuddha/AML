from __future__ import annotations

from functools import partial

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.llm import LLMClient
from src.aml_workflow.nodes import (
    _is_transient,
    load_data_node,
    rule_engine_batch_node,
    enrich_node,
    stage2_triage_node,
    stage3_triage_node,
    sar_node,
    human_review_node,
    finalize_node,
    has_flagged,
    has_escalated,
    needs_sar,
)
from src.aml_workflow.state import WorkflowState

__all__ = ["create_workflow", "_is_transient"]


def create_workflow(
    db: AsyncSession,
    llm: LLMClient | None = None,
    mode: str = "full",
    checkpointer=None,
):
    if llm is None:
        llm = LLMClient()

    _bind = partial  # shorthand

    builder = StateGraph(WorkflowState)

    builder.add_node("load_data", _bind(load_data_node, db=db, llm=llm, mode=mode))
    builder.add_node("rule_engine_batch", _bind(rule_engine_batch_node, db=db, llm=llm, mode=mode))
    builder.add_node("enrich_node", _bind(enrich_node, db=db, llm=llm, mode=mode))
    builder.add_node("stage2_triage", _bind(stage2_triage_node, db=db, llm=llm, mode=mode))
    builder.add_node("stage3_triage", _bind(stage3_triage_node, db=db, llm=llm, mode=mode))
    builder.add_node("sar_node", _bind(sar_node, db=db, llm=llm, mode=mode))
    builder.add_node("human_review", _bind(human_review_node, db=db, llm=llm, mode=mode))
    builder.add_node("finalize", _bind(finalize_node, db=db, llm=llm, mode=mode))

    builder.set_entry_point("load_data")
    builder.add_edge("load_data", "rule_engine_batch")
    builder.add_conditional_edges(
        "rule_engine_batch",
        _bind(has_flagged, mode=mode),
        {"stage2": "enrich_node", "skip": "finalize"},
    )
    builder.add_edge("enrich_node", "stage2_triage")
    builder.add_conditional_edges(
        "stage2_triage",
        _bind(has_escalated, mode=mode),
        {"stage3": "stage3_triage", "sar": "sar_node", "skip": "finalize"},
    )
    builder.add_conditional_edges(
        "stage3_triage",
        _bind(needs_sar, mode=mode),
        {"sar": "sar_node", "skip": "finalize"},
    )
    builder.add_edge("sar_node", "human_review")
    builder.add_edge("human_review", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
