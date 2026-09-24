# FIN-C2-075 — Unit Tests: InvoiceIngestNode (outer pre_process)

import json

from framework.schemas.agent_status import AgentStatus
from src.nodes.invoice_ingest_node import InvoiceIngestNode


class TestInvoiceIngestNode:
    def setup_method(self):
        self.node = InvoiceIngestNode()

    def _state(self, ui, ctx=None):
        return {"user_input": ui, "input_context": ctx or {}, "node_history": [], "error_log": [], "execution_time": {}}

    def test_success_pdf(self):
        result = self.node.execute(self._state("<pdf bytes>", {"invoice_ref": "INV-1", "file_type": "pdf"}))
        assert result["status"] == AgentStatus.SUCCESS
        assert result["invoice_ref"] == "INV-1"
        payload = json.loads(result["validated_input"])
        assert payload["invoice_payload"] == "<pdf bytes>"

    def test_empty_input_error(self):
        result = self.node.execute(self._state("   "))
        assert result["status"] == AgentStatus.ERROR

    def test_non_pdf_rejected(self):
        result = self.node.execute(self._state("data", {"file_type": "docx"}))
        assert result["status"] == AgentStatus.ERROR
        assert "PDF only" in result["error_log"][0]


class TestOCRExtractNodeError:
    def test_ocr_failure_returns_error(self):
        import json
        from src.nodes.ocr_extract_node import OCRExtractNode

        class BoomOCR:
            def extract(self, payload):
                raise RuntimeError("OCR service down")

        node = OCRExtractNode(ocr=BoomOCR())
        state = {"user_input": json.dumps({"invoice_payload": "<pdf>", "invoice_ref": "INV"}),
                 "node_history": [], "error_log": [], "execution_time": {}}
        result = node.execute(state)
        assert result["status"] == AgentStatus.ERROR
        assert "OCR extraction failed" in result["error_log"][0]
