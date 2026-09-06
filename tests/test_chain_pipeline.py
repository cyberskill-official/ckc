"""
Integration tests for the 3-tier chaining pipelines.
"""

import unittest
from pathlib import Path

from code_chain.core.orchestrator import CodeKnowledgeChain


class TestChainPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_repo = (
            Path(__file__).resolve().parent.parent / "examples" / "python-auth-service"
        )
        cls.chain = CodeKnowledgeChain(project_path=str(cls.test_repo))

    def test_overall_status(self):
        status = self.chain.status()
        self.assertTrue(status.all_ready)
        self.assertEqual(status.ready_count, 3)

    def test_chained_query(self):
        res = self.chain.query("AuthService login")
        self.assertIn("AuthService", res.synthesized_context)
        self.assertIn("Graphify", res.synthesized_context)
        self.assertIn("GitNexus", res.synthesized_context)
        self.assertIn("CodeGraph", res.synthesized_context)

    def test_chained_impact(self):
        res = self.chain.impact("login")
        self.assertEqual(res.risk_level, "LOW")
        self.assertGreaterEqual(res.blast_radius_count, 1)
        self.assertIn("Refactor Blast Radius", res.synthesized_report)
        self.assertIn("handle_login_request", res.synthesized_report)

    def test_chained_trace(self):
        res = self.chain.trace("handle_login_request", "verify_password")
        self.assertTrue(res.path_found)
        self.assertGreaterEqual(res.path_length, 2)
        self.assertIn("```mermaid", res.synthesized_flow)
        self.assertIn("login", res.synthesized_flow)


if __name__ == "__main__":
    unittest.main()
