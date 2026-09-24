"""APPipelineGraphNode — the `main` slot GraphNode (FIN-C2-075, Cat 2 + HITL).

Wraps the inner OCR -> match -> approval(interrupt) -> payment subgraph. `propagate_hitl=True`
surfaces the inner ApprovalRouteNode's `interrupt()` to the outer caller so the HITL pause/
resume cycle works across the Cat 2 boundary.
"""

from __future__ import annotations

from typing import Any, ClassVar, cast

from langgraph.errors import GraphBubbleUp

from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class APPipelineGraphNode(GraphNode):
    """Cat 2 main slot — wraps the AP processing + approval domain workflow."""

    # S-1: explicit by design. This is the outer main-slot boundary that
    # receives the caller's first-hop input into the AP subgraph — verified caller required
    # (matches agent.yaml default).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    error_strategy: ClassVar[str] = "propagate"
    # Surface the inner HITL interrupt() to the outer graph caller (D6 across the Cat 2 boundary).
    propagate_hitl: ClassVar[bool] = True

    def __init__(
        self,
        ocr: Any = None,
        erp: Any = None,
        bank: Any = None,
        approval_tiers: Any = None,
        auto_schedule: Any = False,
        hitl: Any = None,
    ) -> None:
        super().__init__()
        self._ocr = ocr
        self._erp = erp
        self._bank = bank
        self._approval_tiers = approval_tiers or {}
        self._auto_schedule = bool(auto_schedule)
        # The outer graph's real `hitl` block (config/config.yaml), forwarded verbatim to the
        # inner graph. Hardcoding it here would silently swallow the deployment's
        # hitl.confirmation_required policy before it ever reaches ApprovalRouteNode.
        self._hitl = dict(hitl) if hitl else {}
        # Cache the compiled subgraph so its checkpointer persists across the invoke (suspend)
        # and resume calls — a fresh InMemorySaver per call would lose the suspended state.
        self._subgraph: Any = None

    def get_subgraph(self) -> Any:
        from langgraph.checkpoint.memory import InMemorySaver
        from src.graph.domain_workflow_graph import APWorkflowGraph

        if self._subgraph is None:
            sg = APWorkflowGraph(config=self._parent_config())
            # HITL: the inner subgraph holds the interrupt() approval node, so it MUST compile
            # with a checkpointer for the interrupt to surface (and be resumable) across the
            # Cat 2 boundary. Deployments inject a durable checkpointer; InMemorySaver default.
            sg.compile(checkpointer=InMemorySaver())
            self._subgraph = sg
        return self._subgraph

    def extract_input(self, state: AgentState) -> str:
        # S-4: runs inside GraphNode.execute() — audit the dispatch into the AP subgraph.
        emit_trace_event(
            "ap_pipeline_dispatched",
            {"invoice_ref": state.get("invoice_ref", ""), "resuming": bool(state.get("subgraph_thread_id"))},
            state,
        )
        return cast(str, state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        # S-4: runs inside GraphNode.execute() — audit the subgraph outcome merged back out.
        emit_trace_event(
            "ap_pipeline_completed",
            {
                "invoice_ref": state.get("invoice_ref", ""),
                "match_result": sub_result.get("match_result", ""),
                "approval_decision": sub_result.get("approval_decision", ""),
                "payment_scheduled": bool(sub_result.get("payment_scheduled", False)),
            },
            state,
        )
        return {
            "invoice_record": sub_result.get("invoice_record", {}),
            "match_result": sub_result.get("match_result", ""),
            "discrepancies": sub_result.get("discrepancies", []),
            "approval_tier": sub_result.get("approval_tier", ""),
            "approval_decision": sub_result.get("approval_decision", ""),
            "payment_scheduled": bool(sub_result.get("payment_scheduled", False)),
            "payment_record": sub_result.get("payment_record", {}),
            "status": sub_result.get("status"),
        }

    def _handle_call_error(self, subgraph: Any, e: Any, state: Any) -> Any:
        # When the inner subgraph fires interrupt() while nested in the outer langgraph runtime,
        # the signal arrives here as a langgraph "bubble-up" sentinel (GraphInterrupt /
        # ParentCommand). It MUST bubble up to the outer runtime so HITL pause/resume works —
        # NOT be wrapped as a SubgraphError. We match both the typed GraphBubbleUp base and any
        # *Interrupt sentinel by class name, to stay robust across langgraph build differences.
        if isinstance(e, GraphBubbleUp) or "interrupt" in type(e).__name__.lower():
            raise e
        return super()._handle_call_error(subgraph, e, state)

    def _parent_config(self) -> dict[str, Any]:
        return {
            "ocr": self._ocr,
            "erp": self._erp,
            "bank": self._bank,
            "approval_tiers": self._approval_tiers,
            "auto_schedule": self._auto_schedule,
            # The inner graph holds the interrupt() approval node, so it needs memory_enabled
            # so BaseGraph.invoke builds the thread config required by the checkpointer.
            "memory_enabled": True,
            # Forward the deployment's real hitl block (including confirmation_required).
            # Fall back to the enabled defaults only when the outer config declared none.
            "hitl": self._hitl or {"enabled": True, "max_hitl": 8},
        }
