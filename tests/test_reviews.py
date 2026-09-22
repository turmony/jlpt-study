import os
import subprocess
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from jlpt_notes.frontmatter import write_card
from jlpt_notes.models import Card
from jlpt_notes.reviews import (
    complete_review,
    due_cards,
    schedule_card,
    schedule_committed_card,
)


def card(card_id: str) -> Card:
    return Card(card_id, "grammar", "N3", card_id, "内容", 1, 1, {})


class ReviewTests(unittest.TestCase):
    def test_late_completion_restarts_seven_day_cycle_without_mutating_card(self) -> None:
        item = card("N3-G-0001")
        event = complete_review(item, date(2026, 7, 10), "incorrect", uncertain=True)
        scheduled = schedule_card(item, date(2026, 7, 1), [event])
        self.assertEqual(date(2026, 7, 17), scheduled.next_review)
        self.assertEqual("incorrect", event["result"])
        self.assertTrue(event["uncertain"])
        self.assertFalse(hasattr(item, "next_review"))

    def test_daily_queue_prioritises_overdue_and_respects_limit(self) -> None:
        items = [
            schedule_card(card("N3-G-0001"), date(2026, 7, 8)),
            schedule_card(card("N2-G-0001"), date(2026, 7, 3)),
            schedule_card(card("N3-G-0002"), date(2026, 7, 10)),
        ]
        queue = due_cards(items, date(2026, 7, 17), 2)
        self.assertEqual(["N2-G-0001", "N3-G-0001"], [item.id for item in queue.selected])
        self.assertEqual(1, queue.not_selected_count)

    def test_git_commit_is_the_submission_boundary(self) -> None:
        with TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
            path = repository / "jlpt-notes/grammar/n3/N3-G-0001.md"
            path.parent.mkdir(parents=True)
            item = card("N3-G-0001")
            write_card(path, item)
            with self.assertRaisesRegex(ValueError, "not been submitted"):
                schedule_committed_card(item, repository, path)

            subprocess.run(["git", "add", "--", path.relative_to(repository)], cwd=repository, check=True)
            environment = os.environ.copy()
            environment.update({
                "GIT_AUTHOR_DATE": "2026-07-01T12:00:00+08:00",
                "GIT_COMMITTER_DATE": "2026-07-01T12:00:00+08:00",
            })
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "-m", "add card"],
                cwd=repository,
                check=True,
                capture_output=True,
                env=environment,
            )
            scheduled = schedule_committed_card(item, repository, path)
            self.assertEqual(date(2026, 7, 8), scheduled.next_review)

            path.write_text(path.read_text(encoding="utf-8") + "\n未提交修改\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not been submitted"):
                schedule_committed_card(item, repository, path)
