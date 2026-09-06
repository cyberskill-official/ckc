"""
Configuration and runtime environment resolution for code-knowledge-chain.
"""

from __future__ import annotations
import shutil
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from code_chain.core.paths import assert_safe_project_path


class ChainConfig(BaseModel):
    """Global configuration for the chaining pipeline."""

    graphify_bin: str = Field(
        default_factory=lambda: shutil.which("graphify") or "graphify"
    )
    gitnexus_bin: str = Field(
        default_factory=lambda: shutil.which("gitnexus") or "gitnexus"
    )
    codegraph_bin: str = Field(
        default_factory=lambda: shutil.which("codegraph") or "codegraph"
    )

    # Timeouts in seconds
    index_timeout: int = 300
    query_timeout: int = 60

    # Indexing options
    graphify_code_only: bool = (
        True  # Defaults to fast AST mode without requiring external LLM API keys
    )
    max_search_depth: int = 5
    max_tokens_budget: int = 4000

    def resolve_project_path(self, path: Optional[str] = None) -> Path:
        target = str(path) if path else str(Path.cwd())
        return assert_safe_project_path(target)

    def get_graphify_index_path(self, project_path: Path) -> Path:
        return project_path / "graphify-out" / "graph.json"

    def get_gitnexus_index_path(self, project_path: Path) -> Path:
        return project_path / ".gitnexus"

    def get_codegraph_index_path(self, project_path: Path) -> Path:
        return project_path / ".codegraph"
