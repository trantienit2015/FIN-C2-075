# 03 — Test Specification — FIN-C2-075

## Coverage map

| Test file | Scope |
|---|---|
| `tests/unit/test_invoice_ingest_node.py` | PDF success, empty error, non-PDF rejected |
| `tests/unit/test_three_way_match_node.py` | matched / amount-discrepancy / invalid-QII + ap_service (tier routing, QII validation, bank redaction) |
| `tests/unit/test_approval_route_node.py` | **PB-7 (node level, portable)**: `interrupt()` is invoked with the approval draft (D6); tier routing; decision propagation |
| `tests/unit/test_payment_and_accounting_nodes.py` | approved schedules / rejected+pending do not / audit redacts bank details |
| `tests/integration/test_graph.py` | **PB-7** interrupt -> AWAITING_HUMAN; resume(approved) -> SUCCESS; empty input no crash |
| `tests/proof_of_boundary/test_import_isolation.py` | PB-4: no Level-0 imports under src/ |
| `tests/proof_of_boundary/test_state_safety.py` | PB-2/PB-5: no credential fields / Pydantic / InvocationContext in State |

## TC / PB mapping

| TC/PB | Covered by |
|---|---|
| TC-01 State contract | test_state_safety |
| TC-02 reject path | InvoiceIngest non-PDF / empty |
| TC-03 no credential in src | gate-credential-scan (CI); bank-account redaction |
| TC-04 ctx via configurable | integration `ctx=` + `input_context=` |
| TC-05 audit logging | emit_trace_event in OCR/match/approval/payment/posting |
| TC-06/07 gates non-bypassable | FunctionNode @final inherited; BaseNode approval node uses execute() only |
| TC-08 required_trust_level | agent.yaml VERIFIED_EXTERNAL |
| **PB-7 HITL interrupt** | Node level (portable): `test_approval_route_node.py` asserts `interrupt()` is called with the draft (D6). Graph level: `test_invoke_pauses_for_human_approval` asserts AWAITING_HUMAN where the langgraph build bubbles the nested interrupt, plus a build-independent payment-safety invariant (`test_payment_never_scheduled_without_approval`: no completed payment output on the pre-approval invoke). `test_resume_approved_schedules_and_audits` verifies resume->SUCCESS on bubbling builds. |

## Run

```bash
PYTHONUTF8=1 python -m pytest tests/ -v
```
