"""Deterministic accounts-payable helpers for FIN-C2-075.

Pure functions — no agenticstar imports, no side effects. Covers the 3-way match,
amount-tier approval routing, qualified-invoice (適格請求書) format validation, and S-3
bank-account redaction. No LLM self-checks; all rules are deterministic.
"""

from __future__ import annotations

from typing import Any
import re

# 適格請求書 registered-business number: 'T' + 13 digits (国税庁 登録番号 format).
_QII_RE = re.compile(r"^T\d{13}$")
# Bank account number patterns to redact from any output.
_BANK_ACCT_RE = re.compile(r"\b\d{7,8}\b")


def validate_qii(registration: str) -> bool:
    """True if the qualified-invoice registration number matches the 国税庁 'T+13 digits' format."""
    return bool(_QII_RE.match((registration or "").strip()))


def three_way_match(
    invoice: dict[str, Any], po: dict[str, Any], goods_receipt: dict[str, Any]
) -> tuple[str, list[Any]]:
    """Match invoice <-> PO <-> goods receipt. Returns (result, discrepancies).

    result is "matched" when no discrepancy, else "discrepancy".
    """
    discrepancies: list[Any] = []
    # amount: invoice vs PO
    inv_amt = invoice.get("amount")
    po_amt = (po or {}).get("amount")
    if inv_amt is not None and po_amt is not None and inv_amt != po_amt:
        discrepancies.append({"field": "amount", "invoice": inv_amt, "po_or_gr": po_amt})
    # quantity: PO vs goods receipt
    po_qty = (po or {}).get("quantity")
    gr_qty = (goods_receipt or {}).get("quantity")
    if po_qty is not None and gr_qty is not None and po_qty != gr_qty:
        discrepancies.append({"field": "quantity", "invoice": po_qty, "po_or_gr": gr_qty})
    # qualified-invoice validity
    if not validate_qii(invoice.get("qii_registration", "")):
        discrepancies.append(
            {"field": "qii_registration", "invoice": invoice.get("qii_registration"), "po_or_gr": "invalid format"}
        )
    return ("matched" if not discrepancies else "discrepancy", discrepancies)


def approval_tier_for(amount: Any, tiers: dict[str, Any]) -> str:
    """Return the required approver tier for an invoice amount.

    tiers e.g. {"department_head": 100000, "finance_manager": 1000000, "cfo": None}.
    Amount <= department_head limit -> department_head; <= finance_manager -> finance_manager;
    otherwise -> cfo.
    """
    if amount is None:
        return "cfo"
    dh = tiers.get("department_head", 100000)
    fm = tiers.get("finance_manager", 1000000)
    if amount <= dh:
        return "department_head"
    if amount <= fm:
        return "finance_manager"
    return "cfo"


def redact_bank_details(obj: Any) -> Any:
    """Recursively redact bank-account-number-shaped digit runs from strings in obj.

    Used by the S-3 output gate so no bank-account number leaves the agent.
    """
    if isinstance(obj, str):
        return _BANK_ACCT_RE.sub("[REDACTED]", obj)
    if isinstance(obj, dict):
        return {
            k: ("[REDACTED]" if "account" in k.lower() and "name" not in k.lower() else redact_bank_details(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact_bank_details(v) for v in obj]
    return obj
