"""Inner domain workflow graph for FIN-C2-075 (Cat 2 + HITL).

Topology: START -> ocr_extract -> three_way_match -> approval_route(interrupt) -> payment_schedule -> END.
Instantiated by APPipelineGraphNode.get_subgraph().
"""

from __future__ import annotations

from typing import Any
from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus

from src.nodes.ocr_extract_node import OCRExtractNode
from src.nodes.three_way_match_node import ThreeWayMatchNode
from src.nodes.approval_route_node import ApprovalRouteNode
from src.nodes.payment_schedule_node import PaymentScheduleNode
from src.schemas.state import State


class APWorkflowGraph(BaseGraph):
    """OCR -> match -> approval (HITL) -> payment inner workflow."""

    @property
    def name(self) -> str:
        return "ap_approval_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        pass

    def register_nodes(self) -> None:
        cfg = self.config if hasattr(self, "config") and self.config else {}
        self._nodes["ocr_extract"] = OCRExtractNode(ocr=cfg.get("ocr"))
        self._nodes["three_way_match"] = ThreeWayMatchNode(erp=cfg.get("erp"))
        # HITL deployment policy travels in the forwarded `hitl` block (config/config.yaml).
        # Default True — the approval gate is kept unless a deployment opts out explicitly.
        hitl_cfg = cfg.get("hitl") or {}
        self._nodes["approval_route"] = ApprovalRouteNode(
            approval_tiers=cfg.get("approval_tiers", {}),
            confirmation_required=hitl_cfg.get("confirmation_required", True),
        )
        self._nodes["payment_schedule"] = PaymentScheduleNode(
            bank=cfg.get("bank"), auto_schedule=cfg.get("auto_schedule", False)
        )

    def add_edges(self) -> None:
        self._sg.add_edge(START, "ocr_extract")
        self._sg.add_edge("ocr_extract", "three_way_match")
        self._sg.add_edge("three_way_match", "approval_route")
        self._sg.add_edge("approval_route", "payment_schedule")
        self._sg.add_edge("payment_schedule", END)

    def route(self, state: AgentState) -> str:
        return END if state.get("status") == AgentStatus.ERROR.value else "payment_schedule"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        return {
            "invoice_record": state.get("invoice_record", {}),
            "match_result": state.get("match_result", ""),
            "discrepancies": state.get("discrepancies", []),
            "approval_tier": state.get("approval_tier", ""),
            "approval_decision": state.get("approval_decision", ""),
            "payment_scheduled": bool(state.get("payment_scheduled", False)),
            "payment_record": state.get("payment_record", {}),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
