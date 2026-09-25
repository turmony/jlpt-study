from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from cache_n2_videos import VideoProbe

SPEC = importlib.util.spec_from_file_location(
    "cache_n4_missing_subtitles", SCRIPTS / "cache_n4_missing_subtitles.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_select_missing_only_when_youtube_subtitle_is_unavailable(
    tmp_path: Path,
) -> None:
    subtitles = tmp_path / "subtitles"
    subtitles.mkdir()
    (subtitles / "good.ja.vtt").write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n你好\n", encoding="utf-8"
    )
    (subtitles / "recovered.ja.vtt").write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nこんにちは\n", encoding="utf-8"
    )
    (subtitles / "local.mixed.vtt").write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n语法\n", encoding="utf-8"
    )
    entries = [
        {
            "lesson": 1,
            "video_id": "aaaaaaaaaaa",
            "status": "complete",
            "subtitle_path": "subtitles/good.ja.vtt",
        },
        {"lesson": 2, "video_id": "bbbbbbbbbbb", "status": "error"},
        {
            "lesson": 3,
            "video_id": "ccccccccccc",
            "status": "error",
            "subtitle_path": "subtitles/recovered.ja.vtt",
        },
        {
            "lesson": 4,
            "video_id": "ddddddddddd",
            "status": "complete",
            "subtitle_path": "subtitles/local.mixed.vtt",
            "subtitle_kind": "local_asr_mixed",
        },
    ]
    assert MODULE.select_missing(entries, tmp_path, {1, 2, 3, 4}) == [entries[1]]


def test_bilibili_part_mapping_and_duration_check() -> None:
    assert MODULE.bilibili_part(99) == 100
    assert MODULE.bilibili_part(100) == 99
    assert MODULE.bilibili_part(15) == 15
    MODULE.check_duration(444, 443.331)
    with pytest.raises(ValueError, match="时长"):
        MODULE.check_duration(474, 463.655)


def test_render_vtt_preserves_mixed_speech_and_timestamps() -> None:
    segments = [
        (1.25, 3.5, " 这节课讲 ～てもいいです。 "),
        (3.6, 5.0, "使ってもいいです。"),
    ]
    assert MODULE.render_vtt(segments) == (
        "WEBVTT\n\n"
        "00:00:01.250 --> 00:00:03.500\n这节课讲 ～てもいいです。\n\n"
        "00:00:03.600 --> 00:00:05.000\n使ってもいいです。\n"
    )
    with pytest.raises(ValueError, match="有效字幕"):
        MODULE.render_vtt([(1, 1, ""), (5, 4, "错")])


def test_run_one_reuses_video_and_writes_provenance_after_valid_vtt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "videos" / "abcdefghijk.f137.mp4"
    video.parent.mkdir()
    video.write_bytes(b"video")
    audio = tmp_path / "audio" / "p15.m4a"
    audio.parent.mkdir()
    audio.write_bytes(b"audio")
    entry = {
        "lesson": 15,
        "playlist_index": 15,
        "video_id": "abcdefghijk",
        "title": "【Ｎ４文法】～てもいいです",
        "duration_seconds": 444,
        "webpage_url": "https://www.youtube.com/watch?v=abcdefghijk",
        "status": "error",
    }
    monkeypatch.setattr(MODULE, "find_local_video", lambda *_: video)
    monkeypatch.setattr(
        MODULE, "probe_video", lambda *_: VideoProbe(444, 1920, 1080, False)
    )
    monkeypatch.setattr(
        MODULE, "download_bilibili", lambda *_, **__: (audio, 443.331, None)
    )
    monkeypatch.setattr(
        MODULE, "transcribe", lambda *_, **__: [(1, 3, "这里是中文，そして日本語。")]
    )

    result = MODULE.run_one(
        entry, tmp_path, model=object(), browser=None, model_name="large-v3"
    )

    assert result["status"] == "complete"
    assert result["video_path"] == "videos/abcdefghijk.f137.mp4"
    assert result["subtitle_kind"] == "local_asr_mixed"
    assert result["subtitle_source"]["bilibili_part"] == 15
    assert result["subtitle_source"]["model"] == "large-v3"
    assert result["subtitle_source"]["url"].endswith("?p=15")
    assert result["subtitle_path"].endswith(".mixed.vtt")
    assert (
        (tmp_path / result["subtitle_path"])
        .read_text(encoding="utf-8")
        .startswith("WEBVTT")
    )


def test_run_one_rejects_mismatched_part_without_marking_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "p99.m4a"
    audio.write_bytes(b"audio")
    entry = {
        "lesson": 99,
        "video_id": "abcdefghijk",
        "title": "～とか",
        "duration_seconds": 474,
        "status": "error",
    }
    monkeypatch.setattr(
        MODULE, "download_bilibili", lambda *_, **__: (audio, 463.655, None)
    )
    with pytest.raises(ValueError, match="时长"):
        MODULE.run_one(entry, tmp_path, model=object(), browser=None)
    assert not list(tmp_path.rglob("*.vtt"))


def test_run_one_downloads_video_only_when_local_video_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "audio" / "p102.m4a"
    video = tmp_path / "videos" / "BV1t4411y7L3_p102.mp4"
    for media in (audio, video):
        media.parent.mkdir(exist_ok=True)
        media.write_bytes(b"media")
    entry = {
        "lesson": 102,
        "video_id": "abcdefghijk",
        "duration_seconds": 782,
        "title": "形式名詞「こと」",
        "status": "error",
    }
    monkeypatch.setattr(MODULE, "find_local_video", lambda *_: None)
    monkeypatch.setattr(
        MODULE, "probe_video", lambda *_: VideoProbe(782, 1920, 1080, False)
    )
    monkeypatch.setattr(
        MODULE,
        "download_bilibili",
        lambda part, _root, kind, _browser: (
            (audio if kind == "audio" else video),
            781.722,
            {},
        ),
    )
    monkeypatch.setattr(MODULE, "transcribe", lambda *_, **__: [(1, 3, "形式名詞こと")])

    result = MODULE.run_one(entry, tmp_path, model=object(), browser=None)

    assert result["video_path"] == "videos/BV1t4411y7L3_p102.mp4"
    assert result["video_source"]["url"].endswith("?p=102")


def test_batch_continues_after_one_lessons_media_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = tmp_path / "course-manifest.json"
    entries = [
        {"lesson": lesson, "video_id": f"{lesson:011d}", "status": "error"}
        for lesson in range(1, 121)
    ]
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "playlist_id": MODULE.YOUTUBE_PLAYLIST_ID,
                "entries": entries,
            }
        ),
        encoding="utf-8",
    )
    fake_whisper = types.ModuleType("faster_whisper")
    fake_whisper.WhisperModel = lambda *_, **__: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_whisper)

    def finish_or_fail(entry: dict, *_: object) -> dict:
        if entry["lesson"] == 1:
            raise TypeError("媒体信息损坏")
        return {**entry, "status": "complete", "subtitle_path": "subtitles/second.vtt"}

    monkeypatch.setattr(MODULE, "run_one", finish_or_fail)

    assert MODULE.main(["--cache-root", str(tmp_path), "--lessons", "1-2"]) == 1
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved["entries"][0]["last_error"] == "媒体信息损坏"
    assert saved["entries"][1]["status"] == "complete"
    assert "补齐 1 课，失败 1 课" in capsys.readouterr().out
