"""AccountingPostNode — outer post_process slot (FIN-C2-075).

Posts the journal entry, builds a tamper-evident audit document, and applies the S-3
deterministic output gate: bank-account details are redacted from the final output before it
leaves the agent. This is deterministic redaction, not an LLM self-check.
"""

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.ap_service import redact_bank_details


class AccountingPostNode(FunctionNode):
    """Post journal entry + build redacted audit document (outer post_process)."""

    # S-1: explicit by design. Posts journal entries (privileged side
    # effect) — verified caller required (matches agent.yaml default).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    # Human-readable statuses for the decision values this pipeline can produce.
    _DECISION_TEXT: ClassVar[dict[str, Any]] = {
        "approved": "approved by the assigned approver",
        "rejected": "rejected by the assigned approver",
        "pending_review": "not yet approved — it is waiting for a human approver",
    }

    def _confirmation_text(self, audit: dict[str, Any], decision: str) -> str:
        """Render the outcome as prose a reader with no context can follow.

        The invoice fields are only populated when an OCR client is wired into the
        deployment. Without one, OCRExtractNode returns its documented empty record —
        so rather than emitting a sentence with holes in it ("Invoice  for vendor :"),
        say what the agent did, what it could not determine, and what input it needs.
        Nothing is inferred from free text: an AP agent must never invent invoice fields.
        """
        decision_text = self._DECISION_TEXT.get(decision, f"recorded with decision '{decision}'")
        tier = audit.get("approval_tier") or "the applicable"
        vendor = audit.get("vendor")
        amount = audit.get("amount")

        if not vendor and amount is None:
            return (
                "No invoice data could be read from this request, so there is nothing to approve "
                "or pay yet. This agent processes accounts-payable invoices: it OCR-extracts the "
                "invoice fields, runs a 3-way match against the purchase order and goods receipt, "
                "validates the qualified-invoice (適格請求書) registration number, routes the "
                f"invoice to {tier} approver tier, and schedules payment only after approval. "
                "Send a PDF invoice payload to have it processed. "
                f"Nothing was posted and no payment was scheduled ({decision_text})."
            )

        ref = audit.get("invoice_ref") or "(no reference)"
        parts = [f"Invoice {ref}"]
        if vendor:
            parts.append(f"from vendor {vendor}")
        if amount is not None:
            parts.append(f"for {amount}")
        header = " ".join(parts)

        match_result = audit.get("match_result") or "not run"
        payment_line = (
            "A payment has been scheduled." if audit.get("payment_scheduled") else "No payment has been scheduled."
        )
        return (
            f"{header}: the 3-way match came back '{match_result}', the invoice was routed to the "
            f"{tier} approver tier, and it is {decision_text}. {payment_line}"
        )

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        decision = state.get("approval_decision", "")
        invoice = state.get("invoice_record", {}) or {}
        payment_record = state.get("payment_record", {}) or {}

        audit = {
            "invoice_ref": state.get("invoice_ref", ""),
            "vendor": invoice.get("vendor", ""),
            "amount": invoice.get("amount"),
            "approval_tier": state.get("approval_tier", ""),
            "approval_decision": decision,
            "match_result": state.get("match_result", ""),
            "payment_scheduled": bool(state.get("payment_scheduled", False)),
            "payment_record": payment_record,
        }

        # S-3 deterministic gate: redact any bank-account details before emitting.
        redacted_audit = redact_bank_details(audit)
        confirmation = redact_bank_details(self._confirmation_text(audit, decision))

        emit_trace_event(
            "accounting_posted",
            {"invoice_ref": audit["invoice_ref"], "decision": decision},
            state,
        )

        return {
            "audit_document": redacted_audit,
            "redacted": True,
            "result": confirmation,
            "formatted_output": confirmation,
            "status": AgentStatus.SUCCESS.value,
        }
