"""InvoiceIngestNode — outer pre_process slot (FIN-C2-075).

S-1 gate: validate file type (PDF only) + size limit, queue the invoice, and serialize the
payload into `validated_input` (JSON string) for the inner Cat 2 subgraph.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

_ALLOWED_TYPES = {"pdf"}
_MAX_LEN = 500_000


class InvoiceIngestNode(FunctionNode):
    """Validate + queue the incoming invoice (outer pre_process)."""

    # S-1: explicit by design. Invoice payloads are financial data —
    # standard business operation, verified caller required (matches agent.yaml default).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")
        if not user_input or not user_input.strip():
            emit_trace_event("invoice_ingest_rejected", {"reason": "empty_payload"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["InvoiceIngestNode: user_input (invoice payload) is empty"],
            }
        if len(user_input) > _MAX_LEN:
            emit_trace_event("invoice_ingest_rejected", {"reason": "payload_too_large"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["InvoiceIngestNode: invoice payload exceeds maximum size"],
            }

        ctx = state.get("input_context", {}) or {}
        file_type = (ctx.get("file_type", "pdf") or "pdf").lower()
        invoice_ref = ctx.get("invoice_ref", "")

        if file_type not in _ALLOWED_TYPES:
            emit_trace_event(
                "invoice_ingest_rejected", {"reason": "unsupported_file_type", "file_type": file_type}, state
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [f"InvoiceIngestNode: unsupported file type '{file_type}' (PDF only)"],
            }

        payload = {"invoice_payload": user_input.strip(), "invoice_ref": invoice_ref, "file_type": file_type}
        emit_trace_event("invoice_ingested", {"invoice_ref": invoice_ref, "file_type": file_type}, state)
        return {
            "invoice_ref": invoice_ref,
            "file_type": file_type,
            "validated_input": json.dumps(payload, ensure_ascii=False),
            "status": AgentStatus.SUCCESS.value,
        }
