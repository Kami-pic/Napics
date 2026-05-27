# 订阅数据流

> 订阅创建时数据从哪来、怎么传、后端怎么处理。改订阅创建逻辑时必读。

## 前端 → 后端数据传递

```
发现页详情（DoubanHotItem + MediaDetail）
  ↓ handleSubscribeConfirm
  ↓ 提取字段：
  │  type ← item.media_type（卡片级别，不是 tab 级别）
  │  season ← 标题正则提取（"第二季"→2, "S02"→2）
  │  clean_name_cn ← detail.clean_name_cn || item.clean_name_cn
  │  clean_name_en ← detail.clean_name_en || detail.english_title
  │  clean_name_original ← detail.clean_name_original
  │  tmdb_id ← detail.tmdb_id || detail.external_ids.tmdb_id
  │  imdb_id ← detail.external_ids.imdb_id
  │  douban_id ← item.douban_id
  ↓
  POST /subscribe → subscriber.add(data)
```

## 后端 subscriber.add() 处理

1. **aliases 构造**：前端清洗名优先 → alias_resolver 补充 → 标题兜底加入 cn
2. **tmdb_id 补全**：中文标题搜 TMDB → 失败用英文清洗名重试
3. **重复检查**：同作品同 purpose 拦截，不同 purpose（追更+洗版）允许共存并给 warning
4. **创建 Subscription**：所有字段（含 sources/best_version/purpose/target_quality/imdb_id）写入

## 红线

- type 必须从卡片 media_type 取，不能用 tab 级别
- aliases 用 `{"cn": [], "en": [], "original": []}`，不能用 `jp`
- tmdb_id 补全必须先中文搜再英文搜
- SubscriptionManager 必须用 shared.py 全局单例
