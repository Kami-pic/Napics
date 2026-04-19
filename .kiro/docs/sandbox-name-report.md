# [一次性] 沙盒全量名称处理报告

> 运行日期：2026-04-18
> 沙盒路径：backend/sandbox_real/
> 视频文件总数：3215

## 总览

| 分类 | 文件数 |
|------|--------|
| 其他视频 | 161 |
| 动画电影 | 79 |
| 动画番 | 2205 |
| 电影 | 76 |
| 电视剧 | 682 |
| 综艺 | 12 |
| **合计** | **3215** |

质量问题数：894 / 3215

## 质量问题

| # | 文件夹 | 文件名 | clean_name | 问题 |
|---|--------|--------|------------|------|
| 1 | 其他地区 | 苹果.mkv | 苹果 | 过短: clean_name='苹果' |
| 2 | 欧美电影 | 羞耻.BD中英双字.mkv | 羞耻 | 过短: clean_name='羞耻' |
| 3 | ff13 | [FFSKY][FF13_THE_MOVIE][EP01][X264_480P_... | (空) | clean_name 为空 |
| 4 | ff13 | [FFSKY][FF13_THE_MOVIE][EP02][X264_480P_... | (空) | clean_name 为空 |
| 5 | ff13 | [FFSKY][FF13_THE_MOVIE][EP03][X264_480P_... | (空) | clean_name 为空 |
| 6 | ff13 | [FFSKY][FF13_THE_MOVIE][EP04][X264_480P_... | (空) | clean_name 为空 |
| 7 | ff13 | [FFSKY][FF13_THE_MOVIE][EP05][X264_480P_... | (空) | clean_name 为空 |
| 8 | ff13 | [FFSKY][FF13_THE_MOVIE][EP06][X264_480P_... | (空) | clean_name 为空 |
| 9 | ff13 | [FFSKY][FF13_THE_MOVIE][EP07][X264_480P_... | (空) | clean_name 为空 |
| 10 | ff13 | [FFSKY][FF13_THE_MOVIE][EP08][X264_480P_... | (空) | clean_name 为空 |
| 11 | ff13 | [FFSKY][FF13_THE_MOVIE][EP09][X264_480P_... | (空) | clean_name 为空 |
| 12 | ff13 | [FFSKY][FF13_THE_MOVIE][EP10][X264_480P_... | (空) | clean_name 为空 |
| 13 | ff13 | [FFSKY][FF13_THE_MOVIE][EP11][X264_480P_... | (空) | clean_name 为空 |
| 14 | ff13 | [FFSKY][FF13_THE_MOVIE][EP12][X264_480P_... | (空) | clean_name 为空 |
| 15 | ff13 | [FFSKY][FF13_THE_MOVIE][EP13][X264_480P_... | (空) | clean_name 为空 |
| 16 | ff13 | [FFSKY][FF13_THE_MOVIE][EP14][X264_480P_... | (空) | clean_name 为空 |
| 17 | ff13 | [FFSKY][FF13_THE_MOVIE][EP15][X264_480P_... | (空) | clean_name 为空 |
| 18 | ff13 | [FFSKY][FF13_THE_MOVIE][EP16][X264_480P_... | (空) | clean_name 为空 |
| 19 | Eureka Seven Hi-Evolution... | Eureka.Seven.Hi-Evolution.Anemone.2018.1... | Eureka Seven Hi-Evolution Anem | 残留技术标签: 'AAC' in 'Eureka Seven Hi-Evolution Anemone AAC5 1' |
| 20 | 91天 91Days | [DMG][91Days][12 END][720P][GB].mp4 | (空) | clean_name 为空 |
| 21 | 东京地震8.0 Tokyo Magnitude 8... | 02.rmvb | 02 | 纯数字: clean_name='02' |
| 22 | 东京地震8.0 Tokyo Magnitude 8... | 03.rmvb | 03 | 纯数字: clean_name='03' |
| 23 | 东京地震8.0 Tokyo Magnitude 8... | 04.rmvb | 04 | 纯数字: clean_name='04' |
| 24 | 东京地震8.0 Tokyo Magnitude 8... | 05.rmvb | 05 | 纯数字: clean_name='05' |
| 25 | 东京地震8.0 Tokyo Magnitude 8... | 06.rmvb | 06 | 纯数字: clean_name='06' |
| 26 | 东京地震8.0 Tokyo Magnitude 8... | 07.rmvb | 07 | 纯数字: clean_name='07' |
| 27 | 东京地震8.0 Tokyo Magnitude 8... | 08.rmvb | 08 | 纯数字: clean_name='08' |
| 28 | 东京地震8.0 Tokyo Magnitude 8... | 09.rmvb | 09 | 纯数字: clean_name='09' |
| 29 | 东京地震8.0 Tokyo Magnitude 8... | 10.rmvb | 10 | 纯数字: clean_name='10' |
| 30 | 东京地震8.0 Tokyo Magnitude 8... | 11.rmvb | 11 | 纯数字: clean_name='11' |
| 31 | 交响情人梦 Nodame Cantabile | 02.mp4 | 02 | 纯数字: clean_name='02' |
| 32 | 交响情人梦 Nodame Cantabile | 03.mp4 | 03 | 纯数字: clean_name='03' |
| 33 | 交响情人梦 Nodame Cantabile | 04.mp4 | 04 | 纯数字: clean_name='04' |
| 34 | 交响情人梦 Nodame Cantabile | 05.mp4 | 05 | 纯数字: clean_name='05' |
| 35 | 交响情人梦 Nodame Cantabile | 06.mp4 | 06 | 纯数字: clean_name='06' |
| 36 | 交响情人梦 Nodame Cantabile | 07.mp4 | 07 | 纯数字: clean_name='07' |
| 37 | 交响情人梦 Nodame Cantabile | 08.mp4 | 08 | 纯数字: clean_name='08' |
| 38 | 交响情人梦 Nodame Cantabile | 09.mp4 | 09 | 纯数字: clean_name='09' |
| 39 | 交响情人梦 Nodame Cantabile | 10.mp4 | 10 | 纯数字: clean_name='10' |
| 40 | 交响情人梦 Nodame Cantabile | 11.mp4 | 11 | 纯数字: clean_name='11' |
| 41 | 军火女王 Season 02 | (09) (2014) 720p.mp4 | (空) | clean_name 为空 |
| 42 | 军火女王 Season 02 | 01 720p.mp4 | 01 | 纯数字: clean_name='01' |
| 43 | 军火女王 Season 02 | 02 (2006) 720p.mp4 | 02 | 纯数字: clean_name='02' |
| 44 | 军火女王 Season 02 | 03 720p.mp4 | 03 | 纯数字: clean_name='03' |
| 45 | 军火女王 Season 02 | 04 720p.mp4 | 04 | 纯数字: clean_name='04' |
| 46 | 军火女王 Season 02 | 05 (2021) 720p.mp4 | 05 | 纯数字: clean_name='05' |
| 47 | 军火女王 Season 02 | 07 720p.mp4 | 07 | 纯数字: clean_name='07' |
| 48 | 军火女王 Season 02 | 08 720p.mp4 | 08 | 纯数字: clean_name='08' |
| 49 | 军火女王 Season 02 | 10 (2010) 720p.mp4 | 10 | 纯数字: clean_name='10' |
| 50 | 军火女王 Season 02 | 11 (2022) 720p.mp4 | 11 | 纯数字: clean_name='11' |

... 还有 844 个问题未列出


## 清洗前后对比（每类抽样）


### 其他视频（161 个文件，8 个文件夹）

| 文件夹 | 原始文件名 | clean_folder | parsed_clean | L1 cn | L1 en | 季 | 集 | 年 |
|--------|-----------|-------------|-------------|-------|-------|---|---|---|
| National Geographic ... | National.Geographic.Man.Made.Bugatt... | National Geographic ... | National Geographic ... |  | National.Geogra... |  |  |  |
| National Geographic ... | National Geographic Megafactories M... | National Geographic ... | National Geographic ... |  | National Geogra... | 1 | 2 |  |
| National Geographic ... | National.Geographic.Ultimate.Factor... | National Geographic ... | National Geographic ... |  | National.Geogra... |  |  |  |
| National Geographic ... | National Geographic Ultimate Factor... | National Geographic ... | National Geographic ... |  | National Geogra... |  |  |  |
| 其他地区 | 你妈妈也一样.And.Your.Mother.Too.2001.BD7... | 你妈妈也一样 And Your Moth... | 你妈妈也一样 And Your Moth... | 你妈妈也一样中西双字玛丽维尔贝... | .And.Your.Mothe... |  |  | 2001 |
| 指匠情挑 Fingersmith》（20... | Fingersmith.A.dvd2rmvb.chs.rmvb | Fingersmith A 2rmvb ... | Fingersmith A dvd2rm... |  | Fingersmith.A.d... |  |  |  |
| 欧美电影 | After.Porn.Ends.2012.720p.WEBRip.x2... | After Porn Ends iNTE... | After Porn Ends -iNT... |  | After.Porn.Ends... |  |  | 2012 |
| 韩国电影 | [日]反情色 アンチポルノ(2017-新年巨献).mp4 | 反情色 アンチポルノ( 新年巨献) | 反情色 アンチポルノ | 日反情色新年巨献 | [ ] アンチポルノ(2017... |  |  |  |

### 动画电影（79 个文件，8 个文件夹）

| 文件夹 | 原始文件名 | clean_folder | parsed_clean | L1 cn | L1 en | 季 | 集 | 年 |
|--------|-----------|-------------|-------------|-------|-------|---|---|---|
| 动画电影 | [SweetSub] VIRGIN PUNK - 01 Clockwo... | VIRGIN PUNK 01 Clock... | VIRGIN PUNK - 01 Clo... |  | [SweetSub] VIRG... |  |  |  |
| BLAME! Blame! (2003) | BLAME! Blame! (2003) 720p.mp4 | BLAME! Blame! | BLAME! Blame! |  | BLAME! Blame! (... |  |  |  |
| Eureka Seven Hi-Evol... | Eureka.Seven.Hi-Evolution.Anemone.2... | Eureka Seven Hi Evol... | Eureka Seven Hi-Evol... |  | Eureka.Seven.Hi... |  |  | 2018 |
| 乔西的虎与鱼 Josee, the Ti... | 乔西的虎与鱼 Josee, the Tiger and the Fis... | 乔西的虎与鱼 Josee, the Ti... | 乔西的虎与鱼 Josee, the Ti... | 乔西的虎与鱼 | Josee, the Tige... |  |  |  |
| 你的名字。 Your Name. (20... | 你的名字。 Your Name. (2016) 1080p.mp4 | 你的名字。 Your Name | 你的名字 Your Name | 你的名字 | 。 Your Name. (2... |  |  |  |
| Berserk Golden Age A... | Berserk Golden Age Arc 1.剑风传奇 剧场版 黄... | Berserk Golden Age A... | Berserk Golden Age A... | 剑风传奇剧场版黄金时代篇霸王之... | Berserk Golden ... |  |  |  |
| Berserk The Golden A... | Berserk.The.Golden.Age.Arc.2.剑风传奇 剧... | Berserk The Golden A... | Berserk The Golden A... | 剑风传奇剧场版黄金时代篇多尔多... | Berserk.The.Gol... |  |  |  |
| Berserk The Golden A... | Berserk.The.Golden.Age.Arc.3.剑风传奇 剧... | Berserk The Golden A... | Berserk The Golden A... | 剑风传奇剧场版黄金时代篇降临中... | Berserk.The.Gol... |  |  |  |

### 动画番（2205 个文件，8 个文件夹）

| 文件夹 | 原始文件名 | clean_folder | parsed_clean | L1 cn | L1 en | 季 | 集 | 年 |
|--------|-----------|-------------|-------------|-------|-------|---|---|---|
| 86-不存在的战区- 86 EIGHTY... | 86-不存在的战区- 86 EIGHTY-SIX S01E01 108... | 86 不存在的战区 86 EIGHTY ... | 86 不存在的战区 86 EIGHTY ... | 不存在的战区 | 86- - 86 EIGHTY... | 1 | 1 |  |
| 91天 91Days | 91天 91Days (2016) 720p.mp4 | 91天 91Days | 91天 91Days | 天 | 91 91Days (2016... |  |  |  |
| JOJO的奇妙冒险 JoJo's Biz... | JOJO的奇妙冒险 JoJo's Bizarre Adventure ... | JOJO的奇妙冒险 JoJo's Biz... | JOJO的奇妙冒险 JoJo's Biz... | 的奇妙冒险 | JOJO JoJo's Biz... | 1 | 1 |  |
| JOJO的奇妙冒险 第一二部(幻影之血+... | JOJO的奇妙冒险 第一二部(幻影之血+战斗潮流) 第01集 在线观看... | JOJO的奇妙冒险 (幻影之血 战斗潮流... | JOJO的奇妙冒险 第一二部 第01集 ... | 的奇妙冒险第一二部幻影之血战斗... | JOJO ( + ) 01 &... | 1 | 1 |  |
| JOJO的奇妙冒险 第五部(黄金之风) | JOJO的奇妙冒险 第五部(黄金之风) 第01话 在线观看&动漫下载 ... | JOJO的奇妙冒险 (黄金之风) 第01... | JOJO的奇妙冒险 第五部 第01话 在... | 的奇妙冒险第五部黄金之风第话在... | JOJO ( ) 01 & A... | 1 | 1 |  |
| JOJO的奇妙冒险 第四部(不灭钻石) | JOJO的奇妙冒险 第四部(不灭钻石) 第01话 在线观看&动漫下载 ... | JOJO的奇妙冒险 (不灭钻石) 第01... | JOJO的奇妙冒险 第四部 第01话 在... | 的奇妙冒险第四部不灭钻石第话在... | JOJO ( ) 01 & A... | 1 | 1 |  |
| JOJO的奇妙冒险第六部 石之海 | E25 官方 霸王龙压制组T Rexmp4 S01E25 1080p.... | E25 官方 霸王龙压制组T Rexmp... | E25 官方 霸王龙压制组T Rexmp... | 官方霸王龙压制组 | E25 T Rexmp4 S0... | 1 | 25 |  |
| PLUTO | 第 1 集 p.NF.WEB-DL.DDP S01E01 1080p.... | 第 1 集 p NF DDP | 第 1 集 p NF WEB DL DD... | 第集 | 1 p.NF.WEB-DL.D... | 1 | 1 |  |

### 电影（76 个文件，8 个文件夹）

| 文件夹 | 原始文件名 | clean_folder | parsed_clean | L1 cn | L1 en | 季 | 集 | 年 |
|--------|-----------|-------------|-------------|-------|-------|---|---|---|
| 007：无暇赴死 No Time to ... | 007：无暇赴死 No Time to Die (2021) 1080... | 007：无暇赴死 No Time to ... | 007 无暇赴死 No Time to ... | 无暇赴死 | 007： No Time to... |  |  |  |
| 21克 21 Grams (2003) | 21克 21 Grams (2003).ts | 21克 21 Grams | 21克 21 Grams | 克 | 21 21 Grams (20... |  |  |  |
| 300勇士：帝国崛起 300 Rise ... | 300勇士：帝国崛起 300 Rise of an Empire (2... | 300勇士：帝国崛起 300 Rise ... | 300勇士 帝国崛起 300 Rise ... | 勇士帝国崛起 | 300 ： 300 Rise ... |  |  |  |
| Marty Supreme (2025)... | Marty.Supreme.2025.1080p.WEBRip.x26... | Marty Supreme AAC | Marty Supreme AAC5 1 |  | Marty.Supreme.2... |  |  | 2025 |
| 两杆大烟枪 Lock, Stock an... | 两杆大烟枪 Lock, Stock and Two Smoking B... | 两杆大烟枪 Lock, Stock an... | 两杆大烟枪 Lock, Stock an... | 两杆大烟枪 | Lock, Stock and... |  |  |  |
| 你好，李焕英 Hi, Mom (2021... | 你好，李焕英 Hi, Mom (2021) 720p.mp4 | 你好，李焕英 Hi, Mom | 你好 李焕英 Hi, Mom | 你好李焕英 | ， Hi, Mom (2021... |  |  |  |
| 信条 Tenet (2020) | 信条 Tenet (2020) 720p.mp4 | 信条 Tenet | 信条 Tenet | 信条 | Tenet (2020) 72... |  |  |  |
| 克洛伊 Chloe (2010) | 克洛伊 Chloe (2010).ts | 克洛伊 Chloe | 克洛伊 Chloe | 克洛伊 | Chloe (2010).ts |  |  |  |

### 电视剧（682 个文件，8 个文件夹）

| 文件夹 | 原始文件名 | clean_folder | parsed_clean | L1 cn | L1 en | 季 | 集 | 年 |
|--------|-----------|-------------|-------------|-------|-------|---|---|---|
| better call saul s5 | better.call.saul.s05e01.1080p.web.h... | better call saul | better call saul |  | better.call.sau... | 5 | 1 |  |
| S1 | 全裸导演.The.Naked.Director.S01E01.官方中字... | 全裸导演 The Naked Direc... | 全裸导演 The Naked Direc... | 全裸导演官方中字 | .The.Naked.Dire... | 1 | 1 |  |
| S2 | 全裸导演 第二季第01集.mp4 | 全裸导演 第01集 | 全裸导演 第二季第01集 | 全裸导演第二季第集 | 01 .mp4 | 1 | 1 |  |
| Sex.Education.S01 | Sex.Education.S01E01.1080p.NF.WEB-D... | Sex Education | Sex Education | 中英 | Sex.Education.S... | 1 | 1 |  |
| Sex.Education.S03 | Sex.Education.S03E01.Episode.1.1080... | Sex Education | Sex Education |  | Sex.Education.S... | 3 | 1 |  |
| Sex.Education.S04.CO... | Sex.Education.S04E01.Episode.1.1080... | Sex Education | Sex Education |  | Sex.Education.S... | 4 | 1 |  |
| 第 1 集 Episode 1 | 第 1 集 Episode 1 S02E01 1080p.mp4 | 第 1 集 Episode | 第 1 集 Episode 1 | 第集 | 1 Episode 1 S02... | 2 | 1 |  |
| 第1季 | S01E01.mkv | S01E01 | S01E01 |  | S01E01.mkv | 1 | 1 |  |

### 综艺（12 个文件，1 个文件夹）

| 文件夹 | 原始文件名 | clean_folder | parsed_clean | L1 cn | L1 en | 季 | 集 | 年 |
|--------|-----------|-------------|-------------|-------|-------|---|---|---|
| 奇葩大会 | [奇葩大会]0203期：方文山现身晓松变迷弟_bd.mp4 | 0203期：方文山现身晓松变迷弟 | 0203期 方文山现身晓松变迷弟 | 奇葩大会期方文山现身晓松变迷弟 | [ ]0203 ： _bd.m... |  |  |  |