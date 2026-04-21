---
name: multilang-search-dispatch
description: >
  多语言搜索词分发：为不同搜索源选择最佳语言的搜索词 + 回退链。
  Use when constructing search keywords for multi-source search (BT/pan/RSS),
  implementing fallback chains, or adding new search sources.
  Depends on clean-name-system for cn/en/original structured names.
  Do NOT use for name cleaning (use clean-name-system) or matching (use L2).
---

# 多语言搜索词分发（Multilang Search Dispatch）

> 不同搜索源有不同的语言生态，用错语言搜索 = 搜不到结果。
> 本 skill 指导如何为每个源选择最佳搜索词，以及 0 结果时如何回退。

## 一、核心原则

### 搜索词不是一个字符串，是一个策略

旧设计：所有源用同一个搜索词（用户输入或 clean_name）。
新设计：每个源有自己的语言优先级，自动选择最佳词 + 回退链。

### 三语言字段

| 字段 | 含义 | 来源 |
|------|------|------|
| cn | 中文名（简体） | clean_name_system 的 cn 字段 |
| en | 英文名 | clean_name_system 的 en 字段，或 TMDB `_get_english_title` |
| original | 原始语言名（日/韩/法等） | clean_name_system 的 original 字段 |
| query | 用户输入的原始搜索词 | 前端搜索框 |

## 二、源→语言优先级映射

### BT/磁力源

| 源 | 优先级 | 说明 |
|---|---|---|
| Prowlarr | en → cn → query | 英文站为主 |
| Bitsearch | en → cn | 英文站 |
| YTS | en → cn | 英文电影站 |
| LimeTorrents | en → cn | 英文站 |
| 磁力熊 | cn → en | 中文片源站 |
| XL720 | cn → en | 中文片源站 |
| Nyaa | original → en → cn | 动画站，日文原名命中率最高 |
| 蜜柑 | cn → original → en | 字幕组站，中文标题为主 |
| ACG.RIP | cn → original → en | 中文字幕组 |
| Bangumi Moe | cn → original → en | 中文字幕组 |

### 网盘源

所有网盘源统一：cn → en（中文优先，纯英文片回退到英文名）

### 新增源时的判断标准

- 站点主要语言是什么？→ 该语言排第一
- 站点是否有中文资源？→ cn 排第二或第三
- 站点是否有日文/韩文资源？→ original 排在对应位置

## 三、回退链

### 触发条件
- 某个源搜索返回 0 结果
- 最多回退 2 次（共 3 轮：默认词 → 回退1 → 回退2）

### 执行方式
- 在同一个执行单元（future/线程）内部同步完成
- 不阻塞其他源的并行搜索
- 共享该源的总超时（如 20s）

### 去重规则
- 回退词和默认词相同时跳过（忽略大小写）
- cn == en 时只搜一次
- 回退链中的词按映射表顺序排列，不重复

### 结果处理
- 回退搜索的结果**追加**到该源的结果列表（不替换）
- 有结果就停止回退（不继续搜后续词）
- SSE 事件返回 `search_keywords`（搜过的词列表）和 `hit_keyword`（命中的词）

## 四、季号拼接

### 规则：格式跟源走，不跟词的语言走

| 源类型 | 季号格式 | 示例 |
|--------|---------|------|
| 中文源 | 第N季 | "进击的巨人 第3季" |
| 英文源 | S0N | "Attack on Titan S03" |

即使 Prowlarr 回退到中文词，季号仍然用 S03 格式（英文站标题通常用 S03）。

### 不拼接的情况
- season_number = 0 或未传
- 用户手动输入的搜索词（不自动加季号）

## 五、前端源 Tab 设计

### "全部"Tab 和"单源"Tab 职责彻底分开

| 维度 | "全部"Tab | 单源 Tab |
|------|----------|---------|
| 搜索词 | 用户输入，后端按映射表分发 | 自动填入该源的最佳词，用户可修改 |
| 搜索方式 | SSE 全源并行 | 单源 JSON 端点 |
| 回退链 | 后端每个源独立回退 | 后端该源独立回退 |
| 筛选器 | 全局筛选器 | 该源专属筛选器 |
| 状态 | 全局 results/keyword | 独立 SourceTabState |

### 状态不互相回写
- 单源 Tab 修改搜索词不影响"全部"Tab
- "全部"Tab 搜索不覆盖单源 Tab 的缓存
- 切换 Tab 时保存/恢复各自的 keyword

### 用户手动改词后不自动回退
- 尊重用户明确输入
- 只有自动填入的默认词才触发回退链

## 六、实现文件

| 文件 | 职责 |
|------|------|
| `backend/search_keyword_mapper.py` | 源→语言映射 + 回退链词表生成 + 季号拼接 |
| `backend/routes/search.py` | SSE 流接入 mapper + 单源端点 |
| `backend/search_helpers.py` | 结果增强（match_score/quality_score/junk 标记） |
| `frontend/components/search/SourceTabs.tsx` | 源 Tab 切换 UI |
| `frontend/components/search/SearchModal.tsx` | 源 Tab 状态管理 + 搜索词填入 |

## 七、踩坑经验

1. **original_title 不是英文名**：TMDB/豆瓣的 original_title 对中国电影是中文、日本动画是日文，必须用 detect_language 判断
2. **SSE 竞态**：用户快速切换搜索时，旧 EventSource 的结果会混入新搜索，必须用 ref 跟踪并关闭旧连接
3. **旧数据兼容**：media_library.json 中旧数据没有 clean_name_cn/en/original 字段，前端需要从 clean_name 字符串中正则拆分
4. **Bangumi 没有英文名**：需要从 TMDB 交叉补全
5. **季号格式跟源走**：Prowlarr 回退到中文词时，季号仍用 S03（英文站标题格式）
