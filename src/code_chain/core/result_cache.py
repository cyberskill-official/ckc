"""Optional filesystem cache for pipeline results (query / impact / trace).

Inspired by ICM's 'glass-box' observability: every result is a readable file.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime
from pathlib import Path


class ResultCache:
    def __init__(self, project_path: Path, *, enabled: bool = True, max_entries: int = 50):
        self.project_path = project_path
        self.enabled = enabled
        self.max_entries = max_entries
        self.results_dir = self.project_path / ".code_chain" / "results"
        self._lock = threading.Lock()

    def save(self, task: str, key: str, content: str) -> Path | None:
        if not self.enabled:
            return None

        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        sanitized_key = re.sub(r"[^a-z0-9_-]", "_", key.lower())[:40]
        filename = f"{timestamp}-{task}-{sanitized_key}.md"

        with self._lock:
            self.results_dir.mkdir(parents=True, exist_ok=True)
            filepath = self.results_dir / filename
            filepath.write_text(content or "", encoding="utf-8")
            self._evict()

        return filepath

    def _evict(self):
        # Must be called with lock held
        if not self.results_dir.exists():
            return

        files = list(self.results_dir.glob("*.md"))
        if len(files) <= self.max_entries:
            return

        # Sort by modification time (oldest first)
        files.sort(key=lambda x: x.stat().st_mtime)
        files_to_remove = files[: len(files) - self.max_entries]

        for f in files_to_remove:
            try:
                f.unlink()
            except OSError:
                pass

    def list_results(self) -> list[Path]:
        if not self.results_dir.exists():
            return []
        with self._lock:
            files = list(self.results_dir.glob("*.md"))
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return files

    def clear(self):
        with self._lock:
            if not self.results_dir.exists():
                return
            for f in self.results_dir.glob("*.md"):
                try:
                    f.unlink()
                except OSError:
                    pass
