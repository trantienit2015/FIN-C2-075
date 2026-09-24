# FIN-C2-075 — Unit Tests: ApprovalRouteNode (D6 HITL interrupt) — PB-7 node-level contract

import src.nodes.approval_route_node as arn
from framework.schemas.agent_status import AgentStatus
from src.nodes.approval_route_node import ApprovalRouteNode

TIERS = {"department_head": 100000, "finance_manager": 1000000, "cfo": None}


def _state(amount, **extra):
    s = {
        "invoice_record": {"vendor": "ACME", "amount": amount, "po_number": "PO-1"},
        "match_result": "matched",
        "discrepancies": [],
        "node_history": [], "error_log": [], "execution_time": {},
    }
    s.update(extra)
    return s


class TestApprovalRouteNode:
    def test_interrupt_is_called_with_draft(self, monkeypatch):
        """PB-7 (node level): execute() calls interrupt() with the approval draft (D6 pattern)."""
        captured = {}

        def fake_interrupt(payload):
            captured["payload"] = payload
            return {"decision": "approved"}  # simulate human resume

        monkeypatch.setattr(arn, "interrupt", fake_interrupt)
        node = ApprovalRouteNode(approval_tiers=TIERS)
        result = node.execute(_state(50000))

        assert "payload" in captured  # interrupt() was invoked
        assert captured["payload"]["draft"]["approval_tier"] == "department_head"
        assert result["status"] == AgentStatus.SUCCESS
        assert result["approval_decision"] == "approved"
        # hitl_draft set for idempotency on resume
        assert result["hitl_draft"]["amount"] == 50000

    def test_tier_routing_cfo(self, monkeypatch):
        monkeypatch.setattr(arn, "interrupt", lambda p: {"decision": "approved"})
        node = ApprovalRouteNode(approval_tiers=TIERS)
        result = node.execute(_state(5_000_000))
        assert result["approval_tier"] == "cfo"

    def test_rejection_decision_propagated(self, monkeypatch):
        monkeypatch.setattr(arn, "interrupt", lambda p: {"decision": "rejected"})
        node = ApprovalRouteNode(approval_tiers=TIERS)
        result = node.execute(_state(500000))
        assert result["approval_decision"] == "rejected"
        assert result["approval_tier"] == "finance_manager"
