# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "av>=15,<17",
#   "rich>=14,<16",
#   "yt-dlp>=2025.1.15",
# ]
# ///
"""Cache an Exit Japanese grammar playlist using one downloader for N5–N1."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence

import cache_n2_videos as downloader


@dataclass(frozen=True)
class Course:
    playlist_id: str
    first_video_id: str
    lesson_count: int


COURSES: dict[str, Course] = {
    "N1": Course("PLynCeSdpMqxCBtZzRikWkdbRGS9csjDYT", "riUjVcsPbqo", 120),
    "N2": Course("PLynCeSdpMqxD6LeS82vp39kQP8mw_JxlY", "0TbPGbvdOnk", 120),
    "N3": Course("PLynCeSdpMqxDS6EC0L7vXYUAVCstRHcQR", "eGxvduVsfJo", 120),
    "N4": Course("PLynCeSdpMqxD8N-l7AC_aFocINA2CKQKi", "tq7OQec7Dnc", 120),
    "N5": Course("PLynCeSdpMqxD4OJHjNB3QkmfzfD7B_s67", "3zRXvtDnev8", 119),
}


def configure_level(level: str):
    """Configure the shared downloader for one verified course playlist."""
    level = level.upper()
    try:
        course = COURSES[level]
    except KeyError as exc:
        raise ValueError(f"不支持的课程等级：{level}") from exc
    downloader.PLAYLIST_ID = course.playlist_id
    downloader.PLAYLIST_URL = (
        f"https://www.youtube.com/playlist?list={course.playlist_id}"
    )
    downloader.DEFAULT_CACHE_ROOT = Path(".firecrawl") / level.lower()
    downloader.COURSE_LEVEL = level
    downloader.EXPECTED_FIRST_VIDEO_ID = course.first_video_id
    downloader.EXPECTED_LESSONS = course.lesson_count
    return downloader


def run_level(level: str, argv: Sequence[str] | None = None) -> int:
    return configure_level(level).main(argv)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="缓存出口日語 N5–N1 语法课程视频及日语字幕",
        add_help=False,
    )
    parser.add_argument("level", choices=sorted(COURSES))
    args, remaining = parser.parse_known_args(argv)
    return run_level(args.level, remaining)


if __name__ == "__main__":
    raise SystemExit(main())
