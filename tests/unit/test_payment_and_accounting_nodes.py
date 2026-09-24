# FIN-C2-075 — Unit Tests: PaymentScheduleNode + AccountingPostNode

from framework.schemas.agent_status import AgentStatus
from src.nodes.payment_schedule_node import PaymentScheduleNode
from src.nodes.accounting_post_node import AccountingPostNode


def _base(**extra):
    s = {"node_history": [], "error_log": [], "execution_time": {}}
    s.update(extra)
    return s


class TestPaymentScheduleNode:
    def test_approved_schedules(self):
        node = PaymentScheduleNode(bank=None, auto_schedule=False)
        result = node.execute(_base(approval_decision="approved", invoice_record={"amount": 1000}))
        assert result["status"] == AgentStatus.SUCCESS
        assert result["payment_scheduled"] is True

    def test_rejected_does_not_schedule(self):
        node = PaymentScheduleNode(bank=None)
        result = node.execute(_base(approval_decision="rejected", invoice_record={"amount": 1000}))
        assert result["status"] == AgentStatus.SUCCESS
        assert result["payment_scheduled"] is False

    def test_pending_does_not_schedule(self):
        node = PaymentScheduleNode(bank=None)
        result = node.execute(_base(approval_decision="", invoice_record={"amount": 1000}))
        assert result["payment_scheduled"] is False


class TestAccountingPostNode:
    def test_audit_redacts_bank_details(self):
        node = AccountingPostNode()
        result = node.execute(_base(
            approval_decision="approved",
            invoice_record={"vendor": "ACME", "amount": 1000, "bank_account": "1234567"},
            payment_record={"scheduled_date": "2026-07-01", "amount": 1000},
            invoice_ref="INV-1", approval_tier="finance_manager", payment_scheduled=True,
            match_result="matched",
        ))
        assert result["status"] == AgentStatus.SUCCESS
        assert result["redacted"] is True
        # audit doc must not echo a raw bank account number
        assert "1234567" not in str(result["audit_document"])
