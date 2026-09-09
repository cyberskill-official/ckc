"""Regression tests for Round-2 env / concurrency parsing."""

from __future__ import annotations

import unittest

from code_chain.ui.server import _parse_max_concurrent_index


class TestConcurrentIndexEnv(unittest.TestCase):
    def test_invalid_max_concurrent_index_defaults(self):
        self.assertEqual(_parse_max_concurrent_index("not-an-int"), 2)
        self.assertEqual(_parse_max_concurrent_index(""), 2)
        self.assertEqual(_parse_max_concurrent_index(None), 2)

    def test_valid_max_concurrent_index(self):
        self.assertEqual(_parse_max_concurrent_index("5"), 5)
        self.assertEqual(_parse_max_concurrent_index("1"), 1)


if __name__ == "__main__":
    unittest.main()
