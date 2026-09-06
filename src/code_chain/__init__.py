"""
Code Knowledge Chain: A unified 3-tier chaining engine for Graphify, GitNexus, and CodeGraph.
"""

from code_chain.core.orchestrator import CodeKnowledgeChain
from code_chain.core.config import ChainConfig
from code_chain.core.models import (
    ProjectGraphStatus,
    ChainedQueryResult,
    ChainedImpactResult,
    ChainedTraceResult,
)

__version__ = "1.0.0"

__all__ = [
    "CodeKnowledgeChain",
    "ChainConfig",
    "ProjectGraphStatus",
    "ChainedQueryResult",
    "ChainedImpactResult",
    "ChainedTraceResult",
]
