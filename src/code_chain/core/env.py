"""
Load a local `.env` file into process environment without overriding existing vars.

Stdlib only — no python-dotenv dependency.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(
    path: str | Path | None = None,
    *,
    override: bool = False,
) -> Path | None:
    """
    Parse KEY=VALUE lines from `.env` and set them in os.environ.

    Searches (in order) when path is omitted:
      1. cwd/.env
      2. package repo root (../../.. from this file) /.env

    Existing environment variables are left alone unless override=True.
    Returns the path loaded, or None if no file was found.
    """
    candidates = []
    if path is not None:
        candidates.append(Path(path))
    else:
        candidates.append(Path.cwd() / ".env")
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        candidates.append(repo_root / ".env")

    for candidate in candidates:
        if not candidate.is_file():
            continue
        _apply_env_file(candidate, override=override)
        return candidate
    return None


def _apply_env_file(path: Path, *, override: bool) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if not override and key in os.environ:
            continue
        os.environ[key] = value
