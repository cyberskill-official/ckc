#!/usr/bin/env python3
"""
One-Click Cross-Platform Setup for Code Knowledge Chain (CKC).
Works on macOS, Linux, and Windows.

Usage:
  python3 scripts/setup.py [--no-ui] [--port 8000] [--force]
"""

from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def print_step(title: str):
    print(f"\n\033[1;36m==>\033[0m \033[1m{title}\033[0m")


def print_success(msg: str):
    print(f"  \033[1;32m✓\033[0m {msg}")


def print_warn(msg: str):
    print(f"  \033[1;33m⚠\033[0m {msg}")


def print_error(msg: str):
    print(f"  \033[1;31m✗\033[0m {msg}")


def run_cmd(
    cmd: list[str], cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=cwd or ROOT_DIR, check=check, text=True, capture_output=True
    )


def check_prerequisites() -> dict[str, bool]:
    print_step("Checking prerequisites...")
    results = {}

    # Python version
    py_ver = sys.version_info
    if py_ver >= (3, 9):
        print_success(f"Python {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
        results["python"] = True
    else:
        print_error(f"Python 3.9+ required (found {py_ver.major}.{py_ver.minor})")
        results["python"] = False

    # Git
    if shutil.which("git"):
        git_ver = run_cmd(["git", "--version"]).stdout.strip()
        print_success(f"{git_ver}")
        results["git"] = True
    else:
        print_error("Git not found on PATH. Please install Git.")
        results["git"] = False

    # Node.js
    if shutil.which("node"):
        node_ver = run_cmd(["node", "--version"]).stdout.strip()
        print_success(f"Node.js {node_ver}")
        results["node"] = True
    else:
        print_warn("Node.js not found. Required for GitNexus and CodeGraph.")
        results["node"] = False

    # npm
    if shutil.which("npm"):
        npm_ver = run_cmd(["npm", "--version"]).stdout.strip()
        print_success(f"npm {npm_ver}")
        results["npm"] = True
    else:
        print_warn("npm not found.")
        results["npm"] = False

    # Check 3 graph engine binaries
    has_graphify = shutil.which("graphify") is not None
    has_gitnexus = shutil.which("gitnexus") is not None
    has_codegraph = shutil.which("codegraph") is not None

    if has_graphify:
        print_success("Graphify binary detected")
    else:
        print_warn("Graphify not detected on PATH. Installing via pip...")
        try:
            run_cmd([sys.executable, "-m", "pip", "install", "graphifyy"])
            print_success("Graphify installed successfully")
            has_graphify = True
        except Exception as e:
            print_warn(
                f"Automatic graphify install failed: {e}. Can run via: pip install graphifyy"
            )

    if has_gitnexus:
        print_success("GitNexus binary detected")
    else:
        if results.get("npm"):
            print_warn("GitNexus not detected. Installing globally via npm...")
            try:
                run_cmd(["npm", "install", "-g", "gitnexus"])
                print_success("GitNexus installed successfully")
                has_gitnexus = True
            except Exception as e:
                print_warn(
                    f"Automatic gitnexus install failed: {e}. Can run: npm install -g gitnexus"
                )

    if has_codegraph:
        print_success("CodeGraph binary detected")
    else:
        if results.get("npm"):
            print_warn("CodeGraph not detected. Installing globally via npm...")
            try:
                run_cmd(["npm", "install", "-g", "@colbymchenry/codegraph"])
                print_success("CodeGraph installed successfully")
                has_codegraph = True
            except Exception as e:
                print_warn(
                    f"Automatic codegraph install failed: {e}. Can run: npm install -g @colbymchenry/codegraph"
                )

    results["engines_ready"] = has_graphify and has_gitnexus and has_codegraph
    return results


def install_package():
    print_step("Installing Python package in editable mode...")
    try:
        run_cmd([sys.executable, "-m", "pip", "install", "-e", "."])
        print_success("Package code-knowledge-chain installed successfully")
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install package: {e.stderr}")
        sys.exit(1)


def init_sample_repositories(force: bool = False):
    print_step("Initializing bundled sample repositories...")
    examples_dir = ROOT_DIR / "examples"
    samples = [
        examples_dir / "python-auth-service",
        examples_dir / "ts-billing-service",
    ]

    for sample in samples:
        if not sample.exists():
            continue

        git_dir = sample / ".git"
        if not git_dir.exists():
            print(f"  Initializing git repo in: {sample.name}")
            run_cmd(["git", "init"], cwd=sample)
            run_cmd(["git", "config", "user.email", "setup@example.com"], cwd=sample)
            run_cmd(["git", "config", "user.name", "CKC Setup"], cwd=sample)
            run_cmd(["git", "add", "."], cwd=sample)
            run_cmd(["git", "commit", "-m", "initial commit"], cwd=sample)
            print_success(f"Git initialized for {sample.name}")
        else:
            print_success(f"Git already initialized for {sample.name}")

        # Index sample if not already indexed or if force is set
        manifest_file = sample / ".code_chain" / "index_manifest.json"
        is_fully_indexed = (
            manifest_file.exists()
            and (sample / "graphify-out").is_dir()
            and (sample / ".gitnexus").is_dir()
            and (sample / ".codegraph").is_dir()
        )
        if not is_fully_indexed or force:
            print(f"  Indexing {sample.name} across all 3 engines...")
            try:
                res = run_cmd(["code-chain", "-p", str(sample), "init"])
                if res.returncode == 0:
                    print_success(f"Indexed {sample.name}")
                else:
                    print_warn(f"Indexing completed with warnings for {sample.name}")
            except Exception as e:
                print_warn(f"Could not run indexing on {sample.name}: {e}")
        else:
            print_success(f"{sample.name} is already indexed (manifest exists)")


def run_health_checks():
    print_step("Running health checks and automated test suite...")
    try:
        res = run_cmd([sys.executable, "-m", "pytest", "tests", "-q"])
        if res.returncode == 0:
            print_success("All test suites passed cleanly!")
        else:
            print_warn(
                f"Some tests failed or reported warnings:\n{res.stdout or res.stderr}"
            )
    except Exception as e:
        print_warn(f"Health check pytest run skipped or failed: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="One-Click Setup for Code Knowledge Chain"
    )
    parser.add_argument(
        "--no-ui", action="store_true", help="Do not launch the Web UI after setup"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Web UI port (default: 8000)"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Web UI host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force re-indexing sample repositories"
    )
    args = parser.parse_args()

    print("\033[1;35m" + "=" * 60)
    print("   Code Knowledge Chain (CKC) - One-Click Setup")
    print("=" * 60 + "\033[0m")

    prereqs = check_prerequisites()
    if not prereqs.get("python") or not prereqs.get("git"):
        print_error("Fatal prerequisites missing. Aborting.")
        sys.exit(1)

    install_package()
    init_sample_repositories(force=args.force)
    run_health_checks()

    print("\n\033[1;32m" + "=" * 60)
    print("   Setup Complete! Code Knowledge Chain is Ready.")
    print("=" * 60 + "\033[0m")
    print("\nAvailable interfaces:")
    print("  • Web UI:     code-chain ui --open")
    print("  • CLI:        code-chain -p <repo> [init|status|query|impact|trace]")
    print("  • MCP Server: code-chain -p <repo> mcp")
    print("  • Python API: from code_chain import CodeKnowledgeChain")

    if not args.no_ui:
        print(
            f"\nStarting Web UI at http://{args.host}:{args.port} (Press Ctrl+C to stop)..."
        )
        try:
            import uvicorn

            uvicorn.run(
                "code_chain.ui.server:app",
                host=args.host,
                port=args.port,
                log_level="info",
            )
        except KeyboardInterrupt:
            print("\nWeb UI stopped.")


if __name__ == "__main__":
    main()
