"""ApprovalRouteNode — inner subgraph step 3 (FIN-C2-075), HITL D6 pattern.

Routes the invoice to the correct approver tier by amount, then calls `interrupt()` to pause
for human approval (D6 backbone pattern). The framework owns the pause/resume mechanism; this
node owns the trigger condition. `hitl_draft` guards against LLM/compute re-execution on
resume; on resume `hitl_feedback` carries the human decision.

Because payment_auto_schedule is OFF by default, every invoice requires a human approval
cycle before payment scheduling.
"""

from __future__ import annotations

from typing import Any
from langgraph.types import interrupt

from framework.nodes.base_node import BaseNode
from framework.schemas.agent_status import AgentStatus
from shared.utils.audit_logger import emit_trace_event

from src.services.ap_service import approval_tier_for


class ApprovalRouteNode(BaseNode):
    """Tiered HITL approval gate (D6 interrupt)."""

    def __init__(self, approval_tiers: dict[str, Any] | None = None, confirmation_required: bool = True):
        super().__init__()
        self._tiers = approval_tiers or {}
        # Deployment policy: whether this deployment can actually deliver interrupt feedback.
        # Defaults to True so the approval gate is kept unless a deployment opts out
        # explicitly via config/config.yaml (hitl.confirmation_required).
        self._confirmation_required = bool(confirmation_required)

    # BaseNode (non-FunctionNode) must override the @abstractmethod security gates. This node's
    # data is gated upstream (OCR/match validate the invoice) and downstream (AccountingPost S-3
    # redaction), so these are no-op passthroughs — the deliberate GraphNode/RemoteAgentNode
    # pattern from the framework (S-2/S-3). Signature: (state, config=None) -> dict.
    def _security_gate_input(self, state: dict[str, Any], config: "dict[str, Any] | None" = None) -> dict[str, Any]:
        return state

    def _security_gate_output(self, state: dict[str, Any], config: "dict[str, Any] | None" = None) -> dict[str, Any]:
        return state

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        invoice = state.get("invoice_record", {}) or {}
        amount = invoice.get("amount")
        tier = approval_tier_for(amount, self._tiers)

        # Idempotency guard: if we already drafted the approval request, reuse it on resume.
        draft = state.get("hitl_draft") or {
            "vendor": invoice.get("vendor", ""),
            "amount": amount,
            "po_number": invoice.get("po_number", ""),
            "match_result": state.get("match_result", ""),
            "discrepancies": state.get("discrepancies", []),
            "approval_tier": tier,
        }

        emit_trace_event("approval_requested", {"approval_tier": tier, "amount": amount}, state)

        # Two INDEPENDENT reasons to skip the blocking wait — neither masks the other.
        #
        # 1. hitl_allowed=False (framework HITL contract, review criterion #12): the caller
        #    is an automated pipeline (GraphNode/RemoteAgentNode composition) with no human
        #    reviewer. This
        #    field is owned by the gateway/parent graph — this node only ever READS it.
        # 2. confirmation_required=False: a deployment policy from config/config.yaml, set
        #    when the runtime has no HITL resume channel at all (the one-shot Marketplace
        #    runner, where AWAITING_HUMAN is reported as a plain failure and the approval is
        #    therefore unreachable by any human).
        #
        # Both land on the SAME conservative path: decision "pending_review", never
        # "approved". PaymentScheduleNode pays only on "approved", so skipping the wait
        # never schedules a payment — the invoice leaves the agent explicitly flagged as
        # still needing human review.
        if not state.get("hitl_allowed", True) or not self._confirmation_required:
            reason = "hitl_allowed=False" if not state.get("hitl_allowed", True) else "confirmation_required=False"
            emit_trace_event("approval_auto_skipped", {"approval_tier": tier, "reason": reason}, state)
            return {
                "approval_tier": tier,
                "approval_decision": "pending_review",
                "hitl_draft": draft,
                "status": AgentStatus.SUCCESS.value,
            }

        # D6 interrupt: pause for human approval. On resume, `feedback` is the human response.
        feedback = interrupt({"draft": draft, "reason": f"approval required at tier '{tier}'"})

        decision = "approved"
        if isinstance(feedback, dict):
            decision = feedback.get("decision", "approved")
        elif isinstance(feedback, str):
            decision = feedback

        emit_trace_event("approval_decided", {"approval_tier": tier, "decision": decision}, state)

        return {
            "approval_tier": tier,
            "approval_decision": decision,
            "hitl_draft": draft,
            "hitl_feedback": feedback,
            "status": AgentStatus.SUCCESS.value,
        }
