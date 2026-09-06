#!/usr/bin/env python3
"""
One-Click Cross-Platform Cleanup for Code Knowledge Chain (CKC).
Safely removes generated artifacts, caches, temporary files, and stops running processes.

Usage:
  python3 scripts/cleanup.py [--all] [--yes]
"""

from __future__ import annotations

import argparse
import os
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


def safe_remove_dir(path: Path):
    if path.exists() and path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
        print_success(
            f"Removed directory: "
            f"{path.relative_to(ROOT_DIR) if path.is_relative_to(ROOT_DIR) else path}"
        )


def safe_remove_file(path: Path):
    if path.exists() and path.is_file():
        path.unlink(missing_ok=True)
        print_success(
            f"Removed file: "
            f"{path.relative_to(ROOT_DIR) if path.is_relative_to(ROOT_DIR) else path}"
        )


def kill_background_daemons():
    print_step("Checking and stopping running background processes...")
    # Stop codegraph daemons if binary exists
    if shutil.which("codegraph"):
        try:
            subprocess.run(
                ["codegraph", "daemon", "stop"], capture_output=True, timeout=5,
                check=False,
            )
            print_success("Stopped codegraph daemons (if any)")
        except Exception:
            pass


def clean_light():
    print_step("Running Light Cleanup (Caches, Python bytecode, build artifacts)...")
    count = 0

    # 1. Clean Python __pycache__ and bytecode
    for p in ROOT_DIR.rglob("__pycache__"):
        if p.is_dir():
            safe_remove_dir(p)
            count += 1

    for p in ROOT_DIR.rglob("*.pyc"):
        safe_remove_file(p)
        count += 1

    # 2. Clean Pytest & Test caches
    safe_remove_dir(ROOT_DIR / ".pytest_cache")
    safe_remove_dir(ROOT_DIR / ".ruff_cache")
    safe_remove_file(ROOT_DIR / ".coverage")

    # 3. Clean Build & Egg info
    safe_remove_dir(ROOT_DIR / "build")
    safe_remove_dir(ROOT_DIR / "dist")
    for p in ROOT_DIR.glob("*.egg-info"):
        safe_remove_dir(p)
    for p in (ROOT_DIR / "src").glob("*.egg-info"):
        safe_remove_dir(p)

    # 4. macOS Finder clutter
    for p in ROOT_DIR.rglob(".DS_Store"):
        if p.is_file():
            safe_remove_file(p)
            count += 1

    print_success(f"Light cleanup completed ({count} cache items cleared).")


def clean_full():
    print_step("Running Full Reset (Generated Graph Indexes, Manifests, Sample Git)...")
    kill_background_daemons()
    clean_light()

    # Search for all generated index directories
    index_folders = [
        "graphify-out",
        ".gitnexus",
        ".codegraph",
        ".code_chain",
        ".claude",
    ]
    for folder_name in index_folders:
        for p in ROOT_DIR.rglob(folder_name):
            if p.is_dir():
                safe_remove_dir(p)

    # Clean nested git and generated docs in examples
    examples_dir = ROOT_DIR / "examples"
    if examples_dir.exists():
        for sub in examples_dir.iterdir():
            if sub.is_dir():
                git_dir = sub / ".git"
                if git_dir.exists():
                    safe_remove_dir(git_dir)
                safe_remove_file(sub / "CLAUDE.md")
                safe_remove_file(sub / "AGENTS.md")

    print_success("Full reset completed. Repository returned to clean source state.")


def main():
    parser = argparse.ArgumentParser(
        description="One-Click Cleanup for Code Knowledge Chain"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Full reset: removes generated graph indexes and stops daemons",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip interactive confirmation"
    )
    args = parser.parse_args()

    mode_label = (
        "FULL RESET (deletes all generated graph indexes, manifests, and caches)"
        if args.all
        else "LIGHT CLEANUP (deletes caches and temporary build files)"
    )

    is_ci = os.getenv("CI", "false").lower() in ("true", "1")
    if not args.yes and not is_ci:
        print(f"\033[1;33mWarning:\033[0m You are about to perform: {mode_label}")
        print("Source code will NOT be affected.")
        confirm = input("Are you sure you want to proceed? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Cleanup cancelled.")
            sys.exit(0)

    if args.all:
        clean_full()
    else:
        clean_light()

    print("\n\033[1;32mCleanup finished successfully.\033[0m")


if __name__ == "__main__":
    main()
