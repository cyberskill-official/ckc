"""
Impact Pipeline: Chains GitNexus (Blast Radius), CodeGraph (Source & Tests), and Graphify (Docs & Schemas).
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
from code_chain.core.config import ChainConfig
from code_chain.core.models import ChainedImpactResult, CrossDomainEntity
from code_chain.adapters import GraphifyAdapter, GitNexusAdapter, CodeGraphAdapter


class ImpactPipeline:
    """Orchestrates 3-tier impact and blast-radius analysis for safe refactoring."""

    def __init__(self, project_path: Path, config: ChainConfig):
        self.project_path = project_path
        self.config = config
        self.graphify = GraphifyAdapter(config.graphify_bin, project_path)
        self.gitnexus = GitNexusAdapter(config.gitnexus_bin, project_path)
        self.codegraph = CodeGraphAdapter(config.codegraph_bin, project_path)

    def run(self, target_symbol: str) -> ChainedImpactResult:
        # Tier 1: GitNexus AST Blast Radius Analysis
        impact_data = self.gitnexus.analyze_impact(target_symbol)
        risk = impact_data.get("risk", "LOW")
        impacted_count = impact_data.get("impactedCount", 0)

        affected_procs = [p.get("name", "") for p in impact_data.get("affected_processes", [])]
        affected_mods = [m.get("name", "") for m in impact_data.get("affected_modules", [])]

        # Extract depth-based call hierarchy
        call_hierarchy: List[Dict[str, Any]] = []
        by_depth = impact_data.get("byDepth", {})
        for depth, items in by_depth.items():
            for item in items:
                call_hierarchy.append({
                    "depth": depth,
                    "symbol": item.get("name"),
                    "file": item.get("filePath"),
                    "relation": item.get("relationType", "CALLS"),
                })

        # Tier 2: CodeGraph Precision Symbol, Callers/Callees & Affected Tests
        cg_node_str = self.codegraph.get_node(target_symbol)
        cg_callers = self.codegraph.get_callers(target_symbol)
        cg_callees = self.codegraph.get_callees(target_symbol)
        affected_tests = self.codegraph.get_affected_tests()

        # Tier 3: Graphify Documentation, Database Schemas & Community Coupling
        docs_and_schemas = self.graphify.find_cross_domain_entities(target_symbol, limit=5)
        graphify_explanation = self.graphify.explain_node(target_symbol)

        # Tier 4: Synthesis & Recommended Refactoring Steps
        steps: List[str] = [
            f"Review `{target_symbol}` definition and internal logic before modifying.",
        ]
        if call_hierarchy:
            steps.append(
                f"Update or verify {len(call_hierarchy)} upstream caller(s): "
                + ", ".join([f"`{c['symbol']}` ({c['file']})" for c in call_hierarchy[:3]])
            )
        if affected_tests:
            steps.append(f"Execute affected test suite: {', '.join(affected_tests[:3])}")
        else:
            steps.append("Create unit tests covering this symbol to prevent regression.")

        doc_names = [d.source_path for d in docs_and_schemas if d.entity_type in ["doc", "schema"]]
        if doc_names:
            steps.append(f"Update associated documentation / schemas: {', '.join(doc_names[:2])}")

        report = self._build_report(
            target_symbol=target_symbol,
            risk=risk,
            impacted_count=impacted_count,
            affected_procs=affected_procs,
            affected_mods=affected_mods,
            call_hierarchy=call_hierarchy,
            cg_node_str=cg_node_str,
            cg_callers=cg_callers,
            cg_callees=cg_callees,
            affected_tests=affected_tests,
            docs_and_schemas=docs_and_schemas,
            graphify_explanation=graphify_explanation,
            steps=steps,
        )

        return ChainedImpactResult(
            target_symbol=target_symbol,
            project_path=str(self.project_path),
            risk_level=risk,
            blast_radius_count=impacted_count,
            affected_modules=affected_mods,
            affected_processes=affected_procs,
            affected_tests=affected_tests,
            call_hierarchy=call_hierarchy,
            associated_docs_and_schemas=docs_and_schemas,
            recommended_refactor_steps=steps,
            synthesized_report=report,
        )

    def _build_report(
        self,
        target_symbol: str,
        risk: str,
        impacted_count: int,
        affected_procs: List[str],
        affected_mods: List[str],
        call_hierarchy: List[Dict[str, Any]],
        cg_node_str: str,
        cg_callers: List[Dict[str, Any]],
        cg_callees: List[Dict[str, Any]],
        affected_tests: List[str],
        docs_and_schemas: List[CrossDomainEntity],
        graphify_explanation: Optional[str],
        steps: List[str],
    ) -> str:
        lines = []
        lines.append(f"# Refactor Blast Radius & Impact Report: `{target_symbol}`")
        lines.append("")
        risk_badge = f"🟢 **{risk} RISK**" if risk == "LOW" else f"🟡 **{risk} RISK**" if risk == "MEDIUM" else f"🔴 **{risk} RISK**"
        lines.append(f"> Assessment: {risk_badge} | Blast Radius: **{impacted_count} dependent component(s)**")
        lines.append("")

        # 1. Structural Blast Radius (GitNexus)
        lines.append("## 1. Structural Blast Radius (GitNexus AST Engine)")
        if call_hierarchy:
            lines.append("### Upstream Call Hierarchy (What Breaks If Changed):")
            for c in call_hierarchy:
                lines.append(f"- Depth {c['depth']}: `{c['symbol']}` in `{c['file']}` [{c['relation']}]")
        else:
            lines.append("- *No external upstream callers detected. Localized blast radius.*")

        if affected_procs:
            lines.append(f"- **Impacted Business Processes:** {', '.join(affected_procs)}")
        if affected_mods:
            lines.append(f"- **Impacted Architectural Clusters:** {', '.join(affected_mods)}")
        lines.append("")

        # 2. Symbol Signature & Immediate Neighbors (CodeGraph)
        lines.append("## 2. Symbol Signature & Precision Callers (CodeGraph)")
        if cg_node_str:
            lines.append(cg_node_str)
        if cg_callers:
            lines.append(f"**Direct Callers:** " + ", ".join([f"`{c['name']}` ({c.get('location', '')})" for c in cg_callers]))
        if cg_callees:
            lines.append(f"**Direct Callees:** " + ", ".join([f"`{c['name']}` ({c.get('location', '')})" for c in cg_callees]))
        if affected_tests:
            lines.append(f"**Affected Tests:** " + ", ".join([f"`{t}`" for t in affected_tests]))
        else:
            lines.append("**Affected Tests:** *No direct test files registered in call radius.*")
        lines.append("")

        # 3. Cross-Domain Knowledge & Architecture (Graphify)
        lines.append("## 3. Cross-Domain Context (Graphify)")
        if graphify_explanation:
            lines.append("```")
            lines.append(graphify_explanation)
            lines.append("```")
        elif docs_and_schemas:
            for d in docs_and_schemas:
                lines.append(f"- **{d.name}** (`{d.source_path}`): Type `{d.entity_type}`, Degree `{d.degree}`")
        else:
            lines.append("- *No external documents or schemas connected to this node.*")
        lines.append("")

        # 4. Action Plan
        lines.append("## 4. Recommended Refactoring Plan")
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")
        lines.append("")

        return "\n".join(lines)
