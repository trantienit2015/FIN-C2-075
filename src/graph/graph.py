"""Outer graph for FIN-C2-075 — Accounts Payable Intelligent Processing & Approval Agent (Cat 2 + HITL).

Backbone: initialize -> pre_process (InvoiceIngest) -> main (APPipelineGraphNode)
-> post_process (AccountingPost) -> finalize. The `main` slot wraps the inner OCR -> match
-> approval(interrupt) -> payment subgraph with propagate_hitl=True (D6 HITL).
"""

from __future__ import annotations

from framework.graph.agent_base_graph import AgentBaseGraph

from src.nodes.invoice_ingest_node import InvoiceIngestNode
from src.nodes.ap_pipeline_graph_node import APPipelineGraphNode
from src.nodes.accounting_post_node import AccountingPostNode
from src.schemas.state import State


class AccountsPayableApprovalGraph(AgentBaseGraph):
    """Cat 2 outer graph for AP intelligent processing + tiered HITL approval."""

    @property
    def name(self) -> str:
        return "fin-c2-075"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects initialize + finalize
        cfg = self.config if hasattr(self, "config") and self.config else {}
        self._nodes["pre_process"] = InvoiceIngestNode()
        self._nodes["main"] = APPipelineGraphNode(
            ocr=cfg.get("ocr"),
            erp=cfg.get("erp"),
            bank=cfg.get("bank"),
            approval_tiers=cfg.get("approval_tiers", {}),
            auto_schedule=cfg.get("payment_auto_schedule", False),
            # Forward the deployment's hitl block so hitl.confirmation_required reaches the
            # inner ApprovalRouteNode (config/config.yaml -> Graph(config=...) -> subgraph).
            hitl=cfg.get("hitl"),
        )
        self._nodes["post_process"] = AccountingPostNode()


# Alias for agent.yaml `module: "src.graph"` / AgentRegistry discovery.
Graph = AccountsPayableApprovalGraph
