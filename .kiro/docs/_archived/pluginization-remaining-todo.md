# [废弃] pluginization-remaining-todo.md

> 全部完成，已归档。Phase 9 已收口，遗留项归入清债阶段。

---

## 判定结论

**建议：继续完成 Phase 9，不回补前置遗漏。**

理由：

1. Phase 5/6/7 的暂缓项不是遗漏，而是**有意识的边界决策**——它们依赖旧 scraper 内部协议、推荐模块、订阅系统等深层耦合，强行迁移会破坏行为等价性。
2. Phase 1 审计文档只是命名没对齐（内容已分散在 PUBLIC_CORE / PLUGIN_BOUNDARY / PRIVATE_PROVIDERS / FRONTEND_PROVIDER_HARDCODE 四份文档中），不影响后续执行。
3. Phase 9 是插件化改造的**最后一个用户可见收益阶段**——完成后前端不再硬编码 provider，新增源时前端零改动。
4. 前置暂缓项适合在插件化收口后开一个独立的"清债阶段"统一处理，届时可以设计 `ScrapeMetadataClient` 兼容层等更系统的方案。

---

## A. Phase 1 文档交付缺口（低优先级）

V2 方案要求输出 `docs/pluginization-audit.md`，当前没有这个文件。

实际审计内容已分散在：
- `PUBLIC_CORE.md` — 可公开核心能力清单
- `PLUGIN_BOUNDARY.md` — Provider 契约与依赖边界
- `PRIVATE_PROVIDERS.md` — 私有 provider 清单
- `FRONTEND_PROVIDER_HARDCODE.md` — 前端硬编码清单

**建议处理**：Phase 9 完成后，写一份 `pluginization-audit.md` 作为索引文档，指向上述四份文档，补齐形式交付。不需要重新审计。

---

## B. Phase 5 MetadataProvider 暂缓项

已完成：手动候选搜索/详情、get_media_info TMDB 路径、/scrape/execute 豆瓣分支。

### 暂缓清单

| 位置 | 说明 | 暂缓原因 |
|---|---|---|
| `routes/scrape.py` TMDB 默认分支 | 把 `TMDBClient` 传给 `scraper.scrape_folder/video` | scraper 依赖完整客户端方法（search_movie/get_tv_detail 等），不能用当前 adapter 简单替换 |
| `scraper.py` / `scraper_tv.py` | 刮削核心内部直接调用 TMDB/豆瓣 client | 需要先设计 `ScrapeMetadataClient` 兼容层 |
| `organizer.py` / `renamer.py` / `analyzer.py` | 整理/重命名/分析内部调用元数据 client | 同上 |
| `shadow_name_manager.py` | 影子名获取调用 TMDB | 同上 |
| `routes/discover.py` / `combined_recommend.py` / `discover_enrich.py` | 发现推荐直接调用 TMDB/豆瓣/Bangumi | 不属于刮削范围，需单独设计 |
| `completeness.py` | 完整性检测直接调用 TMDB | 同上 |
| `subscriber.py` / `rss_engine.py` | 订阅系统内部调用元数据 client | 同上 |
| `local_media_matcher.py` | 本地匹配异步补全调用 TMDB | 同上 |

**解法方向**：设计 `ScrapeMetadataClient` 兼容层（或 Core MetadataService），内部通过 registry 获取 provider，对外暴露旧 client 兼容接口。一次性替换所有内部调用点。

---

## C. Phase 6 Prowlarr 暂缓项

已完成：搜索执行入口（SSE/同步/单源）全部通过 adapter。

### 暂缓清单

| 位置 | 说明 | 暂缓原因 |
|---|---|---|
| `shared.py:get_clients()` | 仍统一构造旧客户端对象 | 全局 client 容器 provider 化是更大范围的重构 |
| `routes/scrape.py:/config/indexers` | Prowlarr 索引器管理接口 | 管理接口不是搜索执行入口 |
| `episode_search.py` | 剧集搜索策略（整季包验证/逐集搜索） | 涉及复杂搜索策略，不纳入搜索 provider 化 |
| `routes/search.py` 旧 `/search` enhanced fallback | 旧增强搜索兼容路径 | 属于旧兼容，后续统一清理 |
| `routes/download.py:/batch-search` | 下载前批量搜索辅助 | 和 Phase 7 下载器更相关 |

---

## D. Phase 7 Download/Storage 暂缓项

已完成：提交、进度、任务列表、文件列表、挂载读取全部 provider 化。

### 暂缓清单

| 位置 | 说明 | 暂缓原因 |
|---|---|---|
| `QBittorrentClient` / `AlistManager` 内部请求逻辑 | 底层 client 实现 | 作为 provider 内部实现保留，不需要重写 |
| `DownloadManager` 状态机 | Core 下载任务状态机 | 属于 Core，不是 provider 边界 |
| 订阅自动下载逻辑 | `rss_engine` 触发下载 | 属于 Core 编排 |
| `/alist/transfer` / `quark_transfer.py` | 网盘转存 | 已在 Phase 8 处理 |

---

## E. Phase 9 前端动态感知剩余项

### 已完成（搜索弹窗 Phase 9-A）

- [x] `api.getProviders()` + 类型定义
- [x] `SourceTabs` 展示名从 provider metadata 派生
- [x] `DIRECT_SOURCES` / `NO_SEEDER_INFO` 改为 capabilities 派生
- [x] `SearchSettingsPanel` 源列表从 provider 构造
- [x] 单源 Tab 默认搜索词从 capabilities 派生
- [x] Prowlarr 索引器筛选从 capabilities 派生

### 已完成（订阅源 Phase 9-B）

- [x] `SubscribeSourceSelect` RSS/直搜分组从 provider metadata 派生
- [x] 内容类型推荐从 provider `recommended_*` capabilities 派生
- [x] 源展示名从 provider `name` 字段获取

### 已完成（Metadata Tab Phase 9-C）

- [x] `CandidatePicker` Tab 列表从 metadata provider 列表驱动
- [x] `SettingsModal` 默认刮削源下拉从 metadata provider 列表动态渲染

### 保留为合理边界（不再推进）

- **CandidatePicker 各源搜索/选择函数**：API 协议不同，需后端统一候选 API 才能消除，属于清债阶段
- **SettingsModal FIELD_GROUPS**：用户配置表单，非 provider 业务判断，复杂度高收益低
- **搜索结果品牌色表**：展示样式 fallback，不参与业务判断
- **Fallback 硬编码**：provider 接口失败时的兜底，合理保留

---

## F. 跨阶段技术债（插件化收口后统一处理）

| 项目 | 说明 | 建议时机 |
|---|---|---|
| `shared.py` 全局单例收口 | 仍持有所有 scraper getter、client 构造 | 插件化全部收口后，开独立清债阶段 |
| `ScrapeMetadataClient` 兼容层 | 统一 scraper/discover/completeness 的元数据调用 | Phase 9 后开独立阶段 |
| `pluginization-audit.md` 索引文档 | 补齐 Phase 1 形式交付 | Phase 9 收口时顺手写 |
| `episode_search.py` provider 化 | 剧集搜索策略接入 provider | 清债阶段 |
| 旧 `/search` enhanced fallback 清理 | 旧兼容路径 | 清债阶段 |
| 前端 `types/index.ts` provider 联合类型演进 | `pan_type`/`channel` 等旧字段 | Phase 9 收口或清债阶段 |

---

## 推荐执行顺序

```
1. ✅ Phase 9 已收口（9-A 搜索弹窗 + 9-B 订阅源 + 9-C Metadata Tab）
2. 下一步：Phase 9 收口文档（pluginization-audit.md 索引 + devlog 归档）
3. 开"清债阶段"：ScrapeMetadataClient 兼容层 + shared.py 收口 + episode_search
4. 进入 Deploy Phase（环境变量/Dockerfile/NAS 文档）
```
