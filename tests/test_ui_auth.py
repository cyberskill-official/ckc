"""Auth middleware, token compare, and artifact allowlist regression tests."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from code_chain.ui import server as ui_server
from code_chain.ui.server import app, tokens_match


class TestUIAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.test_repo = str(
            Path(__file__).resolve().parent.parent / "examples" / "python-auth-service"
        )

    def setUp(self):
        self._prev_token = os.environ.get("CKC_UI_TOKEN")
        self._prev_host = os.environ.get("CKC_HOST")
        os.environ.pop("CKC_UI_TOKEN", None)

    def tearDown(self):
        if self._prev_token is None:
            os.environ.pop("CKC_UI_TOKEN", None)
        else:
            os.environ["CKC_UI_TOKEN"] = self._prev_token
        if self._prev_host is None:
            os.environ.pop("CKC_HOST", None)
        else:
            os.environ["CKC_HOST"] = self._prev_host

    def test_tokens_match_constant_time(self):
        self.assertTrue(tokens_match("secret", "secret"))
        self.assertFalse(tokens_match("secret", "wrong"))
        self.assertFalse(tokens_match("", "secret"))
        self.assertFalse(tokens_match("secret", ""))

    def test_health_always_public(self):
        with patch.dict(os.environ, {"CKC_UI_TOKEN": "test-token-abc"}, clear=False):
            res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    def test_read_api_gated_when_token_set(self):
        with patch.dict(os.environ, {"CKC_UI_TOKEN": "test-token-abc"}, clear=False):
            denied = self.client.get(f"/api/status?project={self.test_repo}")
            self.assertEqual(denied.status_code, 401)

            ok = self.client.get(
                f"/api/status?project={self.test_repo}",
                headers={"Authorization": "Bearer test-token-abc"},
            )
            self.assertEqual(ok.status_code, 200)

            graph = self.client.get(
                f"/api/graph?project={self.test_repo}",
                headers={"X-CKC-Token": "test-token-abc"},
            )
            self.assertEqual(graph.status_code, 200)
            self.assertIn("ETag", graph.headers)

            wrong = self.client.get(
                f"/api/artifacts?project={self.test_repo}",
                headers={"Authorization": "Bearer wrong"},
            )
            self.assertEqual(wrong.status_code, 401)

    def test_static_still_served_with_token(self):
        with patch.dict(os.environ, {"CKC_UI_TOKEN": "test-token-abc"}, clear=False):
            res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("CKC", res.text)
        self.assertIn("ui-token", res.text)

    def test_auth_required_helpers(self):
        with patch.dict(os.environ, {"CKC_UI_TOKEN": "x", "CKC_HOST": "127.0.0.1"}, clear=False):
            self.assertTrue(ui_server.auth_required())
        with patch.dict(os.environ, {"CKC_HOST": "0.0.0.0"}, clear=False):
            os.environ.pop("CKC_UI_TOKEN", None)
            self.assertTrue(ui_server.auth_required())
        with patch.dict(os.environ, {"CKC_HOST": "127.0.0.1"}, clear=False):
            os.environ.pop("CKC_UI_TOKEN", None)
            self.assertFalse(ui_server.auth_required())

    def test_artifact_component_prefix_not_startswith(self):
        # Bare startswith("graphify-out") would incorrectly allow graphify-out-extra/...
        self.assertFalse(ui_server._artifact_path_allowed("graphify-out-extra/secret.txt"))
        self.assertTrue(ui_server._artifact_path_allowed("graphify-out/graph.json"))
        self.assertTrue(ui_server._artifact_path_allowed(".code_chain/docs_index.json"))

        res = self.client.get(
            f"/api/artifacts/content?project={self.test_repo}"
            f"&file=graphify-out-extra/secret.txt"
        )
        self.assertEqual(res.status_code, 403)

    def test_graph_etag_304(self):
        first = self.client.get(f"/api/graph?project={self.test_repo}")
        self.assertEqual(first.status_code, 200)
        etag = first.headers.get("ETag")
        self.assertTrue(etag)
        self.assertIn("subsampled", first.json()["meta"])

        again = self.client.get(
            f"/api/graph?project={self.test_repo}",
            headers={"If-None-Match": etag},
        )
        self.assertEqual(again.status_code, 304)


class TestIndexTimeoutCatch(unittest.TestCase):
    def test_graphify_timeout_returns_structured_failure(self):
        import subprocess

        from code_chain.adapters.graphify_adapter import GraphifyAdapter

        adapter = GraphifyAdapter("graphify", Path("/tmp"))
        with patch.object(
            subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd=["graphify"], timeout=1),
        ), patch.object(adapter, "_extract_cmd", return_value=["graphify", "extract"]):
            result = adapter.index_project(timeout=1)
        self.assertFalse(result["success"])
        self.assertTrue(result.get("timeout"))
        self.assertIn("timed out", result["error"])

    def test_gitnexus_and_codegraph_timeout(self):
        import subprocess

        from code_chain.adapters.codegraph_adapter import CodeGraphAdapter
        from code_chain.adapters.gitnexus_adapter import GitNexusAdapter

        for Adapter, key in (
            (GitNexusAdapter, "nexus_dir"),
            (CodeGraphAdapter, "codegraph_dir"),
        ):
            adapter = Adapter("bin", Path("/tmp"))
            with patch.object(
                subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(cmd=["bin"], timeout=1),
            ):
                result = adapter.index_project(timeout=1)
            self.assertFalse(result["success"], Adapter.__name__)
            self.assertTrue(result.get("timeout"), Adapter.__name__)
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
