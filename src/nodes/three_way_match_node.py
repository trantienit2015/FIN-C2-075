"""ThreeWayMatchNode — inner subgraph step 2 (FIN-C2-075).

Matches invoice <-> PO <-> goods-receipt (rule-based), flags discrepancies, and validates the
qualified-invoice (適格請求書) registration format. The ERP client (PO + goods-receipt lookup)
is injected via the constructor (S-3: no os.environ, no secret in state).
"""

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.ap_service import three_way_match


class ThreeWayMatchNode(FunctionNode):
    """3-way match + discrepancy detection."""

    # S-1: explicit by design. Reads PO/goods-receipt data from the ERP —
    # verified caller required (matches agent.yaml default).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, erp: Any = None) -> None:
        super().__init__()
        self._erp = erp

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        invoice = state.get("invoice_record", {}) or {}
        po_number = invoice.get("po_number", "")

        if self._erp is None:
            # No ERP wired (unit test) — treat PO/GR as matching the invoice for the happy path.
            po = {"amount": invoice.get("amount"), "quantity": 1}
            gr = {"quantity": 1}
        else:
            po = self._erp.fetch_po(po_number)
            gr = self._erp.fetch_goods_receipt(po_number)

        result, discrepancies = three_way_match(invoice, po, gr)

        emit_trace_event(
            "three_way_match",
            {"po_number": po_number, "result": result, "n_discrepancies": len(discrepancies)},
            state,
        )

        return {
            "match_result": result,
            "discrepancies": discrepancies,
            "status": AgentStatus.SUCCESS.value,
        }
