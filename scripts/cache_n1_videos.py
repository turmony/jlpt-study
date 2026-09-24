# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "av>=15,<17",
#   "rich>=14,<16",
#   "yt-dlp>=2025.1.15",
# ]
# ///
"""Manually cache the 120 N1 course videos and Japanese WebVTT subtitles.

Run ``uv run scripts/cache_n1_videos.py``. The cache is independent of N2;
completed lessons are verified and skipped when the command is run again.
"""

from pathlib import Path

import cache_n2_videos as downloader


downloader.PLAYLIST_ID = "PLynCeSdpMqxCBtZzRikWkdbRGS9csjDYT"
downloader.PLAYLIST_URL = (
    "https://www.youtube.com/playlist?list=PLynCeSdpMqxCBtZzRikWkdbRGS9csjDYT"
)
downloader.DEFAULT_CACHE_ROOT = Path(".firecrawl/n1")
downloader.COURSE_LEVEL = "N1"
downloader.EXPECTED_FIRST_VIDEO_ID = "riUjVcsPbqo"


if __name__ == "__main__":
    raise SystemExit(downloader.main())
