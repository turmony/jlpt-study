"""Derive card lifecycle dates from the Git commit that contains its bytes."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass(frozen=True)
class CommitDates:
    created_at: date
    updated_at: date


def committed_files(repository: Path) -> frozenset[Path] | None:
    """Return clean tracked files, or ``None`` outside a Git worktree."""
    try:
        top_path = Path(_git(repository, "rev-parse", "--show-toplevel").strip()).resolve()
        tracked_output = _git(top_path, "ls-files", "-z")
        status_output = _git(top_path, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    except subprocess.CalledProcessError:
        return None

    tracked = {item for item in tracked_output.split("\0") if item}
    changed: set[str] = set()
    entries = status_output.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry or len(entry) < 4:
            continue
        code, relative = entry[:2], entry[3:]
        changed.add(relative)
        if any(marker in code for marker in ("R", "C")) and index < len(entries):
            previous = entries[index]
            index += 1
            if previous:
                changed.add(previous)
    return frozenset((top_path / item).resolve() for item in tracked - changed)


def card_commit_dates(repository: Path, card_path: Path) -> CommitDates | None:
    """Return commit dates only when the current card bytes are in ``HEAD``."""
    top_path = Path(_git(repository, "rev-parse", "--show-toplevel").strip()).resolve()
    full_path = card_path if card_path.is_absolute() else repository / card_path
    full_path = full_path.resolve()
    try:
        relative = full_path.relative_to(top_path).as_posix()
    except ValueError as error:
        raise ValueError(f"card is outside the Git repository: {full_path}") from error

    try:
        head_blob = _git(top_path, "rev-parse", f"HEAD:{relative}").strip()
    except subprocess.CalledProcessError:
        return None
    working_blob = _git(top_path, "hash-object", "--", str(full_path)).strip()
    if not working_blob or working_blob != head_blob:
        return None

    output = _git(top_path, "log", "--follow", "--format=%cI", "--", relative)
    timestamps = [
        datetime.fromisoformat(line.strip().replace("Z", "+00:00"))
        for line in output.splitlines()
        if line.strip()
    ]
    if not timestamps:
        return None
    return CommitDates(created_at=timestamps[-1].date(), updated_at=timestamps[0].date())


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
