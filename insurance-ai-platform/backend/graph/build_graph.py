"""Wires the claims-processing nodes into a compiled LangGraph StateGraph.

Pipeline:
    extraction_node -> retrieval_node -> rule_resolution_node
    -> reasoning_node -> guardrail_node -> (auto_process_node | human_review_node)
    -> audit_log_node -> END

extraction_node short-circuits straight to human_review_node when the
structured input fails validation, since retrieval/rules/reasoning/
guardrails all assume valid extracted_data.

human_review_node calls interrupt(), so a real (durable) checkpointer is
required for that path to actually work -- without one, LangGraph has
nowhere to persist the paused state and resuming later isn't possible.
Pass one explicitly for anything beyond a single in-process test (e.g. a
Postgres-backed saver so a paused review survives an API restart);
omitting it defaults to an in-memory saver, fine for tests but the paused
state won't survive the process exiting.
"""

from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .nodes import (
    audit_log_node,
    auto_process_node,
    extraction_node,
    guardrail_node,
    human_review_node,
    reasoning_node,
    retrieval_node,
    rule_resolution_node,
)
from .state import ClaimState


def route_after_extraction(state: ClaimState) -> Literal["retrieval_node", "human_review_node"]:
    if state.get("extraction_errors"):
        return "human_review_node"
    return "retrieval_node"


def route_after_guardrail(state: ClaimState) -> Literal["auto_process_node", "human_review_node"]:
    guardrail_result = state.get("guardrail_result") or {}
    if guardrail_result.get("passed"):
        return "auto_process_node"
    return "human_review_node"


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    checkpointer = checkpointer or MemorySaver()
    graph = StateGraph(ClaimState)

    graph.add_node("extraction_node", extraction_node)
    graph.add_node("retrieval_node", retrieval_node)
    graph.add_node("rule_resolution_node", rule_resolution_node)
    graph.add_node("reasoning_node", reasoning_node)
    graph.add_node("guardrail_node", guardrail_node)
    graph.add_node("auto_process_node", auto_process_node)
    graph.add_node("human_review_node", human_review_node)
    graph.add_node("audit_log_node", audit_log_node)

    graph.set_entry_point("extraction_node")

    graph.add_conditional_edges(
        "extraction_node",
        route_after_extraction,
        {"retrieval_node": "retrieval_node", "human_review_node": "human_review_node"},
    )
    graph.add_edge("retrieval_node", "rule_resolution_node")
    graph.add_edge("rule_resolution_node", "reasoning_node")
    graph.add_edge("reasoning_node", "guardrail_node")

    graph.add_conditional_edges(
        "guardrail_node",
        route_after_guardrail,
        {"auto_process_node": "auto_process_node", "human_review_node": "human_review_node"},
    )

    graph.add_edge("auto_process_node", "audit_log_node")
    graph.add_edge("human_review_node", "audit_log_node")
    graph.add_edge("audit_log_node", END)

    return graph.compile(checkpointer=checkpointer)
