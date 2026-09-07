"""
Graphify Adapter: Extracts and queries broad project knowledge graphs (multi-modal: docs,
schemas, code hubs).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from code_chain.adapters.base import BaseGraphAdapter
from code_chain.core.docs_index import load_docs_index, local_docs_count
from code_chain.core.models import CrossDomainEntity, EngineStatus

_NON_CODE_RESERVE = 2
_DOC_SUFFIXES = (".md", ".mdx", ".rst", ".adoc")


def classify_entity_type(source_file: str, file_type: str, label: str = "") -> str:
    """Map Graphify nodes to CKC types. SQL files are schemas, not generic code."""
    raw = (file_type or "code").strip().lower() or "code"
    if raw in {"schema", "doc", "config"}:
        return raw
    if raw == "sql":
        return "schema"
    source = (source_file or "").replace("\\", "/").lower()
    if source.endswith(".sql"):
        return "schema"
    if source.endswith(_DOC_SUFFIXES):
        return "doc"
    if (label or "").lower().startswith("public."):
        return "schema"
    return raw


def entity_match_score(
    query_terms: list[str],
    label: str,
    node_id: str,
    source_file: str,
    entity_type: str,
) -> int:
    searchable = f"{label} {node_id} {source_file} {entity_type}".lower()
    score = sum(1 for term in query_terms if term in searchable)
    label_l = (label or "").lower()
    if entity_type == "schema" and any(
        term == label_l or label_l.endswith("." + term) for term in query_terms
    ):
        score += 2
    return score


def select_mixed_entities(
    ranked: list[tuple[int, CrossDomainEntity]], limit: int
) -> list[CrossDomainEntity]:
    """Keep match-score order, but reserve slots for docs/schemas when they hit."""
    if limit <= 0 or not ranked:
        return []
    others = [entity for _score, entity in ranked if entity.entity_type != "code"]
    code = [entity for _score, entity in ranked if entity.entity_type == "code"]
    reserved = min(_NON_CODE_RESERVE, len(others), limit)
    selected: list[CrossDomainEntity] = others[:reserved]
    seen = {entity.id for entity in selected}
    for entity in code:
        if len(selected) >= limit:
            break
        if entity.id in seen:
            continue
        selected.append(entity)
        seen.add(entity.id)
    for entity in others[reserved:]:
        if len(selected) >= limit:
            break
        if entity.id in seen:
            continue
        selected.append(entity)
        seen.add(entity.id)
    return selected


class GraphifyAdapter(BaseGraphAdapter):
    """Adapter for Graphify knowledge graph engine."""

    def __init__(self, bin_path: str, project_path: Path):
        super().__init__(bin_path, project_path)
        self.output_dir = self.project_path / "graphify-out"
        self.graph_json_path = self.output_dir / "graph.json"

    def _bin_available(self) -> bool:
        return bool(shutil.which(self.bin_path) or Path(self.bin_path).is_file())

    def get_status(self) -> EngineStatus:
        available = self._bin_available()
        docs_count = local_docs_count(self.project_path)
        if not self.graph_json_path.exists():
            return EngineStatus(
                engine_name="graphify",
                available=available,
                indexed=False,
                index_path=str(self.graph_json_path),
                node_count=0,
                edge_count=0,
                details={
                    "status": "not_indexed",
                    "local_docs_count": docs_count,
                },
            )

        try:
            with open(self.graph_json_path, encoding="utf-8") as f:
                data = json.load(f)
            nodes = data.get("nodes", [])
            links = data.get("links", [])
            communities = set(n.get("community") for n in nodes if "community" in n)
            return EngineStatus(
                engine_name="graphify",
                available=available,
                indexed=True,
                index_path=str(self.graph_json_path),
                node_count=len(nodes),
                edge_count=len(links),
                details={
                    "status": "ready",
                    "communities_count": len(communities),
                    "built_at_commit": data.get("built_at_commit", "unknown"),
                    "local_docs_count": docs_count,
                },
            )
        except Exception as e:
            return EngineStatus(
                engine_name="graphify",
                available=available,
                indexed=False,
                index_path=str(self.graph_json_path),
                error_message=f"Error reading graph.json: {e!s}",
                details={"local_docs_count": docs_count},
            )

    def _extract_cmd(self, code_only: bool = True) -> list:
        cmd = [self.bin_path, "extract", str(self.project_path)]
        if code_only:
            cmd.append("--code-only")
        else:
            from code_chain.core.llm import resolve_llm_config

            llm_cfg = resolve_llm_config()
            has_cloud_key = any(
                os.getenv(k)
                for k in (
                    "GEMINI_API_KEY",
                    "GOOGLE_API_KEY",
                    "ANTHROPIC_API_KEY",
                    "OPENAI_API_KEY",
                    "DEEPSEEK_API_KEY",
                    "MOONSHOT_API_KEY",
                )
            )
            if llm_cfg:
                base_url, model, api_key = llm_cfg
                cmd.extend(["--backend", "openai", "--max-concurrency", "1"])
                if model and model != "local-model":
                    cmd.extend(["--model", model])
                os.environ.setdefault("OPENAI_BASE_URL", base_url)
                os.environ.setdefault("OPENAI_MODEL", model)
                os.environ.setdefault("OPENAI_API_KEY", api_key)
            elif not has_cloud_key:
                cmd.append("--code-only")
        return cmd

    def index_project(self, code_only: bool = True, timeout: int = 300) -> dict[str, Any]:
        """Runs graphify extraction on the target project."""
        cmd = self._extract_cmd(code_only)
        result = subprocess.run(
            cmd,
            cwd=str(self.project_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=os.environ,
        )

        success = result.returncode == 0 and self.graph_json_path.exists()
        return {
            "success": success,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "graph_json_path": str(self.graph_json_path),
        }

    def load_graph_data(self) -> dict[str, Any]:
        if not self.graph_json_path.exists():
            return {"nodes": [], "links": []}
        try:
            with open(self.graph_json_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"nodes": [], "links": []}

    def find_cross_domain_entities(self, query: str, limit: int = 10) -> list[CrossDomainEntity]:
        """Search for cross-domain entities (docs, schemas, code hubs) matching the query."""
        data = self.load_graph_data()
        nodes = data.get("nodes", [])
        links = data.get("links", [])

        # Build adjacency degree map
        node_degrees: dict[str, int] = {}
        node_connections: dict[str, list[dict[str, Any]]] = {}
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

        ranked: list[tuple[int, CrossDomainEntity]] = []

        for n in nodes:
            label = n.get("label", "")
            node_id = n.get("id", "")
            source_file = n.get("source_file", "")
            entity_type = classify_entity_type(source_file, n.get("file_type", "code"), label)
            score = entity_match_score(query_terms, label, node_id, source_file, entity_type)
            if score <= 0:
                continue
            entity = CrossDomainEntity(
                id=node_id,
                name=label,
                entity_type=entity_type,
                source_path=source_file,
                line_number=int(n.get("source_location", "L0").replace("L", ""))
                if "L" in str(n.get("source_location", ""))
                else None,
                community_id=n.get("community"),
                degree=node_degrees.get(node_id, 0),
                connections=node_connections.get(node_id, [])[:8],
                description=(
                    f"Community {n.get('community')}, {entity_type} artifact in {source_file}"
                ),
            )
            ranked.append((score, entity))

        # Merge local markdown overlay (code-only Graphify skips docs).
        overlay = load_docs_index(self.project_path)
        seen_paths = {
            (entity.source_path or "").replace("\\", "/").lower() for _score, entity in ranked
        }
        for doc in overlay.get("docs") or []:
            if not isinstance(doc, dict):
                continue
            source_file = str(doc.get("source_path") or "")
            label = str(doc.get("name") or source_file)
            node_id = str(doc.get("id") or f"local-doc:{source_file}")
            entity_type = "doc"
            score = entity_match_score(query_terms, label, node_id, source_file, entity_type)
            excerpt = str(doc.get("excerpt") or "")
            if score <= 0 and excerpt:
                searchable = excerpt.lower()
                score = sum(1 for term in query_terms if term in searchable)
            if score <= 0:
                continue
            norm = source_file.replace("\\", "/").lower()
            if norm and norm in seen_paths:
                continue
            if norm:
                seen_paths.add(norm)
            entity = CrossDomainEntity(
                id=node_id,
                name=label,
                entity_type=entity_type,
                source_path=source_file,
                community_id=None,
                degree=0,
                connections=[],
                description=excerpt or f"Local documentation overlay: {source_file}",
            )
            ranked.append((score, entity))

        ranked.sort(key=lambda pair: (pair[0], pair[1].degree), reverse=True)
        return select_mixed_entities(ranked, limit)

    def explain_node(self, node_label: str) -> str | None:
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
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None

    def find_path(self, from_node: str, to_node: str) -> str | None:
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
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None
