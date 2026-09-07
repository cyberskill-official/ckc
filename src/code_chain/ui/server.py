"""
FastAPI Server for Code Knowledge Chain Web UI.
Provides REST and Server-Sent Events (SSE) endpoints for indexing, status, query, impact, and trace.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from code_chain.core.config import ChainConfig
from code_chain.core.docs_index import index_docs_overlay, local_docs_count
from code_chain.core.env import load_dotenv
from code_chain.core.llm import llm_public_status, resolve_llm_config
from code_chain.core.orchestrator import CodeKnowledgeChain
from code_chain.core.paths import (
    UnsafeProjectPathError,
    assert_safe_project_path,
    ensure_engine_gitignore,
)

load_dotenv()

_MAX_ARTIFACT_BYTES = 2 * 1024 * 1024  # 2 MiB

app = FastAPI(
    title="Code Knowledge Chain UI",
    description=(
        "Interactive Web Dashboard for Graphify + GitNexus + CodeGraph 3-Tier Code Intelligence"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active indexing process tracker for cancellation
_active_indexing_lock = threading.Lock()
_active_indexing_processes: dict[str, asyncio.subprocess.Process] = {}
_cancellation_flags: dict[str, bool] = {}


def validate_project_path(path_str: str) -> Path:
    """Validates that path_str is an existing project directory, not a system path."""
    try:
        return assert_safe_project_path(path_str)
    except UnsafeProjectPathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class QueryPayload(BaseModel):
    project_path: str
    query: str = Field(..., min_length=1)
    use_llm: bool = True


class ImpactPayload(BaseModel):
    project_path: str
    symbol: str = Field(..., min_length=1)
    use_llm: bool = True


class TracePayload(BaseModel):
    project_path: str
    from_symbol: str = Field(..., min_length=1)
    to_symbol: str = Field(..., min_length=1)
    use_llm: bool = True


class CancelPayload(BaseModel):
    project_path: str


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "code-knowledge-chain-ui"}


@app.get("/api/samples")
def get_samples() -> dict[str, Any]:
    """Returns bundled sample repositories with resolved absolute paths."""
    base_dir = Path(__file__).resolve().parent.parent.parent.parent / "examples"
    samples = []
    if base_dir.exists():
        for item in sorted(base_dir.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                samples.append(
                    {
                        "id": item.name,
                        "name": item.name.replace("-", " ").title(),
                        "path": str(item.resolve()),
                    }
                )
    return {"samples": samples}


@app.get("/api/status")
def get_status(
    project: str = Query(..., description="Absolute path to target project"),
):
    resolved = validate_project_path(project)
    chain = CodeKnowledgeChain(project_path=str(resolved))
    status = chain.status()

    # Check git metadata if present
    git_dir = resolved / ".git"
    git_info = {"is_git": git_dir.exists()}
    if git_dir.exists():
        try:
            head_file = git_dir / "HEAD"
            if head_file.exists():
                git_info["head"] = head_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    return {
        "status": status.model_dump(),
        "git": git_info,
        "summary": chain.export_summary(),
        "local_docs_count": local_docs_count(resolved),
        "llm": llm_public_status(),
    }


@app.post("/api/index/cancel")
def cancel_indexing(payload: CancelPayload):
    resolved = validate_project_path(payload.project_path)
    proj_key = str(resolved)
    with _active_indexing_lock:
        _cancellation_flags[proj_key] = True
        proc = _active_indexing_processes.get(proj_key)
        if proc and proc.returncode is None:
            try:
                proc.terminate()
                return {
                    "success": True,
                    "message": "Indexing process termination signal sent.",
                }
            except Exception as e:
                return {"success": False, "message": f"Error terminating process: {e}"}
    return {"success": True, "message": "No active process or already finished."}


@app.get("/api/index/stream")
async def stream_indexing(
    request: Request,
    project: str = Query(...),
    multimodal: bool = Query(False),
    force: bool = Query(False),
):
    resolved = validate_project_path(project)
    proj_key = str(resolved)
    config = ChainConfig()
    code_only = not multimodal

    async def event_generator() -> AsyncGenerator[str, None]:
        with _active_indexing_lock:
            _cancellation_flags[proj_key] = False

        yield json.dumps(
            {
                "event": "start",
                "message": f"Starting 3-tier indexing on {resolved}",
                "multimodal": multimodal,
                "force": force,
            }
        )

        if force:
            chain_force = CodeKnowledgeChain(project_path=str(resolved))
            yield json.dumps(
                {
                    "event": "log",
                    "engine": "ckc",
                    "line": "[force] Clearing prior engine indexes...",
                }
            )
            chain_force.index_pipe._clear_engine_indexes()

        # Configure Graphify extract command
        graphify_cmd = [config.graphify_bin, "extract", str(resolved)]
        if multimodal:
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
                graphify_cmd.extend(["--backend", "openai", "--max-concurrency", "1"])
                if model and model != "local-model":
                    graphify_cmd.extend(["--model", model])
                os.environ.setdefault("OPENAI_BASE_URL", base_url)
                os.environ.setdefault("OPENAI_MODEL", model)
                os.environ.setdefault("OPENAI_API_KEY", api_key)
            elif not has_cloud_key:
                graphify_cmd.append("--code-only")
                yield json.dumps(
                    {
                        "event": "log",
                        "engine": "graphify",
                        "line": (
                            "[graphify] ⚠ No LLM service or API key found; "
                            "falling back to AST code-only mode so indexing completes cleanly."
                        ),
                    }
                )
        else:
            graphify_cmd.append("--code-only")

        steps = [
            (
                "graphify",
                "Tier 1: Graphify Multi-modal & Architecture",
                graphify_cmd,
            ),
            (
                "gitnexus",
                "Tier 2: GitNexus Tree-sitter AST & Execution Flow",
                [
                    config.gitnexus_bin,
                    "analyze",
                    str(resolved),
                    "--index-only",
                    "--skip-git",
                ],
            ),
            (
                "codegraph",
                "Tier 3: CodeGraph Symbol Intelligence & Test Impact",
                [config.codegraph_bin, "init", str(resolved)],
            ),
        ]

        overall_success = True
        step_results = {}

        for step_idx, (engine, step_label, cmd) in enumerate(steps, 1):
            if _cancellation_flags.get(proj_key, False):
                yield json.dumps(
                    {"event": "cancelled", "message": "Indexing was cancelled by user."}
                )
                return

            yield json.dumps(
                {
                    "event": "step_start",
                    "step": step_idx,
                    "total_steps": 3,
                    "engine": engine,
                    "label": step_label,
                }
            )

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(resolved),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                with _active_indexing_lock:
                    _active_indexing_processes[proj_key] = proc

                # Stream stdout line by line without blocking the event loop
                assert proc.stdout is not None
                while True:
                    if _cancellation_flags.get(proj_key, False):
                        proc.terminate()
                        await proc.wait()
                        with _active_indexing_lock:
                            _active_indexing_processes.pop(proj_key, None)
                        yield json.dumps(
                            {
                                "event": "cancelled",
                                "message": f"Cancelled during {engine}.",
                            }
                        )
                        return

                    line_bytes = await proc.stdout.readline()
                    if not line_bytes:
                        break
                    clean_line = line_bytes.decode("utf-8", errors="replace").rstrip()
                    yield json.dumps(
                        {
                            "event": "log",
                            "engine": engine,
                            "line": clean_line,
                        }
                    )

                rc = await proc.wait()
                with _active_indexing_lock:
                    _active_indexing_processes.pop(proj_key, None)

                success = rc == 0
                step_results[engine] = {"success": success, "returncode": rc}
                if not success:
                    overall_success = False

                if engine == "graphify":
                    overlay = index_docs_overlay(resolved, code_only=code_only, announce=False)
                    discovered = int(overlay.get("discovered_files") or 0)
                    doc_count = int(overlay.get("doc_count") or 0)
                    step_results[engine]["local_docs_count"] = doc_count
                    if code_only:
                        yield json.dumps(
                            {
                                "event": "log",
                                "engine": "graphify",
                                "line": (
                                    f"Graphify --code-only skipped {discovered} "
                                    f"doc file(s); indexed {doc_count} local chunk(s)"
                                ),
                            }
                        )

                yield json.dumps(
                    {
                        "event": "step_finish",
                        "step": step_idx,
                        "engine": engine,
                        "success": success,
                        "returncode": rc,
                    }
                )

            except Exception as e:
                overall_success = False
                yield json.dumps(
                    {
                        "event": "step_error",
                        "step": step_idx,
                        "engine": engine,
                        "error": str(e),
                    }
                )

        gitignore_added = ensure_engine_gitignore(resolved)

        # Save manifest
        chain = CodeKnowledgeChain(project_path=str(resolved))
        status = chain.status()
        manifest_dir = resolved / ".code_chain"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = manifest_dir / "index_manifest.json"
        manifest_data = {
            "project_path": str(resolved),
            "step_results": step_results,
            "overall_success": overall_success,
            "gitignore_entries_added": gitignore_added,
            "force": force,
            "code_only": code_only,
            "status": status.model_dump(),
        }
        await asyncio.to_thread(
            manifest_file.write_text,
            json.dumps(manifest_data, indent=2),
            "utf-8",
        )

        yield json.dumps(
            {
                "event": "complete",
                "overall_success": overall_success,
                "status": status.model_dump(),
                "summary": chain.export_summary(),
            }
        )

    return EventSourceResponse(event_generator())


@app.post("/api/query")
def run_query(payload: QueryPayload):
    resolved = validate_project_path(payload.project_path)
    chain = CodeKnowledgeChain(project_path=str(resolved))
    result = chain.query(payload.query, use_llm=payload.use_llm)
    return result.model_dump()


@app.post("/api/impact")
def run_impact(payload: ImpactPayload):
    resolved = validate_project_path(payload.project_path)
    chain = CodeKnowledgeChain(project_path=str(resolved))
    result = chain.impact(payload.symbol, use_llm=payload.use_llm)
    return result.model_dump()


@app.post("/api/trace")
def run_trace(payload: TracePayload):
    resolved = validate_project_path(payload.project_path)
    chain = CodeKnowledgeChain(project_path=str(resolved))
    result = chain.trace(payload.from_symbol, payload.to_symbol, use_llm=payload.use_llm)
    return result.model_dump()


@app.get("/api/graph")
def get_graph(project: str = Query(...)):
    """Returns the Graphify knowledge graph in Cytoscape.js elements format."""
    resolved = validate_project_path(project)
    graph_file = resolved / "graphify-out" / "graph.json"
    if not graph_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Graph not yet indexed. Run indexing first.",
        )

    try:
        raw = json.loads(graph_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading graph: {e}") from e

    raw_nodes = raw.get("nodes", [])
    raw_links = raw.get("links", [])

    # Compute degree per node
    degree_map: dict[str, int] = {}
    for link in raw_links:
        src = link.get("source", "")
        tgt = link.get("target", "")
        degree_map[src] = degree_map.get(src, 0) + 1
        degree_map[tgt] = degree_map.get(tgt, 0) + 1

    # Build community metadata
    community_members: dict[int, list[str]] = {}
    for node in raw_nodes:
        c = node.get("community")
        if c is not None:
            community_members.setdefault(c, []).append(node.get("label", node.get("id", "")))

    # Transform to Cytoscape elements
    cy_nodes = []
    for node in raw_nodes:
        nid = node.get("id", "")
        file_type = node.get("file_type", "code")
        source_file = node.get("source_file", "")
        # Map file_type to semantic category
        if file_type == "rationale":
            category = "doc"
        elif source_file.endswith(".sql"):
            category = "schema"
        elif source_file.endswith((".md", ".txt", ".rst", ".adoc")):
            category = "doc"
        elif (
            ".test." in source_file
            or "_test." in source_file
            or ".spec." in source_file
            or "/test" in source_file.lower()
        ):
            category = "test"
        else:
            category = "code"

        cy_nodes.append(
            {
                "data": {
                    "id": nid,
                    "label": node.get("label", nid),
                    "category": category,
                    "file_type": file_type,
                    "community": node.get("community"),
                    "source_file": source_file,
                    "source_location": node.get("source_location"),
                    "degree": degree_map.get(nid, 0),
                    "is_callable": bool(node.get("_callable")),
                    "is_class": bool(node.get("_callable_class")),
                }
            }
        )

    cy_edges = []
    for i, link in enumerate(raw_links):
        cy_edges.append(
            {
                "data": {
                    "id": f"e{i}",
                    "source": link.get("source", ""),
                    "target": link.get("target", ""),
                    "relation": link.get("relation", "references"),
                    "source_file": link.get("source_file", ""),
                    "weight": link.get("weight", 1.0),
                }
            }
        )

    communities_summary = [
        {
            "id": cid,
            "size": len(members),
            "sample_labels": members[:5],
        }
        for cid, members in sorted(community_members.items())
    ]

    return {
        "project_path": str(resolved),
        "elements": {"nodes": cy_nodes, "edges": cy_edges},
        "meta": {
            "node_count": len(cy_nodes),
            "edge_count": len(cy_edges),
            "community_count": len(communities_summary),
            "communities": communities_summary,
        },
    }


@app.get("/api/artifacts")
def list_artifacts(project: str = Query(...)):
    resolved = validate_project_path(project)
    artifacts = []

    candidates = [
        ("Graphify Graph", resolved / "graphify-out" / "graph.json"),
        ("Graphify Analysis", resolved / "graphify-out" / ".graphify_analysis.json"),
        ("Graphify Report", resolved / "graphify-out" / "GRAPH_REPORT.md"),
        ("Graphify Tree View", resolved / "graphify-out" / "GRAPH_TREE.html"),
        ("Chain Manifest", resolved / ".code_chain" / "index_manifest.json"),
        ("Local Docs Overlay", resolved / ".code_chain" / "docs_index.json"),
        ("GitNexus Meta", resolved / ".gitnexus" / "meta.json"),
        ("GitNexus Schema", resolved / ".gitnexus" / "schema.json"),
        ("CodeGraph Database", resolved / ".codegraph" / "codegraph.db"),
    ]

    for label, path in candidates:
        if path.exists():
            try:
                rel_path = path.relative_to(resolved)
                artifacts.append(
                    {
                        "label": label,
                        "relative_path": str(rel_path),
                        "size_bytes": path.stat().st_size,
                        "modified_time": path.stat().st_mtime,
                    }
                )
            except Exception:
                pass

    return {"project_path": str(resolved), "artifacts": artifacts}


@app.get("/api/artifacts/content")
def get_artifact_content(
    project: str = Query(...),
    file: str = Query(...),
):
    resolved = validate_project_path(project)

    # Path traversal protection: only allow relative paths inside specific folders
    clean_file = file.strip().lstrip("/")
    if ".." in clean_file:
        raise HTTPException(status_code=400, detail="Path traversal not permitted.")

    allowed_prefixes = ("graphify-out", ".code_chain", ".gitnexus", ".codegraph")
    if not clean_file.startswith(allowed_prefixes):
        raise HTTPException(
            status_code=403, detail="File is not in an authorized artifact directory."
        )

    target_file = (resolved / clean_file).resolve()
    if not target_file.is_relative_to(resolved):
        raise HTTPException(status_code=403, detail="Resolved path escapes the project directory.")
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found.")

    size = target_file.stat().st_size
    if size > _MAX_ARTIFACT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(f"Artifact exceeds size limit ({size} bytes > {_MAX_ARTIFACT_BYTES} bytes)."),
        )

    binary_suffixes = {".db", ".sqlite", ".sqlite3"}
    if target_file.suffix.lower() in binary_suffixes or target_file.name in {
        "lbug",
        "codegraph.db",
    }:
        return {
            "file": clean_file,
            "size": size,
            "content": "",
            "is_json": False,
            "is_binary": True,
            "message": "Binary artifact listed only; contents are not displayed.",
        }

    try:
        content = target_file.read_text(encoding="utf-8", errors="replace")
        return {
            "file": clean_file,
            "size": len(content),
            "content": content,
            "is_json": clean_file.endswith(".json"),
            "is_binary": False,
            "message": None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading artifact: {e}") from e


# Mount static assets
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
