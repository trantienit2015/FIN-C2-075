# FIN-C2-075 — Unit Tests: ThreeWayMatchNode (inner step 2) + ap_service

from framework.schemas.agent_status import AgentStatus
from src.nodes.three_way_match_node import ThreeWayMatchNode
from src.services.ap_service import approval_tier_for, validate_qii, redact_bank_details


class FakeERP:
    def __init__(self, po, gr):
        self._po, self._gr = po, gr

    def fetch_po(self, n):
        return self._po

    def fetch_goods_receipt(self, n):
        return self._gr


def _state(invoice):
    return {"invoice_record": invoice, "node_history": [], "error_log": [], "execution_time": {}}


class TestThreeWayMatchNode:
    def test_matched(self):
        erp = FakeERP({"amount": 1000, "quantity": 2}, {"quantity": 2})
        node = ThreeWayMatchNode(erp=erp)
        inv = {"amount": 1000, "po_number": "PO1", "qii_registration": "T1234567890123"}
        result = node.execute(_state(inv))
        assert result["status"] == AgentStatus.SUCCESS
        assert result["match_result"] == "matched"
        assert result["discrepancies"] == []

    def test_amount_discrepancy(self):
        erp = FakeERP({"amount": 999, "quantity": 2}, {"quantity": 2})
        node = ThreeWayMatchNode(erp=erp)
        inv = {"amount": 1000, "po_number": "PO1", "qii_registration": "T1234567890123"}
        result = node.execute(_state(inv))
        assert result["match_result"] == "discrepancy"
        assert any(d["field"] == "amount" for d in result["discrepancies"])

    def test_invalid_qii_flagged(self):
        erp = FakeERP({"amount": 1000, "quantity": 1}, {"quantity": 1})
        node = ThreeWayMatchNode(erp=erp)
        inv = {"amount": 1000, "po_number": "PO1", "qii_registration": "BAD"}
        result = node.execute(_state(inv))
        assert any(d["field"] == "qii_registration" for d in result["discrepancies"])


class TestApService:
    def test_tier_routing(self):
        tiers = {"department_head": 100000, "finance_manager": 1000000, "cfo": None}
        assert approval_tier_for(50000, tiers) == "department_head"
        assert approval_tier_for(500000, tiers) == "finance_manager"
        assert approval_tier_for(5000000, tiers) == "cfo"

    def test_validate_qii(self):
        assert validate_qii("T1234567890123") is True
        assert validate_qii("1234567890123") is False

    def test_redact_bank_details(self):
        out = redact_bank_details({"bank_account": "1234567", "vendor": "ACME", "note": "acct 9876543"})
        assert out["bank_account"] == "[REDACTED]"
        assert "[REDACTED]" in out["note"]
        assert out["vendor"] == "ACME"
