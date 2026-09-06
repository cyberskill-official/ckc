"""
Query Pipeline: Chains Graphify (Tier 1), GitNexus (Tier 2), and CodeGraph (Tier 3) to answer developer queries.
"""

from __future__ import annotations
from pathlib import Path
from typing import List
from code_chain.core.config import ChainConfig
from code_chain.core.models import (
    ChainedQueryResult,
    CrossDomainEntity,
    ExecutionFlow,
    SymbolDetail,
)
from code_chain.adapters import GraphifyAdapter, GitNexusAdapter, CodeGraphAdapter


class QueryPipeline:
    """Orchestrates 3-tier chained querying for architectural understanding."""

    def __init__(self, project_path: Path, config: ChainConfig):
        self.project_path = project_path
        self.config = config
        self.graphify = GraphifyAdapter(config.graphify_bin, project_path)
        self.gitnexus = GitNexusAdapter(config.gitnexus_bin, project_path)
        self.codegraph = CodeGraphAdapter(config.codegraph_bin, project_path)

    def run(self, query: str) -> ChainedQueryResult:
        # Tier 1: Graphify broad cross-domain scan
        tier1_entities = self.graphify.find_cross_domain_entities(query, limit=8)

        # Tier 2: GitNexus structural execution flows
        gitnexus_data = self.gitnexus.query_concepts(query)
        tier2_flows: List[ExecutionFlow] = []

        # Parse definitions or processes found in GitNexus
        candidate_symbols = set()
        for d in gitnexus_data.get("definitions", []):
            name = d.get("name")
            if name and not name.endswith((".md", ".txt", ".json", ".sql")):
                candidate_symbols.add(name)

        # Also add symbols from tier 1 entities
        for e in tier1_entities:
            if e.entity_type == "code" and "(" not in e.name:
                candidate_symbols.add(e.name)

        # Collect execution flows for candidate symbols
        for sym in list(candidate_symbols)[:5]:
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
        raw_explore = self.codegraph.explore(query)
        tier3_symbols: List[SymbolDetail] = []
        cg_symbols = self.codegraph.query_symbols(query)

        for s in cg_symbols[:5]:
            callers = self.codegraph.get_callers(s["name"])
            callees = self.codegraph.get_callees(s["name"])
            sym_detail = SymbolDetail(
                name=s["name"],
                kind=s.get("kind", "symbol"),
                file_path=s.get("file", ""),
                line_number=s.get("line"),
                callers=callers,
                callees=callees,
            )
            tier3_symbols.append(sym_detail)

        # Tier 4: Grounded Synthesis
        synthesis = self._synthesize(query, tier1_entities, tier2_flows, raw_explore)

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
        tier1: List[CrossDomainEntity],
        tier2: List[ExecutionFlow],
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
                    [f"{c['neighbor']} ({c['relation']})" for c in ent.connections[:3]]
                )
                lines.append(
                    f"- {icon} **{ent.name}** (`{ent.source_path or 'unknown'}`)"
                )
                lines.append(
                    f"  - Type: `{ent.entity_type}`, Community: `{ent.community_id}`, Degree: `{ent.degree}`"
                )
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
        if raw_explore:
            lines.append(raw_explore)
        else:
            lines.append("- *No direct source symbols found.*")
        lines.append("")

        return "\n".join(lines)
