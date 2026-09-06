"""
FastAPI Server for Code Knowledge Chain Web UI.
Provides REST and Server-Sent Events (SSE) endpoints for indexing, status, query, impact, and trace.
"""

from __future__ import annotations
import asyncio
import json
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, AsyncGenerator
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from code_chain.core.env import load_dotenv
from code_chain.core.orchestrator import CodeKnowledgeChain
from code_chain.core.config import ChainConfig
from code_chain.core.docs_index import index_docs_overlay, local_docs_count
from code_chain.core.llm import llm_public_status
from code_chain.core.paths import (
    UnsafeProjectPathError,
    assert_safe_project_path,
    ensure_engine_gitignore,
)

load_dotenv()

app = FastAPI(
    title="Code Knowledge Chain UI",
    description="Interactive Web Dashboard for Graphify + GitNexus + CodeGraph 3-Tier Code Intelligence",
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
_active_indexing_processes: Dict[str, subprocess.Popen] = {}
_cancellation_flags: Dict[str, bool] = {}


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
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "code-knowledge-chain-ui"}


@app.get("/api/samples")
def get_samples() -> Dict[str, Any]:
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
        if proc and proc.poll() is None:
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

        steps = [
            (
                "graphify",
                "Tier 1: Graphify Multi-modal & Architecture",
                [config.graphify_bin, "extract", str(resolved)]
                + ([] if multimodal else ["--code-only"]),
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
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(resolved),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                with _active_indexing_lock:
                    _active_indexing_processes[proj_key] = proc

                # Stream stdout line by line
                while True:
                    if _cancellation_flags.get(proj_key, False):
                        proc.terminate()
                        yield json.dumps(
                            {
                                "event": "cancelled",
                                "message": f"Cancelled during {engine}.",
                            }
                        )
                        return

                    line = proc.stdout.readline()
                    if not line and proc.poll() is not None:
                        break
                    if line:
                        clean_line = line.rstrip()
                        yield json.dumps(
                            {
                                "event": "log",
                                "engine": engine,
                                "line": clean_line,
                            }
                        )
                    await asyncio.sleep(0.01)

                rc = proc.poll()
                with _active_indexing_lock:
                    if proj_key in _active_indexing_processes:
                        del _active_indexing_processes[proj_key]

                success = rc == 0
                step_results[engine] = {"success": success, "returncode": rc}
                if not success:
                    overall_success = False

                if engine == "graphify":
                    overlay = index_docs_overlay(
                        resolved, code_only=code_only, announce=False
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
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

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
    result = chain.trace(
        payload.from_symbol, payload.to_symbol, use_llm=payload.use_llm
    )
    return result.model_dump()


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
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found.")

    binary_suffixes = {".db", ".sqlite", ".sqlite3"}
    if (
        target_file.suffix.lower() in binary_suffixes
        or target_file.name in {"lbug", "codegraph.db"}
    ):
        return {
            "file": clean_file,
            "size": target_file.stat().st_size,
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
        raise HTTPException(status_code=500, detail=f"Error reading artifact: {e}")


# Mount static assets
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
