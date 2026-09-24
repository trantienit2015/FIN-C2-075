# 02 — Design Specification — FIN-C2-075

## Position in AgentCore Architecture

- **Agent Class**: `AccountsPayableApprovalGraph` (`src/graph/graph.py`)
- **L1 Base type**: `AgentBaseGraph` (L1 direct) — no L2 inheritance.
- **Inheritance**: `AgentBaseGraph` (L1 direct).
- **Category**: Cat 2 — canonical pattern: outer `AgentBaseGraph` + `GraphNode` (`main` slot)
  + inner `BaseGraph` domain subgraph.
- **Pattern**: Orchestration pipeline with HITL (`hitl.enabled: true`).

## Graph topology

```
OUTER (AccountsPayableApprovalGraph : AgentBaseGraph, memory_enabled + hitl.enabled)
  initialize -> pre_process (InvoiceIngestNode)
            -> main (APPipelineGraphNode : GraphNode, propagate_hitl=True)
            -> post_process (AccountingPostNode)
            -> finalize

INNER (APWorkflowGraph : BaseGraph)
  START -> ocr_extract -> three_way_match -> approval_route (interrupt) -> payment_schedule -> END
```

## HITL design (D6)

- The approval node `ApprovalRouteNode` calls `interrupt({...})` inside `execute()` (D6 backbone
  pattern); the framework owns pause/resume, the node owns the trigger.
- `payment_auto_schedule: false` (default) means every invoice requires a human approval cycle
  before `PaymentScheduleNode` schedules anything.
- Cross-Cat-2-boundary HITL: `APPipelineGraphNode` sets `propagate_hitl = True`, compiles the
  inner subgraph with a cached checkpointer, forwards `memory_enabled` to the inner config, and
  overrides `_handle_call_error` to re-raise `GraphBubbleUp` (the inner interrupt) so it surfaces
  as `AWAITING_HUMAN` rather than being wrapped as a SubgraphError.
- `hitl_draft` stores the pre-interrupt approval draft (idempotency on resume); only the 7
  permitted HITL state fields are used (inherited from AgentState — not redeclared).

## Node responsibilities

| Slot | Node | Responsibility |
|---|---|---|
| outer pre_process | `InvoiceIngestNode` | S-1 file-type (PDF only) + size validation; serialize `validated_input`. |
| inner step 1 | `OCRExtractNode` | OCR-extract vendor / amount / PO / due / qualified-invoice registration number. |
| inner step 2 | `ThreeWayMatchNode` | Match invoice / PO / goods-receipt; rule-based discrepancy flags; qualified-invoice format validation. |
| inner step 3 | `ApprovalRouteNode` | Tier by amount; **D6 `interrupt()`** pause for human approval. |
| inner step 4 | `PaymentScheduleNode` | Schedule bank payment ONLY when approved; auto-schedule OFF default. |
| outer post_process | `AccountingPostNode` | Post journal entry; build audit doc; **S-3** redact bank-account details before emitting. |

## State schema (`src/schemas/state.py`)

`class State(AgentState)` adds flat JSON-serializable fields: `invoice_ref`, `file_type`,
`invoice_record`, `match_result`, `discrepancies`, `approval_tier`, `approval_decision`,
`payment_scheduled`, `payment_record`, `audit_document`, `redacted`. HITL fields inherited (not
redeclared). No bank-account number, Pydantic, InvocationContext, or credential in State.

## Security (5-layer)

- **S-1**: agent default `required_trust_level: VERIFIED_EXTERNAL`.
- **S-2**: framework input gate; `InvoiceIngestNode` rejects non-PDF / empty / oversized.
- **S-3**: `AccountingPostNode` deterministic bank-account redaction before output. Secrets
  (LLM/ERP/bank) via entry-point `bound_secrets`/`secrets_factory`/`provision_secrets`; never
  `os.environ`; `requires.secrets` in `agent.yaml`.
- **S-4**: `emit_trace_event()` on OCR / match / approval / payment / posting side-effects.
- **S-5**: framework credential scan; flat-TypedDict State.

## Config (`config/agent.yaml` `agent.config`)

`max_retry`, `timeout_seconds`, `payment_auto_schedule: false`, `approval_tiers`,
`memory_enabled: true`, `hitl: {enabled: true, max_hitl: 8}`.
