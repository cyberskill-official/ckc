"""
Tests for the MCP server stdio protocol.
"""

import json
import subprocess
import unittest
from pathlib import Path


class TestMCPServer(unittest.TestCase):
    def test_mcp_protocol_handshake_and_tools(self):
        test_repo = str(
            Path(__file__).resolve().parent.parent / "examples" / "python-auth-service"
        )

        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "chain_status",
                    "arguments": {"project_path": test_repo},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "chain_impact",
                    "arguments": {"project_path": test_repo, "symbol": "login"},
                },
            },
        ]

        input_payload = "\n".join(json.dumps(r) for r in requests) + "\n"

        proc = subprocess.run(
            ["code-chain", "mcp"],
            input=input_payload,
            capture_output=True,
            text=True,
            timeout=15,
        )

        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 4)

        resp1 = json.loads(lines[0])
        self.assertEqual(resp1["id"], 1)
        self.assertEqual(resp1["result"]["serverInfo"]["name"], "code-knowledge-chain")

        resp2 = json.loads(lines[1])
        self.assertEqual(resp2["id"], 2)
        tool_names = [t["name"] for t in resp2["result"]["tools"]]
        self.assertIn("chain_status", tool_names)
        self.assertIn("chain_query", tool_names)
        self.assertIn("chain_impact", tool_names)
        self.assertIn("chain_trace", tool_names)
        self.assertIn("chain_init", tool_names)

        resp3 = json.loads(lines[2])
        self.assertEqual(resp3["id"], 3)
        self.assertIn(
            "Code Knowledge Chain Status", resp3["result"]["content"][0]["text"]
        )

        resp4 = json.loads(lines[3])
        self.assertEqual(resp4["id"], 4)
        self.assertIn("Refactor Blast Radius", resp4["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
