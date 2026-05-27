# [废弃] FRONTEND_PROVIDER_HARDCODE.md

> 全部完成，已归档。Phase 9 前端动态化已完成。

## 结论

前端已经部分通过后端接口读取搜索源：`api.getSearchSources()` 和 `api.getSubscriptionSources()`。但仍有多处硬编码源名称、分组、展示名、能力判断和推荐策略。Phase 9 应统一改为从 `GET /api/providers` 读取 provider metadata。

## 硬编码点清单

| 文件 | 硬编码内容 | 风险等级 | 依赖 `shared.py` | 适合进入开源版 | 改造建议 |
|---|---|---:|---|---|---|
| `frontend/components/search/useSearchState.ts` | `DIRECT_SOURCES` 写死 BT 直搜源集合 | 中 | 不适用 | 否，需改造 | 改为 provider `type=bt` 且 `capabilities` 区分 `indexer`/`direct_search`。 |
| `frontend/components/search/useSearchState.ts` | `sourceDefaultKeywords` 按源名生成默认搜索词 | 中 | 不适用 | 否，需改造 | 后端 provider 返回 `keyword_profile` 或由 Core API 返回建议关键词。 |
| `frontend/components/search/useSearchState.ts` | `NO_SEEDER_INFO` 写死无做种信息源 | 中 | 不适用 | 否，需改造 | 改为 provider capability：`seeders=false` 或 `seederInfo=none`。 |
| `frontend/components/search/SourceTabs.tsx` | `BT_SOURCE_LABELS` 写死 BT 源展示名 | 中 | 不适用 | 否，需改造 | 使用 `provider.name/display_name`。 |
| `frontend/components/search/SourceTabs.tsx` | `PAN_SOURCE_LABELS` 写死网盘源展示名 | 高 | 不适用 | 否 | 网盘源公开版不应内置，前端只展示后端返回的 private provider。 |
| `frontend/components/media/SubscribeSourceSelect.tsx` | `RSS_SOURCES` 写死 RSS 源集合 | 中 | 不适用 | 否，需改造 | 使用 provider `kind=rss`。 |
| `frontend/components/media/SubscribeSourceSelect.tsx` | `RECOMMENDATIONS` 写死按内容类型推荐源 | 中 | 不适用 | 否，需改造 | 后端返回 provider `recommended_for` 或 Core 返回推荐组。 |
| `frontend/components/search/SearchSettingsPanel.tsx` | 设置页按 `type === "bt"` / `"pan"` 固定分组 | 中 | 不适用 | 部分适合 | 改为 provider `kind/type/riskLevel` 分组。 |
| `frontend/components/settings/SettingsModal.tsx` | Prowlarr、OpenList、TMDB 配置项写死 | 中 | 不适用 | 部分适合 | 保留基础配置页，但 provider 配置应由 registry metadata 渲染。 |
| `frontend/components/detail/CandidatePicker.tsx` | `tmdb/douban/bangumi` Tab 写死 | 中 | 不适用 | 部分适合 | 改为 metadata provider 列表驱动。 |
| `frontend/lib/mediaColors.ts` | `douban/tmdb/bangumi` 评分颜色写死 | 低 | 不适用 | 可保留过渡 | 长期由 provider theme/color 或 source category 驱动。 |
| `frontend/types/index.ts` | provider/source 字段联合类型写死，如 `pan_type`、`channel` | 中 | 不适用 | 需演进 | 新增 provider metadata 类型，旧字段兼容保留。 |

## 当前后端接口状态

| 前端调用 | 当前接口 | 当前问题 |
|---|---|---|
| `api.getSearchSources()` | `GET /search/sources` | 只覆盖 BT/Pan 搜索源，字段不足，不覆盖 metadata/rss/download/storage。 |
| `api.getSubscriptionSources()` | `GET /subscribe/sources` | 只覆盖 RSSSourceManager 中已注册 RSS 源。 |
| 设置页索引器 | `GET /api/config/indexer-priorities` 等 | 仍以 Prowlarr indexer 为中心。 |
| 候选刮削 Tab | 多个 media info/search API | 前端直接知道 `tmdb/douban/bangumi`。 |

## 推荐的 Provider Metadata

前端最少需要这些字段：

| 字段 | 用途 |
|---|---|
| `id` | 稳定 key。 |
| `name` | 展示名。 |
| `kind` | `search` / `rss` / `metadata` / `download` / `storage`。 |
| `type` | `bt` / `pan` / `metadata` / `download` 等二级分类。 |
| `enabled` | 是否启用。 |
| `capabilities` | 决定 UI 功能，例如 `seeders`, `size`, `magnet`, `rss`, `episodes`, `artwork`。 |
| `riskLevel` | 展示风险提示，公开版隐藏 private provider。 |
| `requires` | 配置项，例如 API Key、URL、Token。 |
| `display` | 可选 UI 属性：颜色、排序、推荐标签。 |
| `recommendedFor` | `anime`, `movie`, `tv`, `cn_tv`, `us_tv` 等。 |

## 改造建议

### Phase 9.1：新增统一读取

- 新增 `api.getProviders()`。
- 页面初始化时读取 `GET /api/providers`。
- 暂时保留 `getSearchSources()` 和 `getSubscriptionSources()` 兼容。

验证：

- 打开搜索弹窗，BT/Pan Tab 和现有显示一致。
- 打开订阅弹窗，源列表和现有显示一致。

### Phase 9.2：搜索 UI 去硬编码

- `SourceTabs.tsx` 删除 `BT_SOURCE_LABELS` / `PAN_SOURCE_LABELS`。
- `useSearchState.ts` 的 `DIRECT_SOURCES` 改为 provider metadata 判断。
- `NO_SEEDER_INFO` 改为 `capabilities` 判断。

验证：

- 禁用某个 provider 后前端自动隐藏或禁用。
- 新增 provider metadata 后前端无需改代码即可出现 Tab。

### Phase 9.3：订阅源去硬编码

- `SubscribeSourceSelect.tsx` 使用 `kind=rss` 和 `kind=search` 分组。
- 推荐策略从后端 metadata 获取，或 Core API 根据媒体类型返回推荐 provider。

验证：

- 动画/电影/剧集订阅弹窗推荐源和旧行为等价。

### Phase 9.4：Metadata provider 动态化

- `CandidatePicker.tsx` 的 `tmdb/douban/bangumi` Tab 改为 metadata provider 列表。
- `mediaColors.ts` 颜色由 provider display metadata 或 source category 决定。

验证：

- 现有 TMDB/Douban/Bangumi 候选选择行为不变。

## 公开版风险提示

前端公开版不得出现：

- 内置网盘搜索源品牌列表。
- 私有资源站名称。
- 将“自动下载/自动转存资源”作为默认主路径的 UI 文案。

前端公开版可以出现：

- “Provider 插件”
- “用户自配下载器”
- “用户自配元数据源”
- “示例 provider”
