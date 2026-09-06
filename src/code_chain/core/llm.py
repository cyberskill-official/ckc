"""
Optional OpenAI-compatible LLM synthesis (LM Studio / local servers).

Uses stdlib urllib only — no provider SDK dependencies.
Soft-fails on timeout or connection errors so stacked markdown stays usable.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def resolve_llm_config() -> tuple[str, str, str] | None:
    """
    Return (base_url, model, api_key) when LLM synthesis is configured.

    Enabled when CKC_LLM_BASE_URL or OPENAI_BASE_URL is set.
    """
    base = (os.environ.get("CKC_LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "").strip()
    if not base:
        return None
    model = (
        os.environ.get("CKC_LLM_MODEL") or os.environ.get("OPENAI_MODEL") or ""
    ).strip()
    if not model:
        model = "local-model"
    api_key = (
        os.environ.get("CKC_LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or "lm-studio"
    ).strip()
    return base.rstrip("/"), model, api_key


def llm_is_configured() -> bool:
    return resolve_llm_config() is not None


def llm_public_status() -> dict:
    """Host-only status for UI/status cards (no secrets)."""
    cfg = resolve_llm_config()
    if not cfg:
        return {"configured": False, "base_url": None, "model": None}
    base_url, model, _api_key = cfg
    return {"configured": True, "base_url": base_url, "model": model}


def _approx_tokens(text: str) -> int:
    # Rough chars/4 heuristic for budget trimming.
    return max(1, (len(text) + 3) // 4)


def trim_to_token_budget(text: str, max_tokens: int) -> str:
    """Truncate assembled markdown to approximately max_tokens."""
    if max_tokens <= 0 or _approx_tokens(text) <= max_tokens:
        return text
    target_chars = max(200, max_tokens * 4 - 80)
    truncated = text[:target_chars].rstrip()
    return truncated + "\n\n… *(truncated to max_tokens_budget)*\n"


def chat_completions(
    messages: list,
    *,
    timeout: float = 45.0,
    temperature: float = 0.2,
    max_tokens: int = 800,
) -> str | None:
    """POST /chat/completions; return assistant text or None on soft failure."""
    cfg = resolve_llm_config()
    if not cfg:
        return None
    base_url, model, api_key = cfg
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        choices = data.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        return None
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        OSError,
        ValueError,
        KeyError,
    ):
        return None
    except Exception:
        return None


def synthesize_stacked_context(
    stacked_markdown: str,
    *,
    task: str = "query",
    max_input_chars: int | None = None,
) -> str | None:
    """Ask the local model for a short synthesis of stacked context."""
    if not stacked_markdown.strip():
        return None
    if max_input_chars is None or max_input_chars <= 0:
        max_input_chars = 12000
    capped = stacked_markdown[:max_input_chars]
    system = (
        "You are a code-intelligence assistant. Given stacked knowledge-graph "
        "context from Graphify, GitNexus, and CodeGraph, write a concise grounded "
        "summary for a developer. Prefer concrete symbols, files, and flows. "
        "Do not invent APIs or files that are not in the context."
    )
    user = (
        f"Task type: {task}\n\n"
        "Summarize the following chained context in a short markdown section "
        "(a few bullets or a short paragraph):\n\n"
        f"{capped}"
    )
    return chat_completions(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )


def maybe_append_llm_section(
    stacked_markdown: str,
    *,
    task: str = "query",
    enabled: bool = True,
    max_tokens_budget: int = 4000,
) -> str:
    """
    Append a **Local model synthesis** section when configured and enabled.

    Soft-fail: on any LLM error when configured, append a one-line notice.
    """
    if not enabled or not llm_is_configured():
        return stacked_markdown
    max_input_chars = max(200, max_tokens_budget * 4)
    synthesis = synthesize_stacked_context(
        stacked_markdown,
        task=task,
        max_input_chars=max_input_chars,
    )
    if not synthesis:
        return (
            stacked_markdown.rstrip()
            + "\n\n*Local model synthesis unavailable: no response from configured endpoint.*\n"
        )
    return (
        stacked_markdown.rstrip()
        + "\n\n## Local model synthesis\n\n"
        + synthesis
        + "\n"
    )


def finalize_stacked_markdown(
    stacked_markdown: str,
    *,
    task: str = "query",
    enabled: bool = True,
    max_tokens_budget: int = 4000,
) -> str:
    """Trim → optional LLM append → re-trim so final output stays within budget."""
    text = trim_to_token_budget(stacked_markdown, max_tokens_budget)
    text = maybe_append_llm_section(
        text,
        task=task,
        enabled=enabled,
        max_tokens_budget=max_tokens_budget,
    )
    return trim_to_token_budget(text, max_tokens_budget)
