"""
Graphify Adapter: Extracts and queries broad project knowledge graphs (multi-modal: docs, schemas, code hubs).
"""

from __future__ import annotations
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from code_chain.adapters.base import BaseGraphAdapter
from code_chain.core.models import EngineStatus, CrossDomainEntity


class GraphifyAdapter(BaseGraphAdapter):
    """Adapter for Graphify knowledge graph engine."""

    def __init__(self, bin_path: str, project_path: Path):
        super().__init__(bin_path, project_path)
        self.output_dir = self.project_path / "graphify-out"
        self.graph_json_path = self.output_dir / "graph.json"

    def get_status(self) -> EngineStatus:
        if not self.graph_json_path.exists():
            return EngineStatus(
                engine_name="graphify",
                available=True,
                indexed=False,
                index_path=str(self.graph_json_path),
                node_count=0,
                edge_count=0,
                details={"status": "not_indexed"},
            )

        try:
            with open(self.graph_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            nodes = data.get("nodes", [])
            links = data.get("links", [])
            communities = set(n.get("community") for n in nodes if "community" in n)
            return EngineStatus(
                engine_name="graphify",
                available=True,
                indexed=True,
                index_path=str(self.graph_json_path),
                node_count=len(nodes),
                edge_count=len(links),
                details={
                    "status": "ready",
                    "communities_count": len(communities),
                    "built_at_commit": data.get("built_at_commit", "unknown"),
                },
            )
        except Exception as e:
            return EngineStatus(
                engine_name="graphify",
                available=True,
                indexed=False,
                index_path=str(self.graph_json_path),
                error_message=f"Error reading graph.json: {str(e)}",
            )

    def index_project(
        self, code_only: bool = True, timeout: int = 300
    ) -> Dict[str, Any]:
        """Runs graphify extraction on the target project."""
        cmd = [self.bin_path, "extract", str(self.project_path)]
        if code_only:
            cmd.append("--code-only")

        result = subprocess.run(
            cmd,
            cwd=str(self.project_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        success = result.returncode == 0 and self.graph_json_path.exists()
        return {
            "success": success,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "graph_json_path": str(self.graph_json_path),
        }

    def load_graph_data(self) -> Dict[str, Any]:
        if not self.graph_json_path.exists():
            return {"nodes": [], "links": []}
        try:
            with open(self.graph_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"nodes": [], "links": []}

    def find_cross_domain_entities(
        self, query: str, limit: int = 10
    ) -> List[CrossDomainEntity]:
        """Search for cross-domain entities (docs, schemas, code hubs) matching the query."""
        data = self.load_graph_data()
        nodes = data.get("nodes", [])
        links = data.get("links", [])

        # Build adjacency degree map
        node_degrees: Dict[str, int] = {}
        node_connections: Dict[str, List[Dict[str, Any]]] = {}
        for link in links:
            s = link.get("source")
            t = link.get("target")
            rel = link.get("relation", "connected")
            node_degrees[s] = node_degrees.get(s, 0) + 1
            node_degrees[t] = node_degrees.get(t, 0) + 1

            node_connections.setdefault(s, []).append({"neighbor": t, "relation": rel})
            node_connections.setdefault(t, []).append({"neighbor": s, "relation": rel})

        query_terms = [t.lower() for t in query.split() if len(t) > 2]
        if not query_terms:
            query_terms = [query.lower()]

        matched: List[CrossDomainEntity] = []

        for n in nodes:
            label = n.get("label", "")
            node_id = n.get("id", "")
            source_file = n.get("source_file", "")
            file_type = n.get("file_type", "code")

            searchable = f"{label} {node_id} {source_file} {file_type}".lower()
            score = sum(1 for term in query_terms if term in searchable)

            if score > 0:
                entity = CrossDomainEntity(
                    id=node_id,
                    name=label,
                    entity_type=file_type,
                    source_path=source_file,
                    line_number=int(n.get("source_location", "L0").replace("L", ""))
                    if "L" in str(n.get("source_location", ""))
                    else None,
                    community_id=n.get("community"),
                    degree=node_degrees.get(node_id, 0),
                    connections=node_connections.get(node_id, [])[:8],
                    description=f"Community {n.get('community')}, {file_type} artifact in {source_file}",
                )
                matched.append(entity)

        # Sort by degree and match relevance
        matched.sort(key=lambda x: x.degree, reverse=True)
        return matched[:limit]

    def explain_node(self, node_label: str) -> Optional[str]:
        """Calls `graphify explain` CLI for deep neighborhood explanation."""
        if not self.graph_json_path.exists():
            return None
        try:
            res = subprocess.run(
                [
                    self.bin_path,
                    "explain",
                    node_label,
                    "--graph",
                    str(self.graph_json_path),
                ],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None

    def find_path(self, from_node: str, to_node: str) -> Optional[str]:
        """Calls `graphify path` to find the shortest graph path."""
        if not self.graph_json_path.exists():
            return None
        try:
            res = subprocess.run(
                [
                    self.bin_path,
                    "path",
                    from_node,
                    to_node,
                    "--graph",
                    str(self.graph_json_path),
                ],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None
