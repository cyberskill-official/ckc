"""
Wall-clock helpers for CLI/MCP query paths.

UI uses asyncio.wait_for; CLI/MCP use a thread pool so the main process can
return a structured timeout. The worker thread may keep running briefly after
timeout (Python cannot forcibly kill threads); callers should treat results
after TimeoutError as abandoned.
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class QueryTimeoutError(TimeoutError):
    """Raised when a query/impact/trace exceeds ChainConfig.query_timeout."""

    def __init__(self, timeout: float, operation: str = "operation"):
        self.timeout = timeout
        self.operation = operation
        super().__init__(f"{operation} exceeded query_timeout ({int(timeout)}s).")


def run_with_timeout(fn: Callable[[], T], timeout: float, *, operation: str = "operation") -> T:
    """Run ``fn`` in a worker thread; raise QueryTimeoutError if it exceeds ``timeout``."""
    seconds = max(1.0, float(timeout))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=seconds)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise QueryTimeoutError(seconds, operation=operation) from exc
