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


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


# Default query wall clock leaves room for optional LLM synthesis (~45s).
_DEFAULT_QUERY_TIMEOUT = 90
_DEFAULT_LLM_HTTP_TIMEOUT = 45.0


def llm_http_timeout(query_timeout: int | None = None) -> float:
    """
    Cap LLM HTTP wait so synthesis fits inside the query wall clock.

    Leaves ~15s headroom for engine work when query_timeout is tight.
    """
    budget = (
        int(query_timeout)
        if query_timeout is not None
        else _env_int("CKC_QUERY_TIMEOUT", _DEFAULT_QUERY_TIMEOUT)
    )
    return float(min(_DEFAULT_LLM_HTTP_TIMEOUT, max(5.0, budget - 15.0)))


class ChainConfig(BaseModel):
    """Global configuration for the chaining pipeline.

    Timeouts and budgets are env-wired (see ``.env.example``):
    ``CKC_INDEX_TIMEOUT``, ``CKC_MULTIMODAL_INDEX_TIMEOUT``, ``CKC_QUERY_TIMEOUT``,
    ``CKC_MAX_SEARCH_DEPTH``, ``CKC_MAX_TOKENS_BUDGET``, ``CKC_GRAPHIFY_CODE_ONLY``.

    Index timeout model (intentional dual semantics — do not "unify" casually):
    - **UI SSE** (`/api/index/stream`): one shared wall-clock deadline for all
      engines (Graphify + GitNexus + CodeGraph share the budget).
    - **CLI / MCP** (`IndexPipeline`): each engine gets a full per-engine timeout
      (Graphify uses multimodal timeout when not code-only; others use
      ``index_timeout``). See CONTRIBUTING.md.
    """

    graphify_bin: str = Field(default_factory=lambda: resolve_binary("graphify"))
    gitnexus_bin: str = Field(default_factory=lambda: resolve_binary("gitnexus"))
    codegraph_bin: str = Field(default_factory=lambda: resolve_binary("codegraph"))

    # Timeouts in seconds (env-overridable)
    index_timeout: int = Field(default_factory=lambda: _env_int("CKC_INDEX_TIMEOUT", 300))
    multimodal_index_timeout: int = Field(
        default_factory=lambda: _env_int("CKC_MULTIMODAL_INDEX_TIMEOUT", 900)
    )
    # Wall-clock cap for UI/API/CLI/MCP query, impact, and trace.
    query_timeout: int = Field(
        default_factory=lambda: _env_int("CKC_QUERY_TIMEOUT", _DEFAULT_QUERY_TIMEOUT)
    )

    # Indexing options — honored when IndexPipeline.run(code_only=None)
    graphify_code_only: bool = Field(
        default_factory=lambda: _env_bool("CKC_GRAPHIFY_CODE_ONLY", True)
    )
    # Cap on Tier-2 GitNexus context lookups per query (and related search depth).
    max_search_depth: int = Field(default_factory=lambda: _env_int("CKC_MAX_SEARCH_DEPTH", 5))
    # Approximate token budget for stacked markdown + optional local LLM synthesis.
    max_tokens_budget: int = Field(default_factory=lambda: _env_int("CKC_MAX_TOKENS_BUDGET", 4000))

    # Result caching — writes query/impact/trace markdown to .code_chain/results/
    result_cache_enabled: bool = Field(
        default_factory=lambda: _env_bool("CKC_RESULT_CACHE", True)
    )
    result_cache_max: int = Field(
        default_factory=lambda: _env_int("CKC_RESULT_CACHE_MAX", 50)
    )

    def resolve_project_path(self, path: str | None = None) -> Path:
        target = str(path) if path else str(Path.cwd())
        return assert_safe_project_path(target)

    def get_graphify_index_path(self, project_path: Path) -> Path:
        return project_path / "graphify-out" / "graph.json"

    def get_gitnexus_index_path(self, project_path: Path) -> Path:
        return project_path / ".gitnexus"

    def get_codegraph_index_path(self, project_path: Path) -> Path:
        return project_path / ".codegraph"
