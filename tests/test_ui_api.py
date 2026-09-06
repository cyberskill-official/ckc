"""
Automated unit and integration tests for Code Knowledge Chain Web UI API.
"""

import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from code_chain.ui.server import app


class TestWebUIApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.test_repo = "/Users/stephencheng/.gemini/antigravity/brain/bbdb8b5b-335f-4365-9a0f-e9a7b788bcf7/scratch/test-project"

    def test_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    def test_status_valid_project(self):
        res = self.client.get(f"/api/status?project={self.test_repo}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertTrue(data["status"]["all_ready"])
        self.assertEqual(data["status"]["ready_count"], 3)
        self.assertIn("summary", data)

    def test_status_invalid_path(self):
        res = self.client.get("/api/status?project=/non/existent/path/999")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Directory does not exist", res.json()["detail"])

    def test_status_empty_path(self):
        res = self.client.get("/api/status?project=")
        self.assertEqual(res.status_code, 400)

    def test_query_endpoint(self):
        payload = {
            "project_path": self.test_repo,
            "query": "authentication and login flow",
        }
        res = self.client.post("/api/query", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["query"], payload["query"])
        self.assertIn("synthesized_context", data)
        self.assertIn("AuthService", data["synthesized_context"])

    def test_impact_endpoint(self):
        payload = {
            "project_path": self.test_repo,
            "symbol": "login",
        }
        res = self.client.post("/api/impact", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["target_symbol"], "login")
        self.assertEqual(data["risk_level"], "LOW")
        self.assertGreaterEqual(data["blast_radius_count"], 1)
        self.assertIn("synthesized_report", data)

    def test_trace_endpoint(self):
        payload = {
            "project_path": self.test_repo,
            "from_symbol": "handle_login_request",
            "to_symbol": "verify_password",
        }
        res = self.client.post("/api/trace", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["path_found"])
        self.assertGreaterEqual(data["path_length"], 2)
        self.assertIn("```mermaid", data["synthesized_flow"])

    def test_artifacts_list(self):
        res = self.client.get(f"/api/artifacts?project={self.test_repo}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("artifacts", data)
        labels = [a["label"] for a in data["artifacts"]]
        self.assertIn("Graphify Graph", labels)

    def test_artifacts_content_valid(self):
        res = self.client.get(f"/api/artifacts/content?project={self.test_repo}&file=graphify-out/graph.json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_json"])
        self.assertIn("nodes", data["content"])

    def test_artifacts_content_traversal_blocked(self):
        res = self.client.get(f"/api/artifacts/content?project={self.test_repo}&file=../../etc/passwd")
        self.assertEqual(res.status_code, 400)

    def test_artifacts_content_unauthorized_folder(self):
        res = self.client.get(f"/api/artifacts/content?project={self.test_repo}&file=src/auth.py")
        self.assertEqual(res.status_code, 403)

    def test_cancel_indexing(self):
        payload = {"project_path": self.test_repo}
        res = self.client.post("/api/index/cancel", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

    def test_static_files_served(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Code Knowledge Chain", res.text)
        self.assertIn("tab-dashboard", res.text)


if __name__ == "__main__":
    unittest.main()
