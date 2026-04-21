---
name: multilang-name-enrichment
description: >
  多源英文名补全：从多个数据源获取影视作品的英文名，解决"只有中文+原始语言名，缺少英文名"的问题。
  Use when enriching media data with English names from TMDB/Douban/Bangumi,
  or when diagnosing why search results are poor on English-language sources.
  Depends on clean-name-system for structured name storage, L1 text-processing for detect_language.
  Do NOT use for search keyword dispatch (use multilang-search-dispatch).
---

# 多源英文名补全（Multilang Name Enrichment）

> 英文名是搜索英文 BT 站（Prowlarr/Bitsearch/YTS）的关键。
> 但很多数据源不直接提供英文名，需要主动获取和交叉补全。

## 一、核心问题

### 为什么英文名经常缺失

| 数据源 | title | original_title | 英文名在哪 | 问题 |
|--------|-------|---------------|-----------|------|
| TMDB（zh-CN） | 中文名 | 原始语言名 | 需要 `language=en-US` 单独请求 | original_title 对中国电影是中文 |
| 豆瓣 API v2 | 中文名 | 原始语言名 | subtitle 字段（旧版接口才有） | API v2 热门接口无 subtitle |
| 豆瓣旧版网页 | 中文名 | — | sub_title 字段 | 有英文名但格式不统一 |
| Bangumi | 中文名 | 日文原名 | **完全没有** | 需要从 TMDB 交叉补全 |
| NFO 文件 | 中文名 | 原始语言名 | englishtitle 标签 | 旧 NFO 可能没有此标签 |
| 文件名 | 混合 | — | 正则提取拉丁字母部分 | 质量最低，可能是缩写或乱码 |

### 关键红线

**`original_title` ≠ 英文名**

这是最常见的错误。`original_title` 是作品的原始语言名：
- 中国电影 → 中文（和 title 相同）
- 日本动画 → 日文（假名+汉字）
- 韩国电影 → 韩文
- 美国电影 → 英文（这种情况才等于英文名）

必须用 `detect_language()` 判断后再分配。

## 二、英文名获取优先级

从高到低：

| 优先级 | 来源 | 方法 | 可靠性 |
|--------|------|------|--------|
| 1 | TMDB `_get_english_title` | 用 `language=en-US` 请求 TMDB API（有文件缓存） | 最高（官方英文名） |
| 1.5 | TMDB 搜索结果 `original_title` | 异步补全时 `detect_language == "en"` 直接用 | 高（`_async_enrich_tmdb_ids` 中获取） |
| 2 | TMDB `original_title`（当 `_is_latin` 判断为拉丁字母） | 直接用 | 高（原始语言就是英文） |
| 3 | 豆瓣 `subtitle` 解析 | 用 `/` 分隔后 detect_language 提取英文部分 | 中（API v2 热门接口无此字段） |
| 4 | NFO `originaltitle` 标签 | 读取后需 detect_language 判断是否为英文 | 中（依赖 NFO 质量） |
| 5 | 文件名正则提取 | 匹配连续拉丁字母部分 | 低（可能是缩写/发布组名） |

### TMDB `_get_english_title` 的实现

```python
def _get_english_title(self, media_type: str, tmdb_id: int, original_title: str = "") -> str:
    # 如果 original_title 已经是英文，直接返回
    if original_title and _is_latin(original_title):
        return original_title
    # 否则用 en-US 语言参数请求 TMDB
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
    params = {"api_key": self.api_key, "language": "en-US"}
    resp = requests.get(url, params=params, timeout=5)
    data = resp.json()
    return data.get("title") or data.get("name") or ""
```

注意：这是一次额外的 API 请求，需要考虑频率控制。

## 三、各场景的补全策略

### 场景 A：刮削后更新

```
scraper.scrape_folder() → ScrapeResult(english_title=...)
→ shared._update_clean_names_after_scrape()
→ clean_from_scrape(english_title=...)
→ 写入 media_library.json 的 clean_name_en
```

TMDB 客户端在 `get_movie_detail` / `get_tv_detail` 中已经调用 `_get_english_title`，所以刮削后的数据通常有英文名。

### 场景 B：发现页推荐

```
豆瓣/TMDB/Bangumi 数据 → _inject_clean_names()
→ detect_language(original_title) 判断语言
→ 英文 → clean_name_en
→ 日/韩 → clean_name_original
→ 中文 → 跳过（和 title 重复）
→ 从 subtitle 中提取英文名（如果有）
```

**已知限制**：豆瓣 API v2 热门接口无 subtitle，且 `_async_enrich_tmdb_ids` 是异步的，第一次请求时英文名可能还没补全。

### 场景 C：扫描新文件

```
文件名 → clean_from_filename() → split_names()
→ 正则提取拉丁字母部分 → clean_name_en
```

质量最低，但聊胜于无。刮削后会被更高优先级的数据覆盖。

### 场景 D：树构建

```
文件夹 → clean_for_folder(shadow_name, folder_name)
→ 从 shadow_name 中拆分中英文
→ 如果 en 为空，尝试从 NFO 读取 englishtitle
```

## 四、语言判断规则

使用 L1 的 `detect_language()` 函数：

| 输入 | 判断 | 分配 |
|------|------|------|
| "Inception" | en | → clean_name_en |
| "盗梦空间" | cn | → 跳过（和 title 重复） |
| "進撃の巨人" | jp | → clean_name_original |
| "기생충" | ko | → clean_name_original |
| "Adèle" | en | → clean_name_en（拉丁字母为主） |
| "盗梦空间 Inception" | mixed | → split_by_language 拆分 |

### 特殊情况

- **繁体中文**：先转简体再归入 cn
- **纯汉字的日文名**（如"鬼滅"去掉假名后）：可能被误判为中文，先检测假名
- **法语/德语等拉丁字母语言**：归入 en（不做细分）
- **mixed 类型**：中英混合的 original_title 归入 clean_name_original（当前行为，可能需要 split_by_language 进一步拆分）
- **`_is_latin` vs `detect_language`**：TMDB 客户端的 `_get_english_title` 使用 `_is_latin()`（拉丁字母占比 > 50%）做快速判断；发现页 `_inject_clean_names` 用 L1 的 `detect_language()` 做更精细的语言分类。两处逻辑不同，修改时注意区分

## 五、旧数据兼容

media_library.json 中旧数据没有 `clean_name_cn` / `clean_name_en` / `clean_name_original` 字段。

### 后端兼容
- `clean_name_system.parse_legacy_clean_name()` 从旧 `clean_name` 字符串反向解析
- 树构建时 `clean_for_folder` 自动处理

### 前端兼容
- 如果 `clean_name_cn` 和 `clean_name_en` 都为空，从 `clean_name` 字符串中正则拆分：
  ```typescript
  const cnMatch = raw.match(/[\u4e00-\u9fff]+/g);
  const enMatch = raw.match(/[a-zA-Z][a-zA-Z0-9\s'.:-]*/g);
  ```

## 六、待解决的架构问题

### 发现页"先返回再补全"

当前 `_async_enrich_tmdb_ids` 是异步后台线程，第一次请求时英文名还没补全。

可能的解决方案：
1. **同步补全**：首次加载时同步请求 TMDB，但会拖慢 2-5 秒
2. **前端二次请求**：首次返回后，前端检测到 en 为空时触发补全请求
3. **预缓存**：后台定时任务预先补全热门数据的英文名
4. **接受延迟**：第一次加载缺英文名，刷新后有 ← 当前行为（2026-04-21）

### 豆瓣 API v2 vs 旧版接口

- API v2 热门接口：有 original_title，无 subtitle
- 旧版网页接口：有 sub_title（含英文名），但不稳定
- 建议：优先用 API v2 + TMDB 交叉补全，不依赖豆瓣 subtitle

## 七、实现文件

| 文件 | 职责 |
|------|------|
| `backend/clean_name_system.py` | clean_from_scrape 的 english_title 参数处理 |
| `backend/routes/discover.py` | _inject_clean_names 的语言判断 + _async_enrich_tmdb_ids 的异步英文名补全 |
| `backend/tmdb_client.py` | _get_english_title 方法 |
| `backend/text_processing.py` | detect_language 函数 |
| `frontend/components/detail/FolderDetail.tsx` | 旧数据兼容的前端拆分逻辑 |
