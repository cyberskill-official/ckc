"""
Impact Pipeline: Chains GitNexus (Blast Radius), CodeGraph (Source & Tests), and Graphify
(Docs & Schemas).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from code_chain.adapters import CodeGraphAdapter, GitNexusAdapter, GraphifyAdapter
from code_chain.core.config import ChainConfig
from code_chain.core.llm import finalize_stacked_markdown
from code_chain.core.models import ChainedImpactResult, CrossDomainEntity

_VALID_OUTCOMES = frozenset({"ok", "empty", "error", "ambiguous_unresolved"})


class ImpactPipeline:
    """Orchestrates 3-tier impact and blast-radius analysis for safe refactoring."""

    def __init__(self, project_path: Path, config: ChainConfig):
        self.project_path = project_path
        self.config = config
        self.graphify = GraphifyAdapter(config.graphify_bin, project_path)
        self.gitnexus = GitNexusAdapter(config.gitnexus_bin, project_path)
        self.codegraph = CodeGraphAdapter(config.codegraph_bin, project_path)

    def run(self, target_symbol: str, use_llm: bool = True) -> ChainedImpactResult:
        # Tier 1: GitNexus AST Blast Radius Analysis
        impact_data = self.gitnexus.analyze_impact(target_symbol)
        risk = impact_data.get("risk") or "UNKNOWN"
        if not isinstance(risk, str):
            risk = "UNKNOWN"
        raw_count = impact_data.get("impactedCount", 0)
        impacted_count = raw_count if isinstance(raw_count, int) else 0
        raw_outcome = impact_data.get("_outcome") or "ok"
        outcome = raw_outcome if raw_outcome in _VALID_OUTCOMES else "ok"
        resolved_uid = impact_data.get("_resolved_uid")
        if not isinstance(resolved_uid, str) or not resolved_uid:
            resolved_uid = None

        raw_procs = impact_data.get("affected_processes") or []
        affected_procs = [
            (p.get("name") or "") if isinstance(p, dict) else str(p) for p in raw_procs
        ]
        raw_mods = impact_data.get("affected_modules") or []
        affected_mods = [(m.get("name") or "") if isinstance(m, dict) else str(m) for m in raw_mods]

        # Extract depth-based call hierarchy
        call_hierarchy: list[dict[str, Any]] = []
        by_depth = impact_data.get("byDepth") or {}
        if isinstance(by_depth, dict):
            for depth, items in by_depth.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    call_hierarchy.append(
                        {
                            "depth": depth,
                            "symbol": item.get("name"),
                            "file": item.get("filePath"),
                            "relation": item.get("relationType", "CALLS"),
                        }
                    )

        # Tier 2: CodeGraph Precision Symbol, Callers/Callees & Affected Tests
        cg_node_str = self.codegraph.get_node(target_symbol)
        cg_callers = self.codegraph.get_callers(target_symbol)
        cg_callees = self.codegraph.get_callees(target_symbol)
        source_files: list[str] = []
        target_meta = impact_data.get("target")
        if isinstance(target_meta, dict):
            file_path = target_meta.get("filePath")
            if isinstance(file_path, str) and file_path:
                source_files.append(file_path)
        source_files.extend(self.codegraph.extract_source_files(cg_node_str))
        unique_files = list(dict.fromkeys(source_files))
        affected_tests = self.codegraph.get_affected_tests(unique_files or None)

        # Tier 3: Graphify Documentation, Database Schemas & Community Coupling
        docs_and_schemas = self.graphify.find_cross_domain_entities(target_symbol, limit=5)
        graphify_explanation = self.graphify.explain_node(target_symbol)

        # Tier 4: Synthesis & Recommended Refactoring Steps
        steps: list[str] = [
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

        doc_names = [
            d.source_path
            for d in docs_and_schemas
            if d.entity_type in ["doc", "schema"] and d.source_path
        ]
        if doc_names:
            steps.append(f"Update associated documentation / schemas: {', '.join(doc_names[:2])}")

        report = self._build_report(
            target_symbol=target_symbol,
            risk=risk,
            impacted_count=impacted_count,
            outcome=outcome,
            resolved_uid=resolved_uid,
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
        report = finalize_stacked_markdown(
            report,
            task="impact",
            enabled=use_llm,
            max_tokens_budget=self.config.max_tokens_budget,
            query_timeout=self.config.query_timeout,
        )

        engine_errors = self._collect_engine_errors()
        if engine_errors and outcome in {"ok", "empty"}:
            outcome = "partial_error"

        return ChainedImpactResult(
            target_symbol=target_symbol,
            project_path=str(self.project_path),
            risk_level=risk,
            blast_radius_count=impacted_count,
            outcome=outcome,
            resolved_uid=resolved_uid,
            affected_modules=affected_mods,
            affected_processes=affected_procs,
            affected_tests=affected_tests,
            call_hierarchy=call_hierarchy,
            associated_docs_and_schemas=docs_and_schemas,
            recommended_refactor_steps=steps,
            synthesized_report=report,
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

    def _build_report(
        self,
        target_symbol: str,
        risk: str,
        impacted_count: int,
        outcome: str,
        resolved_uid: str | None,
        affected_procs: list[str],
        affected_mods: list[str],
        call_hierarchy: list[dict[str, Any]],
        cg_node_str: str,
        cg_callers: list[dict[str, Any]],
        cg_callees: list[dict[str, Any]],
        affected_tests: list[str],
        docs_and_schemas: list[CrossDomainEntity],
        graphify_explanation: str | None,
        steps: list[str],
    ) -> str:
        lines = []
        lines.append(f"# Refactor Blast Radius & Impact Report: `{target_symbol}`")
        lines.append("")
        risk_upper = (risk or "UNKNOWN").upper()
        if risk_upper == "LOW":
            risk_badge = f"🟢 **{risk_upper} RISK**"
        elif risk_upper == "MEDIUM":
            risk_badge = f"🟡 **{risk_upper} RISK**"
        elif risk_upper in {"HIGH", "CRITICAL"}:
            risk_badge = f"🔴 **{risk_upper} RISK**"
        else:
            # GitNexus uses UNKNOWN when no callers resolved — not an alarm.
            risk_badge = f"**{risk_upper} RISK**"
        lines.append(
            f"> Assessment: {risk_badge} | Blast Radius: "
            f"**{impacted_count} dependent component(s)**"
            f" | Outcome: `{outcome}`"
        )
        if resolved_uid:
            lines.append(f"> Resolved symbol UID: `{resolved_uid}`")
        lines.append("")

        # 1. Structural Blast Radius (GitNexus)
        lines.append("## 1. Structural Blast Radius (GitNexus AST Engine)")
        if outcome == "ambiguous_unresolved":
            lines.append("- *Ambiguous symbol matches could not be resolved to a unique UID.*")
        elif outcome == "error":
            lines.append("- *GitNexus impact analysis returned an error.*")
        elif outcome == "empty":
            lines.append("- *No impact data returned from GitNexus.*")
        elif call_hierarchy:
            lines.append("### Upstream Call Hierarchy (What Breaks If Changed):")
            for c in call_hierarchy:
                lines.append(
                    f"- Depth {c['depth']}: `{c['symbol']}` in `{c['file']}` [{c['relation']}]"
                )
        elif outcome == "ok" and impacted_count == 0:
            lines.append("- *No external upstream callers detected. Localized blast radius.*")
        else:
            lines.append("- *Upstream call hierarchy unavailable in summary payload.*")

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
            lines.append(
                "**Direct Callers:** "
                + ", ".join([f"`{c['name']}` ({c.get('location', '')})" for c in cg_callers])
            )
        if cg_callees:
            lines.append(
                "**Direct Callees:** "
                + ", ".join([f"`{c['name']}` ({c.get('location', '')})" for c in cg_callees])
            )
        if affected_tests:
            lines.append("**Affected Tests:** " + ", ".join([f"`{t}`" for t in affected_tests]))
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
                lines.append(
                    f"- **{d.name}** (`{d.source_path}`): Type `{d.entity_type}`, "
                    f"Degree `{d.degree}`"
                )
        else:
            lines.append("- *No external documents or schemas connected to this node.*")
        lines.append("")

        # 4. Action Plan
        lines.append("## 4. Recommended Refactoring Plan")
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")
        lines.append("")

        return "\n".join(lines)
