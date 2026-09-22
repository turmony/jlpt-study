from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "cache_n2_videos.py"
SPEC = importlib.util.spec_from_file_location("cache_n2_videos", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_parse_lesson_spec_supports_ranges_and_deduplicates() -> None:
    assert MODULE.parse_lesson_spec("3,1-2,2,5-6") == [1, 2, 3, 5, 6]


@pytest.mark.parametrize("value", ["", "0", "121", "8-3", "1,,2", "a", "1-2-3"])
def test_parse_lesson_spec_rejects_invalid_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.parse_lesson_spec(value)


def test_playlist_items_preserve_original_playlist_positions() -> None:
    info = {
        "entries": [
            {
                "playlist_index": 1,
                "id": "abcdefghijk",
                "title": "第一课",
                "duration": 120,
            },
            None,
            {
                "playlist_index": 3,
                "id": "lmnopqrstuv",
                "title": "第三课",
                "duration": 180,
            },
        ]
    }
    items = MODULE.playlist_items(info, [1, 2, 3, 4])

    assert items[1].video_id == "abcdefghijk"
    assert items[2].video_id is None
    assert "不可用" in items[2].error
    assert items[3].video_id == "lmnopqrstuv"
    assert items[4].error == "播放列表中缺少该位置"


def test_playlist_items_reject_duplicate_video_ids() -> None:
    info = {
        "entries": [
            {"playlist_index": 1, "id": "abcdefghijk", "title": "一"},
            {"playlist_index": 2, "id": "abcdefghijk", "title": "二"},
        ]
    }
    items = MODULE.playlist_items(info, [1, 2])
    assert "重复" in items[1].error
    assert items[1].error == items[2].error


def test_manifest_write_is_readable_and_sorted(tmp_path: Path) -> None:
    path = tmp_path / "course-manifest.json"
    manifest = MODULE.new_manifest()
    MODULE.set_manifest_entry(manifest, {"lesson": 2, "status": "error"})
    MODULE.set_manifest_entry(manifest, {"lesson": 1, "status": "complete"})
    MODULE.write_manifest(path, manifest)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [entry["lesson"] for entry in saved["entries"]] == [1, 2]
    assert not (tmp_path / ".course-manifest.json.tmp").exists()


def test_resolve_cache_path_rejects_parent_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="越过"):
        MODULE.resolve_cache_path(tmp_path / "cache", "../outside.mp4")


def test_verify_subtitle_accepts_webvtt_and_rejects_plain_text(tmp_path: Path) -> None:
    valid = tmp_path / "valid.vtt"
    valid.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n例文です。\n",
        encoding="utf-8",
    )
    MODULE.verify_subtitle(valid)

    invalid = tmp_path / "invalid.vtt"
    invalid.write_text("これは字幕ではありません。", encoding="utf-8")
    with pytest.raises(ValueError, match="WebVTT"):
        MODULE.verify_subtitle(invalid)


def test_downloaded_subtitle_path_accepts_ytdlp_na_ja_name(tmp_path: Path) -> None:
    subtitle_root = tmp_path / "subtitles"
    subtitle_root.mkdir()
    subtitle = subtitle_root / "abcdefghijk.NA.ja.vtt"
    subtitle.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n例文です。\n",
        encoding="utf-8",
    )

    assert MODULE.downloaded_subtitle_path({}, tmp_path, "abcdefghijk") == subtitle


def test_downloaded_subtitle_path_prefers_ytdlp_reported_filepath(
    tmp_path: Path,
) -> None:
    subtitle_root = tmp_path / "subtitles"
    subtitle_root.mkdir()
    subtitle = subtitle_root / "abcdefghijk.custom-name.vtt"
    subtitle.write_text("WEBVTT\n", encoding="utf-8")
    info = {"requested_subtitles": {"ja": {"filepath": str(subtitle)}}}

    assert MODULE.downloaded_subtitle_path(info, tmp_path, "abcdefghijk") == subtitle


def test_download_options_select_video_only_and_japanese_vtt(tmp_path: Path) -> None:
    options = MODULE.download_options(
        tmp_path,
        max_height=1080,
        force=False,
        browser=None,
        progress_hook=lambda _: None,
    )
    assert options["format"] == (
        "bestvideo[height<=1080][ext=mp4]/bestvideo[height<=1080]"
    )
    assert options["subtitleslangs"] == ["ja"]
    assert options["subtitlesformat"] == "vtt/best"
    assert options["concurrent_fragment_downloads"] == 4
    assert "bestaudio" not in options["format"]
    assert options["outtmpl"]["default"].endswith(
        "videos\\%(id)s.f%(format_id)s.%(ext)s"
    ) or options["outtmpl"]["default"].endswith("videos/%(id)s.f%(format_id)s.%(ext)s")


def test_disabled_progress_display_accepts_download_hooks() -> None:
    display = MODULE.ProgressDisplay(total_lessons=1, enabled=False)
    with display:
        display.start_lesson(1, "测试")
        display.update_download(
            {
                "status": "downloading",
                "downloaded_bytes": 512,
                "total_bytes": 1024,
                "speed": 128,
                "eta": 4,
            }
        )
        display.finish_lesson("完成")
    assert display.completed_lessons == 1
