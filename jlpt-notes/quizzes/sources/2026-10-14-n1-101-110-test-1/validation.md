# N1 第101–110条语法出卷记录

- 范围：N1-G-0101至N1-G-0110，每条1题，共10道四选一单选，题序乱序。
- 题源类型：网站原题0道，教学例句派生题10道；试卷明确标记非官方真题。
- 采用日本語NET的5个页面（6题），毎日のんびり日本語教師的4个页面（4题）。
- 学习者授权原文：「101-110语法 允许使用外部信息」。外部题源例外逐题写入source字段。
- 前一轮准备的5份日本語NET证据已逐条核实哈希，直接复用；本轮新增4份授权站点证据，SHA-256均通过，未重复抓取原站。
- 日本語NET运营者背景复用此前核实的ノッチ先生管理人摘录；补充站点发布者记录为毎日のんびり日本語教師。
- 首次盲审及来源复核详见下方独立记录；题目审查版本与当前版本完全匹配。
- 第101、106、109条的原站标级为N2；保留原站标级，本卷按学习者指定的本地N1卡片范围出题。
- 当前全库缓存检查仍有100条既有证据哈希异常；本卷没有使用这些异常记录，采用的9份证据均单独核验通过。
- 正式语法卡、原文及复习日期均未修改；未提交Git。

[试卷](../../papers/2026-10-14-n1-101-110-test-1.md) · [答案与四项解析](../../answers/2026-10-14-n1-101-110-test-1-answers.md) · [最终清单](manifest.json) · [独立盲审](blind-review.json) · [来源复核](source-review.json) · [补充题源记录](external-sources.json) · [最终校验结果](validation-results.json)

## 逐卡覆盖

| 题号 | 语法卡 | 题卡 | 题源摘录 |
| --- | --- | --- | --- |
| 1 | [N1-G-0107](../../../grammar/n1/N1-G-0107.md) | [N1-Q-0071](../../questions/N1-Q-0071.md) | [日本語NET](../cache/e0306146be9c15e6a63a-ef79166839e6.txt) |
| 2 | [N1-G-0102](../../../grammar/n1/N1-G-0102.md) | [N1-Q-0072](../../questions/N1-Q-0072.md) | [毎日のんびり日本語教師](mainichi-102.txt) |
| 3 | [N1-G-0109](../../../grammar/n1/N1-G-0109.md) | [N1-Q-0073](../../questions/N1-Q-0073.md) | [日本語NET](../cache/7d940cbd99277044baa4-43d821836f0e.txt) |
| 4 | [N1-G-0104](../../../grammar/n1/N1-G-0104.md) | [N1-Q-0074](../../questions/N1-Q-0074.md) | [日本語NET](../cache/47d958cc5e499332fa21-3ee0c1043622.txt) |
| 5 | [N1-G-0110](../../../grammar/n1/N1-G-0110.md) | [N1-Q-0075](../../questions/N1-Q-0075.md) | [毎日のんびり日本語教師](mainichi-110.txt) |
| 6 | [N1-G-0106](../../../grammar/n1/N1-G-0106.md) | [N1-Q-0076](../../questions/N1-Q-0076.md) | [日本語NET](../cache/b73d8a14c1b0a77f536c-69c8d5def2ad.txt) |
| 7 | [N1-G-0103](../../../grammar/n1/N1-G-0103.md) | [N1-Q-0077](../../questions/N1-Q-0077.md) | [毎日のんびり日本語教師](mainichi-103.txt) |
| 8 | [N1-G-0108](../../../grammar/n1/N1-G-0108.md) | [N1-Q-0078](../../questions/N1-Q-0078.md) | [毎日のんびり日本語教師](mainichi-108.txt) |
| 9 | [N1-G-0105](../../../grammar/n1/N1-G-0105.md) | [N1-Q-0079](../../questions/N1-Q-0079.md) | [日本語NET](../cache/47d958cc5e499332fa21-3ee0c1043622.txt) |
| 10 | [N1-G-0101](../../../grammar/n1/N1-G-0101.md) | [N1-Q-0080](../../questions/N1-Q-0080.md) | [日本語NET](../cache/e1e29064033711aa8525-f2eea26c985d.txt) |

## 阶段用时

selection、search及第一段draft包含本轮任务前一轮的实际准备工作；等待学习者授权的时间未计入活动阶段。

| 阶段 | 秒 | 调用记录 |
| --- | ---: | --- |
| selection | 14.779 | {"cards": 11, "cache_lookups": 11} |
| search | 120.630 | {"search_calls": 3, "direct_sources_found": 6, "cards_covered": 7, "source_gaps": 4} |
| draft | 103.343 | {"internal_questions": 7, "unresolved_source_cards": 4} |
| scrape | 129.916 | {"additional_pages": 4, "locator_opens": 2} |
| preflight | 0.189 | {"validation_calls": 1} |
| render | 0.004 | {"mode": "preview", "files": 13} |
| blind_review | 199.314 | {"blind_calls": 1, "source_calls": 1, "record_rechecks": 1, "questions_passed": 10} |
| render | 0.845 | {"mode": "final", "files": 13} |

最终validation阶段用时及命令次数在最终清单workflow.phases中；校验退出码、错误及警告保存在最终校验结果中。
