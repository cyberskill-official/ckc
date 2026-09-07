"""
GitNexus Adapter: AST-based structural code intelligence, call graphs, execution tracing,
and blast radius.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from code_chain.adapters.base import BaseGraphAdapter
from code_chain.core.models import EngineStatus


def _extract_json(raw_text: str) -> dict[str, Any] | None:
    """Helper to extract JSON object from CLI stdout that might contain banners."""
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw_text[start : end + 1])
        except Exception:
            return None
    return None


def _candidate_uid(candidate: dict[str, Any]) -> str | None:
    uid = candidate.get("uid") or candidate.get("id")
    return uid if isinstance(uid, str) and uid else None


def _candidate_span(candidate: dict[str, Any]) -> int:
    start = candidate.get("startLine") or candidate.get("line") or 0
    end = candidate.get("endLine") or start
    try:
        return max(0, int(end) - int(start))
    except (TypeError, ValueError):
        return 0


def pick_best_candidate(candidates: list) -> dict[str, Any] | None:
    """Prefer highest score, then impact count, then largest source span (impl over stub)."""
    viable = [c for c in candidates if isinstance(c, dict) and _candidate_uid(c)]
    if not viable:
        return None

    def sort_key(c: dict[str, Any]):
        score = c.get("score")
        try:
            score_v = float(score) if score is not None else 0.0
        except (TypeError, ValueError):
            score_v = 0.0
        impact = c.get("impactedCount")
        impact_v = impact if isinstance(impact, int) else -1
        return (score_v, impact_v, _candidate_span(c))

    return max(viable, key=sort_key)


class GitNexusAdapter(BaseGraphAdapter):
    """Adapter for GitNexus code intelligence engine."""

    def __init__(self, bin_path: str, project_path: Path):
        super().__init__(bin_path, project_path)
        self.nexus_dir = self.project_path / ".gitnexus"

    def _repo_args(self) -> list:
        return ["-r", str(self.project_path)]

    def _meta_stats(self) -> dict[str, int]:
        meta_path = self.nexus_dir / "meta.json"
        if not meta_path.exists():
            return {}
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            stats = data.get("stats") or {}
            return {
                "nodes": int(stats.get("nodes") or 0),
                "edges": int(stats.get("edges") or 0),
                "communities": int(stats.get("communities") or 0),
                "processes": int(stats.get("processes") or 0),
                "files": int(stats.get("files") or 0),
            }
        except Exception:
            return {}

    def _bin_available(self) -> bool:
        return bool(shutil.which(self.bin_path) or Path(self.bin_path).is_file())

    def get_status(self) -> EngineStatus:
        available = self._bin_available()
        if not self.nexus_dir.exists():
            return EngineStatus(
                engine_name="gitnexus",
                available=available,
                indexed=False,
                index_path=str(self.nexus_dir),
                node_count=0,
                edge_count=0,
                details={"status": "not_indexed"},
            )

        stats = self._meta_stats()
        try:
            res = subprocess.run(
                [self.bin_path, "status", "--json"],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            parsed = _extract_json(res.stdout) or {}
            status_label = parsed.get("status") or parsed.get("error") or "unknown"
            is_ready = res.returncode == 0 and status_label not in (
                "not-indexed",
                "missing",
            )
            details = {
                "status": status_label,
                "communities_count": stats.get("communities", 0),
                "processes": stats.get("processes", 0),
                "files": stats.get("files", 0),
            }
            error_message = None
            if res.returncode != 0 and not (is_ready or bool(stats)):
                err = (res.stderr or res.stdout or "").strip()
                error_message = err[:400] if err else f"gitnexus status exit {res.returncode}"
            return EngineStatus(
                engine_name="gitnexus",
                available=available,
                indexed=is_ready or bool(stats),
                index_path=str(self.nexus_dir),
                node_count=stats.get("nodes", 0),
                edge_count=stats.get("edges", 0),
                error_message=error_message,
                details=details,
            )
        except Exception as e:
            return EngineStatus(
                engine_name="gitnexus",
                available=available,
                indexed=self.nexus_dir.exists(),
                index_path=str(self.nexus_dir),
                node_count=stats.get("nodes", 0),
                edge_count=stats.get("edges", 0),
                error_message=str(e),
            )

    def _analyze_cmd(self) -> list:
        cmd = [
            self.bin_path,
            "analyze",
            str(self.project_path),
            "--index-only",
            "--skip-git",
        ]
        return cmd

    def index_project(self, timeout: int = 300) -> dict[str, Any]:
        """Indexes the repository with GitNexus (Tree-sitter AST analysis)."""
        cmd = self._analyze_cmd()
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
                "error": f"gitnexus index timed out after {timeout}s",
                "stdout": stdout,
                "stderr": stderr,
                "nexus_dir": str(self.nexus_dir),
            }
        success = result.returncode == 0 and self.nexus_dir.exists()
        return {
            "success": success,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "nexus_dir": str(self.nexus_dir),
        }

    def query_concepts(self, search_query: str) -> dict[str, Any]:
        """Searches the knowledge graph for execution flows related to a concept."""
        try:
            cmd = [self.bin_path, "query", search_query, *self._repo_args()]
            res = subprocess.run(
                cmd,
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            parsed = _extract_json(res.stdout)
            if parsed:
                return parsed
        except Exception:
            pass
        return {"processes": [], "definitions": []}

    def _run_context(
        self, symbol_name: str, *, uid: str | None = None
    ) -> dict[str, Any] | None:
        cmd = [self.bin_path, "context"]
        if uid:
            cmd.extend(["-u", uid])
        else:
            cmd.append(symbol_name)
        cmd.extend(self._repo_args())
        res = subprocess.run(
            cmd,
            cwd=str(self.project_path),
            capture_output=True,
            text=True,
            timeout=20,
                check=False,
            )
        return _extract_json(res.stdout)

    def get_symbol_context(self, symbol_name: str) -> dict[str, Any] | None:
        """Retrieves 360-degree view of a code symbol: callers, callees, processes."""
        try:
            parsed = self._run_context(symbol_name)
            if not parsed:
                return None
            if parsed.get("status") != "ambiguous":
                return parsed
            candidates = parsed.get("candidates") or []
            best = pick_best_candidate(
                candidates if isinstance(candidates, list) else []
            )
            uid = _candidate_uid(best) if best else None
            if not uid:
                return parsed
            resolved = self._run_context(symbol_name, uid=uid)
            if resolved and resolved.get("status") == "found":
                resolved["_resolved_from_ambiguous"] = True
                resolved["_resolved_uid"] = uid
                return resolved
            return parsed
        except Exception:
            return None

    def _normalize_impact(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """Coerce GitNexus impact payloads so nulls and missing lists cannot crash callers."""
        count = parsed.get("impactedCount")
        if not isinstance(count, int):
            count = 0
        risk = parsed.get("risk")
        if not isinstance(risk, str) or not risk:
            risk = "UNKNOWN"
        if parsed.get("error"):
            count = 0
        procs = parsed.get("affected_processes")
        mods = parsed.get("affected_modules")
        by_depth = parsed.get("byDepth")
        if isinstance(by_depth, list):
            by_depth = {"1": [item for item in by_depth if isinstance(item, dict)]}
        elif not isinstance(by_depth, dict):
            by_depth = {}
        out = dict(parsed)
        out["impactedCount"] = count
        out["risk"] = risk
        out["affected_processes"] = procs if isinstance(procs, list) else []
        out["affected_modules"] = mods if isinstance(mods, list) else []
        out["byDepth"] = by_depth
        # Explicit outcome for callers (ok | empty | error | ambiguous_unresolved).
        if out.get("error"):
            out["_outcome"] = "error"
        elif out.get("status") == "ambiguous" and not out.get("_resolved_uid"):
            out["_outcome"] = "ambiguous_unresolved"
        elif out.get("_outcome") in {"empty", "error", "ambiguous_unresolved", "ok"}:
            pass
        else:
            out["_outcome"] = "ok"
        return out

    def _run_impact(
        self,
        target_symbol: str,
        *,
        uid: str | None = None,
        summary_only: bool = True,
        depth: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any] | None:
        cmd = [self.bin_path, "impact"]
        if uid:
            cmd.extend(["-u", uid])
        else:
            cmd.append(target_symbol)
        cmd.extend(self._repo_args())
        if summary_only:
            cmd.append("--summary-only")
        if depth is not None:
            cmd.extend(["--depth", str(depth)])
        if limit is not None:
            cmd.extend(["--limit", str(limit)])
        res = subprocess.run(
            cmd,
            cwd=str(self.project_path),
            capture_output=True,
            text=True,
            timeout=30,
                check=False,
            )
        return _extract_json(res.stdout)

    def _resolve_impact_target(
        self, target_symbol: str, parsed: dict[str, Any]
    ) -> dict[str, Any]:
        """When GitNexus returns ambiguous matches, re-query the best candidate by UID."""
        if parsed.get("status") != "ambiguous":
            return parsed
        candidates = parsed.get("candidates") or []
        if not isinstance(candidates, list):
            return parsed
        best = pick_best_candidate(candidates)
        uid = _candidate_uid(best) if best else None
        if not uid:
            # Fall back to aggregate fields if present.
            if not isinstance(parsed.get("impactedCount"), int):
                max_count = parsed.get("maxImpactedCount")
                if isinstance(max_count, int):
                    parsed["impactedCount"] = max_count
            if not isinstance(parsed.get("risk"), str) or parsed.get("risk") in (
                None,
                "",
                "UNKNOWN",
            ):
                known = parsed.get("knownMaxRisk") or parsed.get("maxRisk")
                if isinstance(known, str) and known and known != "UNKNOWN":
                    parsed["risk"] = known
            return parsed
        resolved = self._run_impact(target_symbol, uid=uid, summary_only=True)
        if resolved and not resolved.get("error"):
            resolved["_resolved_from_ambiguous"] = True
            resolved["_resolved_uid"] = uid
            return resolved
        return parsed

    def analyze_impact(self, target_symbol: str) -> dict[str, Any]:
        """Blast radius analysis: what breaks if you change a symbol."""
        empty = {
            "impactedCount": 0,
            "risk": "UNKNOWN",
            "affected_processes": [],
            "affected_modules": [],
            "byDepth": {},
            "_outcome": "empty",
        }
        # Summary-only stays under GitNexus's ~64KB stdout cap and is repo-scoped.
        try:
            parsed = self._run_impact(target_symbol, summary_only=True)
            if not parsed:
                return empty
            parsed = self._resolve_impact_target(target_symbol, parsed)
            if parsed.get("status") == "ambiguous" and not parsed.get("_resolved_uid"):
                parsed["_outcome"] = "ambiguous_unresolved"
                return self._normalize_impact(parsed)
            if parsed.get("error"):
                parsed["_outcome"] = "error"
                return self._normalize_impact(parsed)
            uid = parsed.get("_resolved_uid")
            detail = self._run_impact(
                target_symbol,
                uid=uid if isinstance(uid, str) else None,
                summary_only=False,
                depth=2,
                limit=20,
            )
            if detail and not detail.get("error"):
                if detail.get("status") == "ambiguous":
                    detail = self._resolve_impact_target(target_symbol, detail)
                if detail.get("byDepth"):
                    parsed["byDepth"] = detail["byDepth"]
                if detail.get("affected_processes"):
                    parsed["affected_processes"] = detail["affected_processes"]
                if detail.get("affected_modules"):
                    parsed["affected_modules"] = detail["affected_modules"]
                if detail.get("_resolved_uid") and not parsed.get("_resolved_uid"):
                    parsed["_resolved_uid"] = detail["_resolved_uid"]
                    parsed["_resolved_from_ambiguous"] = True
            parsed["_outcome"] = "ok"
            return self._normalize_impact(parsed)
        except Exception:
            pass
        return empty

    def _run_trace(
        self,
        from_symbol: str,
        to_symbol: str,
        *,
        from_uid: str | None = None,
        to_uid: str | None = None,
    ) -> dict[str, Any] | None:
        cmd = [self.bin_path, "trace", from_symbol, to_symbol, *self._repo_args()]
        if from_uid:
            cmd.extend(["--from-uid", from_uid])
        if to_uid:
            cmd.extend(["--to-uid", to_uid])
        res = subprocess.run(
            cmd,
            cwd=str(self.project_path),
            capture_output=True,
            text=True,
            timeout=25,
                check=False,
            )
        return _extract_json(res.stdout)

    def trace_path(self, from_symbol: str, to_symbol: str) -> dict[str, Any] | None:
        """Find the shortest directed execution path between two symbols."""
        try:
            parsed = self._run_trace(from_symbol, to_symbol)
            if not parsed:
                return None
            from_uid: str | None = None
            to_uid: str | None = None
            # Resolve one ambiguous endpoint at a time (GitNexus reports one role).
            for _ in range(2):
                if parsed.get("status") != "ambiguous":
                    break
                candidates = parsed.get("candidates") or []
                best = pick_best_candidate(
                    candidates if isinstance(candidates, list) else []
                )
                uid = _candidate_uid(best) if best else None
                if not uid:
                    break
                role = parsed.get("role")
                if role == "to":
                    to_uid = uid
                else:
                    from_uid = uid
                parsed = self._run_trace(
                    from_symbol, to_symbol, from_uid=from_uid, to_uid=to_uid
                )
                if not parsed:
                    return None
            return parsed
        except Exception:
            return None

    def detect_changes(self) -> dict[str, Any]:
        """Maps git diff hunks to indexed symbols and affected execution flows."""
        try:
            res = subprocess.run(
                [self.bin_path, "detect-changes", *self._repo_args()],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=25,
                check=False,
            )
            parsed = _extract_json(res.stdout)
            if parsed:
                return parsed
            return {"raw_output": res.stdout}
        except Exception as e:
            return {"error": str(e)}
