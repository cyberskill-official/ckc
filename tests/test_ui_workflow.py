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
        cls.test_repo = str(Path(__file__).resolve().parent.parent / "examples" / "python-auth-service")
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
            "use_llm": False
        }
        res = self.client.post("/api/query", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("synthesized_context", data)
        self.assertTrue(len(data["synthesized_context"]) > 0)

    def test_impact_workflow(self):
        """Verify /api/impact returns risk level and blast radius hierarchy."""
        payload = {
            "project_path": self.test_repo,
            "symbol": "login",
            "use_llm": False
        }
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
            "use_llm": False
        }
        res = self.client.post("/api/trace", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["path_found"])
        self.assertGreaterEqual(data["path_length"], 2)
        self.assertIn("steps", data)


if __name__ == "__main__":
    unittest.main()
