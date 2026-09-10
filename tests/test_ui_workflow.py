"""
Automated end-to-end integration tests for CKC UI workflows.
Validates graph elements, links consistency, search payloads, trace flows, and UI contracts.
"""

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from code_chain.ui.server import app


class TestUIWorkflowIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.test_repo = str(
            Path(__file__).resolve().parent.parent / "examples" / "python-auth-service"
        )
        cls.ckc_repo = str(Path(__file__).resolve().parent.parent)

    def test_static_assets_contract(self):
        """Verify HTML serves all expected production UI components."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text
        # Required containers and shims
        self.assertIn("search-mode-btn", html)
        self.assertIn("search-results-dropdown", html)
        self.assertIn("trace-mode-banner", html)
        self.assertIn("toast-container", html)
        self.assertIn("graph-3d", html)
        self.assertIn("cy", html)  # 2D shim preserved for backward compatibility
        self.assertIn("copy-source-path-btn", html)

    def test_graph_elements_and_link_structure(self):
        """Verify that /api/graph returns well-formed nodes and valid link endpoints."""
        res = self.client.get(f"/api/graph?project={self.test_repo}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("elements", data)
        nodes = data["elements"]["nodes"]
        edges = data["elements"]["edges"]

        self.assertGreater(len(nodes), 0)
        self.assertGreater(len(edges), 0)

        node_ids = {n["data"]["id"] for n in nodes}
        for edge in edges:
            ed = edge["data"]
            self.assertIn("source", ed)
            self.assertIn("target", ed)
            self.assertIsInstance(ed["source"], str)
            self.assertIsInstance(ed["target"], str)
            # Source and target should be valid node IDs
            self.assertIn(ed["source"], node_ids)
            self.assertIn(ed["target"], node_ids)

    def test_status_response_schema(self):
        """Verify /api/status provides complete telemetry."""
        res = self.client.get(f"/api/status?project={self.test_repo}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("llm", data)
        self.assertIn("local_docs_count", data)
        self.assertIn("summary", data)

    def test_query_workflow(self):
        """Verify /api/query runs and returns architectural context."""
        payload = {
            "project_path": self.test_repo,
            "query": "How is authentication handled?",
            "use_llm": False,
        }
        res = self.client.post("/api/query", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("synthesized_context", data)
        self.assertTrue(len(data["synthesized_context"]) > 0)

    def test_impact_workflow(self):
        """Verify /api/impact returns risk level and blast radius hierarchy."""
        payload = {"project_path": self.test_repo, "symbol": "login", "use_llm": False}
        res = self.client.post("/api/impact", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["target_symbol"], "login")
        self.assertIn("blast_radius_count", data)
        self.assertIn("call_hierarchy", data)
        self.assertIn("synthesized_report", data)

    def test_trace_workflow(self):
        """Verify /api/trace executes pathfinding and returns markdown flow."""
        payload = {
            "project_path": self.test_repo,
            "from_symbol": "handle_login_request",
            "to_symbol": "verify_password",
            "use_llm": False,
        }
        res = self.client.post("/api/trace", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["path_found"])
        self.assertGreaterEqual(data["path_length"], 2)
        self.assertIn("steps", data)

    def test_byok_and_navigation_static_contracts(self):
        """Verify HTML and CSS contain BYOK, Recent Projects, and Dialog recovery contracts."""
        res_html = self.client.get("/")
        self.assertEqual(res_html.status_code, 200)
        html = res_html.text
        self.assertIn("byok-dialog", html)
        self.assertIn("recent-projects-list", html)
        self.assertIn("header-ai-btn", html)
        self.assertIn("llm-dep-warning", html)
        self.assertIn("engine-core-banner", html)
        self.assertIn("browser-quick-home", html)
        self.assertIn("browser-quick-root", html)
        self.assertIn("provider-pill-grid", html)

        res_css = self.client.get("/styles.css")
        self.assertEqual(res_css.status_code, 200)
        css = res_css.text
        self.assertIn(".folder-browser-dialog:not([open])", css)
        self.assertIn(".byok-dialog:not([open])", css)
        self.assertIn("display: none !important", css)

    def test_browse_api_indexed_flag(self):
        """Verify /api/browse returns is_indexed flag for subdirectories."""
        res = self.client.post("/api/browse", json={"path": self.ckc_repo})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("entries", data)
        self.assertIn("current", data)
        for item in data["entries"]:
            self.assertIn("is_indexed", item)
            self.assertIsInstance(item["is_indexed"], bool)

    def test_graph_workflows_and_indexing_dashboard_contracts(self):
        """Verify HTML and CSS contain contracts for layout modes, filters, and dashboard."""
        res_html = self.client.get("/")
        self.assertEqual(res_html.status_code, 200)
        html = res_html.text

        # Layout modes & fallback contracts
        self.assertIn("graph-layout-modes", html)
        self.assertIn("mode-3d-btn", html)
        self.assertIn("mode-2d-btn", html)
        self.assertIn("mode-dag-btn", html)

        # Noise reduction & relationship flow filters
        self.assertIn("filter-hide-vendor", html)
        self.assertIn("filter-rel-calls", html)
        self.assertIn("filter-rel-imports", html)
        self.assertIn("filter-rel-defines", html)
        self.assertIn("filter-rel-inherits", html)

        # Context panel metrics, quick actions & source preview drawer
        self.assertIn("node-in-degree", html)
        self.assertIn("node-out-degree", html)
        self.assertIn("action-focus-node", html)
        self.assertIn("action-trace-from", html)
        self.assertIn("action-impact-from", html)
        self.assertIn("btn-preview-source", html)
        self.assertIn("source-preview-container", html)
        self.assertIn("source-preview-code", html)

        # Multi-stage indexing progress dashboard & heartbeat
        self.assertIn("indexing-progress-dashboard", html)
        self.assertIn("progress-current-tier-title", html)
        self.assertIn("progress-elapsed-timer", html)
        self.assertIn("progress-heartbeat-badge", html)
        self.assertIn("indexing-progress-bar", html)
        self.assertIn("stepper-tier-1", html)
        self.assertIn("stepper-tier-2", html)
        self.assertIn("stepper-tier-3", html)

        res_css = self.client.get("/styles.css")
        self.assertEqual(res_css.status_code, 200)
        css = res_css.text
        self.assertIn(".indexing-progress-dashboard", css)
        self.assertIn(".layout-mode-btn", css)
        self.assertIn(".source-preview-container", css)
        self.assertIn(".source-line.highlight", css)

    def test_source_preview_workflow(self):
        """Verify /api/source retrieves snippet around target line."""
        res = self.client.get(
            f"/api/source?project={self.test_repo}&file=src/api.py&line=5&window=10"
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["file"], "src/api.py")
        self.assertEqual(data["language"], "python")
        self.assertEqual(data["highlight_line"], 5)
        self.assertIsInstance(data["lines"], list)
        self.assertTrue(len(data["lines"]) > 0)
        self.assertEqual(data["lines"][0]["line_num"], data["start_line"])


if __name__ == "__main__":
    unittest.main()
