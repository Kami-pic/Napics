# [TODO] 下一步工作清单

---

## 订阅系统（Phase 0-3b 已完成，以下为测试中发现的待修复）

### 紧急

- [ ] P0: 发现页详情匹配错误（匹兹堡→年轻的皮特、无敌少侠→同名电影、黑袍→捉鬼小精灵）— 非订阅改动引起，需单独排查 tmdb_client 匹配逻辑
- [ ] P1: 订阅搜索不受源选择限制 — 订阅 tab 点搜索走 SearchModal 全源搜索，应只搜选中的源
- [ ] P2: 订阅卡片显示跟踪源状态 — 每个源的最近搜索状态（成功/失败/超时）

### 重要

- [ ] P3: 保存路径智能填入 — 根据 mediaType 从 config.category_tags 反查路径，洗版用 local_file_path 父目录
- [ ] P5: 日漫日历 Bangumi fallback — 接入 Bangumi Calendar API 获取真实放送日期
- [ ] P6: 订阅冲突提示 — 同一影片已有追更，再点洗版时提示
- [ ] P9: rss_matcher L1/L2 增强 — 跨语言标题匹配

### 延后

- [ ] P7: 搜索结果缓存层（按源+关键词，TTL 30 分钟）
- [ ] P8: 全局速率限制器
- [ ] Phase 4a: 扩展 RSS 源（动漫花园/Nyaa RSS/ACG.RIP/Bangumi Moe/YTS）
- [ ] Phase 4b: 反馈闭环（搜索日志/下载通知/推送接口）

---

## 技术债务

- [x] `pan_models.py` Pydantic V2 迁移
- [ ] `routes/search.py` 拆分 → Phase 1b 已抽离核心逻辑到 search_service.py，剩余端点待清理
- [x] `routes/discover.py` 拆分 → discover_enrich.py
- [x] 后端 `print()` → `logging` 模块
