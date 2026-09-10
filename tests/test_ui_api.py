"""
Automated unit and integration tests for Code Knowledge Chain Web UI API.
"""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from code_chain.ui import server as ui_server
from code_chain.ui.server import app


class TestWebUIApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.test_repo = str(
            Path(__file__).resolve().parent.parent / "examples" / "python-auth-service"
        )

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
        self.assertIn("local_docs_count", data)
        self.assertIn("llm", data)
        self.assertIn("configured", data["llm"])
        self.assertIn("engine_errors", data)
        self.assertIsInstance(data["engine_errors"], dict)

    def test_browse_returns_directories(self):
        """POST /api/browse should return directory listing."""
        res = self.client.post("/api/browse", json={"path": None})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("current", data)
        self.assertIn("parent", data)
        self.assertIn("entries", data)
        self.assertIsInstance(data["entries"], list)
        self.assertGreater(len(data["current"]), 0)

    def test_browse_hides_hidden_dirs(self):
        """POST /api/browse should not return dot-prefixed directories."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, ".hidden_dir"))
            os.makedirs(os.path.join(tmp, "visible_dir"))
            res = self.client.post("/api/browse", json={"path": tmp})
            self.assertEqual(res.status_code, 200)
            names = [e["name"] for e in res.json()["entries"]]
            self.assertIn("visible_dir", names)
            self.assertNotIn(".hidden_dir", names)

    def test_browse_invalid_path_falls_back(self):
        """POST /api/browse with non-existent path should fall back gracefully."""
        res = self.client.post("/api/browse", json={"path": "/nonexistent/path/12345"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(len(data["current"]) > 0)

    def test_browse_marks_indexed_dirs(self):
        """POST /api/browse should mark is_indexed=True when graphify-out/graph.json exists."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            indexed_dir = os.path.join(tmp, "indexed_repo")
            plain_dir = os.path.join(tmp, "plain_repo")
            os.makedirs(os.path.join(indexed_dir, "graphify-out"))
            with open(os.path.join(indexed_dir, "graphify-out", "graph.json"), "w") as f:
                f.write("{}")
            os.makedirs(plain_dir)

            res = self.client.post("/api/browse", json={"path": tmp})
            self.assertEqual(res.status_code, 200)
            entries = {e["name"]: e for e in res.json()["entries"]}
            self.assertTrue(entries["indexed_repo"]["is_indexed"])
            self.assertFalse(entries["plain_repo"]["is_indexed"])

    def test_llm_status_endpoint(self):
        """GET /api/llm/status should return status structure."""
        res = self.client.get("/api/llm/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("provider", data)
        self.assertIn("base_url", data)
        self.assertIn("connected", data)
        self.assertIn("available_models", data)

    def test_llm_config_endpoint_ssrf_protection(self):
        """POST /api/llm/config should reject denied SSRF addresses with 400."""
        res = self.client.post(
            "/api/llm/config",
            json={
                "provider": "custom",
                "base_url": "http://169.254.169.254/v1",
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("detail", res.json())

    def test_llm_config_endpoint_valid_and_disable(self):
        """POST /api/llm/config should accept valid loopback URL, and disable resets."""
        res = self.client.post(
            "/api/llm/config",
            json={
                "provider": "lm-studio",
                "base_url": "http://127.0.0.1:1234/v1",
                "model": "test-model",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["provider"], "lm-studio")
        self.assertEqual(data["base_url"], "http://127.0.0.1:1234/v1")

        disable_res = self.client.post("/api/llm/disable")
        self.assertEqual(disable_res.status_code, 200)
        self.assertFalse(disable_res.json()["configured"])

    def test_cors_loopback_default(self):
        from code_chain.ui.server import is_loopback_host, resolve_cors_origins

        self.assertTrue(is_loopback_host("127.0.0.1"))
        self.assertFalse(is_loopback_host("0.0.0.0"))
        # FIND-001: default is same-origin only (empty allow-list), not wildcard.
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CKC_CORS_ORIGINS", None)
            self.assertEqual(resolve_cors_origins("127.0.0.1"), [])
            self.assertEqual(resolve_cors_origins("0.0.0.0"), [])
        with patch.dict(os.environ, {"CKC_CORS_ORIGINS": "*"}, clear=False):
            self.assertEqual(resolve_cors_origins("127.0.0.1"), ["*"])
            with self.assertRaises(RuntimeError):
                resolve_cors_origins("0.0.0.0")

    def test_status_invalid_path(self):
        res = self.client.get("/api/status?project=/non/existent/path/999")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Directory does not exist", res.json()["detail"])

    def test_status_system_path_blocked(self):
        res = self.client.get("/api/status?project=/etc")
        self.assertEqual(res.status_code, 400)
        detail = res.json()["detail"]
        self.assertTrue(
            "system directory" in detail or "does not look like a software project" in detail
        )

    def test_status_empty_path(self):
        res = self.client.get("/api/status?project=")
        self.assertEqual(res.status_code, 400)

    def test_query_endpoint(self):
        payload = {
            "project_path": self.test_repo,
            "query": "authentication and login flow",
            "use_llm": False,
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
            "use_llm": False,
        }
        res = self.client.post("/api/impact", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["target_symbol"], "login")
        self.assertIn(data["risk_level"], ("LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"))
        self.assertGreaterEqual(data["blast_radius_count"], 1)
        self.assertIn("synthesized_report", data)
        self.assertIn("engine_errors", data)

    def test_trace_endpoint(self):
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
        self.assertIn("```mermaid", data["synthesized_flow"])

    def test_artifacts_list(self):
        res = self.client.get(f"/api/artifacts?project={self.test_repo}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("artifacts", data)
        labels = [a["label"] for a in data["artifacts"]]
        self.assertIn("Graphify Graph", labels)

    def test_artifacts_content_valid(self):
        res = self.client.get(
            f"/api/artifacts/content?project={self.test_repo}&file=graphify-out/graph.json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_json"])
        self.assertIn("nodes", data["content"])

    def test_artifacts_content_traversal_blocked(self):
        res = self.client.get(
            f"/api/artifacts/content?project={self.test_repo}&file=../../etc/passwd"
        )
        self.assertEqual(res.status_code, 400)

    def test_artifacts_content_unauthorized_folder(self):
        res = self.client.get(f"/api/artifacts/content?project={self.test_repo}&file=src/auth.py")
        self.assertEqual(res.status_code, 403)

    def test_artifacts_content_resolved_escape_blocked(self):
        # Symlink-style escape: prefix is allowed, but resolved path must stay in project
        res = self.client.get(
            f"/api/artifacts/content?project={self.test_repo}&file=graphify-out/../../../etc/passwd"
        )
        self.assertIn(res.status_code, (400, 403))

    def test_artifacts_content_size_cap(self):
        # Must use an allowlisted relative path (R2-SEC-11).
        oversized = Path(self.test_repo) / "graphify-out" / "GRAPH_REPORT.md"
        oversized.parent.mkdir(parents=True, exist_ok=True)
        backup = oversized.read_text(encoding="utf-8") if oversized.exists() else None
        try:
            oversized.write_text("x" * (ui_server._MAX_ARTIFACT_BYTES + 1), encoding="utf-8")
            res = self.client.get(
                f"/api/artifacts/content?project={self.test_repo}&file=graphify-out/GRAPH_REPORT.md"
            )
            self.assertEqual(res.status_code, 413)
            self.assertIn("size limit", res.json()["detail"])
        finally:
            if backup is None:
                oversized.unlink(missing_ok=True)
            else:
                oversized.write_text(backup, encoding="utf-8")

    def test_cancel_indexing(self):
        payload = {"project_path": self.test_repo}
        res = self.client.post("/api/index/cancel", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

    def test_static_files_served(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("CKC", res.text)
        self.assertIn("cy", res.text)  # Cytoscape graph container

    def test_graph_enriched_attributes(self):
        res = self.client.get(f"/api/graph?project={self.test_repo}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        nodes = data["elements"]["nodes"]
        self.assertGreater(len(nodes), 0)
        sample = nodes[0]["data"]
        self.assertIn("kind", sample)
        self.assertIn("is_vendor", sample)
        self.assertIn("in_degree", sample)
        self.assertIn("out_degree", sample)
        self.assertIsInstance(sample["is_vendor"], bool)
        self.assertIsInstance(sample["in_degree"], int)
        self.assertIsInstance(sample["out_degree"], int)

    def test_source_snippet_success(self):
        res = self.client.get(
            f"/api/source?project={self.test_repo}&file=src/auth.py&line=10&window=5"
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["file"], "src/auth.py")
        self.assertEqual(data["language"], "python")
        self.assertIn("lines", data)
        self.assertEqual(data["highlight_line"], 10)
        self.assertGreater(len(data["lines"]), 0)
        self.assertEqual(data["lines"][0]["line_num"], data["start_line"])

    def test_source_snippet_string_line_syntax(self):
        res = self.client.get(
            f"/api/source?project={self.test_repo}&file=src/auth.py&line=L10&window=5"
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["highlight_line"], 10)

    def test_source_snippet_path_traversal_blocked(self):
        res = self.client.get(f"/api/source?project={self.test_repo}&file=../../etc/passwd")
        self.assertIn(res.status_code, (400, 403))

    def test_source_snippet_not_found(self):
        res = self.client.get(
            f"/api/source?project={self.test_repo}&file=app/nonexistent_file_xyz.py"
        )
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
