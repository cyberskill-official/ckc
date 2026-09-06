"""
Tests for Server-Sent Events (SSE) indexing stream and cancellation.
"""

import json
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from code_chain.ui.server import app


class TestUIStreaming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.test_repo = str(
            Path(__file__).resolve().parent.parent / "examples" / "python-auth-service"
        )

    def test_indexing_stream_initial_events(self):
        # Read stream events using iter_lines()
        with self.client.stream(
            "GET", f"/api/index/stream?project={self.test_repo}"
        ) as response:
            self.assertEqual(response.status_code, 200)
            events = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    payload = json.loads(line[6:])
                    events.append(payload)
                    # Once we have observed the start and step_start events, break to avoid waiting for full re-index
                    if payload.get("event") in ["step_start", "log"]:
                        break

            self.assertGreater(len(events), 0)
            self.assertEqual(events[0]["event"], "start")

    def test_indexing_cancellation_flow(self):
        # Trigger cancellation endpoint and check response
        res = self.client.post(
            "/api/index/cancel", json={"project_path": self.test_repo}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])


if __name__ == "__main__":
    unittest.main()
