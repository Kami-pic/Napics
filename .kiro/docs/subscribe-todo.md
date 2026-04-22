# [TODO] 订阅系统待修复问题

> Phase 0-3b 已完成，以下是测试中发现的待修复问题。

---

## 紧急（影响使用）

### P0: 发现页详情匹配错误
- 匹兹堡医护前线 → 详情显示"年轻的皮特先生"
- 无敌少侠 (Invincible) → 详情显示同名电影而非动画剧集
- 黑袍纠察队 → 详情显示"捉鬼小精灵"，英文名 The Lost Boys 明显错误
- **根因**：TMDB 搜索用中文标题匹配到了错误结果，或详情缓存 key 冲突
- **不是订阅系统改动引起的**（git diff 确认最近提交未改动 discover/tmdb/douban 相关文件）
- **需要排查**：tmdb_client 的搜索匹配逻辑、详情缓存 key 生成规则、media_type 传递是否正确

### P1: 订阅搜索结果不受源选择限制
- 订阅 tab 点"搜索"走的是 SearchModal（全源搜索），不是订阅调度器的 search_one()
- 用户选了特定源（如只选 mikan），但搜索结果来自所有源
- **修复方案**：SearchModal 接受 sources 参数，或订阅 tab 的搜索走独立的订阅搜索 API

## 重要（体验优化）

### P2: 订阅卡片显示跟踪源状态
- 用户希望在订阅 tab 的卡片上看到"正在跟踪哪些源"的状态
- Prowlarr 算一个单独的源
- 当前 sourcesLabel 已有但旧订阅 sources 为空数组（没选过源）
- **修复方案**：卡片上显示源列表 + 每个源的最近搜索状态（成功/失败/超时）

### P3: 保存路径智能填入
- 需要根据 mediaType（电影/电视剧/动漫/综艺）自动填入对应的媒体库分类路径
- 洗版时应该用 local_file_path 的父目录
- **修复方案**：后端加 API 返回 config.category_tags 的反向映射（标签→路径），前端根据 mediaType 自动填入

### P4: 日历交互优化
- [x] 日历条目带上年份
- [ ] 已完结的订阅不出现在日历中（state=completed 过滤）
- [ ] 后续考虑月历/周视图等更好的交互样式

## 延后

### P5: 日漫日历 Bangumi fallback
- 当前 TMDB 没有放送日期时用"按周推算"兜底，不够准确
- 理想方案：接入 Bangumi Calendar API 获取真实放送日期
- 需要 bangumi_client 支持 calendar 端点

### P6: 订阅冲突提示
- 同一影片已有追更订阅，再点"蹲守升级"时应提示

### P7: 搜索结果缓存层
- search_service 加结果缓存（按源+关键词，TTL 30 分钟）

### P8: 全局速率限制器
- 避免 20 个订阅同时搜索触发限频

### P9: rss_matcher L1/L2 增强
- 引入 L1 normalize + L2 match_chain 做标题匹配
- 解决跨语言匹配（如"葬送的芙莉莲"匹配 "Sousou no Frieren"）
