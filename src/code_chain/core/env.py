"""
Load a local `.env` file into process environment without overriding existing vars.

Stdlib only — no python-dotenv dependency.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path


def probe_local_lm_studio(host: str = "127.0.0.1", port: int = 1234) -> tuple[str, str, str] | None:
    """
    Probe local LM Studio models endpoint (default port 1234).

    Intentionally loopback-only: never probe remote hosts (SSRF guard).
    """
    if host.strip().lower() not in {"127.0.0.1", "localhost", "::1"}:
        return None
    try:
        url = f"http://{host}:{port}/v1/models"
        req = urllib.request.Request(url, headers={"User-Agent": "code-knowledge-chain"})
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            if resp.status == 200:
                payload = json.loads(resp.read().decode("utf-8"))
                models = payload.get("data", [])
                model_id = "local-model"
                for m in models:
                    mid = m.get("id", "")
                    if "embed" not in mid.lower():
                        model_id = mid
                        break
                if model_id == "local-model" and models:
                    model_id = models[0].get("id", "local-model")
                return f"http://{host}:{port}/v1", model_id, "lm-studio"
    except Exception:
        return None
    return None


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

    loaded = None
    for candidate in candidates:
        if not candidate.is_file():
            continue
        _apply_env_file(candidate, override=override)
        loaded = candidate
        break

    if (
        not os.environ.get("CKC_LLM_BASE_URL")
        and not os.environ.get("OPENAI_BASE_URL")
        and os.environ.get("CKC_DISABLE_AUTODETECT", "").lower() not in ("1", "true")
    ):
        detected = probe_local_lm_studio()
        if detected:
            base, model, key = detected
            os.environ.setdefault("CKC_LLM_BASE_URL", base)
            os.environ.setdefault("CKC_LLM_MODEL", model)
            os.environ.setdefault("CKC_LLM_API_KEY", key)
            os.environ.setdefault("OPENAI_BASE_URL", base)
            os.environ.setdefault("OPENAI_MODEL", model)
            os.environ.setdefault("OPENAI_API_KEY", key)

    return loaded


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
