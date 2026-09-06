"""
GitNexus Adapter: AST-based structural code intelligence, call graphs, execution tracing, and blast radius.
"""

from __future__ import annotations
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from code_chain.adapters.base import BaseGraphAdapter
from code_chain.core.models import EngineStatus


def _extract_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """Helper to extract JSON object from CLI stdout that might contain banners."""
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw_text[start : end + 1])
        except Exception:
            return None
    return None


class GitNexusAdapter(BaseGraphAdapter):
    """Adapter for GitNexus code intelligence engine."""

    def __init__(self, bin_path: str, project_path: Path):
        super().__init__(bin_path, project_path)
        self.nexus_dir = self.project_path / ".gitnexus"

    def get_status(self) -> EngineStatus:
        if not self.nexus_dir.exists():
            return EngineStatus(
                engine_name="gitnexus",
                available=True,
                indexed=False,
                index_path=str(self.nexus_dir),
                node_count=0,
                edge_count=0,
                details={"status": "not_indexed"},
            )

        try:
            res = subprocess.run(
                [self.bin_path, "status"],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=15,
            )
            is_ready = res.returncode == 0
            return EngineStatus(
                engine_name="gitnexus",
                available=True,
                indexed=is_ready,
                index_path=str(self.nexus_dir),
                details={"raw_status": res.stdout.strip()},
            )
        except Exception as e:
            return EngineStatus(
                engine_name="gitnexus",
                available=True,
                indexed=self.nexus_dir.exists(),
                index_path=str(self.nexus_dir),
                error_message=str(e),
            )

    def index_project(self, timeout: int = 300) -> Dict[str, Any]:
        """Indexes the repository with GitNexus (Tree-sitter AST analysis)."""
        cmd = [self.bin_path, "analyze", str(self.project_path)]
        result = subprocess.run(
            cmd,
            cwd=str(self.project_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        success = result.returncode == 0 and self.nexus_dir.exists()
        return {
            "success": success,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "nexus_dir": str(self.nexus_dir),
        }

    def query_concepts(self, search_query: str) -> Dict[str, Any]:
        """Searches the knowledge graph for execution flows related to a concept."""
        try:
            res = subprocess.run(
                [self.bin_path, "query", search_query],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=20,
            )
            parsed = _extract_json(res.stdout)
            if parsed:
                return parsed
        except Exception:
            pass
        return {"processes": [], "definitions": []}

    def get_symbol_context(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves 360-degree view of a code symbol: callers, callees, processes."""
        try:
            res = subprocess.run(
                [self.bin_path, "context", symbol_name],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=20,
            )
            return _extract_json(res.stdout)
        except Exception:
            return None

    def analyze_impact(self, target_symbol: str) -> Dict[str, Any]:
        """Blast radius analysis: what breaks if you change a symbol."""
        try:
            res = subprocess.run(
                [self.bin_path, "impact", target_symbol],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            parsed = _extract_json(res.stdout)
            if parsed:
                return parsed
        except Exception:
            pass
        return {
            "impactedCount": 0,
            "risk": "UNKNOWN",
            "affected_processes": [],
            "affected_modules": [],
            "byDepth": {},
        }

    def trace_path(self, from_symbol: str, to_symbol: str) -> Optional[Dict[str, Any]]:
        """Find the shortest directed execution path between two symbols."""
        try:
            res = subprocess.run(
                [self.bin_path, "trace", from_symbol, to_symbol],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=25,
            )
            return _extract_json(res.stdout)
        except Exception:
            return None

    def detect_changes(self) -> Dict[str, Any]:
        """Maps git diff hunks to indexed symbols and affected execution flows."""
        try:
            res = subprocess.run(
                [self.bin_path, "detect-changes"],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=25,
            )
            parsed = _extract_json(res.stdout)
            if parsed:
                return parsed
            return {"raw_output": res.stdout}
        except Exception as e:
            return {"error": str(e)}
