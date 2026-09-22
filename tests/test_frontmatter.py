import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from jlpt_notes.frontmatter import read_card, write_card
from jlpt_notes.models import Card
from jlpt_notes.repository import Repository


class FrontmatterTests(unittest.TestCase):
    def test_card_round_trips_as_structured_frontmatter(self) -> None:
        card = Card(
            id="N3-G-0001",
            kind="grammar",
            level="N3",
            title="～わけではない",
            body="# 核心用法\n并非……",
            card_revision=1,
            schema_version=1,
            source={"teacher": "出口仁", "lesson": "12"},
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "card.md"
            write_card(path, card)
            self.assertEqual(read_card(path), card)

    def test_card_rejects_invalid_level(self) -> None:
        with self.assertRaisesRegex(ValueError, "level"):
            Card(
                id="N9-G-0001", kind="grammar", level="N9", title="x", body="x",
                card_revision=1, schema_version=1, source={},
            )

    def test_legacy_lifecycle_fields_are_ignored_when_reading(self) -> None:
        legacy = '''---
{"id":"N3-G-0001","kind":"grammar","level":"N3","title":"～例",\
"status":"confirmed","card_revision":1,"schema_version":1,\
"created_at":"2026-07-01","updated_at":"2026-07-02",\
"next_review":"2026-07-09","source":{},"tags":[],"confusions":[]}
---

正文
'''
        with TemporaryDirectory() as directory:
            path = Path(directory) / "card.md"
            path.write_text(legacy, encoding="utf-8")
            card = read_card(path)
        self.assertEqual(card.id, "N3-G-0001")
        self.assertFalse(hasattr(card, "next_review"))

    def test_repository_creates_all_required_directories(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "jlpt-notes"
            Repository(root).init_layout()
            self.assertTrue((root / "grammar").is_dir())
            self.assertTrue((root / "backups").is_dir())
