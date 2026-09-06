"""
Indexing Pipeline: Sequentially indexes a repository across Graphify, GitNexus, and CodeGraph.
"""

from __future__ import annotations
import json
import shutil
import time
from pathlib import Path
from typing import Dict, Any, Optional
from code_chain.core.config import ChainConfig
from code_chain.core.docs_index import index_docs_overlay
from code_chain.core.models import ProjectGraphStatus
from code_chain.core.paths import ensure_engine_gitignore
from code_chain.adapters import GraphifyAdapter, GitNexusAdapter, CodeGraphAdapter


class IndexPipeline:
    """Orchestrates indexing across all three graph engines."""

    def __init__(self, project_path: Path, config: ChainConfig):
        self.project_path = project_path
        self.config = config
        self.graphify = GraphifyAdapter(config.graphify_bin, project_path)
        self.gitnexus = GitNexusAdapter(config.gitnexus_bin, project_path)
        self.codegraph = CodeGraphAdapter(config.codegraph_bin, project_path)
        self.manifest_dir = project_path / ".code_chain"
        self.manifest_path = self.manifest_dir / "index_manifest.json"

    def get_status(self) -> ProjectGraphStatus:
        """Retrieves live status from all three engines."""
        s_graphify = self.graphify.get_status()
        s_gitnexus = self.gitnexus.get_status()
        s_codegraph = self.codegraph.get_status()

        ready_count = sum(
            [1 for s in [s_graphify, s_gitnexus, s_codegraph] if s.indexed]
        )
        return ProjectGraphStatus(
            project_path=str(self.project_path),
            graphify=s_graphify,
            gitnexus=s_gitnexus,
            codegraph=s_codegraph,
            all_ready=(ready_count == 3),
            ready_count=ready_count,
        )

    def _clear_engine_indexes(self) -> None:
        """Remove prior engine artifacts so a forced re-index starts clean."""
        targets = [
            self.project_path / "graphify-out",
            self.project_path / ".gitnexus",
            self.project_path / ".codegraph",
            self.manifest_dir / "docs_index.json",
            self.manifest_path,
        ]
        for target in targets:
            if not target.exists():
                continue
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                try:
                    target.unlink()
                except OSError:
                    pass

    def run(
        self, code_only: Optional[bool] = None, force: bool = False
    ) -> Dict[str, Any]:
        """Runs the full 3-engine indexing pipeline."""
        if code_only is None:
            code_only = self.config.graphify_code_only

        if force:
            print("[force] Clearing prior Graphify / GitNexus / CodeGraph indexes...")
            self._clear_engine_indexes()

        start_time = time.time()
        results: Dict[str, Any] = {
            "project_path": str(self.project_path),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "force": force,
            "code_only": code_only,
            "engines": {},
        }

        # 1. Index Graphify (Broad multi-modal & community graph)
        print(
            "[1/3] Indexing with Graphify (Holistic multi-modal & community layer)..."
        )
        t0 = time.time()
        res_graphify = self.graphify.index_project(
            code_only=code_only,
            timeout=self.config.index_timeout,
        )
        docs_overlay = index_docs_overlay(
            self.project_path, code_only=code_only, announce=True
        )
        res_graphify = {
            **res_graphify,
            "local_docs_count": docs_overlay.get("doc_count", 0),
            "docs_index_path": docs_overlay.get("path"),
        }
        t_graphify = time.time() - t0
        results["engines"]["graphify"] = {
            "success": res_graphify.get("success", False),
            "duration_seconds": round(t_graphify, 2),
            "details": res_graphify,
        }

        # 2. Index GitNexus (Structural Tree-sitter AST & call graph)
        print("[2/3] Indexing with GitNexus (Structural AST & execution flow layer)...")
        t0 = time.time()
        res_gitnexus = self.gitnexus.index_project(timeout=self.config.index_timeout)
        t_gitnexus = time.time() - t0
        results["engines"]["gitnexus"] = {
            "success": res_gitnexus.get("success", False),
            "duration_seconds": round(t_gitnexus, 2),
            "details": res_gitnexus,
        }

        # 3. Index CodeGraph (Fine-grained symbol index & fast code exploration)
        print(
            "[3/3] Indexing with CodeGraph (Symbol intelligence & test impact layer)..."
        )
        t0 = time.time()
        res_codegraph = self.codegraph.index_project(timeout=self.config.index_timeout)
        t_codegraph = time.time() - t0
        results["engines"]["codegraph"] = {
            "success": res_codegraph.get("success", False),
            "duration_seconds": round(t_codegraph, 2),
            "details": res_codegraph,
        }

        results["gitignore_entries_added"] = ensure_engine_gitignore(self.project_path)

        # Save manifest
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        total_duration = round(time.time() - start_time, 2)
        status = self.get_status()
        results["total_duration_seconds"] = total_duration
        results["status"] = status.model_dump()

        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results
