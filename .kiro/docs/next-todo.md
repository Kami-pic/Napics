# [TODO] 下一步工作清单

---

## 订阅系统（Phase 0-3b 已完成）

### 紧急

- [ ] 发现页详情匹配错误：匹兹堡医护前线显示成年轻的皮特先生、无敌少侠显示成同名电影、黑袍纠察队显示成捉鬼小精灵。不是订阅改动引起的，需要单独排查 TMDB 搜索匹配逻辑

### 重要

- [ ] 日漫的播出日历 TMDB 经常没数据，需要接入 Bangumi Calendar API 作为备选
- [ ] 同一部作品已经有追更订阅时，再点洗版应该提示用户
- [ ] RSS 匹配器需要增强跨语言匹配能力（"葬送的芙莉莲"匹配 "Sousou no Frieren"）

### 延后

- [ ] 搜索结果缓存（同一个源+同一个关键词 30 分钟内不重复请求）
- [ ] 全局速率限制（避免 20 个订阅同时搜索把源站搞限频）
- [ ] 扩展更多 RSS 源：动漫花园、ACG.RIP、Bangumi Moe、YTS
- [ ] 反馈闭环：搜索日志、下载完成通知、推送接口
- [ ] `routes/search.py` 剩余端点清理

---

## 技术债务

- [x] `pan_models.py` Pydantic V2 迁移
- [x] `routes/discover.py` 拆分 → discover_enrich.py
- [x] 后端 `print()` → `logging` 模块
