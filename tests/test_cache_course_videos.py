from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"


def run_python(code: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-c", code, *args],
        text=True,
        capture_output=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def test_n3_cache_configuration_rejects_wrong_playlist_entry(tmp_path: Path) -> None:
    code = r'''
import argparse
import cache_course_videos

downloader = cache_course_videos.configure_level("N3")
assert downloader.PLAYLIST_ID == "PLynCeSdpMqxDS6EC0L7vXYUAVCstRHcQR"
assert downloader.EXPECTED_FIRST_VIDEO_ID == "eGxvduVsfJo"
assert downloader.DEFAULT_CACHE_ROOT.as_posix() == ".firecrawl/n3"
assert downloader.parser().parse_args([]).lessons == list(range(1, 121))

downloader.fetch_playlist = lambda *_: {
    "id": downloader.PLAYLIST_ID,
    "entries": [{"playlist_index": 1, "id": "wrongvideo1", "title": "wrong"}],
}
args = argparse.Namespace(
    cache_root=Path(sys.argv[1]), playlist_url=downloader.PLAYLIST_URL,
    lessons=[1], cookies_from_browser=None,
)
try:
    downloader.download_batch(args, downloader.ProgressDisplay(1, enabled=False))
except ValueError as exc:
    assert "第1课的视频 ID" in str(exc)
else:
    raise AssertionError("wrong N3 first video was accepted")
assert not (args.cache_root / downloader.MANIFEST_NAME).exists()
'''
    result = run_python("import sys\nfrom pathlib import Path\n" + code, str(tmp_path / "n3"))
    assert result.returncode == 0, result.stdout + result.stderr


def test_shared_cache_cli_uses_each_playlist_length() -> None:
    code = r'''
import cache_course_videos

for level, size, first_id in (
    ("N4", 120, "tq7OQec7Dnc"),
    ("N5", 119, "3zRXvtDnev8"),
):
    downloader = cache_course_videos.configure_level(level)
    assert downloader.EXPECTED_FIRST_VIDEO_ID == first_id
    assert downloader.DEFAULT_CACHE_ROOT.as_posix() == f".firecrawl/{level.lower()}"
    assert downloader.parser().parse_args([]).lessons == list(range(1, size + 1))
    assert downloader.parser().parse_args(["--lessons", str(size)]).lessons == [size]
    assert f"默认缓存第 1—{size} 课" in downloader.parser().format_help()

try:
    downloader.parser().parse_args(["--lessons", "120"])
except SystemExit as exc:
    assert exc.code == 2
else:
    raise AssertionError("N5 lesson 120 should be rejected")
'''
    result = run_python(code)
    assert result.returncode == 0, result.stdout + result.stderr
