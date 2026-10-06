# JLPT 本地学习系统

这是一个以本地 Markdown 为核心的 JLPT 日语学习资料库。系统保存学习输出、校对结果、固定七天复习记录、N5–N1 非听力练习和错题分析。

## 视频课程缓存

学习者手动缓存出口日語课程的视频和日语字幕；缓存是临时材料，不提交 Git。

N5–N1 共用一条缓存命令：`uv run scripts/cache_course_videos.py <等级>`（例如 `N4`）。每个等级的清单位于 `.firecrawl/<等级小写>/course-manifest.json`；N3 和 N4 另提供独立入口 `uv run scripts/cache_n3_videos.py`、`uv run scripts/cache_n4_videos.py`。播放列表和课数集中配置在 `scripts/cache_course_videos.py`。

缓存命令可加 `--lessons 1-20,35` 指定课程，或加 `--verify-only` 只检查已有缓存。生成新语法卡遵守 [视频语法待确认卡流程](docs/video-grammar-workflow.md)。

如需创建资料库，使用 `uv run python -m jlpt_notes init --root jlpt-notes`。

详细设计见 `docs/superpowers/specs/`；实施计划见 `docs/superpowers/plans/`。

## iPad 局域网只读阅读器

阅读器将 `jlpt-notes` 下的 Markdown 和 JSONL 临时渲染成适合 iPad Safari 阅读的网页。目录、全文搜索、JLPT 等级与类型筛选、明暗主题和字号均在网页内使用；正式卡标题会保留 JLPT 编号。试卷页面还支持直接在 iPad 上点选作答并提交，答案会写入试卷文件的答案填写区。生成文件存放在系统临时目录，不会写入学习资料目录。

### Ubuntu / WSL2：命令行本机预览

当前开发目录是 `/home/turmony/projects/n5-n2-n1-1-2-3`。在 Ubuntu 终端运行：

```bash
cd /home/turmony/projects/n5-n2-n1-1-2-3
uv run python -m jlpt_notes reader --headless
```

等待终端显示访问地址后，在本机浏览器打开 `http://127.0.0.1:8765`。命令行模式不依赖 Tkinter 或 `pythonw.exe`；不加 `--lan` 时只监听本机回环地址，不检查或配置 Windows 防火墙。

资料变化会自动重建页面，试卷仍支持在本机作答和提交。更新失败时继续提供上一次成功版本，终端显示错误详情和本次临时日志位置。按 `Ctrl+C` 停止；收到 `SIGTERM` 也会停止监测、关闭端口并清理临时页面。首次构建失败会显示错误、清理本次临时目录并以非零退出码结束；临时日志在会话清理后不再保留。

可用 `--root`、`--config` 指定资料目录和配置文件，用 `--port` 改变端口。例如 `uv run python -m jlpt_notes reader --headless --port 8766`。不加 `--headless` 时仍使用原 Windows 图形启动入口。

### WSL2：iPad 局域网访问

要求 WSL 使用 `mirrored` 镜像网络模式，Windows 当前物理网络为“专用”，iPad 与电脑在同一个可信任的家庭局域网。首次配置并启动：

```bash
uv run python -m jlpt_notes reader --headless --lan --configure-firewall
```

此命令可能显示 Windows 管理员提示，只创建或替换阅读器同名的 Windows 与 Hyper-V 防火墙规则：Private、当前 IPv4 地址、指定 TCP 端口、当前物理网卡对应的私有子网。不会修改全局防火墙设置；HTTP 服务也会检查请求来源，仅接受该子网和本机回环地址。

后续启动只需：

```bash
uv run python -m jlpt_notes reader --headless --lan
```

等待终端显示 `[running]` 后，在 iPad Safari 打开终端给出的地址。检查网络或防火墙失败时，会显示原因并仅提供本机预览。换网络、电脑 IPv4 地址变化或改端口后，重新运行带 `--configure-firewall` 的命令以更新规则。按 `Ctrl+C` 停止阅读器。

Windows 本机浏览器使用 `http://127.0.0.1:8765`。镜像模式默认不允许 Windows 通过自身的局域网 IPv4 回环访问 WSL；此行为由 [`hostAddressLoopback` 设置](https://learn.microsoft.com/en-us/windows/wsl/wsl-config#experimental-settings)控制。iPad 的访问应在 iPad 上实际验证。

### Windows 桌面入口：启动 WSL 中的项目

在当前稳定项目目录的 Ubuntu 终端执行：

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w ./reader/install-wsl-shortcut.ps1)"
```

安装脚本从自身所在位置识别 WSL 发行版和项目目录，查找并检查该发行版中的 `uv`，更新桌面的“JLPT iPad 阅读器”。它通过 `wsl.exe` 启动当前项目的 `uv run python -m jlpt_notes reader --headless --lan`；终端会显示构建进度、访问地址和错误，按 `Ctrl+C` 停止。日常启动不会自动配置防火墙。

已有同名快捷方式会先备份到 Windows `%LOCALAPPDATA%\JLPTReader\shortcut-backups`，安装输出显示备份路径。项目移动后，在新的稳定目录重新执行安装命令。脚本会拒绝缺少必要文件的目录和 `.worktrees` 等临时工作树。

命令末尾加 `-WhatIf` 可以只预览发行版、目录、运行程序和快捷方式参数，不创建或覆盖快捷方式。在 Windows 原生副本中运行脚本时，可以用 `-Distribution` 和 `-ProjectRoot` 指定 WSL 发行版及其 Linux 项目路径。

同一局域网内能连接阅读器的人可能读取学习资料；只在可信任的家庭网络使用。电脑休眠或阅读器停止后，iPad 无法访问；没有离线缓存。

迁移前的 Windows GUI、`pythonw.exe` 和旧部署路径保存在 [Windows 历史说明](docs/reader-windows-legacy.md)。

### 严格只读边界

- 网页服务只接受 `GET` 和 `HEAD` 阅读请求；唯一例外是作答提交端点 `POST /reader/submit-answers`。
- 提交端点只能改写 `quizzes/papers/` 下既有试卷的「答案填写区」代码块内部；不能创建、删除或修改其他文件，文件其余部分逐字节不变；答案区已有内容时拒绝提交。
- 阅读器将 `.md` 和 `.jsonl` 渲染为页面，不会修改其他源文件的内容、大小或修改时间。
- 正文引用的 `quizzes/sources/` 下 `.txt` 和 `.json` 会转为只读证据页，保留原始文本或格式化 JSON；不提供原文件下载，不加入主目录或全文搜索。未被引用的缓存不发布。
- 本地 PNG、JPEG、GIF、WebP 图片也会只读复制到临时站点，保留卡片相对链接并在正文显示；图片变更会触发重建。隐藏文件和链接到资料库外部的文件不发布。
- 损坏的 Markdown 元数据和 JSONL 记录会显示只读警告，不会回写修复。
- 临时网页不会放入 `jlpt-notes`；停止阅读器后会清理本次临时页面。

### 故障排查

图片链接可单独只读检查：`uv run python -m jlpt_notes validate-links --root jlpt-notes`（`validate` 也执行此检查）。命令检查正文中的本地图片、引用式图片和指向 PNG/JPEG/GIF/WebP 的超链接；不联网检查外部图片，不验证图片画面内容。退出码 0 表示通过，1 表示发现问题或资料库不存在，不会创建或修改目录。

图片必须位于资料库内，且符合阅读器的可发布规则。缺图、隐藏文件、符号链接／目录联接和不支持的图片格式均会报告原文档、原链接及解析目标。阅读器仍提供文字阅读，页面显示缺图提示；控制窗口显示问题数量、首条详情与完整临时日志位置。补回图片后会自动重建并清除提示。

普通本地链接和图片可一起只读检查：`uv run python -m jlpt_notes validate-reader-links --root jlpt-notes`。组卷交付前须执行此检查，尤其是补写校验报告后。目标缺失、隐藏、越界或不允许发布时，阅读页面保留链接文字并显示原因，取消无效跳转；控制窗口汇总问题并提供临时日志。补回证据、修改证据或删除证据会触发重建，不需改写原文的证据链接。

从草稿路径准备正式目标文件时，按 `AGENTS.md` 的图片链接规则调用 `rebase_assets` 并在交付审核前校验。完整 pytest 测试包含实际资料库图片链接检查；卡片的审核与复习日期规则见 `AGENTS.md`。

| 现象 | 处理方法 |
|---|---|
| 终端提示未找到专用网络 | 在 Windows“设置 → 网络和 Internet → 当前连接”中将网络配置文件改为“专用网络”，然后重新打开阅读器。只对可信任的家庭网络这样做。 |
| 终端提示防火墙规则缺失或与当前网络不匹配 | 停止阅读器，再运行 `uv run python -m jlpt_notes reader --headless --lan --configure-firewall`；配置失败时保留本机预览。 |
| 两台设备看似连接 Wi-Fi，仍无法打开 | 确认两台设备连接同一个普通 Wi-Fi，而不是访客网络；路由器的“访客隔离/AP 隔离”会阻止设备互访。 |
| 终端提示端口 8765 被占用 | 关闭可能占用该端口的旧阅读器或其他程序，再重新启动。不要同时启动两个阅读器。 |
| 刚才可读，锁屏或一段时间后失联 | 唤醒 Win11 并保持网络连接；电脑睡眠时网页服务暂停。 |
| 首次构建失败 | 按终端给出的错误和日志位置检查损坏或非 UTF-8 文件；修正源文件后停止并重新启动。阅读器不会替你修改文件。 |
| 更新后提示“已继续提供上一个版本” | 当前旧页面仍可安全阅读。按终端给出的临时日志检查最近修改的文件；修正后等待下一次自动更新。 |
| 本机能打开，iPad 不能打开 | 依次检查专用网络、防火墙提示、同一 Wi-Fi、访客隔离和电脑是否休眠；不要通过路由器做端口转发。 |

### 文件监测与页面缓存

Ubuntu 正常使用文件事件通知；连续保存合并为 **500ms** 稳定窗口，只检查发生变化的文件。每 **60秒** 以内容摘要复核全部可发布资料、Git 提交状态和配置资源，补查遗漏的变化；内容未变不重建。通知服务异常时退回 **1秒轮询**，并尝试恢复事件通知。首次构建和更新期间的编辑仍会排队处理；更新失败继续提供最近成功的页面。

重启时，资料、Git 状态、配置、模板、脚本及程序/依赖版本全部匹配，且缓存页面完整性验证通过，才复用上次成功构建。资料变化可用兼容的旧页面作为增量构建起点；配置变化或缓存损坏会重新全量构建。没有有效缓存的首次构建仍需全量生成。

默认缓存位于 **Ubuntu 的 `/home/turmony/.cache/jlpt-reader`**，即 `~/.cache/jlpt-reader`；若设置绝对路径 `XDG_CACHE_HOME`，则使用其下的 `jlpt-reader`。缓存与学习资料分离，删除缓存不会删除卡片、试卷、答案或复习记录。

自动清理在启动、成功保存缓存和运行中每 **60分钟** 执行：每个项目最多保留 **2个成功版本**，所有项目缓存文件数据预算 **3GiB**，包括写入候选文件。两个缓存版本中相同的生成文件经内容校验后共享存储，容量按不重复的文件数据计数；恢复到本次阅读会话时仍创建独立副本。清理只处理本程序拥有的版本及中断残留，不跟随符号链接或 Windows 目录联接。若保留各项目最新版本后仍无空间保存新版本，则跳过本次缓存，阅读器继续运行。

需要手动清理当前项目的页面缓存时，在项目目录运行：

```bash
uv run python -m jlpt_notes reader-cache-clean --root jlpt-notes --config reader/mkdocs.yml
```

清理后当前已启动阅读器继续可读；下一次启动会重新构建。

第5项的当前环境实测与验证结果见[性能报告](docs/reader-performance-2026-10-06.md)：5次缓存命中启动中位12.5秒，10分钟无资料修改时没有多余构建。无有效缓存的首次构建仍全量执行。

### 验收状态

- [x] 自动验证：真实构建前后学习资料的内容、大小和修改时间一致。
- [x] 自动验证：正式卡、嵌套草稿、测试、报告、损坏元数据和损坏 JSONL 均能生成可读页面。
- [x] 自动验证：`GET`/`HEAD` 可读，所有测试的写入类 HTTP 方法均返回 `405`。
- [x] 自动验证：成功更新会切换版本；失败更新继续提供上一次成功版本；停止后地址关闭。
- [x] 自动验证：作答提交只改写试卷答案区，其余字节不变；已有作答拒绝覆盖。
- [x] iPad 实机显示验收：用户于 2026-09-06 确认通过（对应代码版本 `13b2094`）。
- [x] WSL 桌面入口：预览、实际安装、快捷方式参数及独立 Windows 进程启动校验。
- [x] WSL 局域网访问：用户已确认桌面入口显示访问地址，且 iPad 实机访问成功。
- [ ] 待实际设备确认：iPad Safari 的目录、搜索、筛选、主题、字号、滚动恢复和更新提示。
- [ ] 待实际设备确认：iPad Safari 上的作答点选、排序、不确定标记、草稿恢复与提交。

2026-09-06 的显示验收对应当时版本；当前 WSL 环境的局域网和交互验收按上方各自记录确认。
