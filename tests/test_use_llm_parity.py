"""Tests for use_llm parity on UI and MCP surfaces."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from code_chain.ui.server import app


class TestUseLlmParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.test_repo = str(
            Path(__file__).resolve().parent.parent
            / "examples"
            / "python-auth-service"
        )

    def test_ui_query_use_llm_false_omits_synthesis(self):
        env = {
            "CKC_LLM_BASE_URL": "http://127.0.0.1:1234/v1",
            "CKC_LLM_MODEL": "local-model",
        }
        with patch.dict("os.environ", env, clear=False), patch(
            "code_chain.core.llm.synthesize_stacked_context",
            return_value="SHOULD NOT APPEAR",
        ) as synth:
            res = self.client.post(
                "/api/query",
                json={
                    "project_path": self.test_repo,
                    "query": "authentication",
                    "use_llm": False,
                },
            )
        self.assertEqual(res.status_code, 200)
        text = res.json()["synthesized_context"]
        self.assertNotIn("Local model synthesis", text)
        self.assertNotIn("SHOULD NOT APPEAR", text)
        synth.assert_not_called()

    def test_mcp_query_use_llm_false_omits_synthesis(self):
        env = {
            "CKC_LLM_BASE_URL": "http://127.0.0.1:1234/v1",
            "CKC_LLM_MODEL": "local-model",
        }
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "chain_query",
                    "arguments": {
                        "project_path": self.test_repo,
                        "query": "authentication",
                        "use_llm": False,
                    },
                },
            }
        ]
        payload = "\n".join(json.dumps(r) for r in requests) + "\n"
        with patch.dict("os.environ", env, clear=False):
            proc = subprocess.run(
                ["code-chain", "mcp"],
                input=payload,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        text = json.loads(lines[0])["result"]["content"][0]["text"]
        self.assertNotIn("## Local model synthesis", text)


if __name__ == "__main__":
    unittest.main()
