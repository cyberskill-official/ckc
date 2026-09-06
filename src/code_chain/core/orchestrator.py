"""
Orchestrator: The main entry point coordinating Graphify, GitNexus, and CodeGraph pipelines.
"""

from __future__ import annotations
from typing import Optional, Dict, Any
from code_chain.core.config import ChainConfig
from code_chain.core.models import (
    ProjectGraphStatus,
    ChainedQueryResult,
    ChainedImpactResult,
    ChainedTraceResult,
)
from code_chain.pipelines import (
    IndexPipeline,
    QueryPipeline,
    ImpactPipeline,
    TracePipeline,
)
from code_chain.adapters import GitNexusAdapter


class CodeKnowledgeChain:
    """The central unified orchestrator for the 3-engine code knowledge graph chain."""

    def __init__(
        self, project_path: Optional[str] = None, config: Optional[ChainConfig] = None
    ):
        self.config = config or ChainConfig()
        self.project_path = self.config.resolve_project_path(project_path)
        self.index_pipe = IndexPipeline(self.project_path, self.config)
        self.query_pipe = QueryPipeline(self.project_path, self.config)
        self.impact_pipe = ImpactPipeline(self.project_path, self.config)
        self.trace_pipe = TracePipeline(self.project_path, self.config)
        self.gitnexus = GitNexusAdapter(self.config.gitnexus_bin, self.project_path)

    def status(self) -> ProjectGraphStatus:
        """Returns the status and indexing health of all 3 graph engines."""
        return self.index_pipe.get_status()

    def index(self, code_only: bool = True, force: bool = False) -> Dict[str, Any]:
        """Indexes the target project across Graphify, GitNexus, and CodeGraph."""
        return self.index_pipe.run(code_only=code_only, force=force)

    def query(self, concept_or_question: str) -> ChainedQueryResult:
        """Runs the 3-tier chained intelligence query."""
        return self.query_pipe.run(concept_or_question)

    def impact(self, target_symbol: str) -> ChainedImpactResult:
        """Runs the 3-tier refactoring blast radius analysis."""
        return self.impact_pipe.run(target_symbol)

    def trace(self, from_symbol: str, to_symbol: str) -> ChainedTraceResult:
        """Traces the execution path between two symbols across all 3 engines."""
        return self.trace_pipe.run(from_symbol, to_symbol)

    def detect_changes(self) -> Dict[str, Any]:
        """Maps current git diff hunks to indexed knowledge graph symbols."""
        return self.gitnexus.detect_changes()

    def export_summary(self) -> str:
        """Produces a unified status and readiness summary report."""
        status = self.status()
        lines = [
            f"# Code Knowledge Chain Status: `{self.project_path.name}`",
            f"**Path:** `{self.project_path}`",
            "",
            "| Engine | Layer | Status | Nodes | Details |",
            "| :--- | :--- | :--- | :--- | :--- |",
            f"| **Graphify** | Multi-Modal & Architecture | {'✅ Ready' if status.graphify.indexed else '❌ Missing'} | {status.graphify.node_count} | {status.graphify.details.get('communities_count', 0)} communities |",
            f"| **GitNexus** | AST & Execution Flows | {'✅ Ready' if status.gitnexus.indexed else '❌ Missing'} | {status.gitnexus.node_count} | KuzuDB graph |",
            f"| **CodeGraph** | Symbols & Test Impact | {'✅ Ready' if status.codegraph.indexed else '❌ Missing'} | {status.codegraph.node_count} | Fast symbol cache |",
            "",
            f"**Overall Readiness:** {status.ready_count}/3 engines indexed.",
        ]
        return "\n".join(lines)
