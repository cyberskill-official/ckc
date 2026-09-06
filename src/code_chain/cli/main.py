"""
Command-Line Interface (CLI) for code-knowledge-chain.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

import uvicorn

from code_chain.core.env import load_dotenv
from code_chain.core.orchestrator import CodeKnowledgeChain
from code_chain.mcp.server import run_mcp_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code-chain",
        description="Generic Knowledge Graph Chaining Workflow (Graphify + GitNexus + CodeGraph)",
    )
    parser.add_argument(
        "-p",
        "--project",
        default=".",
        help="Path to target project repository (default: current directory)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init / index
    p_init = subparsers.add_parser(
        "init",
        aliases=["index"],
        help="Index a project across Graphify, GitNexus, and CodeGraph",
    )
    p_init.add_argument(
        "--multimodal",
        action="store_true",
        help="Enable LLM multimodal extraction for Graphify docs/images (requires API key)",
    )
    p_init.add_argument(
        "--code-only",
        action="store_true",
        help=(
            "Skip Graphify docs/images and use local AST only "
            "(default without --multimodal; wins if both flags set)"
        ),
    )
    p_init.add_argument(
        "--force", action="store_true", help="Force re-indexing even if already present"
    )

    # status
    subparsers.add_parser(
        "status", help="Check indexing status across all three engines"
    )

    # query
    p_query = subparsers.add_parser(
        "query", help="Run 3-tier chained concept or architecture query"
    )
    p_query.add_argument(
        "query_text", help="The question or architectural concept to investigate"
    )
    p_query.add_argument(
        "--json", action="store_true", help="Output raw JSON instead of markdown"
    )
    p_query.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip optional LM Studio / OpenAI-compatible synthesis even if configured",
    )

    # impact
    p_impact = subparsers.add_parser(
        "impact", help="Analyze blast radius and refactoring impact of a symbol"
    )
    p_impact.add_argument("symbol", help="Target symbol or function to analyze")
    p_impact.add_argument(
        "--json", action="store_true", help="Output raw JSON instead of markdown"
    )
    p_impact.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip optional LM Studio / OpenAI-compatible synthesis even if configured",
    )

    # trace
    p_trace = subparsers.add_parser(
        "trace", help="Trace execution flow between two symbols"
    )
    p_trace.add_argument("from_symbol", help="Source symbol name")
    p_trace.add_argument("to_symbol", help="Destination symbol name")
    p_trace.add_argument(
        "--json", action="store_true", help="Output raw JSON instead of markdown"
    )
    p_trace.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip optional LM Studio / OpenAI-compatible synthesis even if configured",
    )

    # diff
    subparsers.add_parser(
        "diff", help="Map current git diff hunks to indexed symbols and affected flows"
    )

    # mcp
    subparsers.add_parser(
        "mcp", help="Start Model Context Protocol (MCP) stdio server for AI agents"
    )

    # ui
    default_host = os.environ.get("CKC_HOST", "127.0.0.1")
    try:
        default_port = int(os.environ.get("CKC_PORT", "8000"))
    except ValueError:
        default_port = 8000
    p_ui = subparsers.add_parser("ui", help="Start the interactive web dashboard")
    p_ui.add_argument(
        "--host", default=default_host, help=f"Host interface (default: {default_host})"
    )
    p_ui.add_argument(
        "--port",
        type=int,
        default=default_port,
        help=f"Port to listen on (default: {default_port})",
    )
    p_ui.add_argument(
        "--open", action="store_true", help="Automatically open web browser"
    )

    # setup
    p_setup = subparsers.add_parser(
        "setup", help="Run one-click environment setup and verification"
    )
    p_setup.add_argument(
        "--no-ui", action="store_true", help="Do not launch the Web UI after setup"
    )
    p_setup.add_argument(
        "--force", action="store_true", help="Force re-indexing sample repositories"
    )

    # clean / cleanup
    p_clean = subparsers.add_parser(
        "clean",
        aliases=["cleanup"],
        help="Clean generated caches, manifests, or reset indexes",
    )
    p_clean.add_argument(
        "--all",
        action="store_true",
        help="Full reset: removes generated graph indexes and stops background daemons",
    )
    p_clean.add_argument(
        "-y", "--yes", action="store_true", help="Skip interactive confirmation"
    )

    return parser


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "mcp":
        run_mcp_server(args.project)
        return

    if args.command == "ui":
        url = f"http://{args.host}:{args.port}"
        print(f"Starting Code Knowledge Chain UI at: {url}")
        if args.open:
            webbrowser.open(url)
        uvicorn.run(
            "code_chain.ui.server:app", host=args.host, port=args.port, log_level="info"
        )
        return

    if args.command == "setup":
        script = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "scripts"
            / "setup.py"
        )
        cmd = [sys.executable, str(script)]
        if args.no_ui:
            cmd.append("--no-ui")
        if args.force:
            cmd.append("--force")
        subprocess.run(cmd,
            check=False)
        return

    if args.command in ["clean", "cleanup"]:
        script = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "scripts"
            / "cleanup.py"
        )
        cmd = [sys.executable, str(script)]
        if args.all:
            cmd.append("--all")
        if args.yes:
            cmd.append("--yes")
        subprocess.run(cmd,
            check=False)
        return

    try:
        chain = CodeKnowledgeChain(project_path=args.project)
    except Exception as e:
        print(f"Error resolving project path '{args.project}': {e}", file=sys.stderr)
        sys.exit(1)

    if args.command in ["init", "index"]:
        print(f"Initializing 3-tier knowledge graph in: {chain.project_path}")
        # --code-only wins when both flags appear; default remains code-only without --multimodal.
        code_only = True if args.code_only else not args.multimodal
        chain.index(code_only=code_only, force=args.force)
        print("\nIndexing Complete!")
        print(chain.export_summary())

    elif args.command == "status":
        print(chain.export_summary())

    elif args.command == "query":
        result = chain.query(args.query_text, use_llm=not args.no_llm)
        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            print(result.synthesized_context)

    elif args.command == "impact":
        result = chain.impact(args.symbol, use_llm=not args.no_llm)
        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            print(result.synthesized_report)

    elif args.command == "trace":
        result = chain.trace(
            args.from_symbol, args.to_symbol, use_llm=not args.no_llm
        )
        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            print(result.synthesized_flow)

    elif args.command == "diff":
        res = chain.detect_changes()
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
