"""Run the narrow preflight for one video grammar card.

The command is read-only.  It consolidates the target Git state, the exact
playlist record, adjacent-card metadata, and reusable local caches into one
JSON result so card generation does not need several discovery passes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


PLAYLIST_RECORD = re.compile(
    r"^(?P<lesson>\d+)\|(?P<video_id>[^|]+)\|(?P<title>.*)\|(?P<duration>\d+)$"
)


def playlist_entry(path: Path, lesson: int) -> dict[str, Any]:
    """Read one exact lesson from the saved pipe-delimited playlist map."""
    matches = []
    for raw_line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        match = PLAYLIST_RECORD.fullmatch(raw_line.strip())
        if match and int(match.group("lesson")) == lesson:
            matches.append(match.groupdict())
    if len(matches) != 1:
        raise ValueError(f"播放列表缓存中第{lesson}课记录数量为{len(matches)}，预期为1")
    result = matches[0]
    return {
        "lesson": lesson,
        "video_id": result["video_id"],
        "title": result["title"],
        "duration_seconds": int(result["duration"]),
    }


def frontmatter(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"相邻卡没有JSON前置元数据：{path}")
    return json.loads(text[4:].split("\n---\n", 1)[0])


def git_status(repo_root: Path, paths: list[Path]) -> list[str]:
    relative = [path.relative_to(repo_root).as_posix() for path in paths]
    completed = subprocess.run(
        ["git", "status", "--short", "--", *relative],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def build_report(
    repo_root: Path,
    notes_root: Path,
    cache_root: Path,
    playlist_cache: Path,
    lesson: int,
) -> dict[str, Any]:
    entry = playlist_entry(playlist_cache, lesson)
    card_id = f"N3-G-{lesson:04d}"
    card = notes_root / "grammar" / "n3" / f"{card_id}.md"
    assets = notes_root / "assets" / "grammar" / "n3"
    target_paths = [card, *sorted(assets.glob(f"{card_id}-*.png"))]
    previous = notes_root / "grammar" / "n3" / f"N3-G-{lesson - 1:04d}.md"
    video_id = entry["video_id"]
    caches = sorted(
        path.relative_to(repo_root).as_posix()
        for path in cache_root.glob(f"{video_id}*")
        if path.is_file()
    )
    return {
        "card_id": card_id,
        "target": card.relative_to(repo_root).as_posix(),
        "target_exists": card.exists(),
        "target_git_status": git_status(repo_root, target_paths),
        "playlist_cache": playlist_cache.relative_to(repo_root).as_posix(),
        "playlist": entry,
        "previous_card": {
            "path": previous.relative_to(repo_root).as_posix(),
            "metadata": frontmatter(previous),
        },
        "reusable_cache_files": caches,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="视频语法卡单课定向预检（只读）")
    result.add_argument("--lesson", type=int, required=True)
    result.add_argument("--playlist-cache", type=Path, required=True)
    result.add_argument("--repo-root", type=Path, default=Path("."))
    result.add_argument("--notes-root", type=Path, default=Path("jlpt-notes"))
    result.add_argument("--cache-root", type=Path, default=Path(".firecrawl"))
    return result


def main() -> int:
    args = parser().parse_args()
    repo_root = args.repo_root.resolve(strict=True)
    notes_root = (repo_root / args.notes_root).resolve(strict=True)
    cache_root = (repo_root / args.cache_root).resolve(strict=True)
    playlist_cache = (repo_root / args.playlist_cache).resolve(strict=True)
    try:
        report = build_report(
            repo_root, notes_root, cache_root, playlist_cache, args.lesson
        )
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        parser().exit(1, f"错误：{exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["target_git_status"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
