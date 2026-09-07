"""
FastAPI Server for Code Knowledge Chain Web UI.
Provides REST and Server-Sent Events (SSE) endpoints for indexing, status, query, impact, and trace.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import threading
import time
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from code_chain.adapters import CodeGraphAdapter, GitNexusAdapter, GraphifyAdapter
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

logger = logging.getLogger("code_chain.ui")

_MAX_ARTIFACT_BYTES = 2 * 1024 * 1024  # 2 MiB
_MUTATING_PREFIXES = (
    "/api/query",
    "/api/impact",
    "/api/trace",
    "/api/index/cancel",
    "/api/index/stream",
)


def _bind_host() -> str:
    return (os.environ.get("CKC_HOST") or "127.0.0.1").strip() or "127.0.0.1"


def is_loopback_host(host: str | None = None) -> bool:
    """True when the UI bind address is loopback-only (not all-interfaces)."""
    h = (host or _bind_host()).strip().lower()
    return h in {"127.0.0.1", "localhost", "::1"}


def resolve_cors_origins(host: str | None = None) -> list[str]:
    """
    Loopback binds may use wildcard CORS for local tooling.
    Non-loopback binds refuse '*' and default to same-origin only (empty allow-list)
    unless CKC_CORS_ORIGINS lists explicit origins.
    """
    bind = host or _bind_host()
    explicit = (os.environ.get("CKC_CORS_ORIGINS") or "").strip()
    if explicit:
        origins = [o.strip() for o in explicit.split(",") if o.strip()]
        if "*" in origins and not is_loopback_host(bind):
            raise RuntimeError(
                "CKC_CORS_ORIGINS=* is refused when CKC_HOST is not loopback "
                f"(got {bind!r}). Set explicit origins or bind to 127.0.0.1."
            )
        return origins
    if is_loopback_host(bind):
        return ["*"]
    return []


def ui_token() -> str | None:
    token = (os.environ.get("CKC_UI_TOKEN") or "").strip()
    return token or None


def auth_required_for_mutations() -> bool:
    """Enforce shared secret when configured, or when listening beyond loopback."""
    if ui_token():
        return True
    return not is_loopback_host()


class UIAuthMiddleware(BaseHTTPMiddleware):
    """Optional shared-secret gate for mutating UI endpoints."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        is_mutating = any(path == p or path.startswith(p + "/") for p in _MUTATING_PREFIXES)
        # Index stream is GET but mutates disk state
        if path.startswith("/api/index/stream"):
            is_mutating = True
        if not is_mutating:
            return await call_next(request)

        token = ui_token()
        if not auth_required_for_mutations():
            return await call_next(request)
        if not token:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "CKC_UI_TOKEN must be set when the UI binds beyond loopback. "
                        "Set CKC_UI_TOKEN and send Authorization: Bearer <token> "
                        "or X-CKC-Token."
                    )
                },
            )

        provided = (
            request.headers.get("x-ckc-token")
            or request.headers.get("X-CKC-Token")
            or ""
        ).strip()
        auth = (request.headers.get("authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip() or provided
        # EventSource cannot set headers; allow ?token= for SSE only
        if not provided and path.startswith("/api/index/stream"):
            provided = (request.query_params.get("token") or "").strip()

        if provided != token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing UI auth token."},
            )
        return await call_next(request)


app = FastAPI(
    title="Code Knowledge Chain UI",
    description=(
        "Interactive Web Dashboard for Graphify + GitNexus + CodeGraph 3-Tier Code Intelligence"
    ),
    version="1.0.0",
)

_cors_origins = resolve_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(UIAuthMiddleware)

if not is_loopback_host() and not ui_token():
    logger.warning(
        "CKC UI is binding to non-loopback host %s without CKC_UI_TOKEN; "
        "mutating routes will return 503 until a token is configured.",
        _bind_host(),
    )

# Active indexing process tracker for cancellation
_active_indexing_lock = threading.Lock()
_active_indexing_processes: dict[str, asyncio.subprocess.Process] = {}
_cancellation_flags: dict[str, bool] = {}
_active_index_jobs: set[str] = set()


def validate_project_path(path_str: str) -> Path:
    """Validates that path_str is an existing project directory, not a system path."""
    try:
        return assert_safe_project_path(path_str)
    except UnsafeProjectPathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _engine_error_map(status: Any) -> dict[str, str]:
    """Structured per-engine diagnosis for soft-fail observability."""
    errors: dict[str, str] = {}
    for name, eng in (
        ("graphify", status.graphify),
        ("gitnexus", status.gitnexus),
        ("codegraph", status.codegraph),
    ):
        if eng.error_message:
            errors[name] = eng.error_message
        elif not eng.available:
            errors[name] = "binary not found on PATH"
        elif not eng.indexed:
            detail_status = (eng.details or {}).get("status") or "not_indexed"
            errors[name] = str(detail_status)
    return errors


async def _terminate_process(proc: asyncio.subprocess.Process) -> None:
    """Escalate terminate → kill, await exit, and drain stdout."""
    if proc.returncode is not None:
        return
    try:
        proc.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(proc.wait(), timeout=3.0)
    except TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except TimeoutError:
            logger.warning("Process %s did not exit after kill", proc.pid)
            return
    if proc.stdout is not None:
        with contextlib.suppress(TimeoutError, Exception):
            await asyncio.wait_for(proc.stdout.read(), timeout=1.0)


def _build_index_steps(
    resolved: Path, config: ChainConfig, *, multimodal: bool
) -> tuple[list[tuple[str, str, list[str]]], bool]:
    """
    Shared engine argv lists for UI SSE indexing (mirrors IndexPipeline / adapters).
    Returns (steps, code_only).
    """
    code_only = not multimodal
    graphify = GraphifyAdapter(config.graphify_bin, resolved)
    gitnexus = GitNexusAdapter(config.gitnexus_bin, resolved)
    codegraph = CodeGraphAdapter(config.codegraph_bin, resolved)

    graphify_cmd = graphify._extract_cmd(code_only=code_only)
    # When multimodal was requested but adapter fell back to --code-only, reflect that
    if multimodal and "--code-only" in graphify_cmd:
        code_only = True

    steps = [
        (
            "graphify",
            "Tier 1: Graphify Multi-modal & Architecture",
            graphify_cmd,
        ),
        (
            "gitnexus",
            "Tier 2: GitNexus Tree-sitter AST & Execution Flow",
            gitnexus._analyze_cmd(),
        ),
        (
            "codegraph",
            "Tier 3: CodeGraph Symbol Intelligence & Test Impact",
            codegraph._init_cmd(),
        ),
    ]
    return steps, code_only


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
        "engine_errors": _engine_error_map(status),
    }


@app.post("/api/index/cancel")
async def cancel_indexing(payload: CancelPayload):
    resolved = validate_project_path(payload.project_path)
    proj_key = str(resolved)
    with _active_indexing_lock:
        _cancellation_flags[proj_key] = True
        proc = _active_indexing_processes.get(proj_key)
    if proc and proc.returncode is None:
        try:
            await _terminate_process(proc)
            with _active_indexing_lock:
                _active_indexing_processes.pop(proj_key, None)
            return {
                "success": True,
                "message": "Indexing process terminated.",
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

    with _active_indexing_lock:
        if proj_key in _active_index_jobs:
            busy = True
        else:
            _active_index_jobs.add(proj_key)
            busy = False

    if busy:

        async def busy_generator() -> AsyncGenerator[str, None]:
            yield json.dumps(
                {
                    "event": "error",
                    "message": "Indexing already in progress for this project.",
                }
            )

        return EventSourceResponse(busy_generator())

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            with _active_indexing_lock:
                _cancellation_flags[proj_key] = False

            steps, code_only = _build_index_steps(
                resolved, config, multimodal=multimodal
            )
            index_timeout = (
                config.index_timeout if code_only else config.multimodal_index_timeout
            )
            deadline = time.monotonic() + index_timeout

            yield json.dumps(
                {
                    "event": "start",
                    "message": f"Starting 3-tier indexing on {resolved}",
                    "multimodal": multimodal,
                    "force": force,
                    "timeout_seconds": index_timeout,
                }
            )

            if multimodal and code_only and not resolve_llm_config():
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

            if force:
                chain_force = CodeKnowledgeChain(project_path=str(resolved))
                yield json.dumps(
                    {
                        "event": "log",
                        "engine": "ckc",
                        "line": "[force] Clearing prior engine indexes...",
                    }
                )
                await asyncio.to_thread(chain_force.index_pipe._clear_engine_indexes)

            overall_success = True
            step_results: dict[str, Any] = {}

            for step_idx, (engine, step_label, cmd) in enumerate(steps, 1):
                if _cancellation_flags.get(proj_key, False):
                    yield json.dumps(
                        {
                            "event": "cancelled",
                            "message": "Indexing was cancelled by user.",
                        }
                    )
                    return

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    overall_success = False
                    yield json.dumps(
                        {
                            "event": "step_error",
                            "step": step_idx,
                            "engine": engine,
                            "error": f"Index timeout ({index_timeout}s) exceeded.",
                        }
                    )
                    break

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

                    assert proc.stdout is not None
                    while True:
                        if _cancellation_flags.get(proj_key, False):
                            await _terminate_process(proc)
                            with _active_indexing_lock:
                                _active_indexing_processes.pop(proj_key, None)
                            yield json.dumps(
                                {
                                    "event": "cancelled",
                                    "message": f"Cancelled during {engine}.",
                                }
                            )
                            return

                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            await _terminate_process(proc)
                            with _active_indexing_lock:
                                _active_indexing_processes.pop(proj_key, None)
                            overall_success = False
                            yield json.dumps(
                                {
                                    "event": "step_error",
                                    "step": step_idx,
                                    "engine": engine,
                                    "error": f"Index timeout ({index_timeout}s) exceeded.",
                                }
                            )
                            break

                        try:
                            line_bytes = await asyncio.wait_for(
                                proc.stdout.readline(),
                                timeout=min(remaining, 1.0),
                            )
                        except TimeoutError:
                            if proc.returncode is not None:
                                break
                            # No output yet; re-check cancel / deadline
                            continue

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

                    if _cancellation_flags.get(proj_key, False):
                        await _terminate_process(proc)
                        with _active_indexing_lock:
                            _active_indexing_processes.pop(proj_key, None)
                        yield json.dumps(
                            {
                                "event": "cancelled",
                                "message": f"Cancelled during {engine}.",
                            }
                        )
                        return

                    if time.monotonic() > deadline and proc.returncode is None:
                        continue

                    rc = await proc.wait()
                    with _active_indexing_lock:
                        _active_indexing_processes.pop(proj_key, None)

                    success = rc == 0
                    step_results[engine] = {"success": success, "returncode": rc}
                    if not success:
                        overall_success = False

                    if engine == "graphify":
                        overlay = await asyncio.to_thread(
                            index_docs_overlay,
                            resolved,
                            code_only=code_only,
                            announce=False,
                        )
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

            gitignore_added = await asyncio.to_thread(ensure_engine_gitignore, resolved)

            chain = CodeKnowledgeChain(project_path=str(resolved))
            status = await asyncio.to_thread(chain.status)
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

            summary = await asyncio.to_thread(chain.export_summary)
            yield json.dumps(
                {
                    "event": "complete",
                    "overall_success": overall_success,
                    "status": status.model_dump(),
                    "summary": summary,
                }
            )
        finally:
            with _active_indexing_lock:
                _active_index_jobs.discard(proj_key)
                _active_indexing_processes.pop(proj_key, None)

    return EventSourceResponse(event_generator())


async def _run_with_query_timeout(fn: Callable[[], Any]) -> Any:
    config = ChainConfig()
    timeout = max(1, int(config.query_timeout))
    try:
        return await asyncio.wait_for(asyncio.to_thread(fn), timeout=timeout)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Operation exceeded query_timeout ({timeout}s).",
        ) from exc


@app.post("/api/query")
async def run_query(payload: QueryPayload):
    resolved = validate_project_path(payload.project_path)

    def _work() -> dict[str, Any]:
        chain = CodeKnowledgeChain(project_path=str(resolved))
        return chain.query(payload.query, use_llm=payload.use_llm).model_dump()

    return await _run_with_query_timeout(_work)


@app.post("/api/impact")
async def run_impact(payload: ImpactPayload):
    resolved = validate_project_path(payload.project_path)

    def _work() -> dict[str, Any]:
        chain = CodeKnowledgeChain(project_path=str(resolved))
        return chain.impact(payload.symbol, use_llm=payload.use_llm).model_dump()

    return await _run_with_query_timeout(_work)


@app.post("/api/trace")
async def run_trace(payload: TracePayload):
    resolved = validate_project_path(payload.project_path)

    def _work() -> dict[str, Any]:
        chain = CodeKnowledgeChain(project_path=str(resolved))
        return chain.trace(
            payload.from_symbol, payload.to_symbol, use_llm=payload.use_llm
        ).model_dump()

    return await _run_with_query_timeout(_work)


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
