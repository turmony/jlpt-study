# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "av>=15,<17",
#   "faster-whisper>=1.2,<2",
#   "yt-dlp>=2025.1.15",
# ]
# ///
"""Fill only N4 lessons without a usable YouTube WebVTT using Bilibili audio."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from cache_course_videos import COURSES
from cache_n2_videos import (
    cache_relative_path,
    local_now,
    parse_lesson_spec,
    probe_video,
    resolve_cache_path,
    set_manifest_entry,
    verify_subtitle,
    write_manifest,
)

BILIBILI_ID = "BV1t4411y7L3"
YOUTUBE_PLAYLIST_ID = COURSES["N4"].playlist_id
DEFAULT_CACHE_ROOT = Path(".firecrawl/n4")


def bilibili_part(lesson: int) -> int:
    """The two sites put the `～とか` and `形式名詞「の」` lessons in reverse order."""
    if not 1 <= lesson <= 120:
        raise ValueError(f"N4 课号超出范围：{lesson}")
    return {99: 100, 100: 99}.get(lesson, lesson)


def bilibili_url(part: int) -> str:
    return f"https://www.bilibili.com/video/{BILIBILI_ID}?p={part}"


def check_duration(expected: float, actual: float, tolerance: float = 2.0) -> None:
    if expected <= 0 or actual <= 0 or abs(expected - actual) > tolerance:
        raise ValueError(
            f"Bilibili 分 P 与 YouTube 课程时长不匹配：{expected:.2f} 秒 / {actual:.2f} 秒"
        )


def _valid_subtitle(path: Path) -> bool:
    try:
        verify_subtitle(path)
    except (OSError, ValueError):
        return False
    return True


def select_missing(
    entries: list[dict[str, Any]], cache_root: Path, lessons: set[int]
) -> list[dict[str, Any]]:
    """Select only lessons with no usable subtitle, including broken cache records."""
    selected: list[dict[str, Any]] = []
    seen: set[int] = set()
    for entry in entries:
        lesson = entry.get("lesson")
        if lesson not in lessons:
            continue
        if not isinstance(lesson, int) or lesson in seen:
            raise ValueError(f"课程清单课号无效或重复：{lesson}")
        seen.add(lesson)
        video_id = entry.get("video_id")
        if not isinstance(video_id, str) or len(video_id) != 11:
            raise ValueError(f"第 {lesson} 课缺少有效的 YouTube 视频 ID")
        subtitle_path = entry.get("subtitle_path")
        if subtitle_path:
            subtitle = resolve_cache_path(cache_root, subtitle_path)
            if _valid_subtitle(subtitle):
                continue
        # A failed downloader can have left a valid YouTube VTT without
        # recording its path. In that case, this script must not re-transcribe.
        if any(
            _valid_subtitle(path)
            for path in (cache_root / "subtitles").glob(f"{video_id}*.ja.vtt")
        ):
            continue
        selected.append(entry)
    missing_records = lessons - seen
    if missing_records:
        raise ValueError(f"课程清单缺少课号：{sorted(missing_records)}")
    return selected


def find_local_video(cache_root: Path, video_id: str) -> Path | None:
    for path in sorted((cache_root / "videos").glob(f"{video_id}.f*.*")):
        if path.suffix.lower() in {".part", ".ytdl"}:
            continue
        try:
            probe_video(path)
        except (OSError, ValueError):
            continue
        return path
    return None


def download_bilibili(
    part: int, cache_root: Path, kind: str, browser: str | None = None
) -> tuple[Path, float, dict[str, Any]]:
    """Download one audio or video stream; keep it for interrupted reruns."""
    import yt_dlp

    if kind not in {"audio", "video"}:
        raise ValueError(f"不支持的媒体类型：{kind}")
    target_dir = cache_root / ("audio" if kind == "audio" else "videos")
    target_dir.mkdir(parents=True, exist_ok=True)
    options: dict[str, Any] = {
        "format": (
            "bestaudio[ext=m4a]/bestaudio"
            if kind == "audio"
            else "bestvideo[height<=1080][ext=mp4]/bestvideo[height<=1080]"
        ),
        "outtmpl": str(target_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "continuedl": True,
        "overwrites": False,
        "retries": 10,
        "fragment_retries": 10,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    if browser:
        options["cookiesfrombrowser"] = (browser,)
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(bilibili_url(part), download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise ValueError(f"Bilibili {kind} 下载失败：{exc}") from exc
    if not isinstance(info, dict):
        raise TypeError(f"Bilibili P{part} 未返回媒体信息")
    if info.get("id") != f"{BILIBILI_ID}_p{part}":
        raise ValueError(f"Bilibili 分 P 不匹配：预期 P{part}，实际 {info.get('id')}")
    duration = float(info.get("duration") or 0)
    if duration <= 0:
        raise ValueError(f"Bilibili P{part} 缺少时长")
    requested = info.get("requested_downloads") or []
    paths = [
        Path(item["filepath"])
        for item in requested
        if isinstance(item, dict) and isinstance(item.get("filepath"), str)
    ]
    paths.extend(target_dir.glob(f"{BILIBILI_ID}_p{part}.*"))
    media = next(
        (
            path
            for path in paths
            if path.is_file() and path.suffix.lower() not in {".part", ".ytdl"}
        ),
        None,
    )
    if media is None or media.stat().st_size < 1024:
        raise ValueError(f"Bilibili P{part} 下载后未找到有效的 {kind} 文件")
    return media, duration, info


def transcribe(model: Any, audio: Path, title: str) -> list[tuple[float, float, str]]:
    segments, _ = model.transcribe(
        str(audio),
        task="transcribe",
        language=None,
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=False,
        initial_prompt=f"这是一堂日语 N4 语法课，讲解以中文为主，含日语例句。课题：{title}",
    )
    return [(float(s.start), float(s.end), str(s.text)) for s in segments]


def _timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    whole_seconds, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{millis:03d}"


def render_vtt(segments: list[tuple[float, float, str]]) -> str:
    cues: list[str] = []
    previous_end = 0.0
    for start, end, raw_text in segments:
        visible = " ".join(raw_text.split())
        if not visible or start < 0 or end <= start or start < previous_end:
            continue
        cues.append(f"{_timestamp(start)} --> {_timestamp(end)}\n{visible}")
        previous_end = end
    if not cues:
        raise ValueError("转写结果没有有效字幕片段")
    return "WEBVTT\n\n" + "\n\n".join(cues) + "\n"


def run_one(
    entry: dict[str, Any],
    cache_root: Path,
    model: Any,
    browser: str | None,
    model_name: str = "large-v3",
) -> dict[str, Any]:
    lesson = int(entry["lesson"])
    video_id = entry["video_id"]
    expected = float(entry["duration_seconds"])
    part = bilibili_part(lesson)
    audio, audio_duration, _ = download_bilibili(part, cache_root, "audio", browser)
    check_duration(expected, audio_duration)

    video = find_local_video(cache_root, video_id)
    video_source: dict[str, Any] | None = None
    if video is None:
        video, video_duration, _ = download_bilibili(part, cache_root, "video", browser)
        check_duration(expected, video_duration)
        video_source = {"platform": "bilibili", "url": bilibili_url(part), "part": part}
    probe = probe_video(video)
    check_duration(expected, probe.duration_seconds)

    segments = transcribe(model, audio, str(entry.get("title") or ""))
    if any(end > expected + 2 for _, end, _ in segments):
        raise ValueError(f"第 {lesson} 课转写时间超出视频时长")
    body = render_vtt(segments)
    subtitle = cache_root / "subtitles" / f"{video_id}.bilibili.mixed.vtt"
    subtitle.parent.mkdir(parents=True, exist_ok=True)
    temporary = subtitle.with_suffix(".vtt.tmp")
    temporary.write_text(body, encoding="utf-8")
    try:
        verify_subtitle(temporary)
        temporary.replace(subtitle)
    finally:
        temporary.unlink(missing_ok=True)

    now = local_now()
    result = dict(entry)
    result.update(
        {
            "video_path": cache_relative_path(cache_root, video),
            "subtitle_path": cache_relative_path(cache_root, subtitle),
            "subtitle_kind": "local_asr_mixed",
            "subtitle_source": {
                "platform": "bilibili",
                "video_id": BILIBILI_ID,
                "bilibili_part": part,
                "url": bilibili_url(part),
                "transcription": "faster-whisper",
                "model": model_name,
            },
            "audio_path": cache_relative_path(cache_root, audio),
            "width": probe.width,
            "height": probe.height,
            "has_audio": probe.has_audio,
            "video_bytes": video.stat().st_size,
            "subtitle_bytes": subtitle.stat().st_size,
            "downloaded_at": now,
            "checked_at": now,
            "status": "complete",
        }
    )
    if video_source:
        result["video_source"] = video_source
    result.pop("last_error", None)
    return result


def load_n4_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != 1
        or manifest.get("playlist_id") != YOUTUBE_PLAYLIST_ID
    ):
        raise ValueError(f"N4 课程清单格式或播放列表 ID 不匹配：{path}")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or len(entries) != 120:
        raise ValueError(f"N4 课程清单应有 120 条记录：{path}")
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="只为缺失 YouTube 字幕的 N4 课程补 Bilibili 音频转写 WebVTT"
    )
    result.add_argument(
        "--lessons",
        type=lambda s: parse_lesson_spec(s, 120),
        default=list(range(1, 121)),
    )
    result.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    result.add_argument(
        "--model", default="large-v3", help="faster-whisper 多语言模型，默认 large-v3"
    )
    result.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    result.add_argument("--compute-type", default="auto")
    result.add_argument("--cookies-from-browser", choices=("chrome", "edge", "firefox"))
    result.add_argument(
        "--dry-run", action="store_true", help="只列出将补齐的课号，不下载模型或媒体"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    manifest_path = args.cache_root / "course-manifest.json"
    try:
        manifest = load_n4_manifest(manifest_path)
        selected = select_missing(
            manifest["entries"], args.cache_root, set(args.lessons)
        )
        print(
            f"待补字幕：{len(selected)} 课：{', '.join(str(e['lesson']) for e in selected) or '无'}"
        )
        if args.dry_run or not selected:
            return 0
        from faster_whisper import WhisperModel

        model = WhisperModel(
            args.model, device=args.device, compute_type=args.compute_type
        )
        success = 0
        failed = 0
        for entry in selected:
            lesson = entry["lesson"]
            print(
                f"第 {lesson} 课：下载 Bilibili P{bilibili_part(lesson)} 音频并转写……",
                flush=True,
            )
            try:
                updated = run_one(
                    entry, args.cache_root, model, args.cookies_from_browser, args.model
                )
            except (OSError, ValueError, RuntimeError, TypeError) as exc:
                failed += 1
                failed_entry = {
                    **entry,
                    "status": "error",
                    "checked_at": local_now(),
                    "last_error": str(exc),
                }
                set_manifest_entry(manifest, failed_entry)
                write_manifest(manifest_path, manifest)
                print(f"第 {lesson} 课失败：{exc}", file=sys.stderr, flush=True)
                continue
            set_manifest_entry(manifest, updated)
            write_manifest(manifest_path, manifest)
            success += 1
            print(f"第 {lesson} 课完成：{updated['subtitle_path']}", flush=True)
        print(f"补齐 {success} 课，失败 {failed} 课；可重跑继续。")
        return 1 if failed else 0
    except KeyboardInterrupt:
        print("已中断；已完成的课已写入清单，可重跑继续。", file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
