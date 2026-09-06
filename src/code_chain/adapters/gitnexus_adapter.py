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

    def _repo_args(self) -> list:
        return ["-r", str(self.project_path)]

    def _meta_stats(self) -> Dict[str, int]:
        meta_path = self.nexus_dir / "meta.json"
        if not meta_path.exists():
            return {}
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            stats = data.get("stats") or {}
            return {
                "nodes": int(stats.get("nodes") or 0),
                "edges": int(stats.get("edges") or 0),
                "communities": int(stats.get("communities") or 0),
                "processes": int(stats.get("processes") or 0),
                "files": int(stats.get("files") or 0),
            }
        except Exception:
            return {}

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

        stats = self._meta_stats()
        try:
            res = subprocess.run(
                [self.bin_path, "status", "--json"],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=15,
            )
            parsed = _extract_json(res.stdout) or {}
            status_label = parsed.get("status") or parsed.get("error") or "unknown"
            is_ready = res.returncode == 0 and status_label not in (
                "not-indexed",
                "missing",
            )
            details = {
                "status": status_label,
                "communities_count": stats.get("communities", 0),
                "processes": stats.get("processes", 0),
                "files": stats.get("files", 0),
            }
            return EngineStatus(
                engine_name="gitnexus",
                available=True,
                indexed=is_ready or bool(stats),
                index_path=str(self.nexus_dir),
                node_count=stats.get("nodes", 0),
                edge_count=stats.get("edges", 0),
                details=details,
            )
        except Exception as e:
            return EngineStatus(
                engine_name="gitnexus",
                available=True,
                indexed=self.nexus_dir.exists(),
                index_path=str(self.nexus_dir),
                node_count=stats.get("nodes", 0),
                edge_count=stats.get("edges", 0),
                error_message=str(e),
            )

    def _analyze_cmd(self) -> list:
        cmd = [
            self.bin_path,
            "analyze",
            str(self.project_path),
            "--index-only",
            "--skip-git",
        ]
        return cmd

    def index_project(self, timeout: int = 300) -> Dict[str, Any]:
        """Indexes the repository with GitNexus (Tree-sitter AST analysis)."""
        cmd = self._analyze_cmd()
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
            cmd = [self.bin_path, "query", search_query, *self._repo_args()]
            res = subprocess.run(
                cmd,
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
                [self.bin_path, "context", symbol_name, *self._repo_args()],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=20,
            )
            return _extract_json(res.stdout)
        except Exception:
            return None

    def _normalize_impact(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce GitNexus impact payloads so nulls and missing lists cannot crash callers."""
        count = parsed.get("impactedCount")
        if not isinstance(count, int):
            count = 0
        risk = parsed.get("risk")
        if not isinstance(risk, str) or not risk:
            risk = "UNKNOWN"
        if parsed.get("error"):
            count = 0
        procs = parsed.get("affected_processes")
        mods = parsed.get("affected_modules")
        by_depth = parsed.get("byDepth")
        if isinstance(by_depth, list):
            by_depth = {"1": [item for item in by_depth if isinstance(item, dict)]}
        elif not isinstance(by_depth, dict):
            by_depth = {}
        out = dict(parsed)
        out["impactedCount"] = count
        out["risk"] = risk
        out["affected_processes"] = procs if isinstance(procs, list) else []
        out["affected_modules"] = mods if isinstance(mods, list) else []
        out["byDepth"] = by_depth
        return out

    def analyze_impact(self, target_symbol: str) -> Dict[str, Any]:
        """Blast radius analysis: what breaks if you change a symbol."""
        empty = {
            "impactedCount": 0,
            "risk": "UNKNOWN",
            "affected_processes": [],
            "affected_modules": [],
            "byDepth": {},
        }
        # Summary-only stays under GitNexus's ~64KB stdout cap and is repo-scoped.
        cmd = [
            self.bin_path,
            "impact",
            target_symbol,
            *self._repo_args(),
            "--summary-only",
        ]
        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            parsed = _extract_json(res.stdout)
            if parsed:
                if not parsed.get("error"):
                    detail_cmd = [
                        self.bin_path,
                        "impact",
                        target_symbol,
                        *self._repo_args(),
                        "--depth",
                        "2",
                        "--limit",
                        "20",
                    ]
                    detail_res = subprocess.run(
                        detail_cmd,
                        cwd=str(self.project_path),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    detail = _extract_json(detail_res.stdout)
                    if detail and not detail.get("error"):
                        if detail.get("byDepth"):
                            parsed["byDepth"] = detail["byDepth"]
                        if detail.get("affected_processes"):
                            parsed["affected_processes"] = detail[
                                "affected_processes"
                            ]
                        if detail.get("affected_modules"):
                            parsed["affected_modules"] = detail["affected_modules"]
                return self._normalize_impact(parsed)
        except Exception:
            pass
        return empty

    def trace_path(self, from_symbol: str, to_symbol: str) -> Optional[Dict[str, Any]]:
        """Find the shortest directed execution path between two symbols."""
        try:
            res = subprocess.run(
                [self.bin_path, "trace", from_symbol, to_symbol, *self._repo_args()],
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
                [self.bin_path, "detect-changes", *self._repo_args()],
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
