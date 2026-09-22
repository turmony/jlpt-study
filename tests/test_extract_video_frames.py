from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "extract_video_frames.py"
SPEC = importlib.util.spec_from_file_location("extract_video_frames", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_parse_times_accepts_spaces_commas_sorts_and_deduplicates() -> None:
    assert MODULE.parse_times(["30", "1, 15", "15.0"]) == [1.0, 15.0, 30.0]


@pytest.mark.parametrize("value", ["-1", "nan", "inf", "abc"])
def test_parse_times_rejects_invalid_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.parse_times([value])


def test_output_paths_and_frame_names_are_lesson_scoped(tmp_path: Path) -> None:
    frames, contact = MODULE.output_paths(tmp_path, "108")
    assert frames == tmp_path / "f108"
    assert contact == tmp_path / "f108-contact.png"
    assert MODULE.frame_filename(1) == "t001.00.png"
    assert MODULE.frame_filename(315.5) == "t315.50.png"


def test_parse_vtt_cues_removes_inline_timing_and_markup() -> None:
    text = """WEBVTT

00:00:07.920 --> 00:00:09.780
たことにする<00:00:08.140><c>を</c>勉強します

00:06:54.000 --> 00:06:56.000
<c.green>例文</c>
"""
    assert MODULE.parse_vtt_cues(text) == [
        (7.92, "たことにするを勉強します"),
        (414.0, "例文"),
    ]


def test_suggest_candidate_times_uses_first_hits_and_tail() -> None:
    text = """WEBVTT

00:00:12.000 --> 00:00:13.000
文法の説明

00:06:54.000 --> 00:06:55.000
例文
"""
    assert MODULE.suggest_candidate_times(
        text, ["説明", "例文"], 500, tail_fractions=(0.75, 0.85)
    ) == [1.0, 12.0, 375.0, 414.0, 425.0]


def test_suggest_candidate_times_rejects_invalid_tail_fraction() -> None:
    with pytest.raises(ValueError, match="比例"):
        MODULE.suggest_candidate_times("WEBVTT\n", [], 100, tail_fractions=(1.2,))


def test_suggest_candidate_times_ignores_intro_keyword_hits() -> None:
    text = """WEBVTT

00:00:04.000 --> 00:00:05.000
文法

00:00:22.000 --> 00:00:23.000
文法
"""
    times = MODULE.suggest_candidate_times(
        text, ["文法"], 100, tail_fractions=(), minimum_keyword_seconds=10
    )
    assert times == [1.0, 22.0]


@pytest.mark.parametrize("value", ["../108", "108/next", "", "课108"])
def test_validate_lesson_rejects_unsafe_output_names(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        MODULE.validate_lesson(value)
