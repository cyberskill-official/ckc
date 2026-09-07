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

    def test_indexing_stream_initial_events(self):
        with self.client.stream(
            "GET", f"/api/index/stream?project={self.test_repo}"
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
        res = self.client.post(
            "/api/index/cancel", json={"project_path": self.test_repo}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

    def test_cancel_mid_stream(self):
        """Set cancel flag mid-stream and assert a terminal cancelled/complete event."""
        seen = {"start": False, "cancelled": False, "complete": False, "error": False}

        with self.client.stream(
            "GET", f"/api/index/stream?project={self.test_repo}&force=false"
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


if __name__ == "__main__":
    unittest.main()
