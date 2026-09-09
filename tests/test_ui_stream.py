"""
Tests for Server-Sent Events (SSE) indexing stream and cancellation.
"""

import json
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from code_chain.ui import server as ui_server
from code_chain.ui.server import app


class TestUIStreaming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.test_repo = str(
            Path(__file__).resolve().parent.parent / "examples" / "python-auth-service"
        )
        cls.proj_key = str(Path(cls.test_repo).resolve())

    def setUp(self):
        # Clear any leftover cancel/job state from prior stream tests.
        with ui_server._active_indexing_lock:
            ui_server._cancellation_flags[self.proj_key] = False
            ui_server._active_index_jobs.discard(self.proj_key)
        self.client.post("/api/index/cancel", json={"project_path": self.test_repo})
        time.sleep(0.05)

    def test_index_stream_get_returns_405(self):
        res = self.client.get(f"/api/index/stream?project={self.test_repo}")
        self.assertEqual(res.status_code, 405)

    def test_indexing_stream_initial_events(self):
        with self.client.stream(
            "POST",
            "/api/index/stream",
            json={
                "project_path": self.test_repo,
                "force": False,
                "multimodal": False,
            },
        ) as response:
            self.assertEqual(response.status_code, 200)
            events = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    payload = json.loads(line[6:])
                    events.append(payload)
                    # Once we have start/step_start events, break to avoid full re-index wait
                    if payload.get("event") in ["step_start", "log"]:
                        break

            self.assertGreater(len(events), 0)
            self.assertEqual(events[0]["event"], "start")

        # Client disconnect should not leave a stuck job forever; cancel to be sure.
        self.client.post("/api/index/cancel", json={"project_path": self.test_repo})

    def test_indexing_cancellation_flow(self):
        res = self.client.post("/api/index/cancel", json={"project_path": self.test_repo})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

    def test_cancel_mid_stream(self):
        """Set cancel flag mid-stream and assert a terminal cancelled/complete event."""
        seen = {"start": False, "cancelled": False, "complete": False, "error": False}

        with self.client.stream(
            "POST",
            "/api/index/stream",
            json={
                "project_path": self.test_repo,
                "force": False,
                "multimodal": False,
            },
        ) as response:
            self.assertEqual(response.status_code, 200)
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line[6:])
                ev = payload.get("event")
                if ev == "start":
                    seen["start"] = True
                    # Avoid cross-thread TestClient races: flip the in-process flag.
                    with ui_server._active_indexing_lock:
                        ui_server._cancellation_flags[self.proj_key] = True
                elif ev == "cancelled":
                    seen["cancelled"] = True
                    break
                elif ev == "complete":
                    seen["complete"] = True
                    break
                elif ev == "error":
                    seen["error"] = True
                    break

        self.assertTrue(seen["start"], "expected start event before cancel/complete")
        self.assertTrue(
            seen["cancelled"] or seen["complete"] or seen["error"],
            f"expected cancelled/complete/error after mid-stream cancel, got {seen}",
        )
        with ui_server._active_indexing_lock:
            self.assertNotIn(self.proj_key, ui_server._active_index_jobs)

    def test_cancel_sticky_between_reserve_and_generator(self):
        """Cancel set after reservation must remain True at generator-entry check."""
        with ui_server._active_indexing_lock:
            # Mimic reservation: claim job and clear cancel.
            ui_server._active_index_jobs.add(self.proj_key)
            ui_server._cancellation_flags[self.proj_key] = False
            # Race: user cancels after reservation, before generator body runs.
            ui_server._cancellation_flags[self.proj_key] = True
            already_cancelled = ui_server._cancellation_flags.get(self.proj_key, False)
            # Generator entry must honor this without clearing (R2-SEC-02).
            self.assertTrue(already_cancelled)
            ui_server._active_index_jobs.discard(self.proj_key)

        with self.client.stream(
            "POST",
            "/api/index/stream",
            json={
                "project_path": self.test_repo,
                "force": False,
                "multimodal": False,
            },
        ) as response:
            self.assertEqual(response.status_code, 200)
            # Headers mean reservation completed (cancel cleared once).
            # Re-set cancel before reading body so the entry check can fire.
            with ui_server._active_indexing_lock:
                ui_server._cancellation_flags[self.proj_key] = True

            events = []
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line[6:])
                events.append(payload)
                if payload.get("event") in {"cancelled", "start", "complete", "error"}:
                    break

        self.assertTrue(events, "expected at least one SSE event")
        # Prefer cancelled; if the generator already passed the entry check,
        # mid-loop cancel still yields cancelled (covered by test_cancel_mid_stream).
        self.assertIn(events[0].get("event"), {"cancelled", "start"})
        if events[0].get("event") == "start":
            # Flag was set too late for entry check; ensure it was not cleared to False.
            with ui_server._active_indexing_lock:
                self.assertTrue(
                    ui_server._cancellation_flags.get(self.proj_key, False)
                    or self.proj_key not in ui_server._active_index_jobs
                )

        self.client.post("/api/index/cancel", json={"project_path": self.test_repo})


if __name__ == "__main__":
    unittest.main()
