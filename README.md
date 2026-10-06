# jlpt-study

基于 Markdown、Git 和 Python 的本地 JLPT 学习系统，支持语法与词汇卡、固定七天复习、N5–N1 非听力练习，以及适配 iPad 的局域网阅读器。

## 环境要求

- Python 3.10 或更高版本，使用 `uv` 管理解释器与依赖。
- Git，用于学习资料版本管理和审核记录。
- Ubuntu / WSL2；iPad 局域网访问需 WSL2 镜像网络、Windows 专用网络及同一可信局域网。

## 快速启动

在项目根目录执行：

```bash
uv sync --locked
uv run python -m jlpt_notes reader --headless
```

终端显示访问地址后，打开 <http://127.0.0.1:8765>；按 `Ctrl+C` 停止服务。

阅读器提供目录、搜索、筛选、主题和字号设置。试卷支持作答提交，仅写入既有试卷的答案填写区；其他资料只读。页面在临时目录生成，资料变化后自动更新。

## 目录结构

```text
jlpt-notes/       学习资料、试卷、作答与复习记录
src/jlpt_notes/   Python 模块、命令行工具与阅读器
reader/          阅读器配置、静态资源与 Windows 集成脚本
scripts/         课程缓存、视频截图与卡片检查工具
tests/           自动化测试
docs/            操作说明、设计与验证报告
```

项目名称为 `jlpt-study`，资料目录为 `jlpt-notes`，Python 包名与模块名分别为 `jlpt-notes`、`jlpt_notes`。

## 常用命令

```bash
# 检查资料库图片与阅读器文档链接
uv run python -m jlpt_notes validate-reader-links --root jlpt-notes

# 缓存指定课程的视频和日语字幕；支持 N5–N1
uv run scripts/cache_course_videos.py N3 --lessons 1-10

# 清理当前项目的阅读器页面缓存
uv run python -m jlpt_notes reader-cache-clean --root jlpt-notes
```

视频缓存位于 `.firecrawl/<等级小写>/`，属于临时材料，不提交 Git。新建空资料库时使用 `uv run python -m jlpt_notes init --root jlpt-notes`。

## iPad 局域网访问

在满足环境要求的 WSL2 中，首次配置防火墙并启动：

```bash
uv run python -m jlpt_notes reader --headless --lan --configure-firewall
```

后续启动：

```bash
uv run python -m jlpt_notes reader --headless --lan
```

在 iPad Safari 打开终端给出的地址。网络检查失败时仅提供本机预览；更换网络、电脑 IPv4 地址或端口后需重新配置防火墙。仅在可信局域网使用，电脑休眠或服务停止后无法访问。

Windows 桌面快捷方式使用 `reader/install-wsl-shortcut.ps1` 安装。安装命令、缓存机制及故障排查见 [阅读器使用与维护](docs/reader-guide.md)。

## 开发与验证

```bash
uv run python -m pytest
uv run python -m jlpt_notes validate-links --root jlpt-notes
uv run python -m jlpt_notes validate-reader-links --root jlpt-notes
```

## 资料维护

- 保留学习者原文；校对与候选卡在明确提交前保持未提交状态。
- Git 提交是审核凭证，首次提交日从 Git 历史推导；复习固定每七天一次。
- 提交卡片前必须通过图片链接校验；答错或不确定不触发提前复习。
- 学习资料与记录纳入 Git；视频缓存、临时网页和备份 ZIP 不提交。

## 文档

- [协作规则](AGENTS.md) · [资料库说明](jlpt-notes/README.md)
- [视频语法卡流程](docs/video-grammar-workflow.md)
- [阅读器使用与维护](docs/reader-guide.md) · [Windows 历史说明](docs/reader-windows-legacy.md)
- [阅读器性能报告](docs/reader-performance-2026-10-06.md)
- [系统设计](docs/superpowers/specs/) · [实施计划](docs/superpowers/plans/)
