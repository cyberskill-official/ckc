"""
CodeGraph Adapter: Fine-grained symbol intelligence, line-accurate code blocks,
caller/callee trees, and test impacts.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from code_chain.adapters.base import BaseGraphAdapter
from code_chain.core.models import EngineStatus

_LOCATION_RE = re.compile(r"\*\*Location:\*\*\s+(\S+)")


class CodeGraphAdapter(BaseGraphAdapter):
    """Adapter for CodeGraph engine."""

    def __init__(self, bin_path: str, project_path: Path):
        super().__init__(bin_path, project_path)
        self.codegraph_dir = self.project_path / ".codegraph"
        # Per-request / per-adapter symbol lookup cache (reduces CLI fan-out).
        self._symbol_cache: dict[tuple[str, str], Any] = {}

    def _bin_available(self) -> bool:
        return bool(shutil.which(self.bin_path) or Path(self.bin_path).is_file())

    def get_status(self) -> EngineStatus:
        available = self._bin_available()
        if not self.codegraph_dir.exists():
            return EngineStatus(
                engine_name="codegraph",
                available=available,
                indexed=False,
                index_path=str(self.codegraph_dir),
                node_count=0,
                edge_count=0,
                details={"status": "not_indexed"},
            )

        try:
            res = subprocess.run(
                [self.bin_path, "status", "-j", str(self.project_path)],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            parsed: dict[str, Any] = {}
            try:
                parsed = json.loads(res.stdout) if res.stdout.strip() else {}
            except Exception:
                parsed = {}
            node_count = int(parsed.get("nodeCount") or 0)
            edge_count = int(parsed.get("edgeCount") or 0)
            file_count = int(parsed.get("fileCount") or 0)
            indexed = bool(parsed.get("initialized", self.codegraph_dir.exists()))
            error_message = None
            if res.returncode != 0 and not indexed:
                err = (res.stderr or res.stdout or "").strip()
                error_message = err[:400] if err else f"codegraph status exit {res.returncode}"
            return EngineStatus(
                engine_name="codegraph",
                available=available,
                indexed=indexed,
                index_path=str(self.codegraph_dir),
                node_count=node_count,
                edge_count=edge_count,
                error_message=error_message,
                details={
                    "status": "ready" if indexed else "not_indexed",
                    "file_count": file_count,
                    "languages": parsed.get("languages") or [],
                },
            )
        except Exception as e:
            return EngineStatus(
                engine_name="codegraph",
                available=available,
                indexed=self.codegraph_dir.exists(),
                index_path=str(self.codegraph_dir),
                error_message=str(e),
            )

    def _init_cmd(self) -> list[str]:
        return [self.bin_path, "init", str(self.project_path)]

    def index_project(self, timeout: int = 300) -> dict[str, Any]:
        """Runs codegraph init or index on the target project."""
        cmd = self._init_cmd()
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return {
                "success": False,
                "returncode": None,
                "timeout": True,
                "error": f"codegraph index timed out after {timeout}s",
                "stdout": stdout,
                "stderr": stderr,
                "codegraph_dir": str(self.codegraph_dir),
            }
        success = result.returncode == 0 and self.codegraph_dir.exists()
        return {
            "success": success,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "codegraph_dir": str(self.codegraph_dir),
        }

    def query_symbols(self, query: str) -> list[dict[str, Any]]:
        """Searches for symbols matching query (prefers JSON ``-j`` like callers/callees)."""
        try:
            # Prefer structured JSON output when the CLI supports it.
            res = subprocess.run(
                [
                    self.bin_path,
                    "query",
                    "-j",
                    "-p",
                    str(self.project_path),
                    query,
                ],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            parsed = self._parse_query_symbols_json(res.stdout)
            if parsed is not None:
                return parsed
            if res.returncode != 0 and (res.stderr or "").strip():
                # Fall back to legacy text mode (older CLIs may reject -j).
                res = subprocess.run(
                    [self.bin_path, "query", query],
                    cwd=str(self.project_path),
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
            return self._parse_query_symbols_text(res.stdout)
        except Exception as e:
            self.record_error("query_symbols", e)
            return []

    def _parse_query_symbols_json(self, stdout: str) -> list[dict[str, Any]] | None:
        """Parse codegraph query -j payload; None if not JSON."""
        text = (stdout or "").strip()
        if not text or not text.startswith(("{", "[")):
            return None
        try:
            payload = json.loads(text)
        except Exception:
            return None
        raw_items: list[Any]
        if isinstance(payload, list):
            raw_items = payload
        elif isinstance(payload, dict):
            raw_items = (
                payload.get("symbols") or payload.get("results") or payload.get("matches") or []
            )
        else:
            return []
        results: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("symbol") or "").strip()
            if not name:
                continue
            file_path = str(item.get("filePath") or item.get("file") or item.get("path") or "")
            line_raw = item.get("startLine") or item.get("line") or 0
            try:
                line = int(line_raw)
            except (TypeError, ValueError):
                line = 0
            results.append(
                {
                    "kind": str(item.get("kind") or item.get("type") or "symbol"),
                    "name": name,
                    "file": file_path,
                    "line": line,
                }
            )
        return results

    def _parse_query_symbols_text(self, stdout: str) -> list[dict[str, Any]]:
        lines = (stdout or "").splitlines()
        results: list[dict[str, Any]] = []
        for line in lines:
            sline = line.strip()
            if not sline or sline.startswith(("Search Results", "─")):
                continue
            # e.g., "method      login"
            parts = sline.split()
            if len(parts) >= 2 and parts[0] in [
                "function",
                "method",
                "class",
                "interface",
                "type",
                "const",
                "var",
            ]:
                results.append({"kind": parts[0], "name": parts[1], "file": "", "line": 0})
            elif (
                (sline.startswith(("src/", "./")) or ":" in sline)
                and results
                and not results[-1]["file"]
            ):
                fparts = sline.split(":")
                results[-1]["file"] = fparts[0]
                if len(fparts) > 1 and fparts[1].isdigit():
                    results[-1]["line"] = int(fparts[1])
        return results

    def explore(self, query: str) -> str:
        """Explores an area: relevant symbols' source + call paths in one shot."""
        try:
            res = subprocess.run(
                [self.bin_path, "explore", query],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=25,
                check=False,
            )
            return res.stdout.strip()
        except Exception as e:
            self.record_error("explore", e)
            return f"Explore error: {e!s}"

    def get_node(self, symbol_name: str) -> str:
        """Gets symbol's source and caller/callee trail or file view."""
        try:
            res = subprocess.run(
                [self.bin_path, "node", symbol_name],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            return res.stdout.strip()
        except Exception as e:
            self.record_error("get_node", e)
            return f"Node error: {e!s}"

    def get_callers(self, symbol: str) -> list[dict[str, Any]]:
        """Finds all functions/methods that call a specific symbol."""
        cache_key = ("callers", symbol)
        if cache_key in self._symbol_cache:
            return self._symbol_cache[cache_key]
        try:
            res = subprocess.run(
                [
                    self.bin_path,
                    "callers",
                    "-j",
                    "-p",
                    str(self.project_path),
                    symbol,
                ],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if not res.stdout.strip():
                self._symbol_cache[cache_key] = []
                return []
            payload = json.loads(res.stdout)
            callers_raw = payload.get("callers") or []
            callers: list[dict[str, Any]] = []
            for item in callers_raw:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "")
                if not name:
                    continue
                file_path = str(item.get("filePath") or "")
                start_line = item.get("startLine")
                location = (
                    f"{file_path}:{start_line}"
                    if file_path and start_line is not None
                    else file_path
                )
                callers.append(
                    {
                        "kind": str(item.get("kind") or ""),
                        "name": name,
                        "location": location,
                    }
                )
            self._symbol_cache[cache_key] = callers
            return callers
        except Exception as e:
            self.record_error("get_callers", e)
            self._symbol_cache[cache_key] = []
            return []

    def get_callees(self, symbol: str) -> list[dict[str, Any]]:
        """Finds all functions/methods that a specific symbol calls."""
        cache_key = ("callees", symbol)
        if cache_key in self._symbol_cache:
            return self._symbol_cache[cache_key]
        try:
            res = subprocess.run(
                [
                    self.bin_path,
                    "callees",
                    "-j",
                    "-p",
                    str(self.project_path),
                    symbol,
                ],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if not res.stdout.strip():
                self._symbol_cache[cache_key] = []
                return []
            payload = json.loads(res.stdout)
            callees_raw = payload.get("callees") or []
            callees: list[dict[str, Any]] = []
            for item in callees_raw:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "")
                if not name:
                    continue
                file_path = str(item.get("filePath") or "")
                start_line = item.get("startLine")
                location = (
                    f"{file_path}:{start_line}"
                    if file_path and start_line is not None
                    else file_path
                )
                callees.append(
                    {
                        "kind": str(item.get("kind") or ""),
                        "name": name,
                        "location": location,
                    }
                )
            self._symbol_cache[cache_key] = callees
            return callees
        except Exception as e:
            self.record_error("get_callees", e)
            self._symbol_cache[cache_key] = []
            return []

    def extract_source_files(self, node_text: str) -> list[str]:
        """Parse source file paths from `codegraph node` markdown output."""
        if not node_text:
            return []
        match = _LOCATION_RE.search(node_text)
        if not match:
            return []
        location = match.group(1)
        file_path = location.split(":")[0]
        return [file_path] if file_path else []

    def get_affected_tests(self, files: list[str] | None = None) -> list[str]:
        """Finds test files affected by changed source files."""
        if not files:
            return []
        cmd = [self.bin_path, "affected", "-j", *files]
        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            tests: list[str] = []
            try:
                parsed = json.loads(res.stdout) if res.stdout.strip() else {}
                raw_tests = parsed.get("affectedTests") or []
                tests = [str(t) for t in raw_tests if t]
            except Exception:
                for line in res.stdout.splitlines():
                    sline = line.strip()
                    if sline and ("test_" in sline or ".test." in sline or ".spec." in sline):
                        tests.append(sline)
            return tests
        except Exception as e:
            self.record_error("get_affected_tests", e)
            return []
