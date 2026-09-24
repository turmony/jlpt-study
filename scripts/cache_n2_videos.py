# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "av>=15,<17",
#   "rich>=14,<16",
#   "yt-dlp>=2025.1.15",
# ]
# ///
"""Manually cache the N2 course videos and Japanese subtitles.

The script is intentionally not invoked by the grammar-card workflow. Run it
manually with ``uv run scripts/cache_n2_videos.py``. Completed lessons are
verified and skipped on later runs, and yt-dlp keeps partial downloads so an
interrupted batch can be resumed.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

PLAYLIST_URL = (
    "https://www.youtube.com/playlist?list=PLynCeSdpMqxD6LeS82vp39kQP8mw_JxlY"
)
PLAYLIST_ID = "PLynCeSdpMqxD6LeS82vp39kQP8mw_JxlY"
EXPECTED_LESSONS = 120
DEFAULT_CACHE_ROOT = Path(".firecrawl/n2")
COURSE_LEVEL = "N2"
EXPECTED_FIRST_VIDEO_ID: str | None = None
MANIFEST_NAME = "course-manifest.json"
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
VTT_CUE = re.compile(
    r"(?m)^(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3}\s+-->\s+"
    r"(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3}"
)
INCOMPLETE_SUFFIXES = {".part", ".temp", ".tmp", ".ytdl"}


@dataclass(frozen=True)
class PlaylistItem:
    lesson: int
    video_id: str | None
    title: str
    duration_seconds: float | None
    webpage_url: str | None
    error: str | None = None


@dataclass(frozen=True)
class VideoProbe:
    duration_seconds: float
    width: int
    height: int
    has_audio: bool


def local_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_lesson_spec(value: str, maximum: int = EXPECTED_LESSONS) -> list[int]:
    """Parse ``1-20,35,80-90`` into sorted, unique lesson numbers."""
    lessons: set[int] = set()
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            raise argparse.ArgumentTypeError("课程序号中不能包含空项")
        if "-" in part:
            if part.count("-") != 1:
                raise argparse.ArgumentTypeError(f"无效课程范围：{part!r}")
            start_text, end_text = part.split("-", 1)
            if not start_text.isdigit() or not end_text.isdigit():
                raise argparse.ArgumentTypeError(f"无效课程范围：{part!r}")
            start, end = int(start_text), int(end_text)
            if start > end:
                raise argparse.ArgumentTypeError(f"课程范围起点不能大于终点：{part!r}")
            lessons.update(range(start, end + 1))
        elif part.isdigit():
            lessons.add(int(part))
        else:
            raise argparse.ArgumentTypeError(f"无效课程序号：{part!r}")
    if not lessons:
        raise argparse.ArgumentTypeError("至少需要一个课程序号")
    invalid = sorted(number for number in lessons if not 1 <= number <= maximum)
    if invalid:
        raise argparse.ArgumentTypeError(
            f"课程序号必须在 1-{maximum} 之间：{', '.join(map(str, invalid))}"
        )
    return sorted(lessons)


def safe_video_id(value: Any) -> str | None:
    if not isinstance(value, str) or not VIDEO_ID.fullmatch(value):
        return None
    return value


def optional_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def playlist_items(
    playlist_info: dict[str, Any], requested_lessons: Sequence[int]
) -> dict[int, PlaylistItem]:
    """Return requested entries without renumbering unavailable playlist items."""
    requested = set(requested_lessons)
    selected: dict[int, PlaylistItem] = {}
    entries = playlist_info.get("entries")
    if not isinstance(entries, list):
        raise TypeError("播放列表没有可读取的 entries")

    for position, raw_entry in enumerate(entries, start=1):
        if raw_entry is None:
            index = position
            if index in requested:
                selected[index] = PlaylistItem(
                    lesson=index,
                    video_id=None,
                    title="",
                    duration_seconds=None,
                    webpage_url=None,
                    error="播放列表条目不可用、被删除或为私密视频",
                )
            continue
        if not isinstance(raw_entry, dict):
            continue
        raw_index = raw_entry.get("playlist_index", position)
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            index = position
        if index not in requested:
            continue
        if index in selected:
            raise ValueError(f"播放列表第 {index} 项出现重复记录")
        video_id = safe_video_id(raw_entry.get("id"))
        title = str(raw_entry.get("title") or "").strip()
        webpage_url = raw_entry.get("webpage_url") or raw_entry.get("url")
        if video_id and not (
            isinstance(webpage_url, str)
            and webpage_url.startswith(("http://", "https://"))
        ):
            webpage_url = f"https://www.youtube.com/watch?v={video_id}"
        error = None
        if video_id is None:
            error = "播放列表条目缺少有效的视频 ID，可能已被删除或设为私密"
        elif not title:
            error = "播放列表条目缺少可读标题"
        selected[index] = PlaylistItem(
            lesson=index,
            video_id=video_id,
            title=title,
            duration_seconds=optional_float(raw_entry.get("duration")),
            webpage_url=str(webpage_url) if webpage_url else None,
            error=error,
        )

    for lesson in requested_lessons:
        selected.setdefault(
            lesson,
            PlaylistItem(
                lesson=lesson,
                video_id=None,
                title="",
                duration_seconds=None,
                webpage_url=None,
                error="播放列表中缺少该位置",
            ),
        )

    by_video: dict[str, list[int]] = {}
    for item in selected.values():
        if item.video_id:
            by_video.setdefault(item.video_id, []).append(item.lesson)
    duplicate_ids = {key: value for key, value in by_video.items() if len(value) > 1}
    for video_id, lessons in duplicate_ids.items():
        detail = f"视频 ID {video_id} 重复出现在课程 {', '.join(map(str, lessons))}"
        for lesson in lessons:
            item = selected[lesson]
            selected[lesson] = PlaylistItem(
                lesson=item.lesson,
                video_id=item.video_id,
                title=item.title,
                duration_seconds=item.duration_seconds,
                webpage_url=item.webpage_url,
                error=detail,
            )
    return selected


def new_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "playlist_id": PLAYLIST_ID,
        "playlist_url": PLAYLIST_URL,
        "fetched_at": None,
        "expected_lessons": EXPECTED_LESSONS,
        "entries": [],
    }


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return new_manifest()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取缓存清单 {path}：{exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError(f"不支持的缓存清单格式：{path}")
    if not isinstance(data.get("entries"), list):
        raise TypeError(f"缓存清单 entries 不是列表：{path}")
    if data.get("playlist_id") != PLAYLIST_ID:
        raise ValueError(f"缓存清单播放列表与{COURSE_LEVEL}课程不匹配：{path}")
    return data


def manifest_entries(manifest: dict[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for entry in manifest.get("entries", []):
        if not isinstance(entry, dict):
            continue
        lesson = entry.get("lesson")
        if isinstance(lesson, int) and 1 <= lesson <= EXPECTED_LESSONS:
            result[lesson] = entry
    return result


def set_manifest_entry(manifest: dict[str, Any], entry: dict[str, Any]) -> None:
    entries = manifest_entries(manifest)
    entries[int(entry["lesson"])] = entry
    manifest["entries"] = [entries[key] for key in sorted(entries)]


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Write a manifest atomically so interruption cannot corrupt the old copy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def cache_relative_path(cache_root: Path, path: Path) -> str:
    root = cache_root.resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"缓存文件不在缓存目录内：{path}") from exc


def resolve_cache_path(cache_root: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError("缓存清单缺少文件路径")
    root = cache_root.resolve()
    candidate = (root / Path(relative)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"缓存清单路径越过缓存目录：{relative}") from exc
    return candidate


def probe_video(path: Path) -> VideoProbe:
    if not path.is_file() or path.stat().st_size < 1024:
        raise ValueError(f"视频不存在或文件过小：{path}")
    try:
        import av

        with av.open(str(path)) as container:
            if not container.streams.video:
                raise ValueError(f"视频文件没有视频流：{path}")
            stream = container.streams.video[0]
            if container.duration is not None:
                duration = float(container.duration / av.time_base)
            elif stream.duration is not None and stream.time_base is not None:
                duration = float(stream.duration * stream.time_base)
            else:
                raise ValueError(f"无法确定视频时长：{path}")
            width = int(stream.codec_context.width or 0)
            height = int(stream.codec_context.height or 0)
            if (
                not math.isfinite(duration)
                or duration <= 1
                or width <= 0
                or height <= 0
            ):
                raise ValueError(f"视频元数据无效：{path}")
            return VideoProbe(duration, width, height, bool(container.streams.audio))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"无法打开视频 {path}：{exc}") from exc


def verify_subtitle(path: Path) -> None:
    if not path.is_file() or path.stat().st_size < 20:
        raise ValueError(f"日语字幕不存在或文件过小：{path}")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"无法读取日语字幕 {path}：{exc}") from exc
    if not text.lstrip().startswith("WEBVTT") or VTT_CUE.search(text) is None:
        raise ValueError(f"日语字幕不是有效的 WebVTT 文件：{path}")


def verify_manifest_entry(
    cache_root: Path, entry: dict[str, Any], expected_video_id: str | None = None
) -> tuple[Path, Path, VideoProbe]:
    if entry.get("status") != "complete":
        raise ValueError(str(entry.get("last_error") or "缓存状态不是 complete"))
    video_id = safe_video_id(entry.get("video_id"))
    if video_id is None:
        raise ValueError("缓存清单中的视频 ID 无效")
    if expected_video_id and video_id != expected_video_id:
        raise ValueError(
            f"缓存视频 ID {video_id} 与播放列表视频 ID {expected_video_id} 不一致"
        )
    video = resolve_cache_path(cache_root, entry.get("video_path"))
    subtitle = resolve_cache_path(cache_root, entry.get("subtitle_path"))
    probe = probe_video(video)
    verify_subtitle(subtitle)
    return video, subtitle, probe


def format_bytes(value: float | None) -> str:
    if value is None:
        return "?"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(size) < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


class ProgressDisplay:
    """Two Rich tasks: the batch and the currently downloading video."""

    def __init__(self, total_lessons: int, enabled: bool = True) -> None:
        self.enabled = enabled
        self.total_lessons = total_lessons
        self.completed_lessons = 0
        self.progress: Any = None
        self.overall_task: Any = None
        self.download_task: Any = None
        if enabled:
            from rich.console import Console
            from rich.progress import (
                BarColumn,
                Progress,
                SpinnerColumn,
                TaskProgressColumn,
                TextColumn,
                TimeElapsedColumn,
            )

            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("{task.description}", markup=False),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TextColumn("{task.fields[detail]}", markup=False),
                console=Console(stderr=True),
            )

    def __enter__(self) -> Self:
        if self.enabled:
            self.progress.start()
            self.overall_task = self.progress.add_task(
                f"{COURSE_LEVEL} 总进度",
                total=self.total_lessons,
                detail=f"0/{self.total_lessons} 课",
            )
            self.download_task = self.progress.add_task(
                "等待下载",
                total=None,
                detail="",
                visible=False,
            )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.enabled:
            self.progress.stop()

    def start_lesson(self, lesson: int, title: str) -> None:
        if self.enabled:
            shortened = title if len(title) <= 42 else f"{title[:39]}..."
            self.progress.update(
                self.download_task,
                description=f"第 {lesson} 课 {shortened}",
                total=None,
                completed=0,
                detail="准备",
                visible=True,
            )

    def update_download(self, data: dict[str, Any]) -> None:
        if not self.enabled or data.get("status") not in {"downloading", "finished"}:
            return
        if data.get("status") == "finished":
            total = data.get("total_bytes") or data.get("downloaded_bytes")
            self.progress.update(
                self.download_task,
                total=total or 1,
                completed=total or 1,
                detail="视频下载完成，正在检查字幕",
            )
            return
        downloaded = int(data.get("downloaded_bytes") or 0)
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        speed = data.get("speed")
        eta = data.get("eta")
        detail_parts = [
            f"{format_bytes(downloaded)}/{format_bytes(total)}",
            f"{format_bytes(speed)}/s" if speed else "速度 ?",
        ]
        if isinstance(eta, (int, float)):
            detail_parts.append(f"剩余 {int(eta)}s")
        self.progress.update(
            self.download_task,
            total=int(total) if total else None,
            completed=downloaded,
            detail=" · ".join(detail_parts),
        )

    def finish_lesson(self, status: str) -> None:
        self.completed_lessons += 1
        if self.enabled:
            self.progress.update(self.download_task, visible=False)
            self.progress.update(
                self.overall_task,
                advance=1,
                detail=f"{self.completed_lessons}/{self.total_lessons} 课 · {status}",
            )

    def log(self, message: str) -> None:
        if self.enabled:
            self.progress.console.print(message, markup=False)
        else:
            print(message, file=sys.stderr)


def cookie_option(browser: str | None) -> dict[str, Any]:
    if not browser:
        return {}
    return {"cookiesfrombrowser": (browser, None, None, None)}


def fetch_playlist(
    playlist_url: str,
    maximum_lesson: int,
    browser: str | None,
) -> dict[str, Any]:
    import yt_dlp

    options: dict[str, Any] = {
        "extract_flat": "in_playlist",
        "skip_download": True,
        "playlistend": maximum_lesson,
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
    }
    options.update(cookie_option(browser))
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(playlist_url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise ValueError(f"无法读取播放列表：{exc}") from exc
    if not isinstance(info, dict):
        raise TypeError("无法读取播放列表元数据")
    return info


def download_options(
    cache_root: Path,
    max_height: int,
    force: bool,
    browser: str | None,
    progress_hook: Any,
) -> dict[str, Any]:
    video_root = cache_root / "videos"
    subtitle_root = cache_root / "subtitles"
    video_root.mkdir(parents=True, exist_ok=True)
    subtitle_root.mkdir(parents=True, exist_ok=True)
    options: dict[str, Any] = {
        "format": (
            f"bestvideo[height<={max_height}][ext=mp4]/bestvideo[height<={max_height}]"
        ),
        "outtmpl": {
            "default": str(video_root / "%(id)s.f%(format_id)s.%(ext)s"),
            "subtitle": str(subtitle_root / "%(id)s.%(language)s.%(ext)s"),
        },
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["ja"],
        "subtitlesformat": "vtt/best",
        "noplaylist": True,
        "continuedl": True,
        "overwrites": force,
        "retries": 10,
        "fragment_retries": 10,
        "file_access_retries": 3,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [progress_hook],
    }
    options.update(cookie_option(browser))
    return options


def downloaded_video_path(
    info: dict[str, Any], cache_root: Path, video_id: str
) -> Path:
    for requested in info.get("requested_downloads") or []:
        if not isinstance(requested, dict):
            continue
        filepath = requested.get("filepath")
        if isinstance(filepath, str):
            candidate = Path(filepath)
            if candidate.is_file():
                return candidate
    candidates = [
        path
        for path in (cache_root / "videos").glob(f"{video_id}.f*.*")
        if path.is_file() and path.suffix.lower() not in INCOMPLETE_SUFFIXES
    ]
    if not candidates:
        raise ValueError(f"下载结束后没有找到视频文件：{video_id}")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def downloaded_subtitle_path(
    info: dict[str, Any], cache_root: Path, video_id: str
) -> Path:
    requested_subtitles = info.get("requested_subtitles")
    if isinstance(requested_subtitles, dict):
        for subtitle in requested_subtitles.values():
            if not isinstance(subtitle, dict):
                continue
            filepath = subtitle.get("filepath")
            if isinstance(filepath, str):
                candidate = Path(filepath)
                if candidate.is_file() and candidate.suffix.lower() == ".vtt":
                    return candidate

    exact = cache_root / "subtitles" / f"{video_id}.ja.vtt"
    if exact.is_file():
        return exact
    candidates = [
        path
        for path in (cache_root / "subtitles").glob(f"{video_id}.*.vtt")
        if path.is_file() and ".ja." in path.name.casefold()
    ]
    if not candidates:
        raise ValueError(f"视频没有可用的日语 WebVTT 字幕：{video_id}")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def subtitle_kind(info: dict[str, Any]) -> str:
    subtitles = info.get("subtitles")
    if isinstance(subtitles, dict) and subtitles.get("ja"):
        return "manual"
    automatic = info.get("automatic_captions")
    if isinstance(automatic, dict) and automatic.get("ja"):
        return "automatic"
    return "unknown"


def download_item(
    item: PlaylistItem,
    cache_root: Path,
    max_height: int,
    force: bool,
    browser: str | None,
    display: ProgressDisplay,
) -> dict[str, Any]:
    if item.video_id is None:
        raise ValueError(item.error or "视频 ID 无效")
    import yt_dlp

    url = item.webpage_url or f"https://www.youtube.com/watch?v={item.video_id}"
    options = download_options(
        cache_root,
        max_height,
        force,
        browser,
        display.update_download,
    )
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise ValueError(f"yt-dlp 下载失败：{exc}") from exc
    if not isinstance(info, dict):
        raise TypeError(f"下载器没有返回视频信息：{item.video_id}")

    video = downloaded_video_path(info, cache_root, item.video_id)
    subtitle = downloaded_subtitle_path(info, cache_root, item.video_id)
    probe = probe_video(video)
    verify_subtitle(subtitle)
    format_id = info.get("format_id")
    return {
        "lesson": item.lesson,
        "playlist_index": item.lesson,
        "video_id": item.video_id,
        "title": str(info.get("title") or item.title),
        "duration_seconds": optional_float(info.get("duration"))
        or probe.duration_seconds,
        "webpage_url": str(info.get("webpage_url") or url),
        "video_path": cache_relative_path(cache_root, video),
        "subtitle_path": cache_relative_path(cache_root, subtitle),
        "subtitle_kind": subtitle_kind(info),
        "format_id": str(format_id) if format_id is not None else None,
        "width": probe.width,
        "height": probe.height,
        "has_audio": probe.has_audio,
        "video_bytes": video.stat().st_size,
        "subtitle_bytes": subtitle.stat().st_size,
        "downloaded_at": local_now(),
        "checked_at": local_now(),
        "status": "complete",
    }


def unavailable_entry(item: PlaylistItem, error: str) -> dict[str, Any]:
    return {
        "lesson": item.lesson,
        "playlist_index": item.lesson,
        "video_id": item.video_id,
        "title": item.title,
        "duration_seconds": item.duration_seconds,
        "webpage_url": item.webpage_url,
        "checked_at": local_now(),
        "status": "error",
        "last_error": error,
    }


def refresh_cached_entry(
    existing: dict[str, Any], item: PlaylistItem, probe: VideoProbe
) -> dict[str, Any]:
    updated = dict(existing)
    updated.update(
        {
            "playlist_index": item.lesson,
            "title": item.title,
            "duration_seconds": item.duration_seconds or probe.duration_seconds,
            "webpage_url": item.webpage_url,
            "width": probe.width,
            "height": probe.height,
            "has_audio": probe.has_audio,
            "checked_at": local_now(),
            "status": "complete",
        }
    )
    updated.pop("last_error", None)
    return updated


def verify_only(
    manifest: dict[str, Any],
    lessons: Sequence[int],
    cache_root: Path,
    display: ProgressDisplay,
) -> tuple[int, int]:
    entries = manifest_entries(manifest)
    complete = 0
    failed = 0
    for lesson in lessons:
        entry = entries.get(lesson)
        title = str(entry.get("title") or "") if entry else ""
        display.start_lesson(lesson, title)
        try:
            if entry is None:
                raise ValueError("缓存清单中没有该课程")
            verify_manifest_entry(cache_root, entry)
        except (OSError, ValueError) as exc:
            failed += 1
            display.log(f"第 {lesson} 课校验失败：{exc}")
            display.finish_lesson("失败")
        else:
            complete += 1
            display.finish_lesson("有效")
    return complete, failed


def download_batch(
    args: argparse.Namespace, display: ProgressDisplay
) -> tuple[int, int, int]:
    cache_root: Path = args.cache_root
    manifest_path = cache_root / MANIFEST_NAME
    manifest = load_manifest(manifest_path)
    display.log(f"正在读取 {COURSE_LEVEL} 播放列表……")
    playlist = fetch_playlist(
        args.playlist_url, max(args.lessons), args.cookies_from_browser
    )
    if EXPECTED_FIRST_VIDEO_ID is not None:
        if playlist.get("id") != PLAYLIST_ID:
            raise ValueError(
                f"{COURSE_LEVEL} 播放列表 ID 不匹配："
                f"预期 {PLAYLIST_ID}，实际 {playlist.get('id')}"
            )
        entries = playlist.get("entries")
        first = entries[0] if isinstance(entries, list) and entries else None
        if not isinstance(first, dict) or first.get("id") != EXPECTED_FIRST_VIDEO_ID:
            raise ValueError(
                f"{COURSE_LEVEL} 播放列表第1课的视频 ID 与课程入口不一致："
                f"预期 {EXPECTED_FIRST_VIDEO_ID}，实际 {first.get('id') if isinstance(first, dict) else '缺失'}"
            )
    items = playlist_items(playlist, args.lessons)
    manifest.update(
        {
            "schema_version": 1,
            "playlist_id": str(playlist.get("id") or PLAYLIST_ID),
            "playlist_url": args.playlist_url,
            "playlist_title": playlist.get("title"),
            "fetched_at": local_now(),
            "expected_lessons": EXPECTED_LESSONS,
        }
    )
    write_manifest(manifest_path, manifest)

    completed = 0
    skipped = 0
    failed = 0
    for lesson in args.lessons:
        item = items[lesson]
        display.start_lesson(lesson, item.title)
        if item.error:
            failed += 1
            set_manifest_entry(manifest, unavailable_entry(item, item.error))
            write_manifest(manifest_path, manifest)
            display.log(f"第 {lesson} 课不可用：{item.error}")
            display.finish_lesson("失败")
            continue

        existing = manifest_entries(manifest).get(lesson)
        if existing is not None and not args.force:
            try:
                _, _, probe = verify_manifest_entry(
                    cache_root, existing, expected_video_id=item.video_id
                )
            except (OSError, ValueError):
                pass
            else:
                skipped += 1
                set_manifest_entry(
                    manifest, refresh_cached_entry(existing, item, probe)
                )
                write_manifest(manifest_path, manifest)
                display.finish_lesson("已缓存")
                continue

        try:
            entry = download_item(
                item,
                cache_root,
                args.max_height,
                args.force,
                args.cookies_from_browser,
                display,
            )
        except (OSError, TypeError, ValueError) as exc:
            failed += 1
            message = str(exc).strip() or type(exc).__name__
            set_manifest_entry(manifest, unavailable_entry(item, message))
            write_manifest(manifest_path, manifest)
            display.log(f"第 {lesson} 课下载失败：{message}")
            display.finish_lesson("失败")
        else:
            completed += 1
            set_manifest_entry(manifest, entry)
            write_manifest(manifest_path, manifest)
            display.finish_lesson("完成")
    return completed, skipped, failed


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"必须是整数：{value!r}") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("数值必须大于零")
    return number


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            f"手动下载出口日語 {COURSE_LEVEL} 播放列表的视频流和日语字幕；"
            "默认缓存第 1—120 课并显示总进度与当前视频进度。"
        )
    )
    result.add_argument(
        "--lessons",
        type=parse_lesson_spec,
        default=parse_lesson_spec("1-120"),
        metavar="RANGE",
        help="课程范围，例如 1-20,35,80-90；默认 1-120",
    )
    result.add_argument(
        "--cache-root",
        type=Path,
        default=DEFAULT_CACHE_ROOT,
        help=f"缓存目录；默认 {DEFAULT_CACHE_ROOT.as_posix()}",
    )
    result.add_argument(
        "--playlist-url",
        default=PLAYLIST_URL,
        help="播放列表网址；通常无需修改",
    )
    result.add_argument(
        "--max-height",
        type=positive_int,
        default=1080,
        help="视频最大高度；默认 1080",
    )
    result.add_argument(
        "--cookies-from-browser",
        choices=("chrome", "edge", "firefox"),
        help="需要登录验证时，从指定浏览器读取 Cookie",
    )
    result.add_argument(
        "--verify-only",
        action="store_true",
        help="只校验清单和本地文件，不访问播放列表或下载",
    )
    result.add_argument(
        "--force",
        action="store_true",
        help="重新下载指定课程；不会删除旧格式文件",
    )
    result.add_argument(
        "--no-progress",
        action="store_true",
        help="禁用动态进度条，改用普通错误输出",
    )
    return result


def configure_utf8_output() -> None:
    """Keep Chinese progress and errors readable when PowerShell redirects output."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    configure_utf8_output()
    args = parser().parse_args(argv)
    if args.verify_only and args.force:
        parser().error("--verify-only 与 --force 不能同时使用")

    manifest_path = args.cache_root / MANIFEST_NAME
    try:
        with ProgressDisplay(
            len(args.lessons), enabled=not args.no_progress
        ) as display:
            if args.verify_only:
                manifest = load_manifest(manifest_path)
                complete, failed = verify_only(
                    manifest, args.lessons, args.cache_root, display
                )
                downloaded = 0
                skipped = complete
            else:
                downloaded, skipped, failed = download_batch(args, display)
    except KeyboardInterrupt:
        print(
            "\n下载已中断；已完成文件和清单均已保留，可重复运行继续。", file=sys.stderr
        )
        return 130
    except (OSError, TypeError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    print(
        f"完成：新下载 {downloaded} 课，已缓存/已验证 {skipped} 课，失败 {failed} 课。"
    )
    print(f"缓存清单：{manifest_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
