"""
Unified Pydantic models representing knowledge entities across Graphify, GitNexus, and CodeGraph.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EngineStatus(BaseModel):
    engine_name: str
    available: bool = False
    indexed: bool = False
    index_path: str | None = None
    node_count: int = 0
    edge_count: int = 0
    details: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class ProjectGraphStatus(BaseModel):
    project_path: str
    graphify: EngineStatus
    gitnexus: EngineStatus
    codegraph: EngineStatus
    all_ready: bool = False
    ready_count: int = 0


class CrossDomainEntity(BaseModel):
    """Tier 1 entity from Graphify: Multi-modal project artifacts (docs, schemas, code hubs)."""

    id: str
    name: str
    entity_type: str = "code"  # code, doc, schema, config, community
    source_path: str | None = None
    line_number: int | None = None
    community_id: int | None = None
    community_name: str | None = None
    degree: int = 0
    connections: list[dict[str, Any]] = Field(default_factory=list)
    description: str | None = None


class ExecutionFlow(BaseModel):
    """Tier 2 entity from GitNexus: Structural AST execution flows and blast radius."""

    id: str
    name: str
    entity_type: str = "Function"  # Function, Method, Class, Process
    file_path: str
    upstream_callers: list[dict[str, Any]] = Field(default_factory=list)
    downstream_callees: list[dict[str, Any]] = Field(default_factory=list)
    impacted_count: int = 0
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    affected_processes: list[dict[str, Any]] = Field(default_factory=list)
    affected_modules: list[str] = Field(default_factory=list)
    execution_steps: list[dict[str, Any]] = Field(default_factory=list)


class SymbolDetail(BaseModel):
    """Tier 3 entity from CodeGraph: Precision symbol definitions, code blocks, test impacts."""

    name: str
    kind: str = "function"  # function, class, interface, type, variable
    file_path: str
    line_number: int | None = None
    source_snippet: str | None = None
    callers: list[dict[str, Any]] = Field(default_factory=list)
    callees: list[dict[str, Any]] = Field(default_factory=list)
    affected_test_files: list[str] = Field(default_factory=list)


class ChainedQueryResult(BaseModel):
    """Combined 3-tier intelligence query result."""

    query: str
    project_path: str
    tier1_cross_domain: list[CrossDomainEntity] = Field(default_factory=list)
    tier2_execution_flows: list[ExecutionFlow] = Field(default_factory=list)
    tier3_symbols: list[SymbolDetail] = Field(default_factory=list)
    synthesized_context: str = ""


class ChainedImpactResult(BaseModel):
    """Combined 3-tier blast radius and refactor impact result."""

    target_symbol: str
    project_path: str
    risk_level: str = "LOW"
    blast_radius_count: int = 0
    # ok | empty | error | ambiguous_unresolved
    outcome: str = "ok"
    resolved_uid: str | None = None
    affected_modules: list[str] = Field(default_factory=list)
    affected_processes: list[str] = Field(default_factory=list)
    affected_tests: list[str] = Field(default_factory=list)
    call_hierarchy: list[dict[str, Any]] = Field(default_factory=list)
    associated_docs_and_schemas: list[CrossDomainEntity] = Field(default_factory=list)
    recommended_refactor_steps: list[str] = Field(default_factory=list)
    synthesized_report: str = ""


class ChainedTraceStep(BaseModel):
    step_number: int
    symbol_name: str
    file_path: str
    relation_to_next: str | None = None
    source_snippet: str | None = None
    domain_tags: list[str] = Field(default_factory=list)


class ChainedTraceResult(BaseModel):
    """Combined 3-tier execution flow trace between two symbols."""

    from_symbol: str
    to_symbol: str
    project_path: str
    path_found: bool = False
    path_length: int = 0
    steps: list[ChainedTraceStep] = Field(default_factory=list)
    cross_domain_touchpoints: list[str] = Field(default_factory=list)
    synthesized_flow: str = ""
