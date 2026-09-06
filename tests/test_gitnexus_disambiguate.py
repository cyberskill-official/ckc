"""Unit tests for GitNexus ambiguous-symbol resolution and context disambiguation."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from code_chain.adapters.gitnexus_adapter import (
    GitNexusAdapter,
    pick_best_candidate,
)


class TestGitNexusCandidatePick(unittest.TestCase):
    def test_prefers_higher_impact_when_scores_tie(self):
        best = pick_best_candidate(
            [
                {
                    "uid": "Function:a.ts:login",
                    "name": "login",
                    "score": 0.56,
                    "impactedCount": 0,
                    "startLine": 1,
                    "endLine": 1,
                },
                {
                    "uid": "Function:b.ts:authnCtr.login",
                    "name": "login",
                    "score": 0.56,
                    "impactedCount": 1,
                    "startLine": 100,
                    "endLine": 400,
                },
            ]
        )
        self.assertIsNotNone(best)
        assert best is not None
        self.assertEqual(best["uid"], "Function:b.ts:authnCtr.login")

    def test_prefers_larger_span_when_impact_missing(self):
        best = pick_best_candidate(
            [
                {
                    "id": "Function:resolver.ts:login",
                    "name": "login",
                    "score": 0.56,
                    "startLine": 21,
                    "endLine": 21,
                },
                {
                    "id": "Function:controller.ts:authnCtr.login",
                    "name": "login",
                    "score": 0.56,
                    "startLine": 1723,
                    "endLine": 2053,
                },
            ]
        )
        self.assertIsNotNone(best)
        assert best is not None
        self.assertIn("controller", best["id"])

    def test_empty_candidates(self):
        self.assertIsNone(pick_best_candidate([]))
        self.assertIsNone(pick_best_candidate([{"name": "x"}]))


class TestGitNexusContextDisambiguate(unittest.TestCase):
    def test_ambiguous_context_requeries_by_uid(self):
        adapter = GitNexusAdapter("gitnexus", Path("/tmp/proj"))
        ambiguous = {
            "status": "ambiguous",
            "candidates": [
                {
                    "uid": "Function:a.py:login",
                    "name": "login",
                    "score": 0.4,
                    "startLine": 1,
                    "endLine": 1,
                },
                {
                    "uid": "Function:b.py:AuthService.login",
                    "name": "login",
                    "score": 0.9,
                    "startLine": 10,
                    "endLine": 40,
                },
            ],
        }
        found = {
            "status": "found",
            "symbol": {"uid": "Function:b.py:AuthService.login", "name": "login"},
            "incoming": {"calls": []},
            "outgoing": {"calls": []},
            "processes": [],
        }
        with patch.object(
            adapter, "_run_context", side_effect=[ambiguous, found]
        ) as mocked:
            result = adapter.get_symbol_context("login")
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["_resolved_uid"], "Function:b.py:AuthService.login")
        self.assertEqual(mocked.call_count, 2)
        mocked.assert_any_call("login", uid="Function:b.py:AuthService.login")


class TestImpactOutcomes(unittest.TestCase):
    def test_empty_outcome(self):
        adapter = GitNexusAdapter("gitnexus", Path("/tmp/proj"))
        with patch.object(adapter, "_run_impact", return_value=None):
            result = adapter.analyze_impact("missing_symbol")
        self.assertEqual(result["_outcome"], "empty")

    def test_ambiguous_unresolved_outcome(self):
        adapter = GitNexusAdapter("gitnexus", Path("/tmp/proj"))
        ambiguous = {
            "status": "ambiguous",
            "candidates": [{"name": "login"}],  # no uid → cannot resolve
            "risk": "UNKNOWN",
        }
        with patch.object(adapter, "_run_impact", return_value=ambiguous):
            result = adapter.analyze_impact("login")
        self.assertEqual(result["_outcome"], "ambiguous_unresolved")


if __name__ == "__main__":
    unittest.main()
