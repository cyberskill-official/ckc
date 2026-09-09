"""
Trace Pipeline: Chains GitNexus (Directed AST Trace), CodeGraph (Source Signatures), and
Graphify (Domain Tags).
"""

from __future__ import annotations

from pathlib import Path

from code_chain.adapters import CodeGraphAdapter, GitNexusAdapter, GraphifyAdapter
from code_chain.core.config import ChainConfig
from code_chain.core.llm import finalize_stacked_markdown
from code_chain.core.models import ChainedTraceResult, ChainedTraceStep

_MAX_ENRICHED_HOPS = 8
_SNIPPET_CHARS = 800


def _mermaid_escape(text: str) -> str:
    """Escape labels for Mermaid node text (quotes / brackets / newlines)."""
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace('"', "'")
        .replace("[", "(")
        .replace("]", ")")
        .replace("\n", " ")
        .replace("\r", " ")
    )


class TracePipeline:
    """Orchestrates 3-tier execution flow tracing between two code symbols."""

    def __init__(self, project_path: Path, config: ChainConfig):
        self.project_path = project_path
        self.config = config
        self.graphify = GraphifyAdapter(config.graphify_bin, project_path)
        self.gitnexus = GitNexusAdapter(config.gitnexus_bin, project_path)
        self.codegraph = CodeGraphAdapter(config.codegraph_bin, project_path)

    def run(self, from_symbol: str, to_symbol: str, use_llm: bool = True) -> ChainedTraceResult:
        # Tier 1: GitNexus AST Trace
        trace_data = self.gitnexus.trace_path(from_symbol, to_symbol)
        if not trace_data or trace_data.get("status") != "ok":
            # Fallback to Graphify path if GitNexus doesn't find a direct AST path.
            # Graphify returns free-text stdout — not structured hops — so path_found
            # stays False; keep the Graphify text under a clear heading.
            g_path = self.graphify.find_path(from_symbol, to_symbol)
            lines = [
                f"# Execution Trace: `{from_symbol}` ➔ `{to_symbol}`",
                "",
                "> No directed execution path found in GitNexus AST.",
                "",
            ]
            if g_path:
                lines.extend(
                    [
                        "## Graphify fallback",
                        "",
                        g_path,
                        "",
                    ]
                )
            else:
                lines.extend(
                    [
                        "## Graphify fallback",
                        "",
                        "No path found in project graph.",
                        "",
                    ]
                )
            synthesis = finalize_stacked_markdown(
                "\n".join(lines),
                task="trace",
                enabled=use_llm,
                max_tokens_budget=self.config.max_tokens_budget,
                query_timeout=self.config.query_timeout,
            )
            engine_errors = self._collect_engine_errors()
            outcome = "partial_error" if engine_errors else "empty"
            return ChainedTraceResult(
                from_symbol=from_symbol,
                to_symbol=to_symbol,
                project_path=str(self.project_path),
                path_found=False,
                path_length=0,
                steps=[],
                synthesized_flow=synthesis,
                outcome=outcome,
                engine_errors=engine_errors,
            )

        hops = trace_data.get("hops", [])
        edges = trace_data.get("edges", [])
        steps: list[ChainedTraceStep] = []
        cross_domain_touchpoints: list[str] = []
        codegraph_ready = self.codegraph.get_status().indexed

        # Tier 2 & 3: Enrich each hop with CodeGraph code context & Graphify domain tags
        for i, hop in enumerate(hops):
            name = hop.get("name", f"step_{i}")
            file_path = hop.get("filePath", "")
            rel = edges[i].get("relType", "CALLS") if i < len(edges) else None

            # Check Graphify for domain artifacts
            domain_entities = self.graphify.find_cross_domain_entities(name, limit=2)
            tags = [f"{e.entity_type}:{e.name}" for e in domain_entities if e.entity_type != "code"]
            cross_domain_touchpoints.extend(tags)

            snippet = None
            if codegraph_ready and i < _MAX_ENRICHED_HOPS:
                node_text = self.codegraph.get_node(name)
                if node_text and not node_text.startswith("Node error:"):
                    snippet = node_text[:_SNIPPET_CHARS]
                    if len(node_text) > _SNIPPET_CHARS:
                        snippet = snippet.rstrip() + "…"

            step = ChainedTraceStep(
                step_number=i + 1,
                symbol_name=name,
                file_path=file_path,
                relation_to_next=rel,
                source_snippet=snippet,
                domain_tags=tags,
            )
            steps.append(step)

        # Tier 4: Mermaid Diagram & Synthesis
        diagram_lines = ["```mermaid", "graph TD"]
        for i in range(len(steps) - 1):
            s_curr = steps[i]
            s_next = steps[i + 1]
            rel_label = _mermaid_escape(s_curr.relation_to_next or "CALLS")
            curr_label = _mermaid_escape(f"{s_curr.symbol_name} ({s_curr.file_path})")
            next_label = _mermaid_escape(f"{s_next.symbol_name} ({s_next.file_path})")
            diagram_lines.append(
                f'  n{i}["{curr_label}"] -->|{rel_label}| n{i + 1}["{next_label}"]'
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
            report_lines.append(
                f"{s.step_number}. **`{s.symbol_name}`** (`{s.file_path}`){rel_str}{tag_str}"
            )
            if s.source_snippet:
                report_lines.append("")
                report_lines.append("```")
                report_lines.append(s.source_snippet)
                report_lines.append("```")
                report_lines.append("")

        report_lines.append("")
        synthesis = finalize_stacked_markdown(
            "\n".join(report_lines),
            task="trace",
            enabled=use_llm,
            max_tokens_budget=self.config.max_tokens_budget,
            query_timeout=self.config.query_timeout,
        )

        engine_errors = self._collect_engine_errors()
        outcome = "partial_error" if engine_errors else "ok"

        return ChainedTraceResult(
            from_symbol=from_symbol,
            to_symbol=to_symbol,
            project_path=str(self.project_path),
            path_found=True,
            path_length=len(steps),
            steps=steps,
            cross_domain_touchpoints=list(set(cross_domain_touchpoints)),
            synthesized_flow=synthesis,
            outcome=outcome,
            engine_errors=engine_errors,
        )

    def _collect_engine_errors(self) -> dict[str, str]:
        errors: dict[str, str] = {}
        for name, adapter in (
            ("graphify", self.graphify),
            ("gitnexus", self.gitnexus),
            ("codegraph", self.codegraph),
        ):
            take = getattr(adapter, "take_error", None)
            if not callable(take):
                continue
            err = take()
            if isinstance(err, str) and err.strip():
                errors[name] = err
        return errors
