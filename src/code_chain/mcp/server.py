"""
Model Context Protocol (MCP) Stdio Server for code-knowledge-chain.
Exposes the 3-tier chaining workflow as native MCP tools to Claude Code,
Cursor, Antigravity, and other AI agents.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from code_chain.core.config import ChainConfig
from code_chain.core.env import load_dotenv
from code_chain.core.orchestrator import CodeKnowledgeChain
from code_chain.core.timeouts import QueryTimeoutError, run_with_timeout


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
                "and CodeGraph for a project."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": (
                            "Path to the repository "
                            "(defaults to server working directory)"
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
                "(Graphify, GitNexus, CodeGraph)."
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
                "architecture, and connections across documentation, AST execution "
                "flows, and verbatim code blocks."
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
                "Calculate blast radius and refactoring impact for a symbol: "
                "returns upstream callers, affected business processes, impacted "
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
                            "The function, class, or method name to analyze for "
                            "refactoring impact"
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
                "across the codebase, complete with hop sequence and diagram."
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
                "execution flows (GitNexus detect-changes)."
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
        results = chain.index(code_only=not multimodal, force=force)
        if as_json:
            return json.dumps(results, indent=2, default=str)
        return chain.export_summary()

    if name == "chain_query":
        query_text = arguments.get("query", "")
        use_llm = arguments.get("use_llm", True)

        def _work() -> Any:
            return chain.query(query_text, use_llm=bool(use_llm))

        res = run_with_timeout(_work, timeout, operation="chain_query")
        return _format_result(res.synthesized_context, res, as_json=as_json)

    if name == "chain_impact":
        symbol = arguments.get("symbol", "")
        use_llm = arguments.get("use_llm", True)

        def _work() -> Any:
            return chain.impact(symbol, use_llm=bool(use_llm))

        res = run_with_timeout(_work, timeout, operation="chain_impact")
        return _format_result(res.synthesized_report, res, as_json=as_json)

    if name == "chain_trace":
        from_sym = arguments.get("from_symbol", "")
        to_sym = arguments.get("to_symbol", "")
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
                        "version": "1.0.0",
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
                text_result = handle_tool_call(
                    tool_name, tool_args, default_project_path
                )
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
                                "text": f"Error executing {tool_name}: {e!s}",
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
                                "text": f"Error executing {tool_name}: {e!s}",
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
