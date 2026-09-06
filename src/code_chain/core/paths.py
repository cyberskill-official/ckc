"""
Project-path safety and target-repo hygiene for Code Knowledge Chain.
"""

from __future__ import annotations

from pathlib import Path


class UnsafeProjectPathError(ValueError):
    """Raised when a path is not a safe, project-like repository root."""


_SYSTEM_PREFIXES = (
    Path("/etc"),
    Path("/private/etc"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
    Path("/dev"),
    Path("/proc"),
    Path("/sys"),
    Path("/var"),
    Path("/private/var"),
    Path("/root"),
    Path("/System"),
    Path("/Library"),
    Path("/Windows"),
    Path("/Program Files"),
    Path("/Program Files (x86)"),
)

_PROJECT_MARKERS = (
    ".git",
    "package.json",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Cargo.toml",
    "go.mod",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "Gemfile",
    "mix.exs",
    ".code_chain",
    "src",
)

ENGINE_GITIGNORE_ENTRIES = (
    "graphify-out/",
    ".gitnexus/",
    ".codegraph/",
    ".code_chain/",
)


def is_blocked_system_path(resolved: Path) -> bool:
    """True for filesystem roots and well-known OS directories."""
    if resolved.parent == resolved:
        return True
    for prefix in _SYSTEM_PREFIXES:
        try:
            resolved.relative_to(prefix)
            return True
        except ValueError:
            continue
    return False


def has_project_marker(resolved: Path) -> bool:
    return any((resolved / marker).exists() for marker in _PROJECT_MARKERS)


def assert_safe_project_path(path_str: str) -> Path:
    """Resolve and reject empty, missing, system, or non-project directories."""
    if not path_str or not str(path_str).strip():
        raise UnsafeProjectPathError("Repository path cannot be empty.")
    try:
        resolved = Path(path_str.strip()).expanduser().resolve()
    except Exception as exc:
        raise UnsafeProjectPathError(f"Invalid path syntax: {exc}") from exc

    if not resolved.exists():
        raise UnsafeProjectPathError(f"Directory does not exist: {resolved}")
    if not resolved.is_dir():
        raise UnsafeProjectPathError(f"Path is not a directory: {resolved}")
    if is_blocked_system_path(resolved):
        raise UnsafeProjectPathError(
            f"Refusing to use system directory as a project: {resolved}"
        )
    if not has_project_marker(resolved):
        raise UnsafeProjectPathError(
            f"Path does not look like a software project (missing .git, "
            f"package manifest, src/, or .code_chain): {resolved}"
        )
    return resolved


def ensure_engine_gitignore(project_path: Path) -> list[str]:
    """Append engine index dirs to the target .gitignore when the repo is a git worktree."""
    if not (project_path / ".git").exists():
        return []
    gitignore = project_path / ".gitignore"
    existing_lines = (
        gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    )
    existing = {line.strip() for line in existing_lines}
    to_add = [
        entry
        for entry in ENGINE_GITIGNORE_ENTRIES
        if entry not in existing and entry.rstrip("/") not in existing
    ]
    if not to_add:
        return []
    block_lines: list[str] = []
    if existing_lines and existing_lines[-1].strip():
        block_lines.append("")
    if "# code-knowledge-chain indexes" not in existing:
        block_lines.append("# code-knowledge-chain indexes")
    block_lines.extend(to_add)
    block_lines.append("")
    with gitignore.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(block_lines))
    return to_add
