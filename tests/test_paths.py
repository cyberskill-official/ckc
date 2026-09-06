"""Unit tests for project-path lockdown and target gitignore hygiene."""

import tempfile
import unittest
from pathlib import Path
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

    def test_accepts_bundled_sample(self):
        sample = Path(__file__).resolve().parent.parent / "examples" / "python-auth-service"
        resolved = assert_safe_project_path(str(sample))
        self.assertEqual(resolved, sample.resolve())

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


if __name__ == "__main__":
    unittest.main()
