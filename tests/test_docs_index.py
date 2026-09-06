"""Unit tests for the local markdown docs overlay."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from code_chain.adapters.graphify_adapter import (
    GraphifyAdapter,
    classify_entity_type,
)
from code_chain.core.docs_index import (
    index_docs_overlay,
    load_docs_index,
    write_docs_index,
)


class TestDocsIndex(unittest.TestCase):
    def test_markdown_classified_as_doc(self):
        self.assertEqual(
            classify_entity_type("docs/ARCH.md", "code", "Architecture Document"),
            "doc",
        )
        self.assertEqual(classify_entity_type("README.mdx", "code", "Readme"), "doc")
        self.assertEqual(classify_entity_type("guide.rst", "code", "Guide"), "doc")

    def test_write_and_load_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "ARCH.md").write_text(
                "# Architecture Document\n"
                "Authentication is handled by AuthService.\n",
                encoding="utf-8",
            )
            (root / "src").mkdir()
            (root / "src" / "auth.py").write_text("class AuthService: pass\n", encoding="utf-8")
            (root / ".git").mkdir()
            (root / "node_modules").mkdir()
            (root / "node_modules" / "README.md").write_text("# Skip me\n", encoding="utf-8")

            result = write_docs_index(root)
            self.assertEqual(result["discovered_files"], 1)
            self.assertGreaterEqual(result["doc_count"], 1)
            loaded = load_docs_index(root)
            self.assertGreaterEqual(loaded["doc_count"], 1)
            doc = loaded["docs"][0]
            self.assertEqual(doc["entity_type"], "doc")
            self.assertEqual(doc["source_path"], "docs/ARCH.md")
            self.assertIn("Architecture", doc["name"])
            self.assertIn("AuthService", doc["excerpt"])

    def test_frontmatter_excerpt_uses_heading_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "guide.md").write_text(
                "---\ntitle: Ignored YAML Title\ndescription: frontmatter noise\n---\n"
                "# Real Heading\n"
                "Body about AuthService login flow.\n",
                encoding="utf-8",
            )
            result = write_docs_index(root)
            self.assertGreaterEqual(result["doc_count"], 1)
            excerpts = " ".join(d["excerpt"] for d in result["docs"])
            names = " ".join(d["name"] for d in result["docs"])
            self.assertIn("AuthService", excerpts)
            self.assertNotIn("frontmatter noise", excerpts)
            self.assertIn("Real Heading", names)

    def test_auth_service_query_surfaces_arch_doc(self):
        sample = (
            Path(__file__).resolve().parent.parent
            / "examples"
            / "python-auth-service"
        )
        index_docs_overlay(sample, code_only=True, announce=False)
        adapter = GraphifyAdapter("graphify", sample)
        hits = adapter.find_cross_domain_entities("AuthService", limit=8)
        doc_hits = [e for e in hits if e.entity_type == "doc"]
        self.assertTrue(
            any(
                "ARCH" in (e.source_path or "") or "Architecture" in e.name
                for e in doc_hits
            ),
            (
                "Expected ARCH.md doc hit, got: "
                f"{[(e.name, e.source_path, e.entity_type) for e in hits]}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
