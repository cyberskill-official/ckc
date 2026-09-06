"""
Base adapter interface for code knowledge graph engines.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any
from code_chain.core.models import EngineStatus


class BaseGraphAdapter(ABC):
    """Abstract base class for graph engine adapters."""

    def __init__(self, bin_path: str, project_path: Path):
        self.bin_path = bin_path
        self.project_path = project_path

    @abstractmethod
    def get_status(self) -> EngineStatus:
        """Check if the engine is available and whether the project is indexed."""
        pass

    @abstractmethod
    def index_project(self, **kwargs) -> Dict[str, Any]:
        """Index or update the project knowledge graph."""
        pass
