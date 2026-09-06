"""
Unified Pydantic models representing knowledge entities across Graphify, GitNexus, and CodeGraph.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class EngineStatus(BaseModel):
    engine_name: str
    available: bool = False
    indexed: bool = False
    index_path: Optional[str] = None
    node_count: int = 0
    edge_count: int = 0
    details: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


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
    source_path: Optional[str] = None
    line_number: Optional[int] = None
    community_id: Optional[int] = None
    community_name: Optional[str] = None
    degree: int = 0
    connections: List[Dict[str, Any]] = Field(default_factory=list)
    description: Optional[str] = None


class ExecutionFlow(BaseModel):
    """Tier 2 entity from GitNexus: Structural AST execution flows and blast radius."""

    id: str
    name: str
    entity_type: str = "Function"  # Function, Method, Class, Process
    file_path: str
    upstream_callers: List[Dict[str, Any]] = Field(default_factory=list)
    downstream_callees: List[Dict[str, Any]] = Field(default_factory=list)
    impacted_count: int = 0
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    affected_processes: List[Dict[str, Any]] = Field(default_factory=list)
    affected_modules: List[str] = Field(default_factory=list)
    execution_steps: List[Dict[str, Any]] = Field(default_factory=list)


class SymbolDetail(BaseModel):
    """Tier 3 entity from CodeGraph: Precision symbol definitions, code blocks, test impacts."""

    name: str
    kind: str = "function"  # function, class, interface, type, variable
    file_path: str
    line_number: Optional[int] = None
    source_snippet: Optional[str] = None
    callers: List[Dict[str, Any]] = Field(default_factory=list)
    callees: List[Dict[str, Any]] = Field(default_factory=list)
    affected_test_files: List[str] = Field(default_factory=list)


class ChainedQueryResult(BaseModel):
    """Combined 3-tier intelligence query result."""

    query: str
    project_path: str
    tier1_cross_domain: List[CrossDomainEntity] = Field(default_factory=list)
    tier2_execution_flows: List[ExecutionFlow] = Field(default_factory=list)
    tier3_symbols: List[SymbolDetail] = Field(default_factory=list)
    synthesized_context: str = ""


class ChainedImpactResult(BaseModel):
    """Combined 3-tier blast radius and refactor impact result."""

    target_symbol: str
    project_path: str
    risk_level: str = "LOW"
    blast_radius_count: int = 0
    affected_modules: List[str] = Field(default_factory=list)
    affected_processes: List[str] = Field(default_factory=list)
    affected_tests: List[str] = Field(default_factory=list)
    call_hierarchy: List[Dict[str, Any]] = Field(default_factory=list)
    associated_docs_and_schemas: List[CrossDomainEntity] = Field(default_factory=list)
    recommended_refactor_steps: List[str] = Field(default_factory=list)
    synthesized_report: str = ""


class ChainedTraceStep(BaseModel):
    step_number: int
    symbol_name: str
    file_path: str
    relation_to_next: Optional[str] = None
    source_snippet: Optional[str] = None
    domain_tags: List[str] = Field(default_factory=list)


class ChainedTraceResult(BaseModel):
    """Combined 3-tier execution flow trace between two symbols."""

    from_symbol: str
    to_symbol: str
    project_path: str
    path_found: bool = False
    path_length: int = 0
    steps: List[ChainedTraceStep] = Field(default_factory=list)
    cross_domain_touchpoints: List[str] = Field(default_factory=list)
    synthesized_flow: str = ""
