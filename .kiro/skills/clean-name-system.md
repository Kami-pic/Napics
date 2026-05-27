---
name: clean-name-system
description: >
  清洗名系统：从脏文件名/刮削数据中提取结构化的多语言名称，服务于 UI 展示、搜索词构造、匹配评分。
  Use when generating clean_name for folders/videos, constructing search keywords,
  or preparing multi-language name fields for downstream matching.
  Depends on L1 text-processing for normalize/splitByLanguage/detectLanguage.
  Do NOT use for matching/scoring (use L2), filtering (use L3), or sorting (use L4).
---

# 清洗名系统（Clean Name System）

> 从混乱的文件名和刮削数据中，提取结构化的多语言名称。
> 是 L1 文本处理的业务层封装，所有清洗逻辑的唯一入口。

## 一、核心概念

### clean_name 不是一个字符串，是一个结构

旧设计中 `clean_name` 是单个字符串（如 "进击的巨人 S01E03"），下游要用时再拆。
新设计中 `clean_name` 是结构化数据，包含多语言名称和附加信息：

```python
class CleanNameResult:
    cn: str           # 中文名（简体）："进击的巨人"
    en: str           # 英文名："Attack on Titan"
    original: str     # 原始语言名（日文/韩文/法语等非中非英语言）："進撃の巨人"
    display: str      # UI 展示用的组合名："进击的巨人 S01E03"
    suffix: str       # 附加尾缀："S01E03" / "第2季" / "剧场版"
    source: str       # 来源："manual" / "nfo" / "tmdb" / "scrape" / "parsed"
    confidence: str   # 置信度："high" / "medium" / "low"
```

### 为什么需要结构化

| 下游场景 | 需要的字段 | 旧设计的问题 |
|---------|-----------|-------------|
| 搜索词构造 | cn / en / original 分别给不同源 | 旧 clean_name 是混合字符串，要再拆一次 |
| UI 展示 | display（组合名） | 旧设计能满足，但格式不统一 |
| 匹配评分 | cn / en 分别比较 | 旧设计要从混合字符串中猜哪部分是中文 |
| 刮削候选 | cn 给豆瓣，en 给 TMDB，original 给 Bangumi | 旧设计完全不支持 |

## 二、清洗层级

### Level 0：去噪（strip_noise）

从脏文件名中去除所有非作品名的内容，输出"可能是作品名"的文本。

**去除内容**（按顺序）：
1. 方括号及内容：`[字幕组]`、`[1080p]`、`【广告】`、`「引号」`
2. 圆括号内的技术信息：`(BD 720P x264 10bit AAC)`、`(C46B0638)`
3. 圆括号内的广告/URL：`(www.xxx.com)`
4. 广告站名：电影天堂、影视帝国、红旅首发、66影视、AGE动漫 等
5. 裸 URL：`www.xxx.com`、`http://...`
6. 质量标签：2160p/1080p/720p/BluRay/WEB-DL/x264/x265/HEVC/DTS/AAC/10bit 等
7. 语言标签：中英双字/国粤双语/简繁字幕/双语字幕 等
8. 字幕组/发布组名：YYeTs/RARBG/FGT/SPARKS/FIX字幕侠/深影字幕组/弯弯字幕组 等
9. 流媒体来源标签：在线观看、动漫下载 等
10. 分辨率数字：1920x1080、1280X720
11. CD/Disc 分片标记
12. hash 值：`(C46B0638)`
13. 文件扩展名
14. 集标题（SxxExx 后面的英文集标题，如 "Chapter One MADMAX"）
15. 季范围尾缀：`S1-S3`、`1-8季`（用户手动标注的"已下载哪几季"）
16. 尾部独立季号：紧跟中文的 `S1`、`S01`、`S`、`16季`（文件夹名上的季标注）
17. 紧跟中文名的 `TV版`（如 `方子传TV版` → `方子传`）

**不去除**：
- 年份（保留，后续层级按需使用或去除）
- 季集号（保留，后续层级提取）
- 作品名中的关键词（如"剧场版"紧跟中文名时保留）
- 紧跟中文名的"剧场版"（与 TV版 不同，剧场版是作品名的一部分）

**输入输出**：
```
"[字幕组][进击的巨人][01][1080p][x265].mkv"
→ "进击的巨人 01"

"电影天堂www.dytt.com.盗梦空间.Inception.2010.BD1080P.中英双字.mkv"
→ "盗梦空间 Inception 2010"
```

**实现**：`clean_name_system.py` 的 `strip_noise()` 函数。

### Level 1：语言分离（split_names）

对 Level 0 的输出做语言分离，提取 cn / en / original。

**策略**：
1. 调用 L1 `split_by_language` 分离中文和英文
2. 检测是否有日文假名 → 归入 original
3. 检测是否有韩文 → 归入 original
4. 年份提取并剥离（不属于任何语言名）

**输入输出**：
```
"盗梦空间 Inception 2010"
→ { cn: "盗梦空间", en: "Inception", original: "", year: "2010" }

"進撃の巨人 进击的巨人 Attack on Titan"
→ { cn: "进击的巨人", en: "Attack on Titan", original: "進撃の巨人", year: "" }

"千と千尋の神隠し"
→ { cn: "", en: "", original: "千と千尋の神隠し", year: "" }
```

**特殊处理**：
- 繁体中文先转简体再归入 cn（调用 L1 的繁简转换）
- 日文中的汉字（无假名）不误判为中文（先检测假名）
- 纯英文名：cn 为空，en 有值
- 纯中文名：en 为空，cn 有值
- S/E+数字季集号保护：`split_by_language` 中 `s5`、`S01E03` 等模式作为整体 token 归入 en，不会被拆分成 `s` + `5`
- 纯数字不作为有效英文名：`clean_from_filename` 中从文件名解析出的纯数字 en 直接清空（如 `02.mkv` 不产生 `en=02`）

### Level 2：附加信息提取（extract_suffix）

从文件名或上下文中提取季集号、特殊标记等附加信息。

**提取内容**：
| 类型 | 模式 | 输出 |
|------|------|------|
| 季+集 | S01E03、s1e3 | suffix="S01E03" |
| 纯集号 | EP03、E03、第3集、03（尾部数字） | suffix="E03" |
| 绝对集号 | 第148话、148 | suffix="E148" |
| 季号 | Season 2、第2季、S02 | suffix="第2季"（中文展示）/ "S02"（英文） |
| 剧场版 | 剧场版、劇場版 | suffix="剧场版" |
| OVA/SP | OVA、OAD、SP、特别篇 | suffix="OVA" / "SP" |

**规则**：
- 季集号从 `parse_filename`（tmdb_client）获取，不重复造轮子
- 中文展示用"第X季"/"第X集"，英文/搜索用 "S0X"/"E0X"
- 剧场版/OVA 等标记从文件名或文件夹名中提取

### Level 3：组装展示名（compose_display）

将 cn / en / suffix 组装成 UI 展示用的 display 字符串。

**组装规则**：
| 场景 | display 格式 | 示例 |
|------|-------------|------|
| 电影文件夹 | cn [+ en] | "盗梦空间" / "盗梦空间 Inception" |
| TV 文件夹 | cn [+ en] | "进击的巨人" |
| 季文件夹 | cn + 第X季 | "进击的巨人 第3季" |
| 视频（剧集） | cn + SxxExx | "进击的巨人 S03E01" |
| 视频（电影） | cn [+ en] | "盗梦空间" |
| 剧场版 | cn + 剧场版 | "进击的巨人 剧场版" |

**规则**：
- cn 为空时用 en 替代
- cn 和 en 相同时只显示一个
- suffix 为空时不拼接

## 三、数据来源优先级

清洗名的各字段可能来自多个数据源，优先级从高到低：

| 优先级 | 来源 | cn | en | original | 说明 |
|--------|------|----|----|----------|------|
| 4 | manual | ✓ | ✓ | ✓ | 用户手动设置，最高优先 |
| 3 | nfo | ✓ | ✓ | ✓ | NFO 文件中的 title/originaltitle |
| 3 | tmdb | ✓ | ✓ | ✓ | TMDB API 返回的多语言标题 |
| 2 | douban/bangumi | ✓ | ✓ | ✓ | 豆瓣/Bangumi 补充 |
| 2 | scrape | ✓ | ✓ | - | 刮削结果（可能不含原始语言名） |
| 1 | parsed | ✓ | ✓ | - | 从文件名解析（Level 0+1） |
| 0 | (空) | - | - | - | 未设置 |

**合并规则**：
- 每个字段（cn/en/original）独立比较优先级
- 低优先级不覆盖高优先级（复用现有 `safe_set_clean_name` 的思路，扩展到多字段）
- 同优先级：后来的覆盖先来的（刮削结果更新）

## 四、调用场景映射

### 场景 A：扫描/同步新文件

```
文件名 → strip_noise() → split_names() → extract_suffix()
→ CleanNameResult(cn, en, original="", suffix, source="parsed", confidence="low")
→ 存入 media_library.json
```

### 场景 B：刮削成功后

```
刮削结果(title, original_title, english_title)
→ 直接填入 cn/en/original（不需要 strip_noise，刮削数据已经是干净的）
→ extract_suffix()（从文件名提取季集号）
→ compose_display()
→ CleanNameResult(source="tmdb"/"nfo", confidence="high")
→ safe_update（优先级保护写入）
```

### 场景 C：树构建时（get_library_tree）— 已接入

```
finalize 阶段：
  文件夹节点 → clean_for_folder(folder_name, shadow_name, folder_type)
  如果 en/original 为空且有 NFO → 从 NFO 补全（exists 预检避免无用 IO）

post_process 阶段：
  season 子文件夹 → clean_for_folder(parent_cn=父级cn, folder_type="season", season_num=N)
  视频节点 → clean_from_filename(parent_cn=父级cn, parent_en=父级en)
  尊重已有的高优先级 clean_name（manual/nfo/tmdb 不被覆盖）
```

### 场景 D：搜索词构造 — 已接入

```
媒体库搜索：FolderDetail/VideoDetail 直接用 node.clean_name_cn / node.clean_name_en
发现页搜索：_inject_clean_names() 统一注入 cn/en/original
前端 SearchModal props：cnName / enName / originalName
下游按源语言映射表选词：
  Prowlarr/Bitsearch → en
  磁力熊/XL720 → cn
  Nyaa → original > en
  蜜柑 → cn > original
  网盘 → cn > en
```

### 场景 E：手动编辑

```
用户输入 → 直接设置对应字段
→ source="manual", confidence="high"
→ 最高优先级，不被任何自动流程覆盖
```

## 五、持久化设计

### media_library.json 字段扩展

现有：
```json
{
  "clean_name": "进击的巨人 S01E03",
  "clean_name_source": "scrape"
}
```

新增（向后兼容）：
```json
{
  "clean_name": "进击的巨人 S01E03",
  "clean_name_source": "tmdb",
  "clean_name_cn": "进击的巨人",
  "clean_name_en": "Attack on Titan",
  "clean_name_original": "進撃の巨人"
}
```

- `clean_name` 保留为 display 字符串（向后兼容）
- 新增 `clean_name_cn` / `clean_name_en` / `clean_name_original` 三个结构化字段
- 旧数据没有新字段时，从 `clean_name` 反向解析（split_names）

### 文件夹级 clean_name

文件夹没有持久化记录（不在 media_library.json 中），每次树构建时动态计算。
这是合理的——文件夹的 clean_name 依赖子节点数据，动态计算保证一致性。

## 六、与现有代码的关系

### 替代关系（已完成）

| 旧函数 | 新函数 | 状态 |
|---------|--------|------|
| `_clean_filename_for_folder` (analyzer.py) | `strip_noise` (clean_name_system.py) | ✅ 树构建已切换 |
| `_extract_chinese_name` (analyzer.py) | `split_names` 中调用 L1 `split_by_language` | ✅ 树构建已切换 |
| `clean_season_name` (analyzer.py) | `clean_for_folder(folder_type="season")` | ✅ post_process 已切换 |
| `clean_episode_name` (analyzer.py) | `clean_from_filename(parent_cn=...)` | ✅ post_process 已切换 |
| `_update_clean_names_after_scrape` (shared.py) | `clean_from_scrape` + `safe_update_clean_name` | ✅ 已切换 |

> 旧函数仍保留在 analyzer.py 中（其他模块可能还在引用），但树构建和刮削流程已全部切换到新系统。

### 保留不动

| 函数 | 原因 |
|------|------|
| `safe_set_clean_name` (shared.py) | 优先级保护机制保留，扩展为多字段版本 |
| `clean_keyword` (text_processing.py) | 搜索清洗和名称清洗是不同场景，保留 |
| `generate_standard_name` (renamer.py) | 重命名用，和 clean_name 是不同用途 |
| `parse_filename` (tmdb_client.py) | 文件名解析器，clean_name 系统调用它 |

## 七、置信度判断

| 条件 | confidence |
|------|-----------|
| source=manual | high |
| source=nfo/tmdb 且 cn+en 都有值 | high |
| source=scrape 且 cn 有值 | medium |
| source=parsed 且 cn 有值 | medium |
| source=parsed 且只有 en | low |
| cn 和 en 都为空 | low |

置信度影响下游行为：
- high：搜索时直接用，不需要回退
- medium：搜索时用，但准备回退词
- low：搜索时可能需要用户确认或多轮回退


## 八、已知限制和边界情况

| 情况 | 当前处理 | 说明 |
|------|---------|------|
| 法语/德语等非英文拉丁字母（如 Adèle） | 归入 en 字段 | 不做特殊处理，L1 的 split_by_language 会把拉丁字母归入英文 |
| 纯集号文件名（如 `02.mkv`） | strip_noise 后只剩数字 | 需要依赖 parent_cn/parent_en 从父文件夹继承名称 |
| 集标题混入英文名（如 `S02E01 Chapter One`） | strip_noise 去除 SxxExx 后的英文集标题 | 只去大写开头的英文集标题，避免误删作品名 |
| 字幕组名不断增加 | strip_noise 中维护已知字幕组列表 | 新字幕组需要手动添加到正则中 |
| `SP` 在英文单词中误匹配（如 Spirited） | extract_suffix 用词边界 `(?<![a-zA-Z])` 保护 | 只匹配独立的 SP，不匹配单词内部的 |
| 繁体中文名同时是日文汉字 | 先检测假名，有假名归 original，无假名归 cn 并转简体 | 纯汉字的日文名（如"鬼滅の刃"去掉の后）可能被误判为中文 |
| 中文名粘连数字（如"夏日重现03"） | 数字紧邻中文时归入 cn | split_by_language 的规则，03 会跟着中文走 |
