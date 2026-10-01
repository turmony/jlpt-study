# N2 第81–90条语法出卷记录

- 20道四选一形式选择题；N2-G-0081至N2-G-0090，每卡2题。
- 2道日本語NET网站原题，18道例句派生题（日本語NET16题、Hagoromo2题）；非官方真题。
- 日本語NET目标卡近期缓存命中0；新采用11页，证据已加入缓存；第86条另采用Hagoromo条目及用例接口，未混入NET缓存。运营者背景复用既有核实记录。
- 第86条Hagoromo例外由用户于2026-10-01明确许可，记录在manifest workflow.source_exception；仓库单站规则未修改。
- 独立首次全卷盲答、修改题增量重盲审、全卷最小题源复核均通过。第3题两轮修订，其余修改题一轮；第7题仅校正解析，未改题干、选项、答案。
- 最终结构化校验通过；机械校验0错误、0警告；图片链接及112条NET缓存证据哈希校验通过。

## 文件

- 试卷：../../papers/2026-10-01-n2-lessons-81-90-test-1.md
- 答案与四项解析：../../answers/2026-10-01-n2-lessons-81-90-test-1-answers.md
- 题卡：../../questions/N2-Q-0161.md 至 N2-Q-0180.md
- 单一最终清单：manifest.json
- 最小题源证据：manifest每题source.evidence_paths；NET证据位于../cache/，Hagoromo位于hagoromo-1112.md。
- 审题证据：本目录n2-8190-*-review.json。
- 例外校验入口：uv run python jlpt-notes/quizzes/sources/2026-10-01-n2-lessons-81-90-test-1/validate_with_exception.py validate --root . --draft jlpt-notes/quizzes/sources/2026-10-01-n2-lessons-81-90-test-1/manifest.json --stage final

## 记录的阶段耗时

阶段可能重叠，不能直接相加；等待用户题源答复和额外Hagoromo接口取证包含在草稿阶段。搜索调用共4次（搜索3次、map1次）；其余取证为scrape。

| 阶段 | 秒 |
|---|---:|
| selection | 37.09 |
| search | 77.19 |
| scrape | 129.9 |
| draft | 490.32 |
| render | 0.03 |
| preflight | 27.77 |
| revision | 83.03 |
| blind_review | 491.46 |
| validation | 121.64 |
