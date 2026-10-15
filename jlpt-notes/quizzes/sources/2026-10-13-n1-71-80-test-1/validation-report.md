# N1 第71–80条语法乱序练习（10道单选题） · 出卷与校验记录

- 范围：N1-G-0071 至 N1-G-0080，每卡1题，共10道四选一形式选择；题序已打乱。
- 题源：0道网站原题，10道例句派生题（日本語NET8题，Iku老師日文2题）；非官方真题。
- 缓存：复用命中0页；新访问并采用10页，其中日本語NET8页写入缓存，2页授权补充证据保存在本目录。
- 外部题源授权：学习者本轮明确回复「允许使用外部题源」，仅用于第77、80条。
- 预检、独立盲答与来源复核：10/10通过，无必须修订问题。审题者 /root/quiz_blind_review；题目revision与审题版本一致。
- 机械校验：N1、结构10/0/0，0错误、0警告。图片链接及阅读器链接检查通过。
- 本次采用的10份证据完整性通过；全库缓存校验发现101条既有证据哈希不匹配，未修复旧记录，不声称全库缓存通过。
- 第80条补充站点归为N2；按学习者指定的本地N1第80条选题，语法考点不变。
- 文件保持未提交；正式语法卡及复习记录未修改。

## 交付文件

- [试卷](../../papers/2026-10-13-n1-71-80-test-1.md)
- [答案解析](../../answers/2026-10-13-n1-71-80-test-1-answers.md)
- [结构化生成清单](manifest.json)
- [独立盲审与来源复核原始记录](independent-review.json)

| 题号 | 覆盖卡片 | 题卡 | 最小证据 | 教学来源 |
| --- | --- | --- | --- | --- |
| 1 | N1-G-0076 | [N1-Q-0041](../../questions/N1-Q-0041.md) | [摘录](../cache/72a8a6295e00ac0acd80-5436a06a5a7f.txt) | [日本語NET](https://nihongokyoshi-net.com/2019/06/21/jlptn1-grammar-waoroka/) |
| 2 | N1-G-0071 | [N1-Q-0042](../../questions/N1-Q-0042.md) | [摘录](../cache/0f55de682204f3bc73d6-b53abe4dace3.txt) | [日本語NET](https://nihongokyoshi-net.com/2019/07/15/jlptn1-grammar-nitaru/) |
| 3 | N1-G-0078 | [N1-Q-0043](../../questions/N1-Q-0043.md) | [摘录](../cache/6122a5c00a534192fb14-e34edf4d4107.txt) | [日本語NET](https://nihongokyoshi-net.com/2019/06/24/jlptn1-grammar-basoremadeda/) |
| 4 | N1-G-0074 | [N1-Q-0044](../../questions/N1-Q-0044.md) | [摘录](../cache/eb411563d4ec8e5d02b3-60b23e4f9bf4.txt) | [日本語NET](https://nihongokyoshi-net.com/2019/06/18/jlptn1-grammar-itari/) |
| 5 | N1-G-0079 | [N1-Q-0045](../../questions/N1-Q-0045.md) | [摘录](../cache/1d9fbabf9ddc9586bdcb-bf96e1c4f8c1.txt) | [日本語NET](https://nihongokyoshi-net.com/2019/06/16/jlptn1-grammar-bekarazu/) |
| 6 | N1-G-0072 | [N1-Q-0046](../../questions/N1-Q-0046.md) | [摘录](../cache/d3a5d6feddf398929622-b083f8cb832c.txt) | [日本語NET](https://nihongokyoshi-net.com/2019/04/26/jlptn1-grammar-nihikikae/) |
| 7 | N1-G-0075 | [N1-Q-0047](../../questions/N1-Q-0047.md) | [摘录](../cache/1e84318fe3aeb330616d-d5631698cb6a.txt) | [日本語NET](https://nihongokyoshi-net.com/2019/07/05/jlptn1-grammar-nokiwami/) |
| 8 | N1-G-0073 | [N1-Q-0048](../../questions/N1-Q-0048.md) | [摘录](../cache/d6f518a02fbecaf4fa10-814dd50f539f.txt) | [日本語NET](https://nihongokyoshi-net.com/2019/05/10/jlptn1-grammar-nimomashite/) |
| 9 | N1-G-0077 | [N1-Q-0049](../../questions/N1-Q-0049.md) | [摘录](supplemental-77.txt) | [Iku老師日文](https://jp.ikuchannel.com/grammar/pattern-ba-koso) |
| 10 | N1-G-0080 | [N1-Q-0050](../../questions/N1-Q-0050.md) | [摘录](supplemental-80.txt) | [Iku老師日文](https://jp.ikuchannel.com/grammar/pattern-de-wa-arumai-ka) |

## 实测阶段用时

计时区间可能重叠，总和不代表完整墙钟耗时；未单独计时的补充检索和草拟不补造数据。

| 阶段 | 已完成区间合计（秒） |
| --- | ---: |
| 选卡与查缓存 | 16.308 |
| 日本語NET检索 | 51.492 |
| 取证与保存摘录 | 89.942 |
| 首批题目草拟 | 141.566 |
| 预检 | 0.750 |
| 独立审题与来源复核 | 352.636 |
| 预览与最终渲染 | 0.732 |
| 机械及链接校验 | 137.225 |

未发生题目修订，未记录revision阶段；补充检索另有2次工具调用、4条查询，未单独计时。阶段详情与调用数见manifest的workflow。

最终校验使用：

```text
quiz_pipeline.py validate --stage final
validate_quiz.py --structure 10,0,0 --level N1
jlpt_notes validate-links --root jlpt-notes
jlpt_notes validate-reader-links --root jlpt-notes
```

预览机械检查曾因指向正式资料库而找不到尚未发布的题卡；改用临时预览根目录后通过，最终产物再次校验通过。
