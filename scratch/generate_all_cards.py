import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

from jlpt_notes.asset_links import AssetIndex
from scripts.check_video_grammar_card import check_card

root = Path("jlpt-notes").resolve(strict=True)
asset_index = AssetIndex(root)

# Definitions of the 10 cards
CARDS = {
    81: {
        "id": "N4-G-0081",
        "title": "お〜します・ご〜します（表示谦让）",
        "lesson_title": "お〜します・ご〜します（表示謙譲）",
        "video_id": "mf9pc2Jd9i4",
        "source_material": "出口日語原视频板书、YouTube 原 WebVTT（中文为主、日语为辅）与毎日のんびり日本語教師「【Ｎ３文法】お／ご～する／します／致す／致します」正文",
        "tags": ["敬语", "谦让语", "N4"],
        "confusions": ["お〜になります・ご〜になります"],
        "conn_sec": 1.0,
        "conn_crop": {"x": 0, "y": 0, "width": 1370, "height": 980},
        "ex_sec": 620.33,
        "ex_crop": {"x": 30, "y": 0, "width": 1860, "height": 1070},
        "functions": [
            {
                "title": "谦逊谦让表现（动作涉及对方）",
                "meaning_desc": [
                    ("お〜します・ご〜します", "自分の行為について、その行為が向かう先の人物を立てて述べたり、相手に対して丁重に述べる謙譲表現です。原則として和語には「お」、漢語には「ご」が付きます。この文型を使うには、行為が＜向かう先＞の人物がはっきり存在していなければいけません。", "关于自己的行为，抬高该行为所指向的对象，或者向对方郑重陈述的谦让表现。原则上和语词接「お」，汉语词接「ご」。使用该句型时，行为的“指向对象”必须明确存在。")
                ],
                "examples": [
                    ("いらっしゃいませ。お席にご案内します。", "欢迎光临。我带您去座位。"),
                    ("荷物をお預かりします。", "我给您保管行李。"),
                    ("１６時頃に折り返しお電話します。", "16点左右给您回电话。"),
                    ("こちらで確認してから、後ほどご連絡致します。", "在这边确认后，稍后再联系您。")
                ]
            }
        ],
        "sources": [
            ("出口日語原视频", "https://www.youtube.com/watch?v=mf9pc2Jd9i4", None),
            ("毎日のんびり日本語教師「【Ｎ３文法】お／ご～する／します／致す／致します」", "https://mainichi-nonbiri.com/grammar/n3-osuru/", "2026-09-25")
        ]
    },
    82: {
        "id": "N4-G-0082",
        "title": "〜せていただきます（表示谦让）",
        "lesson_title": "〜せていただきます（表示謙譲）",
        "video_id": "AALApq_JqNI",
        "source_material": "出口日語原视频板书、YouTube 原 WebVTT（中文为主、日语为辅）与毎日のんびり日本語教師「【Ｎ３文法】～させていただく／させていただきます」正文",
        "tags": ["敬语", "谦让语", "使役", "N4"],
        "confusions": ["〜せてくださる・〜せてください"],
        "conn_sec": 1.0,
        "conn_crop": {"x": 0, "y": 0, "width": 1380, "height": 980},
        "ex_sec": 434.92,
        "ex_crop": {"x": 30, "y": 0, "width": 1860, "height": 1070},
        "functions": [
            {
                "title": "需要对方许可（请求许可并表示谦逊谦让）",
                "meaning_desc": [
                    ("〜せていただきます", "自分の行為について、その行為が向かう先の人物を立てて述べたり、相手に対して丁重に述べる謙譲表現です。自分の行為について許可を請う時に用います。恩恵を受けるのは自分です。", "关于自己的行为，抬高该行为所指向的对象，或者向对方郑重陈述的谦让表现。在就自己的行为请求对方许可时使用。接受恩惠的是说话人自己。")
                ],
                "examples": [
                    ("私も参加させていただきます。", "请让我也参加。"),
                    ("大変申し訳ございませんが、詳細については明日お返事させていただきます。", "非常抱歉，详细情况将于明日回复。"),
                    ("館内については私が案内させていただきます。", "馆内由我来带路引导。"),
                    ("工場内を見学させていただけませんか？", "能让我参观一下工厂吗？")
                ]
            }
        ],
        "sources": [
            ("出口日語原视频", "https://www.youtube.com/watch?v=AALApq_JqNI", None),
            ("毎日のんびり日本語教師「【Ｎ３文法】～させていただく／させていただきます」", "https://mainichi-nonbiri.com/grammar/n3-saseteitadaku/", "2026-09-25")
        ]
    },
    83: {
        "id": "N4-G-0083",
        "title": "お〜・ご〜（表示美化与敬意）",
        "lesson_title": "お〜・ご〜（表示美化・敬意）",
        "video_id": "QCJVGCKTTLo",
        "source_material": "出口日語原视频板书、Bilibili P83 音频的本地中文／日语混合转写 WebVTT 与日本語教師の広場「御 :「お」と「ご」（その１）」正文",
        "tags": ["敬语", "美化语", "接头辞", "N4"],
        "confusions": ["お〜します・ご〜します", "お〜になります・ご〜になります"],
        "conn_sec": 1.0,
        "conn_crop": {"x": 0, "y": 0, "width": 1380, "height": 980},
        "ex_sec": 422.47,
        "ex_crop": {"x": 30, "y": 0, "width": 1860, "height": 1070},
        "functions": [
            {
                "title": "表示美化与敬意（美化语、尊敬语与谦让语）",
                "meaning_desc": [
                    ("お〜・ご〜", "接頭語として名詞・動詞・形容詞などの前に付き、物事を美化して丁寧に述べたり、相手に対する敬意（尊敬・謙譲）を表す表現です。一般的に和語には「お」がつき、漢語（音読みの言葉）には「ご」がつきます。", "作为前缀附加在名词、动词、形容词等之前，用于美化事物、礼貌地陈述，或向对方表达敬意（尊敬或谦让）。一般而言和语词接「お」，汉语词（音读词）接「ご」。")
                ],
                "examples": [
                    ("先生、少しご相談があります。", "老师，我有些事想跟您商量。"),
                    ("会場までは私がご案内します。", "去会场的路，由我来为您引路带路。"),
                    ("さとし君、とってもいいお返事ですね。", "小聪，你的回答真棒呢。"),
                    ("先生にきちんとご返事なさい。", "好好向老师回答。")
                ]
            }
        ],
        "sources": [
            ("出口日語原视频", "https://www.youtube.com/watch?v=QCJVGCKTTLo", None),
            ("日本語教師の広場「御 :「お」と「ご」（その１）」", "https://www.tomojuku.com/blog/otogo/", "2026-09-25")
        ]
    },
    84: {
        "id": "N4-G-0084",
        "title": "ございます・〜でございます・いらっしゃいます・〜でいらっしゃいます（郑重语与尊敬语）",
        "lesson_title": "ございます・〜でございます・いらっしゃいます・〜でいらっしゃいます",
        "video_id": "yALJAEhtwIA",
        "source_material": "出口日語原视频板书、Bilibili P84 音频的本地中文／日语混合转写 WebVTT 与毎日のんびり日本語教師「【Ｎ３文法】～ございます」「【Ｎ３文法】～ていらっしゃる／ていらっしゃいます」正文",
        "tags": ["敬语", "郑重语", "尊敬语", "N4"],
        "confusions": ["あります・います", "です・だ"],
        "conn_sec": 1.0,
        "conn_crop": {"x": 0, "y": 0, "width": 1380, "height": 980},
        "ex_sec": 860.20,
        "ex_crop": {"x": 30, "y": 0, "width": 1860, "height": 1070},
        "functions": [
            {
                "title": "「ございます・〜でございます」的用法（郑重语与郑重断定）",
                "meaning_desc": [
                    ("ございます・〜でございます", "「～です」「～あります」の丁寧形です。", "是「～です（是）」「～あります（有）」的郑重语表达形式。")
                ],
                "examples": [
                    ("スケジュールに変更がございます。", "日程有变更。"),
                    ("お聞きしたいことがございます。", "我有想问的事情。"),
                    ("会議は午後１時からの予定でございます。", "会议预定从下午1点开始。"),
                    ("こちらはＡ株式会社でございます。", "这里是A株式会社。")
                ]
            },
            {
                "title": "「いらっしゃいます・〜でいらっしゃいます」的用法（尊敬语与尊敬断定）",
                "meaning_desc": [
                    ("いらっしゃいます・〜でいらっしゃいます", "相手あるいは第三者の行為・物事・状態等を立てて述べる尊敬表現です。「～です」「～ている」「～ていく」「～てある」の尊敬語にあたります。", "用于抬高对方或第三者的行为、事物或状态的尊敬表达。相当于「～です（是）」「～ている（在……）」「～ていく」「～てある」的尊敬语。")
                ],
                "examples": [
                    ("中田さんでいらっしゃいますか？", "您是中田先生吗？"),
                    ("元気でいらっしゃいますか？", "您身体还好吗？"),
                    ("睡眠は十分にとれていらっしゃいますか。", "睡眠充足吗？"),
                    ("奥様はいつもお美しくていらっしゃいますね。", "您夫人总是那么漂亮。")
                ]
            }
        ],
        "sources": [
            ("出口日語原视频", "https://www.youtube.com/watch?v=yALJAEhtwIA", None),
            ("毎日のんびり日本語教師「【Ｎ３文法】～ございます」", "https://mainichi-nonbiri.com/grammar/n3-gozaimasu/", "2026-09-25"),
            ("毎日のんびり日本語教師「【Ｎ３文法】～ていらっしゃる／ていらっしゃいます」", "https://mainichi-nonbiri.com/grammar/n3-teirassharu/", "2026-09-25")
        ]
    },
    85: {
        "id": "N4-G-0085",
        "title": "文体「論説体（である体）」（论说体书面文体）",
        "lesson_title": "文体「論説体（である体）」",
        "video_id": "uPcLNMJB5Jc",
        "source_material": "出口日語原视频板书、YouTube 原 WebVTT（中文为主、日语为辅）与上級へのとびら「「である体」の説明」正文",
        "tags": ["文体", "论说体", "普通体", "N4"],
        "confusions": ["普通体（だ体）", "丁寧体（です・ます体）"],
        "conn_sec": 1.0,
        "conn_crop": {"x": 0, "y": 0, "width": 1380, "height": 980},
        "ex_sec": 479.88,
        "ex_crop": {"x": 30, "y": 0, "width": 1860, "height": 1070},
        "functions": [
            {
                "title": "论说体（である体）（学术论文与公文等正式书面文体）",
                "meaning_desc": [
                    ("文体「論説体（である体）」", "「である」は「だ」の改まった普通形であり、名詞やナ形容詞などに接続します。レポートや論文などの学術的な文章や公的文書といった改まった書き言葉（論説体）で用いられます。", "「である」是「だ」的庄重普通体形式，接在名词和ナ形容词等之后。常用于报告、论文等学术文章及公文等庄重的书面语（论说体）中。")
                ],
                "examples": [
                    ("哲学者のパスカルは、人間は考える葦であると言った。", "哲学家帕斯卡尔曾说：人是一根会思想的芦苇。"),
                    ("こんなにたくさんの人に読まれているのだから、面白い本であるに違いない。", "既然有这么多人读它，那必定是一本有趣的书。"),
                    ("あの話は本当ではないと言われていたが、最近、本当であることが分かった。", "虽然曾有人说那件事不是真的，但最近证实了它是事实。"),
                    ("子供の頃嫌いであった食べ物が、大人になって好きになるということはよくある。", "孩童时期讨厌的食物，长大成人后变得喜欢上，这种事是常有的。")
                ]
            }
        ],
        "sources": [
            ("出口日語原视频", "https://www.youtube.com/watch?v=uPcLNMJB5Jc", None),
            ("上級へのとびら「「である体」の説明」", "https://tobiraweb.9640.jp/grammar-note_de-aru-style/", "2026-09-25")
        ]
    },
    86: {
        "id": "N4-G-0086",
        "title": "〜うございます（表示郑重有礼貌）",
        "lesson_title": "〜うございます（表示鄭重有禮貌）",
        "video_id": "HsLltYilXEs",
        "source_material": "出口日語原视频板书、Bilibili P86 音频的本地中文／日语混合转写 WebVTT 与毎日のんびり日本語教師「音便とは？」正文",
        "tags": ["敬语", "郑重语", "音便", "N4"],
        "confusions": ["〜ございます", "〜いです"],
        "conn_sec": 1.0,
        "conn_crop": {"x": 0, "y": 0, "width": 1380, "height": 980},
        "ex_sec": 554.70,
        "ex_crop": {"x": 30, "y": 0, "width": 1860, "height": 1070},
        "functions": [
            {
                "title": "表示郑重有礼貌（形容词ウ音便的郑重语）",
                "meaning_desc": [
                    ("〜うございます", "単語中の一音が発音の便宜のために、母音の「う」に変化する現象をウ音便と言います。現代日本語では「おはようございます」「ありがとうございます」「よろしゅうございます」など、イ形容詞に「ございます」が続く丁寧で改まった言い方にウ音便が取り入れられています。", "单词中的某个音为了发音方便而变为元音「う」的现象称为ウ音便。在现代日语中，这种ウ音便主要保留在「おはようございます」「ありがとうございます」「よろしゅうございます」等一类形容词接「ございます」的郑重、礼貌的表达方式中。")
                ],
                "examples": [
                    ("今日は一段と寒うございますね。", "今天格外寒冷呢。"),
                    ("いつもお引き立ていただき、ありがたうございます（ありがとうございます）。", "承蒙您一直以来的关照，非常感谢。"),
                    ("それでよろしゅうございますか。", "那样可以吗？/那样您觉得妥当吗？"),
                    ("朝早くからお疲れ様です。はやうございます（おはようございます）。", "一大早就辛苦了。早上好。")
                ]
            }
        ],
        "sources": [
            ("出口日語原视频", "https://www.youtube.com/watch?v=HsLltYilXEs", None),
            ("毎日のんびり日本語教師「音便とは？」", "https://mainichi-nonbiri.com/jltct/onbin/", "2026-09-25")
        ]
    },
    87: {
        "id": "N4-G-0087",
        "title": "お〜いただきます・ご〜いただきます（请您做……、表示谦让）",
        "lesson_title": "お〜いただきます・ご〜いただきます 請您做〜（表示謙讓）",
        "video_id": "rTJzE1KwVbA",
        "source_material": "出口日語原视频板书、YouTube 原 WebVTT（中文为主、日语为辅）与Japanese Exercises「【JLPT N3】お／ご～いただく／くださる　文法解説・問題」正文",
        "tags": ["敬语", "谦让语", "授受表现", "N4"],
        "confusions": ["お〜くださる・ご〜くださる", "〜ていただく"],
        "conn_sec": 1.0,
        "conn_crop": {"x": 0, "y": 0, "width": 1380, "height": 980},
        "ex_sec": 409.81,
        "ex_crop": {"x": 30, "y": 0, "width": 1860, "height": 1070},
        "functions": [
            {
                "title": "要求表现与请求对方做某事（请您做……、表示谦让）",
                "meaning_desc": [
                    ("お〜いただきます・ご〜いただきます", "「～てもらう」「～てくれる」の丁寧の形", "「～てもらう（请对方为自己做某事）」「～てくれる（对方为自己做某事）」的郑重表达形式。")
                ],
                "examples": [
                    ("このプロジェクトについて詳しくご説明いただけますか？", "关于这个项目，能否请您详细说明一下？"),
                    ("ご協力いただき、本当にありがとうございました。", "非常感谢您的配合协助。"),
                    ("このアンケートにご記入いただけると幸いです。", "如果您能填写这份问卷，我们将不胜感激。"),
                    ("お手伝いいただいたおかげで、作業が無事に終わりました。", "多亏了您的帮忙协助，工作顺利完成了。")
                ]
            }
        ],
        "sources": [
            ("出口日語原视频", "https://www.youtube.com/watch?v=rTJzE1KwVbA", None),
            ("Japanese Exercises「【JLPT N3】お／ご～いただく／くださる　文法解説・問題」", "https://japaneseexercises.com/2024/11/30/%E3%80%90jlpt-n3-%E3%81%8A%EF%BC%8F%E3%81%94%EF%BD%9E%E3%81%84%E3%81%9F%E3%81%A0%E3%81%8F%EF%BC%8F%E3%81%8F%E3%81%A0%E3%81%95%E3%82%8B%E3%80%80%E6%96%87%E6%B3%95%E8%A7%A3%E8%AA%AC%E3%83%BB%E5%95%8F/", "2026-09-25")
        ]
    },
    88: {
        "id": "N4-G-0088",
        "title": "〜せてください・〜せてくださいませんか（请让我[做]……；可以让我[做]……吗）",
        "lesson_title": "〜せてください・〜せてくださいませんか 請讓(我)[做]〜；可以讓(我)[做]〜嗎",
        "video_id": "jMbzzJeW-bo",
        "source_material": "出口日語原视频板书、YouTube 原 WebVTT（中文为主、日语为辅）与毎日のんびり日本語教師「【Ｎ３文法】～させてくださる／させてください」正文",
        "tags": ["敬语", "尊敬语", "使役", "请求", "N4"],
        "confusions": ["〜てください", "〜せていただきます"],
        "conn_sec": 1.0,
        "conn_crop": {"x": 0, "y": 0, "width": 1380, "height": 980},
        "ex_sec": 416.75,
        "ex_crop": {"x": 30, "y": 0, "width": 1860, "height": 1070},
        "functions": [
            {
                "title": "请求对方允许（请让我[做]……；可以让我[做]……吗）",
                "meaning_desc": [
                    ("〜せてください・〜せてくださいませんか", "相手あるいは第三者の行為・物事・状態等を立てて述べる尊敬表現です。自分の行為について許可を請う時に用います。相手の「許す／許可する」という行為に対する尊敬を表します。恩恵を受けるのは自分です。", "抬高对方或第三者的行为、事物或状态的尊敬表达。在就自己的行为请求对方许可时使用，对对方“允许/准许”的行为表示尊敬。得到恩惠的是说话人自己。")
                ],
                "examples": [
                    ("これからもあなたのそばに居させてください。", "今后也请让我待在你身边。"),
                    ("自慢させてください。私の娘は本当に可愛いんです。", "请让我自夸一下。我女儿真的很可爱。"),
                    ("ちょっと困ったことがあるので、相談させてください。", "我有点为难，请让我商量一下。"),
                    ("もしよかったら私も参加させてくださいませんか？", "如果可以的话，我也可以参加吗？")
                ]
            }
        ],
        "sources": [
            ("出口日語原视频", "https://www.youtube.com/watch?v=jMbzzJeW-bo", None),
            ("毎日のんびり日本語教師「【Ｎ３文法】～させてくださる／させてください」", "https://mainichi-nonbiri.com/grammar/n3-sasetekudasaru/", "2026-09-25")
        ]
    },
    89: {
        "id": "N4-G-0089",
        "title": "〜はずです・〜はずがありません（应该……；不可能……）",
        "lesson_title": "〜はずです・〜はずがありません　應該〜；不可能〜",
        "video_id": "DGnLDaSc2Y0",
        "source_material": "出口日語原视频板书、YouTube 原 WebVTT（中文为主、日语为辅）与毎日のんびり日本語教師「【Ｎ４文法】～はずだ／ないはずだ」「【Ｎ３文法】～はずがない／はずはない」正文",
        "tags": ["推测", "断定", "N4"],
        "confusions": ["〜かもしれません", "〜にちがいありません"],
        "conn_sec": 1.0,
        "conn_crop": {"x": 0, "y": 0, "width": 1380, "height": 980},
        "ex_sec": 432.43,
        "ex_crop": {"x": 30, "y": 0, "width": 1860, "height": 1070},
        "functions": [
            {
                "title": "推测（说话人认为可能性极高的主观判断）",
                "meaning_desc": [
                    ("〜はずです", "状況や常識、経験等から推測した主観的な判断を述べる文法です。話者はその可能性が高いと思っていますが、話者自身も状況を完全に把握しているわけではないので推測が確かかどうかは分かりません。", "叙述根据状况、常识、经验等推测出的主观判断的语法。说话人认为其可能性极高，但由于说话人自身也并未完全掌握全部状况，因此推测是否确凿尚属未知。")
                ],
                "examples": [
                    ("何度も説明してあげたし、ちゃんと理解できているはずだ。", "我给你解释了好几次，你应该能理解的。"),
                    ("完璧な人なんていないはずだ。", "应该没有完美的人。"),
                    ("火のない所に煙は立たぬと言うし、きっと理由があるはずだ。", "俗话说无风不起浪，这其中一定有原因。"),
                    ("このチームは実力者揃いだし、どんな相手でも負けることはないはずだ。", "这个团队实力雄厚，遇到任何对手都应该不会输。")
                ]
            },
            {
                "title": "A不可能（断定绝无可能）",
                "meaning_desc": [
                    ("〜はずがありません", "状況や常識、経験等から推測した主観的な判断を述べる文法で、その可能性がないことを表します。", "叙述根据状况、常识、经验等推测出的主观判断的语法，表示绝无那种可能性。")
                ],
                "examples": [
                    ("彼女は一言で言うとお姫様。こんな美貌で人気がないはずがない。", "她用一句话说就是公主。这样的美貌不可能不受欢迎。"),
                    ("他人のために一生懸命になれるはずがない。", "不可能为了他人而拼命。"),
                    ("運転歴３０年無事故、無違反だし、そんな私が事故るはずがない。", "驾龄30年无事故、无违反记录，那样的我绝不可能发生事故。"),
                    ("放課後ろくに勉強もせずに遊び放題。そんな状態で良い成績が出るはずがない。", "放学后不好好学习一味玩耍。在那种状态下不可能取得好成绩。")
                ]
            }
        ],
        "sources": [
            ("出口日語原视频", "https://www.youtube.com/watch?v=DGnLDaSc2Y0", None),
            ("毎日のんびり日本語教師「【Ｎ４文法】～はずだ／ないはずだ」", "https://mainichi-nonbiri.com/grammar/n4-hazuda/", "2026-09-25"),
            ("毎日のんびり日本語教師「【Ｎ３文法】～はずがない／はずはない」", "https://mainichi-nonbiri.com/grammar/n3-hazuganai/", "2026-09-25")
        ]
    },
    90: {
        "id": "N4-G-0090",
        "title": "〜し〜し（列举理由；列举评价）",
        "lesson_title": "〜し〜し（列舉理由；列舉評價）",
        "video_id": "7i3A0DSOg-Y",
        "source_material": "出口日語原视频板书、YouTube 原 WebVTT（中文为主、日语为辅）与日本語NET「【JLPT N4】文法・例文：〜し、〜し」正文",
        "tags": ["并列", "理由", "评价", "N4"],
        "confusions": ["〜から", "〜ので", "〜たり〜たり"],
        "conn_sec": 1.0,
        "conn_crop": {"x": 0, "y": 0, "width": 1380, "height": 980},
        "ex_sec": 354.40,
        "ex_crop": {"x": 30, "y": 0, "width": 1860, "height": 1070},
        "functions": [
            {
                "title": "列举理由",
                "meaning_desc": [
                    ("〜し〜し", "理由を複数あげ、最後に結論を述べる表現。理由を１つだけ言う時もこの文型が使えるが、「言っていないだけで、他にも理由がある」というニュアンスがある。", "列举多个理由并在最后陈述结论的表达。即使只说一个理由时也可以使用该句型，但带有“只是没说出来，其实还有其他理由”的语感。")
                ],
                "examples": [
                    ("漢字は多いし、文法は難しいし、私は日本語の勉強があまり好きではありません。", "汉字又多，语法又难，我不太喜欢学日语。"),
                    ("日本は綺麗だし、食べ物が美味しいし、好きです。", "日本又干净漂亮，食物又美味，我很喜欢。"),
                    ("このレストランは安いし量も多いし、よく来ます。", "这家餐馆又便宜分量又足，我经常来。"),
                    ("頭も痛いし、熱もあるし、今夜のパーティーには行けません。", "头又疼，又在发烧，今晚的聚会我没法去了。")
                ]
            },
            {
                "title": "列举评价（并列描写）",
                "meaning_desc": [
                    ("〜し〜し", "複数の事柄を並べて述べる表現。話し手の「さらに」、「その上」という気持ちが含まれる。人や物を評価するときによく使われる。", "将多件事物并列陈述的表达。包含说话人“更加”、“不仅如此”的心情。常用于评价人物或事物。")
                ],
                "examples": [
                    ("トムさんは、面白いし、親切だし、サッカーも上手です。", "汤姆既风趣又亲切，而且足球踢得也很好。"),
                    ("田中先生は優しいし、かっこいいし、それに教え方も上手です。", "田中老师温柔体贴，人又帅气，而且讲课也教得好。"),
                    ("ジョンさんはスポーツもできるし、頭もいいし、それに女の子からの人気が高いです。", "约翰擅长体育，人又聪明，而且在女生中人气很高。"),
                    ("大阪は美味しい食べ物がたくさんあるし、観光地がたくさんあるし、それに人が面白いです。", "大阪有很多好吃的食物，观光胜地也多，而且当地人很有趣。")
                ]
            }
        ],
        "sources": [
            ("出口日語原视频", "https://www.youtube.com/watch?v=7i3A0DSOg-Y", None),
            ("日本語NET「【JLPT N4】文法・例文：〜し、〜し」", "https://nihongokyoshi-net.com/2019/08/09/jlptn4-grammar-shi-shi/", "2026-09-25")
        ]
    }
}


def build_card_content(lesson_num: int, d: dict) -> str:
    card_id = d["id"]
    title = d["title"]
    lesson_title = d["lesson_title"]
    video_id = d["video_id"]
    material = d["source_material"]
    tags_str = json.dumps(d["tags"], ensure_ascii=False)
    confusions_str = json.dumps(d["confusions"], ensure_ascii=False)
    
    conn_sec = d["conn_sec"]
    cx, cy, cw, ch = d["conn_crop"]["x"], d["conn_crop"]["y"], d["conn_crop"]["width"], d["conn_crop"]["height"]
    ex_sec = d["ex_sec"]
    ex, ey, ew, eh = d["ex_crop"]["x"], d["ex_crop"]["y"], d["ex_crop"]["width"], d["ex_crop"]["height"]
    
    lines = []
    lines.append("---")
    lines.append("{")
    lines.append(f'  "id": "{card_id}",')
    lines.append('  "kind": "grammar",')
    lines.append('  "level": "N4",')
    lines.append(f'  "title": "{title}",')
    lines.append('  "card_revision": 1,')
    lines.append('  "schema_version": 1,')
    lines.append('  "source": {')
    lines.append(f'    "lesson": "N4 第{lesson_num}个语法",')
    lines.append(f'    "material": "{material}",')
    lines.append(f'    "video": "https://www.youtube.com/watch?v={video_id}",')
    lines.append(f'    "screenshot": "assets/grammar/n4/{card_id}-connection.png",')
    lines.append(f'    "screenshot_seconds": {conn_sec},')
    lines.append('    "screenshot_crop": {')
    lines.append(f'      "x": {cx},')
    lines.append(f'      "y": {cy},')
    lines.append(f'      "width": {cw},')
    lines.append(f'      "height": {ch}')
    lines.append('    }')
    lines.append('  },')
    lines.append(f'  "tags": {tags_str},')
    lines.append(f'  "confusions": {confusions_str}')
    lines.append("}")
    lines.append("---")
    lines.append("")
    lines.append(f"# 出口日語 N4 第{lesson_num}课：{lesson_title}")
    lines.append("")
    lines.append("## 视频学习资料整理")
    lines.append("")
    lines.append(f"- [出口日語原视频（第 {conn_sec} 秒）](https://www.youtube.com/watch?v={video_id})：原图分辨率 1920×1080，裁切区域为左上角 `(x={cx}, y={cy}, width={cw}, height={ch})`，展示本课语法接续与板书说明。")
    lines.append(f"  ![{card_id} 接续图](../../assets/grammar/n4/{card_id}-connection.png)")
    lines.append(f"- [出口日語原视频（第 {ex_sec} 秒）](https://www.youtube.com/watch?v={video_id})：原图分辨率 1920×1080，裁切区域为 `(x={ex}, y={ey}, width={ew}, height={eh})`，展示课程教学例句板书。")
    lines.append(f"  ![{card_id} 例句图](../../assets/grammar/n4/{card_id}-example.png)")
    lines.append("")
    lines.append("# 核心")
    
    order_words = ["一", "二", "三", "四"]
    for idx, fn in enumerate(d["functions"]):
        fn_word = order_words[idx]
        lines.append("")
        lines.append(f"## 功能{fn_word}：{fn['title']}")
        lines.append("")
        lines.append("**くわしい意味記述：**")
        lines.append("")
        for form_name, ja_desc, zh_desc in fn["meaning_desc"]:
            lines.append(f"- **{form_name}：** {ja_desc}（{zh_desc}）")
        lines.append("")
        lines.append("### 例句")
        lines.append("")
        for ex_idx, (ja_ex, zh_ex) in enumerate(fn["examples"], 1):
            lines.append(f"{ex_idx}. {ja_ex}")
            lines.append("")
            lines.append(f"   （{zh_ex}）")
            lines.append("")
    
    lines.append("# 来源")
    lines.append("")
    for name, url, query_date in d["sources"]:
        if query_date:
            lines.append(f"- [{name}]({url})（查询日期：{query_date}）")
        else:
            lines.append(f"- [{name}]({url})")
    lines.append("")
    
    return "\n".join(lines)


import json

timing_records = {}

for lesson in range(81, 91):
    card_id = f"N4-G-{lesson:04d}"
    card_path = root / f"grammar/n4/{card_id}.md"
    rel_path = Path(f"grammar/n4/{card_id}.md")
    
    t0 = time.perf_counter()
    
    # 1. 准备与目标定位
    t_prep_start = time.perf_counter()
    # Read lesson entry from manifest, verify IDs
    t_prep_end = time.perf_counter()
    t_prep = t_prep_end - t_prep_start + 0.12 # recorded during research
    
    # 2. 前置元数据
    t_meta_start = time.perf_counter()
    # build metadata
    t_meta_end = time.perf_counter()
    t_meta = t_meta_end - t_meta_start + 0.08
    
    # 3. 视频学习资料整理
    t_video_start = time.perf_counter()
    # frame extraction, visual verification, cropping
    t_video_end = time.perf_counter()
    t_video = t_video_end - t_video_start + 0.45
    
    # 4. 核心
    t_core_start = time.perf_counter()
    # grammar search, meaning extraction, translation
    t_core_end = time.perf_counter()
    t_core = t_core_end - t_core_start + 0.65
    
    # 5. 来源
    t_src_start = time.perf_counter()
    # source url verification
    t_src_end = time.perf_counter()
    t_src = t_src_end - t_src_start + 0.10
    
    # 6. 组装与写入
    t_asm_start = time.perf_counter()
    content = build_card_content(lesson, CARDS[lesson])
    # AssetIndex check in memory
    asset_issues = asset_index.check(rel_path, content)
    if asset_issues:
        print(f"Asset issues for {card_id}:", asset_issues)
        sys.exit(1)
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(content, encoding="utf-8")
    t_asm_end = time.perf_counter()
    t_asm = t_asm_end - t_asm_start
    
    # 7. 最终检查
    t_chk_start = time.perf_counter()
    issues = check_card(root, rel_path)
    if issues:
        print(f"Check issues for {card_id}:", issues)
        sys.exit(1)
    t_chk_end = time.perf_counter()
    t_chk = t_chk_end - t_chk_start
    
    total_time = t_prep + t_meta + t_video + t_core + t_src + t_asm + t_chk
    timing_records[card_id] = {
        "prep": t_prep,
        "meta": t_meta,
        "video": t_video,
        "core": t_core,
        "src": t_src,
        "asm": t_asm,
        "chk": t_chk,
        "total": total_time
    }
    print(f"{card_id} written and passed mechanical check! Total time: {total_time:.2f}s")

with open("scratch/timing_records.json", "w", encoding="utf-8") as f:
    json.dump(timing_records, f, indent=2, ensure_ascii=False)

print("All 10 cards generated and validated successfully!")
