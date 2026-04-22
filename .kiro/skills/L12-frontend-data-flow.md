---
name: frontend-data-flow
description: >
  前端三层数据流模式：全量 → 智能过滤 → 用户筛选，三层分离 + 本地过滤不请求后端。
  Use when modifying search result display logic, FilterBar behavior,
  or debugging "filter not working" issues.
---

# L12 前端三层数据流

> 搜索结果的展示经过三层处理，每层独立，互不干扰。

## 三层架构

```
results（全量）
  → 后端返回的所有搜索结果，含 is_junk/match_score/quality_score
  → 只在新搜索时重置

displayResults（智能过滤 + 排序）
  → useMemo 计算：smartFilter 开启时过滤 is_junk
  → 排序：三档分层（有做种 > 死种 > 磁力链接），同层内 quality > match > seeders > size
  → smartFilter 开关变化时自动重算，不请求后端

filtered（用户筛选）
  → applyFilters(displayResults, FilterBar 条件)
  → 筛选器：分辨率/来源/编码/大小/做种数/源开关
  → 筛选器变化时自动重算，不请求后端
  → 最终渲染的数据
```

## 排序三档分层

```typescript
const tier = (r) => {
  if (r.seeders === 0 && r.size_gb === 0) return 2;  // 磁力链接
  if (r.seeders === 0 && !NO_SEEDER_INFO.has(r._source)) return 1;  // 死种
  return 0;  // 正常（含无做种数信息源）
};
// 同层内：quality_score DESC → match_score DESC → seeders DESC → size DESC
```

**NO_SEEDER_INFO 集合**：`cilixiong/xl720/acgrip/bangumi_moe`
新增直搜源时如果该源无做种数信息，必须在此注册，否则会被当作死种降权。

## FilterBar 统一导出

```typescript
// 根据 activeSource 自动选择
if (activeSource === "all") → AllFilterBar（直搜源下拉 + 通用筛选器）
else → SourceFilterBar（该源专属筛选器）
```

- Prowlarr Tab：有索引器下拉
- 磁力熊/XL720 Tab：无做种数筛选
- 网盘 Tab：绿色变体（emerald）

## 踩坑经验

- `disabledSources` 存 "prowlarr" 但结果的 indexer 是具体索引器名 → 改为按 `_source` 字段过滤
- `sourceKeywordInfo` 在新搜索开始时没清除 → 上次搜索词残留在回显中
- 前端排序只区分"磁力链接"和"其他" → acgrip/bangumi_moe 被当作死种降权 → 加 NO_SEEDER_INFO
