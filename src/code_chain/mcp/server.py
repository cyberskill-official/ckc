"""
Model Context Protocol (MCP) Stdio Server for code-knowledge-chain.
Exposes the 3-tier chaining workflow as native MCP tools to Claude Code,
Cursor, Antigravity, and other AI agents.
"""

from __future__ import annotations

import json
import re
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from code_chain.core.config import ChainConfig
from code_chain.core.env import load_dotenv
from code_chain.core.orchestrator import CodeKnowledgeChain
from code_chain.core.timeouts import QueryTimeoutError, run_with_timeout

try:
    _PACKAGE_VERSION = version("code-knowledge-chain")
except PackageNotFoundError:
    # Keep in sync with pyproject.toml / code_chain.__version__ when not installed.
    _PACKAGE_VERSION = "1.0.0"


def make_tool_definition(
    name: str, description: str, input_schema: dict[str, Any]
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": input_schema,
    }


_FORMAT_PROP = {
    "type": "string",
    "enum": ["text", "json"],
    "description": (
        "Response format: 'text' (default markdown) or 'json' "
        "(structured model dump including engine_errors / outcome)"
    ),
}


def get_available_tools() -> list:
    return [
        make_tool_definition(
            name="chain_status",
            description=(
                "Check the indexing health and readiness of Graphify, GitNexus, "
                "and CodeGraph for a project. "
                "Inputs: project_path. "
                "Process: Checks index directories and manifests. "
                "Output: Summary of index status."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": (
                            "Path to the repository (defaults to server working directory)"
                        ),
                    },
                    "format": _FORMAT_PROP,
                },
            },
        ),
        make_tool_definition(
            name="chain_init",
            description=(
                "Index a repository across all three knowledge graph engines "
                "(Graphify, GitNexus, CodeGraph). "
                "Inputs: project path. "
                "Process: Graphify extract → GitNexus index → CodeGraph index. "
                "Output: Indexing summary and manifest."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the target repository directory",
                    },
                    "multimodal": {
                        "type": "boolean",
                        "description": (
                            "Whether to enable LLM multimodal extraction for "
                            "non-code files (defaults to false for fast AST indexing)"
                        ),
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Clear prior indexes and re-run extraction (default false)",
                    },
                    "format": _FORMAT_PROP,
                },
                "required": ["project_path"],
            },
        ),
        make_tool_definition(
            name="chain_query",
            description=(
                "Query the 3-tier chained knowledge graph to understand features, "
                "architecture, and connections. "
                "Inputs: natural language query. "
                "Process: Tier 1 (Graphify) → cross-domain entities; "
                "Tier 2 (GitNexus) → AST execution flows; "
                "Tier 3 (CodeGraph) → symbol definitions and source snippets. "
                "Output: stacked markdown with per-tier sections and reading guide."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project repository",
                    },
                    "query": {
                        "type": "string",
                        "description": (
                            "The architectural concept, feature, or question "
                            "(e.g. 'How does authentication work?')"
                        ),
                    },
                    "use_llm": {
                        "type": "boolean",
                        "description": (
                            "Append local LM Studio / OpenAI-compatible synthesis "
                            "when configured (default true)"
                        ),
                    },
                    "format": _FORMAT_PROP,
                },
                "required": ["query"],
            },
        ),
        make_tool_definition(
            name="chain_impact",
            description=(
                "Calculate blast radius and refactoring impact for a symbol. "
                "Inputs: target symbol. "
                "Process: CodeGraph lookup → GitNexus upstream trace. "
                "Output: returns upstream callers, affected business processes, impacted "
                "tests, and step-by-step refactoring plan."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project repository",
                    },
                    "symbol": {
                        "type": "string",
                        "description": (
                            "The function, class, or method name to analyze for refactoring impact"
                        ),
                    },
                    "use_llm": {
                        "type": "boolean",
                        "description": (
                            "Append local LM Studio / OpenAI-compatible synthesis "
                            "when configured (default true)"
                        ),
                    },
                    "format": _FORMAT_PROP,
                },
                "required": ["symbol"],
            },
        ),
        make_tool_definition(
            name="chain_trace",
            description=(
                "Trace the exact directed execution path between two symbols "
                "across the codebase. "
                "Inputs: source and destination symbols. "
                "Process: GitNexus path resolution → CodeGraph snippet fetch. "
                "Output: trace flow complete with hop sequence and diagram."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project repository",
                    },
                    "from_symbol": {
                        "type": "string",
                        "description": "Source function or symbol name",
                    },
                    "to_symbol": {
                        "type": "string",
                        "description": "Destination function or symbol name",
                    },
                    "use_llm": {
                        "type": "boolean",
                        "description": (
                            "Append local LM Studio / OpenAI-compatible synthesis "
                            "when configured (default true)"
                        ),
                    },
                    "format": _FORMAT_PROP,
                },
                "required": ["from_symbol", "to_symbol"],
            },
        ),
        make_tool_definition(
            name="chain_diff",
            description=(
                "Map current git diff hunks to indexed symbols and affected "
                "execution flows (GitNexus detect-changes). "
                "Inputs: git workspace diff. "
                "Process: map changed lines to AST nodes. "
                "Output: JSON mapping of diff hunks to affected flows."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project repository",
                    },
                    "format": _FORMAT_PROP,
                },
            },
        ),
    ]


def _wants_json(arguments: dict[str, Any]) -> bool:
    fmt = str(arguments.get("format") or "text").strip().lower()
    return fmt == "json"


def _format_result(text: str, payload: Any, *, as_json: bool) -> str:
    if as_json:
        if hasattr(payload, "model_dump"):
            return json.dumps(payload.model_dump(), indent=2)
        return json.dumps(payload, indent=2, default=str)
    return text


def _require_nonempty(value: Any, field_name: str) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _sanitize_error_message(exc: BaseException) -> str:
    """Strip absolute paths and truncate error text returned to MCP clients."""
    msg = str(exc)
    msg = re.sub(r"(?:[A-Za-z]:)?(?:/|\\)[^\s:]+", "[path]", msg)
    msg = re.sub(r"\s+", " ", msg).strip()
    return msg[:400] if msg else type(exc).__name__


def handle_tool_call(name: str, arguments: dict[str, Any], default_path: str) -> str:
    path = arguments.get("project_path") or default_path
    chain = CodeKnowledgeChain(project_path=path)
    config = chain.config if hasattr(chain, "config") else ChainConfig()
    timeout = max(1, int(getattr(config, "query_timeout", 90)))
    as_json = _wants_json(arguments)

    if name == "chain_status":
        if as_json:
            return json.dumps(chain.status().model_dump(), indent=2)
        return chain.export_summary()

    if name == "chain_init":
        multimodal = arguments.get("multimodal", False)
        force = bool(arguments.get("force", False))
        index_timeout = max(
            1,
            int(
                getattr(config, "multimodal_index_timeout", 900)
                if multimodal
                else getattr(config, "index_timeout", 300)
            ),
        )

        def _index() -> Any:
            return chain.index(code_only=not multimodal, force=force)

        results = run_with_timeout(_index, index_timeout, operation="chain_init")
        if as_json:
            return json.dumps(results, indent=2, default=str)
        return chain.export_summary()

    if name == "chain_query":
        query_text = _require_nonempty(arguments.get("query"), "query")
        use_llm = arguments.get("use_llm", True)

        def _work() -> Any:
            return chain.query(query_text, use_llm=bool(use_llm))

        res = run_with_timeout(_work, timeout, operation="chain_query")
        return _format_result(res.synthesized_context, res, as_json=as_json)

    if name == "chain_impact":
        symbol = _require_nonempty(arguments.get("symbol"), "symbol")
        use_llm = arguments.get("use_llm", True)

        def _work() -> Any:
            return chain.impact(symbol, use_llm=bool(use_llm))

        res = run_with_timeout(_work, timeout, operation="chain_impact")
        return _format_result(res.synthesized_report, res, as_json=as_json)

    if name == "chain_trace":
        from_sym = _require_nonempty(arguments.get("from_symbol"), "from_symbol")
        to_sym = _require_nonempty(arguments.get("to_symbol"), "to_symbol")
        use_llm = arguments.get("use_llm", True)

        def _work() -> Any:
            return chain.trace(from_sym, to_sym, use_llm=bool(use_llm))

        res = run_with_timeout(_work, timeout, operation="chain_trace")
        return _format_result(res.synthesized_flow, res, as_json=as_json)

    if name == "chain_diff":
        res = chain.detect_changes()
        return json.dumps(res, indent=2, default=str)

    raise ValueError(f"Unknown tool: {name}")


def run_mcp_server(default_project_path: str = ".") -> None:
    """Runs a standard JSON-RPC 2.0 MCP server loop over stdin/stdout."""
    load_dotenv()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "code-knowledge-chain",
                        "version": _PACKAGE_VERSION,
                    },
                },
            }
        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": get_available_tools()},
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                text_result = handle_tool_call(tool_name, tool_args, default_project_path)
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": text_result}],
                        "isError": False,
                    },
                }
            except QueryTimeoutError as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Error executing {tool_name}: {_sanitize_error_message(e)}"
                                ),
                            }
                        ],
                        "isError": True,
                    },
                }
            except Exception as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Error executing {tool_name}: {_sanitize_error_message(e)}"
                                ),
                            }
                        ],
                        "isError": True,
                    },
                }
        else:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
