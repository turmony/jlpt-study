# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "av>=15,<17",
#   "rich>=14,<16",
#   "yt-dlp>=2025.1.15",
# ]
# ///
"""Cache the N4 grammar course with the shared video downloader."""

from cache_course_videos import run_level


if __name__ == "__main__":
    raise SystemExit(run_level("N4"))
