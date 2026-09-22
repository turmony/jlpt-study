"""Run the mechanical checks for one video grammar card."""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import unquote, urlsplit

from jlpt_notes.asset_links import AssetIndex, rendered_links

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

BANNED_HEADINGS = (
    "# 核心与接续",
    "# 语义边界、适用条件与后项限制",
    "# 原视频例句",
    "# 易混项及 JLPT 考点",
    "# 来源与复核记录",
    "# 中文释义分组与场景演示",
)


def parse_card(text: str) -> tuple[dict, str]:
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", text, re.DOTALL)
    if not match:
        raise ValueError("缺少JSON前置元数据")
    metadata = json.loads(match.group(1))
    if not isinstance(metadata, dict):
        raise TypeError("前置元数据必须是对象")
    return metadata, match.group(2).lstrip("\r\n")


def function_example_counts(body: str) -> list[int]:
    matches = list(re.finditer(r"(?m)^## 功能[^\n]*$", body))
    counts = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        section = body[match.end():end]
        if "### 例句" not in section:
            counts.append(0)
            continue
        examples = section.split("### 例句", 1)[1]
        counts.append(len(re.findall(r"(?m)^\d+\. ", examples)))
    return counts


def local_image_paths(
    root: Path, source: Path, text: str, published_images: frozenset[Path]
) -> list[Path]:
    images = []
    for link, is_image in rendered_links(text):
        parsed = urlsplit(link)
        if not is_image or parsed.scheme or parsed.netloc:
            continue
        relative = Path(unquote(parsed.path))
        candidate = (root / source.parent / relative).resolve()
        if candidate in published_images:
            images.append(candidate)
    return images


def png_dimensions(path: Path) -> tuple[int, int]:
    """Read PNG dimensions from its signature and IHDR chunk."""
    header = path.read_bytes()[:24]
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("不是有效PNG文件")
    return struct.unpack(">II", header[16:24])


def check_card(root: Path, source: Path, state: str) -> list[str]:
    issues: list[str] = []
    full_path = root / source
    text = full_path.read_text(encoding="utf-8")
    try:
        metadata, body = parse_card(text)
    except (ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    expected_id = full_path.stem
    if metadata.get("id") != expected_id:
        issues.append(f"卡号与文件名不一致：{metadata.get('id')!r} != {expected_id!r}")
    if state == "draft":
        if metadata.get("status") != "draft":
            issues.append("待确认卡的status必须为draft")
        if "next_review" in metadata:
            issues.append("待确认卡不得设置next_review")
        if "未提交待确认版本" not in body:
            issues.append("待确认卡缺少醒目提示")
    else:
        if metadata.get("status") != "confirmed":
            issues.append("待提交正式卡的status必须为confirmed")
        if "未提交待确认版本" in body:
            issues.append("待提交正式卡仍含待确认提示")
        try:
            submitted = date.fromisoformat(metadata["updated_at"])
            next_review = date.fromisoformat(metadata["next_review"])
            if next_review != submitted + timedelta(days=7):
                issues.append("next_review必须为updated_at加七天")
        except (KeyError, TypeError, ValueError):
            issues.append("待提交正式卡缺少有效的updated_at或next_review")

    found_banned = [heading for heading in BANNED_HEADINGS if heading in body]
    if found_banned:
        issues.append("出现禁用栏目：" + "、".join(found_banned))
    counts = function_example_counts(body)
    if not counts:
        issues.append("未找到功能栏目")
    elif any(not 3 <= count <= 5 for count in counts):
        issues.append(f"每个功能须有3～5条例句，当前为{counts}")

    asset_index = AssetIndex(root)
    asset_issues = asset_index.check(source, text)
    issues.extend(map(str, asset_issues))
    images = local_image_paths(root, source, text, asset_index.images)
    if len(images) != 2:
        issues.append(f"必须恰有两张本地图片，当前为{len(images)}")
    else:
        for image_path in images:
            try:
                width, height = png_dimensions(image_path)
                if width < 1 or height < 1:
                    issues.append(f"图片尺寸无效：{image_path}")
            except (OSError, ValueError) as exc:
                issues.append(f"图片无法读取：{image_path}（{exc}）")

    source_section = body.split("# 来源", 1)[1] if "# 来源" in body else ""
    external_sources = [
        link for link, _ in rendered_links(source_section)
        if urlsplit(link).scheme.lower() in {"http", "https"}
    ]
    if len(external_sources) < 2:
        issues.append("来源至少应包含原视频和一个实际采用的语法条目")

    return issues


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="检查一张视频语法卡的机械条件")
    result.add_argument("card", type=Path, help="相对于资料库根目录的卡片路径")
    result.add_argument("--root", type=Path, default=Path("jlpt-notes"))
    result.add_argument("--state", choices=("draft", "final"), required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        root = args.root.resolve(strict=True)
        source = args.card
        if source.is_absolute():
            source = source.resolve(strict=True).relative_to(root)
        issues = check_card(root, source, args.state)
    except (OSError, TypeError, ValueError) as exc:
        parser().exit(1, f"错误：{exc}\n")
    for issue in issues:
        print(issue)
    if issues:
        return 1
    print(f"视频语法卡机械检查通过：{source.as_posix()}（{args.state}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
