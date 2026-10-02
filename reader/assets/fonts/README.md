# 阅读器本地字体

字体来源为 Google Fonts 官方仓库，下载于 2026-10-02。三个 WOFF2 文件均使用 SIL Open Font License 1.1；对应 `*-OFL.txt` 随字体复制到临时站点。不从 CDN 请求字体，搜索和学习资料不会发送到 Google。

| 文件 | 用途 | 处理方式 |
| --- | --- | --- |
| `google-sans-latin.woff2` | 界面中的拉丁字母、数字 | Google Sans，保留 U+0000–024F，字重 400–700，GRAD=0、opsz=20 |
| `noto-sans-jp.woff2` | 日文与中日共用汉字 | Noto Sans JP，保留原字体字符集，字重 400–700 |
| `noto-sans-sc-fallback.woff2` | 常用简体中文补字 | Noto Sans SC，保留 GB2312 中 JP 字体不包含的字符，字重 400–700 |

三个字体按上表顺序回退；其他生僻字由设备系统字体显示。总大小约 4.6 MiB。使用 fontTools 的 subset 和 variable-font instancer 后压缩为 WOFF2，运行时不需要 fontTools 或额外网络依赖。

官方来源：

- [Google Sans](https://fonts.google.com/specimen/Google+Sans) / [源文件](https://github.com/google/fonts/tree/main/ofl/googlesans)
- [Noto Sans JP](https://fonts.google.com/specimen/Noto+Sans+JP) / [源文件](https://github.com/google/fonts/tree/main/ofl/notosansjp)
- [Noto Sans SC](https://fonts.google.com/specimen/Noto+Sans+SC) / [源文件](https://github.com/google/fonts/tree/main/ofl/notosanssc)

下载的原始 TTF SHA-256（Google Fonts `main` 后续可能更新）：

```text
GoogleSans[GRAD,opsz,wght].ttf d0a87d835a944b8b40d0e82a5651bb59ab97b936a2aeed5946eb57e7b2a3a90a
NotoSansJP[wght].ttf          c2f3b4d463500a2ddcd3849cded1fceeb9fd6d1c32e6cbecd568453ba50fc68f
NotoSansSC[wght].ttf          a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da
```
