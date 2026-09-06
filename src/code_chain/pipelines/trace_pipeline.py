"""
Trace Pipeline: Chains GitNexus (Directed AST Trace), CodeGraph (Source Signatures), and Graphify (Domain Tags).
"""

from __future__ import annotations
from pathlib import Path
from typing import List
from code_chain.core.config import ChainConfig
from code_chain.core.models import ChainedTraceResult, ChainedTraceStep
from code_chain.adapters import GraphifyAdapter, GitNexusAdapter, CodeGraphAdapter


class TracePipeline:
    """Orchestrates 3-tier execution flow tracing between two code symbols."""

    def __init__(self, project_path: Path, config: ChainConfig):
        self.project_path = project_path
        self.config = config
        self.graphify = GraphifyAdapter(config.graphify_bin, project_path)
        self.gitnexus = GitNexusAdapter(config.gitnexus_bin, project_path)
        self.codegraph = CodeGraphAdapter(config.codegraph_bin, project_path)

    def run(self, from_symbol: str, to_symbol: str) -> ChainedTraceResult:
        # Tier 1: GitNexus AST Trace
        trace_data = self.gitnexus.trace_path(from_symbol, to_symbol)
        if not trace_data or trace_data.get("status") != "ok":
            # Fallback to Graphify path if GitNexus doesn't find a direct AST path
            g_path = self.graphify.find_path(from_symbol, to_symbol)
            return ChainedTraceResult(
                from_symbol=from_symbol,
                to_symbol=to_symbol,
                project_path=str(self.project_path),
                path_found=bool(g_path),
                path_length=0,
                steps=[],
                synthesized_flow=f"No directed execution path found in GitNexus AST. Graphify path check:\n{g_path or 'No path found in project graph.'}",
            )

        hops = trace_data.get("hops", [])
        edges = trace_data.get("edges", [])
        steps: List[ChainedTraceStep] = []
        cross_domain_touchpoints: List[str] = []

        # Tier 2 & 3: Enrich each hop with CodeGraph code context & Graphify domain tags
        for i, hop in enumerate(hops):
            name = hop.get("name", f"step_{i}")
            file_path = hop.get("filePath", "")
            rel = edges[i].get("relType", "CALLS") if i < len(edges) else None

            # Check Graphify for domain artifacts
            domain_entities = self.graphify.find_cross_domain_entities(name, limit=2)
            tags = [f"{e.entity_type}:{e.name}" for e in domain_entities if e.entity_type != "code"]
            cross_domain_touchpoints.extend(tags)

            step = ChainedTraceStep(
                step_number=i + 1,
                symbol_name=name,
                file_path=file_path,
                relation_to_next=rel,
                domain_tags=tags,
            )
            steps.append(step)

        # Tier 4: Mermaid Diagram & Synthesis
        diagram_lines = ["```mermaid", "graph TD"]
        for i in range(len(steps) - 1):
            s_curr = steps[i]
            s_next = steps[i + 1]
            rel_label = s_curr.relation_to_next or "CALLS"
            diagram_lines.append(
                f'  n{i}["{s_curr.symbol_name} ({s_curr.file_path})"] -->|{rel_label}| n{i+1}["{s_next.symbol_name} ({s_next.file_path})"]'
            )
        diagram_lines.append("```")

        report_lines = [
            f"# Execution Trace: `{from_symbol}` ➔ `{to_symbol}`",
            "",
            f"> Found deterministic execution path across **{len(steps)} hops**.",
            "",
            "## Execution Flow Diagram",
            "\n".join(diagram_lines),
            "",
            "## Hop-by-Hop Breakdown",
        ]

        for s in steps:
            rel_str = f" ➔ *({s.relation_to_next})*" if s.relation_to_next else " 🏁 *(Terminal)*"
            tag_str = f" [Tags: {', '.join(s.domain_tags)}]" if s.domain_tags else ""
            report_lines.append(f"{s.step_number}. **`{s.symbol_name}`** (`{s.file_path}`){rel_str}{tag_str}")

        report_lines.append("")

        return ChainedTraceResult(
            from_symbol=from_symbol,
            to_symbol=to_symbol,
            project_path=str(self.project_path),
            path_found=True,
            path_length=len(steps),
            steps=steps,
            cross_domain_touchpoints=list(set(cross_domain_touchpoints)),
            synthesized_flow="\n".join(report_lines),
        )
