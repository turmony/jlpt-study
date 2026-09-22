"""Fixed seven-day review scheduling derived from Git and review events."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .git_state import card_commit_dates
from .models import Card


@dataclass(frozen=True)
class ScheduledCard:
    card: Card
    submitted_on: date
    last_reviewed_on: date | None = None

    @property
    def id(self) -> str:
        return self.card.id

    @property
    def next_review(self) -> date:
        return (self.last_reviewed_on or self.submitted_on) + timedelta(days=7)


@dataclass(frozen=True)
class DailyQueue:
    selected: tuple[ScheduledCard, ...]
    due_count: int
    overdue_count: int
    not_selected_count: int


def schedule_card(
    card: Card,
    submitted_on: date,
    events: Iterable[Mapping[str, object]] = (),
) -> ScheduledCard:
    """Build transient review state without changing the card file."""
    completed = []
    for event in events:
        if event.get("event_type") != "review_completed" or event.get("card_id") != card.id:
            continue
        raw_date = event.get("date")
        if isinstance(raw_date, str):
            completed.append(date.fromisoformat(raw_date))
    return ScheduledCard(card, submitted_on, max(completed) if completed else None)


def schedule_committed_card(
    card: Card,
    repository: Path,
    card_path: Path,
    events: Iterable[Mapping[str, object]] = (),
) -> ScheduledCard:
    """Schedule a card only when its current bytes are present in Git ``HEAD``."""
    commit_dates = card_commit_dates(repository, card_path)
    if commit_dates is None:
        raise ValueError("card version has not been submitted to Git")
    return schedule_card(card, commit_dates.created_at, events)


def due_cards(cards: Iterable[ScheduledCard], on_date: date, limit: int) -> DailyQueue:
    """Choose due cards, always putting the most overdue cards first."""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    due = [item for item in cards if item.next_review <= on_date]
    due.sort(key=lambda item: (item.next_review, item.id))
    selected = tuple(due[:limit])
    return DailyQueue(selected, len(due), sum(item.next_review < on_date for item in due), len(due) - len(selected))


def complete_review(
    card: Card,
    completed_on: date,
    result: str,
    uncertain: bool = False,
) -> dict[str, object]:
    """Return the event that advances the schedule; never rewrite the card."""
    return {
        "event_type": "review_completed",
        "card_id": card.id,
        "card_revision": card.card_revision,
        "result": result,
        "uncertain": uncertain,
        "date": completed_on.isoformat(),
    }
