"""Unit tests for Graphify entity typing and mixed search ranking."""

import unittest

from code_chain.adapters.graphify_adapter import (
    classify_entity_type,
    entity_match_score,
    select_mixed_entities,
)
from code_chain.core.models import CrossDomainEntity


def _entity(entity_id: str, name: str, entity_type: str, degree: int) -> CrossDomainEntity:
    return CrossDomainEntity(
        id=entity_id,
        name=name,
        entity_type=entity_type,
        source_path="x",
        degree=degree,
    )


class TestGraphifyEntityTyping(unittest.TestCase):
    def test_sql_file_is_schema(self):
        self.assertEqual(
            classify_entity_type(
                "supabase/migrations/20260801000000_platform_schema.sql",
                "code",
                "public.entitlements",
            ),
            "schema",
        )

    def test_public_label_is_schema(self):
        self.assertEqual(classify_entity_type("", "code", "public.exams"), "schema")

    def test_code_stays_code(self):
        self.assertEqual(
            classify_entity_type("src/lib/entitlements.ts", "code", "entitlements.ts"),
            "code",
        )

    def test_md_file_is_doc(self):
        self.assertEqual(
            classify_entity_type("docs/ARCH.md", "code", "Architecture Document"),
            "doc",
        )

    def test_qualified_table_outscore_filename(self):
        terms = ["entitlements", "schema", "public.entitlements"]
        table = entity_match_score(
            terms,
            "public.entitlements",
            "n1",
            "supabase/migrations/x.sql",
            "schema",
        )
        ts = entity_match_score(
            terms, "entitlements.ts", "n2", "src/lib/entitlements.ts", "code"
        )
        self.assertGreater(table, ts)

    def test_select_reserves_schema_slots(self):
        ranked = [
            (1, _entity("c1", "entitlements.ts", "code", 51)),
            (1, _entity("c2", "resolve.ts", "code", 20)),
            (1, _entity("s1", "public.entitlements", "schema", 3)),
            (1, _entity("s2", "public.exams", "schema", 2)),
        ]
        selected = select_mixed_entities(ranked, limit=4)
        types = [e.entity_type for e in selected]
        names = [e.name for e in selected]
        self.assertEqual(types.count("schema"), 2)
        self.assertIn("public.entitlements", names)
        self.assertIn("entitlements.ts", names)


if __name__ == "__main__":
    unittest.main()
