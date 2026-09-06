"""
Unit tests for code-knowledge-chain adapters.
"""

import unittest
from pathlib import Path
from code_chain.core.config import ChainConfig
from code_chain.adapters import GraphifyAdapter, GitNexusAdapter, CodeGraphAdapter


class TestAdapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = ChainConfig()
        cls.test_repo = (
            Path(__file__).resolve().parent.parent / "examples" / "python-auth-service"
        )

    def test_graphify_adapter_status_and_entities(self):
        adapter = GraphifyAdapter(self.config.graphify_bin, self.test_repo)
        status = adapter.get_status()
        self.assertTrue(status.available)
        self.assertTrue(status.indexed)
        self.assertGreater(status.node_count, 0)

        entities = adapter.find_cross_domain_entities("AuthService")
        self.assertGreater(len(entities), 0)
        self.assertEqual(entities[0].name, "AuthService")

    def test_gitnexus_adapter_status_and_impact(self):
        adapter = GitNexusAdapter(self.config.gitnexus_bin, self.test_repo)
        status = adapter.get_status()
        self.assertTrue(status.available)
        self.assertTrue(status.indexed)

        impact = adapter.analyze_impact("login")
        self.assertEqual(impact.get("risk"), "LOW")
        self.assertGreaterEqual(impact.get("impactedCount", 0), 1)

    def test_codegraph_adapter_status_and_callers(self):
        adapter = CodeGraphAdapter(self.config.codegraph_bin, self.test_repo)
        status = adapter.get_status()
        self.assertTrue(status.available)
        self.assertTrue(status.indexed)

        callers = adapter.get_callers("login")
        self.assertGreater(len(callers), 0)
        self.assertEqual(callers[0]["name"], "handle_login_request")


if __name__ == "__main__":
    unittest.main()
