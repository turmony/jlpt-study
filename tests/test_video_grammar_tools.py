from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def load_script(name: str):
    path = Path(__file__).parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CHECKER = load_script("check_video_grammar_card")


def test_function_example_counts_checks_each_function() -> None:
    body = """# 核心

## 功能一：A

### 例句

1. 一
2. 二
3. 三

## 功能二：B

### 例句

1. 一
2. 二
3. 三
4. 四

# 来源
"""
    assert CHECKER.function_example_counts(body) == [3, 4]


def test_parse_card_rejects_missing_frontmatter() -> None:
    with pytest.raises(ValueError, match="前置元数据"):
        CHECKER.parse_card("# card")


def test_checker_rejects_persisted_lifecycle_fields_and_draft_banner(tmp_path) -> None:
    root = tmp_path / "notes"
    card = root / "grammar/n2/N2-G-0001.md"
    card.parent.mkdir(parents=True)
    card.write_text(
        '---\n{"id":"N2-G-0001","status":"draft","created_at":"2026-09-22"}\n---\n\n'
        '> **未提交待确认版本**\n',
        encoding="utf-8",
    )
    issues = CHECKER.check_card(root.resolve(), Path("grammar/n2/N2-G-0001.md"))
    assert any("生命周期字段" in issue for issue in issues)
    assert any("正文不得包含待确认提示" in issue for issue in issues)
