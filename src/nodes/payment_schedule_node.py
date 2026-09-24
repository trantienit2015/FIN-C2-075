"""PaymentScheduleNode — inner subgraph step 4 (FIN-C2-075).

Schedules the bank payment ONLY when the invoice was approved by the human (HITL) and
`payment_auto_schedule` is not forcing an unsafe auto-pay. The bank client is injected via the
constructor (S-3: no os.environ, no secret in state). No bank-account number is stored in State.
"""

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class PaymentScheduleNode(FunctionNode):
    """Schedule bank payment after human approval (auto-schedule OFF by default)."""

    # S-1: explicit by design. Schedules bank payments (privileged side
    # effect) — verified caller required (matches agent.yaml default).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, bank: Any = None, auto_schedule: bool = False):
        super().__init__()
        self._bank = bank
        self._auto_schedule = bool(auto_schedule)

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        decision = state.get("approval_decision", "")
        invoice = state.get("invoice_record", {}) or {}
        amount = invoice.get("amount")

        if decision != "approved":
            emit_trace_event("payment_skipped", {"reason": "not approved", "decision": decision}, state)
            return {
                "payment_scheduled": False,
                "payment_record": {},
                "status": AgentStatus.SUCCESS.value,
            }

        if self._bank is None:
            # No bank client wired (unit test) — record scheduling intent without a real call.
            record = {"scheduled_date": "pending", "amount": amount}
        else:
            # Bank client returns a record WITHOUT a raw account number in State.
            record = self._bank.schedule_payment(invoice)

        emit_trace_event("payment_scheduled", {"amount": amount}, state)

        return {
            "payment_scheduled": True,
            "payment_record": {"scheduled_date": record.get("scheduled_date", "pending"), "amount": amount},
            "status": AgentStatus.SUCCESS.value,
        }
