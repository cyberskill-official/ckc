"""
Configuration and runtime environment resolution for code-knowledge-chain.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from pydantic import BaseModel, Field

from code_chain.core.paths import assert_safe_project_path


def resolve_binary(name_or_path: str) -> str:
    """Resolve a binary path across PATH, python bin directory, and env overrides."""
    if not name_or_path:
        return name_or_path

    env_var = f"CKC_{name_or_path.upper().replace('-', '_')}_BIN"
    env_override = os.getenv(env_var)
    if env_override and Path(env_override).exists():
        return env_override

    p = Path(name_or_path)
    if p.is_file() and (os.access(p, os.X_OK) or sys.platform == "win32"):
        return str(p)

    found = shutil.which(name_or_path)
    if found:
        return found

    exe_dir = Path(sys.executable).parent
    candidate = exe_dir / name_or_path
    if candidate.is_file() and (os.access(candidate, os.X_OK) or sys.platform == "win32"):
        return str(candidate)

    if sys.platform == "win32":
        candidate_exe = exe_dir / f"{name_or_path}.exe"
        if candidate_exe.is_file():
            return str(candidate_exe)

    return name_or_path


def get_code_chain_cmd() -> list[str]:
    """Get the command array to execute code-chain CLI in the current Python environment."""
    resolved = resolve_binary("code-chain")
    if resolved != "code-chain" or shutil.which("code-chain"):
        return [resolved]
    return [sys.executable, "-m", "code_chain"]


class ChainConfig(BaseModel):
    """Global configuration for the chaining pipeline."""

    graphify_bin: str = Field(
        default_factory=lambda: resolve_binary("graphify")
    )
    gitnexus_bin: str = Field(
        default_factory=lambda: resolve_binary("gitnexus")
    )
    codegraph_bin: str = Field(
        default_factory=lambda: resolve_binary("codegraph")
    )

    # Timeouts in seconds
    index_timeout: int = 300
    # Soft upper bound for interactive query/impact/trace work (UI messaging / future caps).
    query_timeout: int = 60

    # Indexing options
    graphify_code_only: bool = (
        True  # Defaults to fast AST mode without requiring external LLM API keys
    )
    # Cap on Tier-2 GitNexus context lookups per query (and related search depth).
    max_search_depth: int = 5
    max_tokens_budget: int = 4000

    def resolve_project_path(self, path: str | None = None) -> Path:
        target = str(path) if path else str(Path.cwd())
        return assert_safe_project_path(target)

    def get_graphify_index_path(self, project_path: Path) -> Path:
        return project_path / "graphify-out" / "graph.json"

    def get_gitnexus_index_path(self, project_path: Path) -> Path:
        return project_path / ".gitnexus"

    def get_codegraph_index_path(self, project_path: Path) -> Path:
        return project_path / ".codegraph"
