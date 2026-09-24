"""AgentCore Platform v1.0 — FIN-C2-075 State schema."""

# ADR-005: flat TypedDict only. No Pydantic / InvocationContext / credentials / bank account
# numbers persisted in State. HITL fields (hitl_feedback, hitl_draft, hitl_status, hitl_count,
# hitl_allowed, hitl_metadata, subgraph_thread_id) are inherited from AgentState — do NOT
# redeclare them.

from typing import Any
from framework.schemas.agent_state import AgentState


class State(AgentState):
    """Accounts-payable approval pipeline state.

    Shared + HITL fields inherited from AgentState. Agent-specific fields only below.
    """

    # InvoiceIngestNode (outer pre_process) outputs
    invoice_ref: str
    file_type: str

    # OCRExtractNode (inner) output — extracted invoice record (no bank-account number in State)
    invoice_record: dict[str, Any]  # {"vendor","amount","po_number","due_date","qii_registration"}

    # ThreeWayMatchNode (inner) outputs
    match_result: str  # "matched" | "discrepancy"
    discrepancies: list[Any]  # list of {"field","invoice","po_or_gr"}

    # ApprovalRouteNode (inner, HITL) outputs
    approval_tier: str  # "department_head" | "finance_manager" | "cfo"
    approval_decision: str  # "approved" | "rejected" | "" (pending)

    # PaymentScheduleNode (inner) outputs
    payment_scheduled: bool
    payment_record: dict[str, Any]  # {"scheduled_date","amount"} — no bank-account number

    # AccountingPostNode (outer post_process) outputs
    audit_document: dict[str, Any]
    redacted: bool
