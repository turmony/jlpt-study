# 阅读器性能实施计划

> **For agentic workers:** 按任务执行测试驱动开发；独立文件域可并行，完成后统一集成和独立评审。

**Goal:** 事件监测、60秒复核、可验证持久缓存及有界自动清理。
**Architecture:** 保留现有 SourceWatcher 和 ReaderController 接口扩展；缓存管理独立于可发布临时站点，控制器负责校验/恢复/保存。
**Tech Stack:** Python >=3.10、watchdog、MkDocs、标准库摘要/锁/文件操作、uv、pytest。
**Spec:** ../specs/2026-10-06-reader-performance-design.md

## Global Constraints

60秒复核；500ms稳定窗口；异常1秒轮询；每60分钟自动清理；每项目2个成功版本、全局缓存文件预算3GiB；不写学习资料，不commit/push，不丢stash，保留之前迁移改动。

## Review Focus

- 仅Git提交而资料mtime未变，目录移动和相同大小/mtime编辑仍被发现。
- 构建期间新事件和首次构建期间的变化保留。
- 缓存输出被改动或配置/依赖变化时不能发布旧缓存为最新资料。
- 清理不能删除活跃版本、外部链接目标或其他程序目录。
- 超预算或缓存不可用不能导致阅读器无法启动。

## Task 1: 事件监测

Files: src/jlpt_notes/reader/watcher.py、tests/reader/test_watcher.py、tests/reader/test_event_watcher.py。
Interfaces: SourceWatcher(root,on_change,...,extra_paths=(),reconcile_seconds=60); snapshot_sources(root,*,extra_paths=(),content_hashes=False) 保留原用法。
- [x] 写行为测试并观察缺少事件模式/复核/内容指纹/回退/在途变化而失败。
- [x] 实现事件监测、统一遍历快照、可中止调度和回调工作线程；Git只读检查。
- [x] 定向pytest验证现有轮询测试和新增事件行为。

## Task 2: 有界持久缓存

Files: src/jlpt_notes/reader/cache.py、tests/reader/test_cache.py。
Interfaces: ReaderCache(source_root,config_path,*,directory=None,max_bytes=3*1024**3,max_versions=2); input_fingerprint(root,config)->str; restore(destination,signature)->bool; save(site,signature)->bool; cleanup()->None。
- [x] 写实际文件恢复、内容/配置/Git失效、损坏、安全清理、版本/容量限制测试并观察RED。
- [x] 实现完整输入与输出指纹、原子保存、跨进程锁、安全配额和清理。
- [x] 定向pytest验证；错误返回/抛出由控制器处理，不写学习资料。

## Task 3: 控制器集成与说明

Files: controller.py、pyproject.toml、uv.lock、README.md、controller/headless集成测试、tests/reader/conftest.py。
- [x] 测试跨启动缓存复用、启动期间编辑、缓存不可用、失败构建不覆盖缓存并观察RED。
- [x] 集成缓存验证/恢复/保存、60分钟清理、配置事件与监测启动生命周期；声明watchdog直接依赖。
- [x] README记录用户已确认WSL桌面和iPad访问、缓存清理规则及异常行为。

## Task 4: 验证和性能

- [x] 定向测试、完整pytest、JS测试、图片validate-links和git diff --check。
- [x] 5次检测/暖启动测量及10分钟空闲观察；保留性能报告，不以估算冒充实测。

## 完成证据

- 最终Python完整测试399通过、1跳过、82子测试通过；JavaScript32通过；实际资料图片校验退出码0；定向缓存32与监测40通过。
- 5次有效缓存启动中位12.495秒；第5项前本机启动基线106.732秒（1次），耗时减少88.3%。
- 空闲600.067秒复核9次、构建回调0次；监测进程及Git子进程合计单核CPU占比6.92%，旧版60秒基线41.76%，监测CPU减少83.4%。
- 实际2个成功缓存版本共享相同生成文件，不重复文件数据约2.005GiB，低于3GiB预算；真实HTTP缓存恢复验证首页与版本信息200。
- 独立复审无未解决Critical/Important；此前迁移工作保留、学习文件内容与mtime未改、无commit/push、stash保留。
- 完整结果见[性能报告](../../reader-performance-2026-10-06.md)，原始JSON随文档保存。
- [x] 独立代码评审、修复与必要重测，报告完成情况；不提交/推送。
