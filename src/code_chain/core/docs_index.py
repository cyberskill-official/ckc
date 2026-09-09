"""
Local markdown / docs overlay for Graphify --code-only mode.

Graphify's code-only extract skips documentation. CKC walks the project and
writes `.code_chain/docs_index.json` so docs still surface in search/synthesis.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

DOC_SUFFIXES = {".md", ".mdx", ".rst", ".adoc"}
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "graphify-out",
    ".gitnexus",
    ".codegraph",
    ".code_chain",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
}
EXCERPT_CHARS = 400
_HEADING_RE = re.compile(r"^(?:=+\s+(.+?)\s*=+\s*$|#{1,6}\s+(.+))$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

logger = logging.getLogger("code_chain.docs_index")


def docs_index_path(project_path: Path) -> Path:
    return project_path / ".code_chain" / "docs_index.json"


def is_doc_path(path: Path) -> bool:
    return path.suffix.lower() in DOC_SUFFIXES


def _should_skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES or name.startswith(".")


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        stripped = _FRONTMATTER_RE.sub("", text, count=1)
        return stripped if stripped else text
    return text


def _extract_title(text: str, fallback: str) -> str:
    body = _strip_frontmatter(text)
    match = _HEADING_RE.search(body)
    if match:
        return (match.group(1) or match.group(2) or fallback).strip()
    for line in body.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return fallback


def _excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _first_heading_body(text: str) -> str:
    """Prefer the body under the first markdown/adoc heading; skip YAML frontmatter."""
    body = _strip_frontmatter(text).lstrip()
    match = _HEADING_RE.search(body)
    if not match:
        return body
    after = body[match.end() :].lstrip("\n")
    next_heading = _HEADING_RE.search(after)
    if next_heading:
        after = after[: next_heading.start()]
    return after.strip() or body


def _chunk_by_heading(text: str, fallback_title: str) -> list[tuple[str, str]]:
    """Split a doc into (title, body) chunks by headings; whole file if none."""
    body = _strip_frontmatter(text)
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        return [(fallback_title, body.strip())]

    chunks: list[tuple[str, str]] = []
    # Prefatory text before the first heading (rare after frontmatter strip).
    preface = body[: matches[0].start()].strip()
    if preface:
        chunks.append((fallback_title, preface))

    for i, match in enumerate(matches):
        title = (match.group(1) or match.group(2) or fallback_title).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section = body[start:end].strip()
        chunks.append((title, section or title))
    return chunks


def discover_doc_files(project_path: Path) -> list[Path]:
    """Walk the project and collect documentation files, pruning skip dirs early."""
    root = project_path.resolve()
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Mutate dirnames in-place so os.walk does not descend into skip dirs.
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for name in filenames:
            path = Path(dirpath) / name
            if is_doc_path(path):
                found.append(path)
    return sorted(found)


def build_docs_entries(project_path: Path) -> list[dict[str, Any]]:
    """Build overlay entries from discovered documentation files (heading chunks)."""
    root = project_path.resolve()
    entries: list[dict[str, Any]] = []
    for path in discover_doc_files(root):
        rel = str(path.relative_to(root)).replace("\\", "/")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        file_title = _extract_title(text, path.stem)
        chunks = _chunk_by_heading(text, file_title)
        for idx, (title, section_body) in enumerate(chunks):
            excerpt_source = section_body or _first_heading_body(text)
            chunk_id = f"local-doc:{rel}" if idx == 0 else f"local-doc:{rel}#{idx}"
            entries.append(
                {
                    "id": chunk_id,
                    "name": title,
                    "entity_type": "doc",
                    "source_path": rel,
                    "excerpt": _excerpt(excerpt_source),
                    "suffix": path.suffix.lower(),
                }
            )
    return entries


def write_docs_index(project_path: Path) -> dict[str, Any]:
    """Write `.code_chain/docs_index.json` and return a summary dict."""
    root = project_path.resolve()
    discovered = discover_doc_files(root)
    entries = build_docs_entries(root)
    out_dir = root / ".code_chain"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "project_path": str(root),
        "doc_count": len(entries),
        "discovered_files": len(discovered),
        "docs": entries,
    }
    out_path = docs_index_path(root)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return {
        "success": True,
        "doc_count": len(entries),
        "discovered_files": len(discovered),
        "path": str(out_path),
        "docs": entries,
    }


def load_docs_index(project_path: Path) -> dict[str, Any]:
    """Load the local docs overlay, or an empty structure if missing."""
    path = docs_index_path(project_path)
    if not path.exists():
        return {"doc_count": 0, "docs": []}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        docs = data.get("docs") or []
        if not isinstance(docs, list):
            docs = []
        return {
            "doc_count": int(data.get("doc_count") or len(docs)),
            "discovered_files": int(data.get("discovered_files") or 0),
            "docs": docs,
            "path": str(path),
        }
    except Exception:
        return {"doc_count": 0, "docs": []}


def local_docs_count(project_path: Path) -> int:
    return int(load_docs_index(project_path).get("doc_count") or 0)


def index_docs_overlay(
    project_path: Path, *, code_only: bool = True, announce: bool = True
) -> dict[str, Any]:
    """Build the overlay and optionally print the code-only skip message."""
    result = write_docs_index(project_path)
    discovered = int(result.get("discovered_files") or 0)
    indexed = int(result.get("doc_count") or 0)
    if announce and code_only:
        logger.info(
            "Graphify --code-only skipped %s doc file(s); indexed %s local chunk(s)",
            discovered,
            indexed,
        )
    return result
