"""Unit tests for query / trace synthesis improvements."""

from __future__ import annotations
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from code_chain.core.config import ChainConfig
from code_chain.core.llm import trim_to_token_budget
from code_chain.core.models import SymbolDetail
from code_chain.pipelines.query_pipeline import QueryPipeline
from code_chain.pipelines.trace_pipeline import TracePipeline


class TestQuerySynthesis(unittest.TestCase):
    def test_synthesize_includes_tier3_symbols(self):
        pipe = QueryPipeline(Path("."), ChainConfig())
        symbols = [
            SymbolDetail(
                name="AuthService",
                kind="class",
                file_path="src/auth.py",
                line_number=10,
                callers=[{"name": "handle_login_request"}],
                callees=[{"name": "verify_password"}],
            )
        ]
        text = pipe._synthesize(
            "AuthService login",
            tier1=[],
            tier2=[],
            tier3=symbols,
            raw_explore="explore blob",
        )
        self.assertIn("AuthService", text)
        self.assertIn("src/auth.py:10", text)
        self.assertIn("handle_login_request", text)
        self.assertIn("verify_password", text)
        self.assertIn("explore blob", text)
        self.assertIn("Precision Source Context", text)

    def test_trim_to_token_budget(self):
        long_text = "word " * 5000
        trimmed = trim_to_token_budget(long_text, max_tokens=50)
        self.assertIn("truncated to max_tokens_budget", trimmed)
        self.assertLess(len(trimmed), len(long_text))


class TestTraceCodeGraphEnrichment(unittest.TestCase):
    def test_get_node_snippet_appears_in_flow(self):
        pipe = TracePipeline(Path("/tmp/fake-project"), ChainConfig())
        pipe.gitnexus = MagicMock()
        pipe.graphify = MagicMock()
        pipe.codegraph = MagicMock()

        pipe.gitnexus.trace_path.return_value = {
            "status": "ok",
            "hops": [
                {"name": "handle_login_request", "filePath": "src/api.py"},
                {"name": "login", "filePath": "src/auth.py"},
            ],
            "edges": [{"relType": "CALLS"}],
        }
        pipe.graphify.find_cross_domain_entities.return_value = []
        status = MagicMock()
        status.indexed = True
        pipe.codegraph.get_status.return_value = status
        pipe.codegraph.get_node.side_effect = lambda name: (
            f"SOURCE FOR {name}\n" + ("x" * 50)
        )

        with patch(
            "code_chain.pipelines.trace_pipeline.finalize_stacked_markdown",
            side_effect=lambda text, **kwargs: text,
        ):
            result = pipe.run("handle_login_request", "login", use_llm=False)

        self.assertTrue(result.path_found)
        self.assertEqual(len(result.steps), 2)
        self.assertIsNotNone(result.steps[0].source_snippet)
        self.assertIn("SOURCE FOR handle_login_request", result.synthesized_flow)
        self.assertIn("SOURCE FOR login", result.synthesized_flow)
        self.assertLessEqual(len(result.steps[0].source_snippet or ""), 800)

    def test_skips_enrichment_when_not_indexed(self):
        pipe = TracePipeline(Path("/tmp/fake-project"), ChainConfig())
        pipe.gitnexus = MagicMock()
        pipe.graphify = MagicMock()
        pipe.codegraph = MagicMock()

        pipe.gitnexus.trace_path.return_value = {
            "status": "ok",
            "hops": [{"name": "a", "filePath": "a.py"}],
            "edges": [],
        }
        pipe.graphify.find_cross_domain_entities.return_value = []
        status = MagicMock()
        status.indexed = False
        pipe.codegraph.get_status.return_value = status

        with patch(
            "code_chain.pipelines.trace_pipeline.finalize_stacked_markdown",
            side_effect=lambda text, **kwargs: text,
        ):
            result = pipe.run("a", "b", use_llm=False)

        pipe.codegraph.get_node.assert_not_called()
        self.assertIsNone(result.steps[0].source_snippet)

    def test_graphify_fallback_path_found_false(self):
        pipe = TracePipeline(Path("/tmp/fake-project"), ChainConfig())
        pipe.gitnexus = MagicMock()
        pipe.graphify = MagicMock()
        pipe.codegraph = MagicMock()
        pipe.gitnexus.trace_path.return_value = None
        pipe.graphify.find_path.return_value = "A -> B -> C (graphify text path)"

        with patch(
            "code_chain.pipelines.trace_pipeline.finalize_stacked_markdown",
            side_effect=lambda text, **kwargs: text,
        ):
            result = pipe.run("A", "C", use_llm=False)

        self.assertFalse(result.path_found)
        self.assertEqual(result.path_length, 0)
        self.assertEqual(result.steps, [])
        self.assertIn("Graphify fallback", result.synthesized_flow)
        self.assertIn("graphify text path", result.synthesized_flow)


if __name__ == "__main__":
    unittest.main()
