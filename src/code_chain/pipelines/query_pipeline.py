"""
Query Pipeline: Chains Graphify (Tier 1), GitNexus (Tier 2), and CodeGraph (Tier 3) to
answer developer queries.
"""

from __future__ import annotations

from pathlib import Path

from code_chain.adapters import CodeGraphAdapter, GitNexusAdapter, GraphifyAdapter
from code_chain.core.config import ChainConfig
from code_chain.core.llm import finalize_stacked_markdown
from code_chain.core.models import (
    ChainedQueryResult,
    CrossDomainEntity,
    ExecutionFlow,
    SymbolDetail,
)

_MAX_TIER1 = 8
_MAX_TIER2 = 5
_MAX_TIER3 = 5
_MAX_EXPLORE_CHARS = 2500
_SNIPPET_CHARS = 800
_SNIPPET_TOP_N = 2


class QueryPipeline:
    """Orchestrates 3-tier chained querying for architectural understanding."""

    def __init__(self, project_path: Path, config: ChainConfig):
        self.project_path = project_path
        self.config = config
        self.graphify = GraphifyAdapter(config.graphify_bin, project_path)
        self.gitnexus = GitNexusAdapter(config.gitnexus_bin, project_path)
        self.codegraph = CodeGraphAdapter(config.codegraph_bin, project_path)
        self._label_cache: dict[str, str] | None = None

    def _neighbor_label(self, neighbor_id: str) -> str:
        """Resolve Graphify neighbor node IDs to human-readable labels when possible."""
        if not neighbor_id:
            return neighbor_id
        if self._label_cache is None:
            self._label_cache = {}
            data = self.graphify.load_graph_data()
            for node in data.get("nodes") or []:
                nid = node.get("id")
                label = node.get("label")
                if isinstance(nid, str) and nid:
                    self._label_cache[nid] = (
                        label if isinstance(label, str) and label else nid
                    )
        return self._label_cache.get(neighbor_id, neighbor_id)

    def run(self, query: str, use_llm: bool = True) -> ChainedQueryResult:
        # Tier 1: Graphify broad cross-domain scan
        tier1_entities = self.graphify.find_cross_domain_entities(
            query, limit=_MAX_TIER1
        )

        # Tier 2: GitNexus structural execution flows
        gitnexus_data = self.gitnexus.query_concepts(query)
        tier2_flows: list[ExecutionFlow] = []

        # Deterministic candidate order (sorted), not hash-order from a set.
        candidate_symbols: list[str] = []
        seen: set = set()
        for d in gitnexus_data.get("definitions", []):
            name = d.get("name")
            if (
                name
                and not name.endswith((".md", ".txt", ".json", ".sql"))
                and name not in seen
            ):
                seen.add(name)
                candidate_symbols.append(name)

        for e in tier1_entities:
            if e.entity_type == "code" and "(" not in e.name and e.name not in seen:
                seen.add(e.name)
                candidate_symbols.append(e.name)

        candidate_symbols = sorted(candidate_symbols)
        depth_cap = min(_MAX_TIER2, max(1, self.config.max_search_depth))

        for sym in candidate_symbols[:depth_cap]:
            ctx = self.gitnexus.get_symbol_context(sym)
            if ctx and ctx.get("status") == "found":
                symbol_info = ctx.get("symbol", {})
                incoming = ctx.get("incoming", {})
                outgoing = ctx.get("outgoing", {})
                processes = ctx.get("processes", [])

                flow = ExecutionFlow(
                    id=symbol_info.get("uid", sym),
                    name=symbol_info.get("name", sym),
                    entity_type=symbol_info.get("kind", "Symbol"),
                    file_path=symbol_info.get("filePath", ""),
                    upstream_callers=incoming.get("calls", [])
                    + incoming.get("imports", []),
                    downstream_callees=outgoing.get("calls", [])
                    + outgoing.get("has_method", []),
                    affected_processes=processes,
                )
                tier2_flows.append(flow)

        # Tier 3: CodeGraph fine-grained source exploration and symbol definitions
        raw_explore = self.codegraph.explore(query) or ""
        if len(raw_explore) > _MAX_EXPLORE_CHARS:
            raw_explore = (
                raw_explore[:_MAX_EXPLORE_CHARS].rstrip()
                + "\n… *(explore output truncated)*\n"
            )
        tier3_symbols: list[SymbolDetail] = []
        cg_symbols = self.codegraph.query_symbols(query)

        for idx, s in enumerate(cg_symbols[:_MAX_TIER3]):
            callers = self.codegraph.get_callers(s["name"])
            callees = self.codegraph.get_callees(s["name"])
            snippet = None
            if idx < _SNIPPET_TOP_N:
                node_text = self.codegraph.get_node(s["name"])
                if node_text and not node_text.startswith("Node error:"):
                    snippet = node_text[:_SNIPPET_CHARS]
                    if len(node_text) > _SNIPPET_CHARS:
                        snippet = snippet.rstrip() + "…"
            sym_detail = SymbolDetail(
                name=s["name"],
                kind=s.get("kind", "symbol"),
                file_path=s.get("file", ""),
                line_number=s.get("line"),
                source_snippet=snippet,
                callers=callers,
                callees=callees,
            )
            tier3_symbols.append(sym_detail)

        # Tier 4: Grounded Synthesis
        synthesis = self._synthesize(
            query, tier1_entities, tier2_flows, tier3_symbols, raw_explore
        )
        synthesis = finalize_stacked_markdown(
            synthesis,
            task="query",
            enabled=use_llm,
            max_tokens_budget=self.config.max_tokens_budget,
        )

        return ChainedQueryResult(
            query=query,
            project_path=str(self.project_path),
            tier1_cross_domain=tier1_entities,
            tier2_execution_flows=tier2_flows,
            tier3_symbols=tier3_symbols,
            synthesized_context=synthesis,
        )

    def _synthesize(
        self,
        query: str,
        tier1: list[CrossDomainEntity],
        tier2: list[ExecutionFlow],
        tier3: list[SymbolDetail],
        raw_explore: str,
    ) -> str:
        lines = []
        lines.append(f"# Chained Code Intelligence: '{query}'")
        lines.append("")
        lines.append(
            "> Generated via 3-Tier Chained Knowledge Graph (Graphify + GitNexus + CodeGraph)"
        )
        lines.append("")

        # 1. Broad Cross-Domain Knowledge (Graphify)
        lines.append("## 1. Project & Domain Architecture (Graphify)")
        if tier1:
            for ent in tier1:
                icon = (
                    "📄"
                    if ent.entity_type == "doc"
                    else "🗄️"
                    if ent.entity_type == "schema"
                    else "🧩"
                )
                conn_str = ", ".join(
                    [
                        f"{self._neighbor_label(str(c.get('neighbor', '')))} ({c.get('relation')})"
                        for c in ent.connections[:3]
                    ]
                )
                lines.append(
                    f"- {icon} **{ent.name}** (`{ent.source_path or 'unknown'}`)"
                )
                lines.append(
                    
                        f"  - Type: `{ent.entity_type}`, Community: `{ent.community_id}`, "
                        f"Degree: `{ent.degree}`"
                    
                )
                if ent.description and ent.entity_type == "doc":
                    lines.append(f"  - Excerpt: {ent.description}")
                if conn_str:
                    lines.append(f"  - Key Connections: {conn_str}")
        else:
            lines.append("- *No direct cross-domain documents or schemas matched.*")
        lines.append("")

        # 2. Execution Flows & Structural Call Graphs (GitNexus)
        lines.append("## 2. Structural Execution Flows (GitNexus AST)")
        if tier2:
            for flow in tier2:
                lines.append(
                    f"### Flow: `{flow.name}` ({flow.entity_type} in `{flow.file_path}`)"
                )
                if flow.upstream_callers:
                    callers = ", ".join(
                        [c.get("name", "unknown") for c in flow.upstream_callers[:4]]
                    )
                    lines.append(f"- **Invoked By (Upstream):** {callers}")
                if flow.downstream_callees:
                    callees = ", ".join(
                        [c.get("name", "unknown") for c in flow.downstream_callees[:4]]
                    )
                    lines.append(f"- **Invokes (Downstream):** {callees}")
                if flow.affected_processes:
                    procs = ", ".join(
                        [
                            p.get("label", p.get("id", "proc"))
                            for p in flow.affected_processes[:3]
                        ]
                    )
                    lines.append(f"- **Business Processes:** {procs}")
        else:
            lines.append(
                "- *No multi-hop execution flow cycles detected for this query.*"
            )
        lines.append("")

        # 3. Precision Code Blocks & Source (CodeGraph)
        lines.append("## 3. Precision Source Context (CodeGraph)")
        if tier3:
            for sym in tier3:
                loc = sym.file_path or "unknown"
                if sym.line_number:
                    loc = f"{loc}:{sym.line_number}"
                lines.append(f"### `{sym.name}` ({sym.kind} at `{loc}`)")
                if sym.source_snippet:
                    lines.append("")
                    lines.append("```")
                    lines.append(sym.source_snippet)
                    lines.append("```")
                    lines.append("")
                if sym.callers:
                    caller_names = ", ".join(
                        c.get("name", "?") for c in sym.callers[:5]
                    )
                    lines.append(f"- **Callers:** {caller_names}")
                if sym.callees:
                    callee_names = ", ".join(
                        c.get("name", "?") for c in sym.callees[:5]
                    )
                    lines.append(f"- **Callees:** {callee_names}")
        if raw_explore:
            if tier3:
                lines.append("")
                lines.append("#### Explore output")
            lines.append(raw_explore)
        elif not tier3:
            lines.append("- *No direct source symbols found.*")
        lines.append("")

        return "\n".join(lines)
