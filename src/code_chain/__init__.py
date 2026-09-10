"""
Code Knowledge Chain: A unified 3-tier chaining engine for Graphify, GitNexus, and CodeGraph.
"""

from code_chain.core.config import ChainConfig
from code_chain.core.models import (
    ChainedImpactResult,
    ChainedQueryResult,
    ChainedTraceResult,
    ProjectGraphStatus,
)
from code_chain.core.orchestrator import CodeKnowledgeChain

__version__ = "1.0.0"  # keep in sync with pyproject.toml [project].version

__all__ = [
    "ChainConfig",
    "ChainedImpactResult",
    "ChainedQueryResult",
    "ChainedTraceResult",
    "CodeKnowledgeChain",
    "ProjectGraphStatus",
]
