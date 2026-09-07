"""
Base adapter interface for code knowledge graph engines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from code_chain.core.config import resolve_binary
from code_chain.core.models import EngineStatus


class BaseGraphAdapter(ABC):
    """Abstract base class for graph engine adapters."""

    def __init__(self, bin_path: str, project_path: Path):
        self.bin_path = resolve_binary(bin_path)
        self.project_path = project_path
        # Soft-fail channel: last error per operation (drained by pipelines).
        self._last_error: str | None = None

    def record_error(self, operation: str, err: BaseException | str) -> None:
        """Record a soft-fail so callers can distinguish empty vs failed."""
        text = str(err).strip() or type(err).__name__
        self._last_error = f"{operation}: {text[:380]}"

    def take_error(self) -> str | None:
        """Return and clear the last soft-fail message, if any."""
        err = self._last_error
        self._last_error = None
        return err

    def peek_error(self) -> str | None:
        return self._last_error

    @abstractmethod
    def get_status(self) -> EngineStatus:
        """Check if the engine is available and whether the project is indexed."""

    @abstractmethod
    def index_project(self, **kwargs) -> dict[str, Any]:
        """Index or update the project knowledge graph."""
