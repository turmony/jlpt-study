from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"


def test_n1_uses_separate_cache_and_rejects_wrong_first_video(tmp_path: Path) -> None:
    code = r'''
import argparse
from pathlib import Path
import cache_n1_videos

module = cache_n1_videos.downloader
assert module.COURSE_LEVEL == "N1"
assert module.PLAYLIST_ID == "PLynCeSdpMqxCBtZzRikWkdbRGS9csjDYT"
assert module.EXPECTED_FIRST_VIDEO_ID == "riUjVcsPbqo"
assert module.DEFAULT_CACHE_ROOT == Path(".firecrawl/n1")
assert module.parser().parse_args([]).lessons == list(range(1, 121))

module.fetch_playlist = lambda *_: {
    "id": module.PLAYLIST_ID,
    "entries": [{"playlist_index": 1, "id": "wrongvideo1", "title": "wrong"}],
}
args = argparse.Namespace(
    cache_root=Path(sys.argv[1]), playlist_url=module.PLAYLIST_URL,
    lessons=[1], cookies_from_browser=None,
)
try:
    module.download_batch(args, module.ProgressDisplay(1, enabled=False))
except ValueError as exc:
    assert "第1课的视频 ID" in str(exc)
else:
    raise AssertionError("wrong playlist entry was accepted")
assert not (args.cache_root / module.MANIFEST_NAME).exists()
'''
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-c", "import sys\n" + code, str(tmp_path / "n1")],
        text=True, capture_output=True, encoding="utf-8", env=env, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_n1_rejects_n2_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "course-manifest.json"
    manifest.write_text(
        '{"schema_version":1,"playlist_id":"PLynCeSdpMqxD6LeS82vp39kQP8mw_JxlY","entries":[]}',
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-c",
         "import cache_n1_videos,sys; from pathlib import Path; cache_n1_videos.downloader.load_manifest(Path(sys.argv[1]))",
         str(manifest)],
        text=True, capture_output=True, encoding="utf-8", env=env, check=False,
    )
    assert result.returncode != 0
    assert "播放列表" in result.stderr
