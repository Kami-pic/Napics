# [废弃] 名称流转链路治理 — 设计讨论

> 对应 skill-build-todo.md 阶段 2.0
> 目标：给名称加上来源追踪和可信度分层，防止高质量名称被低质量覆盖

---

## 一、现状分析

### 系统中有两套名称

| 名称 | 用途 | 存储位置 | 有来源追踪？ |
|------|------|----------|-------------|
| `clean_name` | 中文展示名、搜索词（中文部分）、本地匹配 | media_library.json 每条视频 | ❌ 没有 |
| `shadow_name` | 英文标准名、搜索词（英文部分）、本地匹配 | media_library.json 每条视频 | ✅ 有 `shadow_name_source` |

### clean_name 的写入点（4 个，无保护）

| # | 写入点 | 来源 | 质量 | 保护机制 |
|---|--------|------|------|----------|
| W1 | 扫描 `/scan` `/sync` | `_clean_filename_for_folder(file_name)` | 低：纯文件名清洗 | 仅在 clean_name 为空时写入 |
| W2 | 刮削后 `_update_clean_names_after_scrape` | 刮削结果的中文标题 | 中：TMDB/豆瓣标题 | ⚠️ **无条件覆盖** |
| W3 | 树构建 `get_library_tree` | shadow_name 去年份 / 文件夹名清洗 | 运行时计算 | 不持久化，无风险 |
| W4 | 用户手动 `/library/clean-name` | 用户输入 | 最高 | ⚠️ **无条件覆盖** |

### shadow_name 的写入点（4 个，部分保护）

| # | 写入点 | source 值 | 质量 | 保护机制 |
|---|--------|-----------|------|----------|
| S1 | NFO 提取 `batch_generate` | `"nfo"` | 高 | — |
| S2 | TMDB 搜索 `batch_generate` | `"tmdb"` | 中高 | — |
| S3 | 整理流程 `auto_fill` | `"parsed"` | 中低 | ✅ 不覆盖 manual |
| S4 | 用户手动 `set()` | `"manual"` | 最高 | 无条件覆盖（应该的） |

### 已识别的覆盖风险

#### 🔴 高危：`_update_clean_names_after_scrape` 无条件覆盖 clean_name
```
场景：用户手动设置了 clean_name = "沙丘 第二部"
      → 刮削成功，标题 = "沙丘2"
      → clean_name 被覆盖为 "沙丘2"
      → 用户的手动设置丢失
```

#### 🟡 中危：`auto_fill` 只保护 manual，不保护 nfo
```
场景：NFO 提取了 shadow_name = "Dune Part Two (2024)" [source=nfo]
      → 整理流程调用 auto_fill(source="parsed")
      → shadow_name 被覆盖为 "沙丘 第二部 Dune Part Two" [source=parsed]
      → 丢失了年份，质量下降
```

### 名称的消费点

| 消费场景 | 使用的名称 | 代码位置 |
|----------|-----------|----------|
| 前端树展示 | clean_name（运行时计算） | routes/library.py `get_library_tree` |
| 搜索词构造（中文） | clean_name | search_query_builder.py |
| 搜索词构造（英文） | shadow_name | search_query_builder.py |
| 本地媒体匹配 | clean_name + shadow_name | local_media_matcher.py |
| 刮削搜索 | clean_name / file_name | scraper.py / tmdb_client.py |

---

## 二、设计方案讨论

### 核心问题

> **要解决什么？** 名称被低质量来源覆盖，导致搜索词不准、匹配失败、展示错误。
>
> **不解决什么？** 不改变现有的重命名行为，不改变前端展示逻辑。

### 方案 A：统一 trust_level（TODO 中的原始方案）

给每条视频加两个字段：
```json
{
  "name_source": "filename_parsed" | "nfo_parsed" | "scrape_exact" | "user_manual",
  "trust_level": 1 | 2 | 3 | 4
}
```

**问题**：
- clean_name 和 shadow_name 是两个独立的名称，来源可能不同
- 一个 trust_level 无法同时描述两个名称的可信度
- 例如：clean_name 来自用户手动（trust=4），shadow_name 来自 parsed（trust=1）

### 方案 B：分别追踪（推荐）

给 clean_name 加独立的来源字段，shadow_name 已有 `shadow_name_source`：
```json
{
  "clean_name": "进击的巨人",
  "clean_name_source": "parsed" | "scrape" | "manual",
  
  "shadow_name": "Attack on Titan (2013)",
  "shadow_name_source": "nfo" | "tmdb" | "parsed" | "manual" | "douban" | "bangumi"
}
```

统一优先级表（两套名称共用）：
```
manual (4) > nfo (3) > tmdb (3) > scrape (2) > parsed (1) > "" (0)
```

**优点**：
- 和现有 shadow_name_source 机制一致，学习成本低
- 每个名称独立追踪，精确控制
- 不需要额外的 trust_level 字段，优先级从 source 直接推导

**缺点**：
- 多一个字段 `clean_name_source`

### 方案 C：合并为单一"最佳名称"

去掉 clean_name / shadow_name 的区分，统一为一个 `display_name` + `search_names[]`。

**问题**：
- 改动太大，违反"非破坏性"原则
- clean_name 和 shadow_name 服务于不同场景（中文展示 vs 英文搜索），合并会丢失信息

### 推荐：方案 B

理由：
1. 最小改动 — 只加一个 `clean_name_source` 字段
2. 和现有 `shadow_name_source` 机制对齐
3. 优先级规则简单明确
4. 不改变任何现有行为，只加保护

---

## 三、方案 B 详细设计

### 3.1 新增字段

media_library.json 每条视频新增：
```json
{
  "clean_name_source": "parsed" | "scrape" | "manual" | ""
}
```

现有数据默认 `clean_name_source = ""`（空字符串，等同于 parsed，最低优先级）。

### 3.2 优先级表

| source 值 | 优先级 | 含义 | 适用于 |
|-----------|--------|------|--------|
| `"manual"` | 4 | 用户手动设置 | clean_name + shadow_name |
| `"nfo"` | 3 | NFO 文件提取 | shadow_name |
| `"tmdb"` | 3 | TMDB API 查询 | shadow_name |
| `"scrape"` | 2 | 刮削结果标题 | clean_name |
| `"douban"` | 2 | 豆瓣刮削 | shadow_name |
| `"bangumi"` | 2 | Bangumi 刮削 | shadow_name |
| `"parsed"` | 1 | 文件名/文件夹名清洗 | clean_name + shadow_name |
| `""` | 0 | 未标记（历史数据） | clean_name |

### 3.3 写入保护规则

**核心规则：低优先级不覆盖高优先级。**

#### clean_name 写入保护

```python
CLEAN_NAME_PRIORITY = {"manual": 4, "scrape": 2, "parsed": 1, "": 0}

def safe_set_clean_name(item: dict, new_name: str, source: str) -> bool:
    """安全设置 clean_name，低优先级不覆盖高优先级"""
    existing_source = item.get("clean_name_source", "")
    if CLEAN_NAME_PRIORITY.get(existing_source, 0) > CLEAN_NAME_PRIORITY.get(source, 0):
        return False  # 拒绝覆盖
    item["clean_name"] = new_name
    item["clean_name_source"] = source
    return True
```

#### shadow_name 写入保护（改进现有 auto_fill）

```python
SHADOW_NAME_PRIORITY = {"manual": 4, "nfo": 3, "tmdb": 3, "scrape": 2, "douban": 2, "bangumi": 2, "parsed": 1, "": 0}

def auto_fill(self, file_path, shadow_name, source, ...):
    existing_source = item.get("shadow_name_source", "")
    if SHADOW_NAME_PRIORITY.get(existing_source, 0) > SHADOW_NAME_PRIORITY.get(source, 0):
        return False  # 不覆盖更高优先级
    # ... 写入
```

### 3.4 各写入点的改造

| 写入点 | 当前行为 | 改造后 |
|--------|----------|--------|
| W1 扫描 | 空时填入 | `safe_set_clean_name(item, cleaned, "parsed")` |
| W2 刮削后 | 无条件覆盖 | `safe_set_clean_name(item, cn_title, "scrape")` — 不覆盖 manual |
| W4 用户手动 | 无条件覆盖 | `safe_set_clean_name(item, name, "manual")` — 始终成功 |
| S3 整理 auto_fill | 不覆盖 manual | 不覆盖 manual + nfo + tmdb |

### 3.5 实施步骤（对应 TODO 2.0.1 ~ 2.0.3）

#### 2.0.1 只读/扩展（本次）
- [ ] 给 media_library.json 现有数据打标 `clean_name_source`
  - 有 `shadow_name` 且 clean_name 看起来像刮削结果 → `"scrape"`
  - 其余 → `""` （未标记）
- [ ] 写 `safe_set_clean_name` 辅助函数
- [ ] 不改变任何现有写入逻辑

#### 2.0.2 旁路运行
- [ ] 写验证脚本，统计各 source 分布
- [ ] 检测低质量名称（过短、纯数字、纯缩写）
- [ ] 检测可能的错误覆盖（模拟 safe_set_clean_name 的拦截效果）
- [ ] 输出报告供人工审阅

#### 2.0.3 正式拦截
- [ ] W2 `_update_clean_names_after_scrape` 改用 `safe_set_clean_name`
- [ ] S3 `auto_fill` 改为分层优先级
- [ ] 搜索词构造时优先用高优先级名称

---

## 四、讨论结论（2026-04-18 确认）

### Q1：source 细分 → 确认细分
clean_name_source 和 shadow_name_source 统一用相同的 source 值集合（nfo/tmdb/douban/bangumi/scrape/parsed/manual）。不影响性能，代码只是一个字符串字段。

### Q2：历史数据清洗 → 分两步做
沙盒全量测试（3215 个文件）发现 894 个质量问题（28%），主要是：
- 纯数字文件名（`02.rmvb`）→ 需要 fallback 到文件夹名
- clean_name 为空（方括号全去掉后什么都不剩）→ 需要 fallback 到文件夹名
- 残留技术标签（`AAC5.1`）→ 清洗规则需补充

策略：
1. 2.0.1 打标时，对 clean_name 为空或纯数字的条目，自动从文件夹名提取 clean_name 作为 fallback
2. 不做大规模重新清洗（风险太大），只修复明显的低质量名称
3. 把问题记录到 2.0.2 验证脚本的检查项

### Q3：set() 不改
手动修改 = 最高可信度（用户手动改说明自动的错了），set() 保持无条件覆盖，source 固定为 "manual"。

### Q4：不做 history
不需要持久化历史记录。

---

## 五、风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 历史数据打标不准 | 低 | 低（最差情况是下次刮削时被覆盖，和现在一样） | 2.0.2 验证脚本检查 |
| safe_set_clean_name 拦截了正确的覆盖 | 中 | 中（名称不更新） | 2.0.2 旁路运行先观察 |
| 新字段增加 JSON 体积 | 低 | 极低（每条多 20 字节） | 可忽略 |
