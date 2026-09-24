# PB-6 (GraphNode boundary supplement): the scaffold PB-6 stub
# (test_pb_invoke_order.py) only discovers concrete BaseNode subclasses under
# src/nodes/. APPipelineGraphNode lives at the `main` slot by design (Cat 2
# canonical layout, keeps the outer main-slot wrapper out of the PB-6
# self-discovery walk so a single-node probe doesn't drag the whole inner
# subgraph along). That placement does NOT exempt it from boundary testing:
# it is the first node in the outer backbone to receive caller input, so its
# S-1 trust gate and its input/output field mapping are a real security
# boundary that PB-6 never touches. This file closes that gap.

import pytest

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.ap_pipeline_graph_node import APPipelineGraphNode


def _make_node() -> APPipelineGraphNode:
    return APPipelineGraphNode(ocr=None, erp=None, bank=None, approval_tiers={}, auto_schedule=False)


class TestGraphNodeTrustGate:
    """S-1: required_trust_level must be declared and enforced before execute()/get_subgraph() runs."""

    def test_required_trust_level_declared(self):
        assert APPipelineGraphNode.required_trust_level == TrustLevel.VERIFIED_EXTERNAL

    def test_insufficient_trust_denied_before_subgraph_dispatch(self):
        # BaseNode.__call__() denies via a status=error result (not an exception -
        # matches the actual S-1 gate implementation verified against
        # framework/nodes/base_node.py, see PB-6 test_pb_invoke_order.py convention).
        node = _make_node()
        state = {
            "caller_trust_level": TrustLevel.ANONYMOUS.value,
            "correlation_id": "pb-graphnode-boundary-test",
            "validated_input": '{"invoice_payload": "test", "invoice_ref": "INV-1", "file_type": "pdf"}',
        }
        result = node(state)
        assert result["status"] == AgentStatus.ERROR.value
        assert "trust gate" in result["error_log"][0].lower()
        # get_subgraph() must never be invoked when the trust gate denies the call.
        assert node._subgraph is None


class TestGraphNodeBoundaryMapping:
    """Criterion #9: extract_input/merge_output must map fields explicitly, no raw pass-through."""

    def test_extract_input_only_takes_contracted_field(self):
        node = _make_node()
        state = {"validated_input": "validated-payload", "user_input": "raw", "session_id": "s1"}
        assert node.extract_input(state) == "validated-payload"

    def test_extract_input_falls_back_to_user_input(self):
        node = _make_node()
        state = {"user_input": "raw-payload"}
        assert node.extract_input(state) == "raw-payload"

    def test_merge_output_maps_explicit_fields_only(self):
        node = _make_node()
        sub_result = {
            "invoice_record": {"vendor": "Acme"},
            "match_result": "matched",
            "discrepancies": [],
            "approval_tier": "department_head",
            "approval_decision": "approved",
            "payment_scheduled": True,
            "payment_record": {"scheduled_date": "2026-08-01", "amount": 1000},
            "status": "success",
            "internal_subgraph_debug_field": "must-not-leak",
        }
        merged = node.merge_output({"correlation_id": "c1", "invoice_ref": "INV-1"}, sub_result)

        assert merged == {
            "invoice_record": {"vendor": "Acme"},
            "match_result": "matched",
            "discrepancies": [],
            "approval_tier": "department_head",
            "approval_decision": "approved",
            "payment_scheduled": True,
            "payment_record": {"scheduled_date": "2026-08-01", "amount": 1000},
            "status": "success",
        }
        assert "internal_subgraph_debug_field" not in merged


class TestGraphNodeDelegatesGatingToInner:
    """Delegation-with-intent: GraphNode.__call__ intentionally skips S-2/S-4/S-3
    (see class docstring in src/nodes/ap_pipeline_graph_node.py) because the inner
    subgraph's entry node already runs the standard BaseNode security pipeline."""

    def test_inner_entry_node_has_security_gates(self):
        from framework.nodes.function_node import FunctionNode
        from src.nodes.ocr_extract_node import OCRExtractNode

        assert issubclass(OCRExtractNode, FunctionNode)
        if not hasattr(FunctionNode, "_security_gate_input"):
            # Legacy local wheel (1.0.0rc1) does not define the @final S-2/S-3 hooks
            # yet; the CI wheel (agenticstar-agentcore==1.0.0) does, and is the gate
            # of record (see tests/proof_of_boundary/test_pb_invoke_order.py).
            pytest.skip("framework wheel lacks _security_gate_input/output (rc1) — runs on CI wheel 1.0.0")
        assert hasattr(OCRExtractNode, "_security_gate_input")
        assert hasattr(OCRExtractNode, "_security_gate_output")
