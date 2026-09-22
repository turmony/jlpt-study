import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from jlpt_notes.models import Card
from jlpt_notes.repository import Repository


def sample_card() -> Card:
    return Card("N3-G-0001", "grammar", "N3", "～わけではない", "内容", 1, 1,
                {"teacher": "出口仁"})


class RepositoryTests(unittest.TestCase):
    def test_prepare_draft_preserves_original_and_writes_no_lifecycle_fields(self) -> None:
        with TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "notes")
            draft = repo.create_draft("我的理解：并非全部否定。", sample_card())
            before = draft.read_bytes()
            repo.prepare_draft(draft.stem)
            self.assertIn("我的理解：并非全部否定。", draft.read_text(encoding="utf-8"))
            self.assertEqual(before, draft.read_bytes())
            self.assertTrue((repo.root / "grammar" / "n3" / "N3-G-0001.md").exists())
            self.assertFalse((repo.root / "reviews" / "events.jsonl").exists())
            formal = json.loads((repo.root / "grammar" / "n3" / "N3-G-0001.md").read_text(encoding="utf-8").split("---")[1])
            self.assertTrue({"status", "created_at", "updated_at", "next_review"}.isdisjoint(formal))
