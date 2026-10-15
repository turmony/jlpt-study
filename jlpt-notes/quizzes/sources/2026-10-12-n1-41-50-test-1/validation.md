# N1 第41–50课试卷核验记录

10道形式选择题，41–50每课1题，顺序为乱序；网站原题0道、教学例句派生题10道。每题均保留原例句、变换记录、答案依据和全部四项解析。

- [试卷](../../papers/2026-10-12-n1-41-50-test-1.md)
- [答案与四项解析](../../answers/2026-10-12-n1-41-50-test-1-answers.md)
- 题卡：quizzes/questions/N1-Q-0011.md 至 N1-Q-0020.md
- [结构化清单](manifest.json)
- 缓存证据：quizzes/sources/cache/；补充网站证据：本目录下 N1-G-0042、0046、0047、0049-evidence.txt。

覆盖：N1-G-0041、0042、0043、0044、0045、0046、0047、0048、0049、0050各1题。

## 题源与审查

日本語NET 6页；毎日のんびり日本語教師3页；Iku老師日文1页。依用户本轮AGENTS.md第7条的日本日语教育网站范围补足缺口，并在清单记录题源例外。新抓取10页、缓存命中0页。运营者背景沿用已有日本語NET资料。

独立审题者 /root/quiz_blind_review 先盲答、后读取最小证据及生成记录；10题全部通过来源真实性、唯一解与自然性核对。第6题替换1个干扰项并经过1轮增量复审；第3题干扰项解析精确化，不改变题干或选项。

## 校验

- 结构化清单最终门禁：10题通过。
- 试卷/答案/题卡机械校验：0错误、0警告。
- validate-links：通过。
- validate-reader-links：通过。
- 流水线定向测试：9 passed；新增教学网站被接受，未核实域名仍被拒绝。
- 旧全库缓存存在101条预先已有的哈希不一致；本轮未复用这些记录。6条新增日本語NET缓存单独使用原verify脚本核验通过；4条补充网站证据独立复核通过。旧缓存未修复。

## 阶段时间

|阶段|秒|说明|
|---|---:|---|
|selection|9.513|{"cards": 10}|
|search|32.052|{"web_calls": 3}|
|scrape|153.482|{"new_pages": 6}|
|preflight|0.672|{"questions": 6}|
|render|0.003|{"mode": "preview", "files": 9}|
|revision|0.415|{"revised_questions": 1}|
|scrape|113.537|{"new_pages": 4}|
|draft|113.601|{"questions": 10}|
|preflight|0.791|{"questions": 10}|
|render|0.004|{"mode": "preview", "files": 13}|
|blind_review|371.678|{"reviewed_questions": 10, "reviewed_revisions": 11}|
|render|0.695|{"mode": "final", "files": 13}|
|validation|91.136|{"errors": 0, "warnings": 0, "checks": 4}|

第一批6题初稿未单独启动draft计时，其用时包含在首个scrape阶段；后续draft与补充scrape阶段并行，阶段时间不可相加作为总耗时。

## 已核实教学页面

- N1-G-0041：[ 日本語NET「〜といえども」](https://nihongokyoshi-net.com/2019/07/02/jlptn1-grammar-toiedomo/)（访问日期 2026-10-12）
- N1-G-0042：[ 毎日のんびり日本語教師「～といったらありはしない／といったらない」](https://mainichi-nonbiri.com/grammar/n1-toittaraarihashinai/)（访问日期 2026-10-12）
- N1-G-0043：[ 日本語NET「〜かと思いきや」](https://nihongokyoshi-net.com/2019/07/16/jlptn1-grammar-katoomoikiya/)（访问日期 2026-10-12）
- N1-G-0044：[ 日本語NET「〜ときたら」](https://nihongokyoshi-net.com/2019/07/04/jlptn1-grammar-tokitara/)（访问日期 2026-10-12）
- N1-G-0045：[ 日本語NET「〜ところを」](https://nihongokyoshi-net.com/2019/05/22/jlptn1-grammar-tokoro/)（访问日期 2026-10-12）
- N1-G-0046：[ Iku老師日文「N + にしたところで／としたところで」](https://jp.ikuchannel.com/grammar/pattern-ni-shitatokorode)（访问日期 2026-10-12）
- N1-G-0047：[ 毎日のんびり日本語教師「～とは：用法③ 驚き・意外・あきれ」](https://mainichi-nonbiri.com/grammar/n3-toha/)（访问日期 2026-10-12）
- N1-G-0048：[ 日本語NET「〜とはいえ」](https://nihongokyoshi-net.com/2019/02/17/jlptn1-grammar-towaie/)（访问日期 2026-10-12）
- N1-G-0049：[ 毎日のんびり日本語教師「～とばかりに／と言わんばかりに」](https://mainichi-nonbiri.com/grammar/n1-tobakarini/)（访问日期 2026-10-12）
- N1-G-0050：[ 日本語NET「〜ともなく / 〜ともなしに」](https://nihongokyoshi-net.com/2020/06/11/jlptn1-grammar-tomonaku/)（访问日期 2026-10-12）

正式语法卡、复习周期和作答历史均未修改。
