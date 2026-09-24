"""OCRExtractNode — inner subgraph step 1 (FIN-C2-075).

Parses the JSON payload from the outer pre_process, then OCR-extracts the structured invoice
record (vendor, amount, PO number, due date, qualified-invoice registration number). The OCR
client is injected via the constructor (S-3: no os.environ, no secret in state).
"""

from __future__ import annotations

import json
from typing import Any, ClassVar, cast

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class OCRExtractNode(FunctionNode):
    """OCR-extract structured invoice fields."""

    # S-1: explicit by design. Processes financial invoice content —
    # verified caller required (matches agent.yaml default).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, ocr: Any = None) -> None:
        super().__init__()
        self._ocr = ocr

    def _parse(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        try:
            return cast(dict[str, Any], json.loads(raw) if raw else {})
        except (ValueError, TypeError):
            return {}

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        payload = self._parse(state.get("user_input", ""))
        invoice_payload = payload.get("invoice_payload", "")
        invoice_ref = payload.get("invoice_ref", "")

        if not invoice_payload:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["OCRExtractNode: empty invoice payload in inner input"],
            }

        if self._ocr is None:
            # No OCR wired (unit test) — deterministic minimal record, never silent.
            record = {"vendor": "", "amount": None, "po_number": "", "due_date": "", "qii_registration": ""}
        else:
            try:
                record = self._ocr.extract(invoice_payload)
            except Exception as exc:
                emit_trace_event(
                    "ocr_extract_failed",
                    {
                        "invoice_ref": invoice_ref,
                        "error": str(exc),
                        "correlation_id": state.get("correlation_id"),
                        "trace_id": state.get("trace_id"),
                    },
                    state,
                )
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": [f"OCRExtractNode: OCR extraction failed: {exc}"],
                }

        emit_trace_event(
            "invoice_ocr_extracted",
            {
                "invoice_ref": invoice_ref,
                "correlation_id": state.get("correlation_id"),
                "trace_id": state.get("trace_id"),
            },
            state,
        )

        return {
            "invoice_ref": invoice_ref,
            "invoice_record": record,
            "status": AgentStatus.SUCCESS.value,
        }
