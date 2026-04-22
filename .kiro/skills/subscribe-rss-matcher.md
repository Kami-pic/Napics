# RSS 匹配器

> rss_matcher.py 的过滤链逻辑。改匹配规则、Quality Cutoff、集数判定时必读。

## 过滤链

```
match_items(items, subscription):
  1. _filter_title_match — 跨语言标题匹配（L1+L2）
  2. _filter_quality — 最低质量要求
  3. _filter_keywords — 包含/排除关键词
  4. _filter_episodes — 集数匹配 + Quality Cutoff + 指纹去重
```

## 标题匹配（_filter_title_match）

- 从 subscription.aliases 构造候选名称列表（cn + en + original + search_keyword）
- 用 search_helpers.extract_bt_title_for_match 清洗 BT 标题
- 用 match_scoring.match_chain 计算匹配分
- score < 20 过滤（明显不相关）
- 解决跨语言匹配：如"葬送的芙莉莲"匹配 "Sousou no Frieren"

## Quality Cutoff（_filter_episodes）

- subscription.target_quality 非空时启用
- 遍历 downloaded_episodes，解析每集的 quality_tag
- 质量 rank >= target_quality 的 rank → 加入 cutoff_episodes 集合
- 匹配时跳过 cutoff_episodes 中的集号（即使有更好版本也不再搜索）

## 集数匹配规则

- 电影：`"0" not in downloaded` 时通过
- 剧集正常模式：`ep_key not in downloaded` 时通过（只下缺失集）
- 剧集洗版模式：不受已下载限制，但 Quality Cutoff 仍生效
- 整季包：有 S01 但无 E01 → `_looks_like_season_pack` → 通过
- 指纹去重：同 info_hash 不重复推送
