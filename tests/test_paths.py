"""Unit tests for project-path lockdown and target gitignore hygiene."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_chain.core.paths import (
    UnsafeProjectPathError,
    assert_safe_project_path,
    ensure_engine_gitignore,
)


class TestProjectPathSafety(unittest.TestCase):
    def test_rejects_system_etc(self):
        with self.assertRaises(UnsafeProjectPathError):
            assert_safe_project_path("/etc")

    def test_rejects_missing(self):
        with self.assertRaises(UnsafeProjectPathError):
            assert_safe_project_path("/non/existent/path/999")

    def test_rejects_src_only_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            with self.assertRaises(UnsafeProjectPathError):
                assert_safe_project_path(str(root))

    def test_gitignore_appends_engine_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
            added = ensure_engine_gitignore(root)
            self.assertIn("graphify-out/", added)
            text = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("graphify-out/", text)
            self.assertIn(".gitnexus/", text)
            self.assertEqual(ensure_engine_gitignore(root), [])

    def test_gitignore_opt_out_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            with patch.dict(os.environ, {"CKC_SKIP_GITIGNORE": "1"}, clear=False):
                self.assertEqual(ensure_engine_gitignore(root), [])
            self.assertFalse((root / ".gitignore").exists())


if __name__ == "__main__":
    unittest.main()
