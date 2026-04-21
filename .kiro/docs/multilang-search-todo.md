# [TODO] 多语言搜索词 + 源 Tab 切换设计

> 目标：每个搜索源使用最适合的语言搜索词，UI 从"筛选开关"改为"源 Tab 切换"，每个 Tab 有独立搜索词和筛选器。
> 前提：媒体至少有 cnName + enName 两个清洗名可用（由 clean_name_system.py 保证，已完成）。
> 清洗名字段：cn / en / original，前端通过 clean_name_cn / clean_name_en / clean_name_original 获取。
> 范围：只做"搜索词填入 + 回退链"，不涉及筛选器定制和 UI 细节（后续 TODO）。

---

## 一、源穷举 + 最佳搜索词映射

### BT/磁力（6 源）

| 源 | 语言生态 | 默认搜索词 | 回退顺序 | 说明 |
|---|---|---|---|---|
| Prowlarr | 英文为主（1337x/TorrentGalaxy/IPT 等） | enName | en → cn → original | 大部分索引器是英文站 |
| Bitsearch | 英文站 | enName | en → cn | 搜中文基本无结果 |
| 磁力熊 | 中文为主 | cnName | cn → en | 国产片源站 |
| XL720 | 中文为主 | cnName | cn → en | 国产片源站 |
| Nyaa | 日文/英文（动画站） | jpName > enName | jp → en → cn | 日文原名命中率最高 |
| 蜜柑 | 中文/日文（字幕组） | cnName | cn → jp → en | 字幕组标题通常中文 |

### 网盘（9 源，中文优先但不绝对）

| 源 | 语言生态 | 默认搜索词 | 回退顺序 | 说明 |
|---|---|---|---|---|
| PanSearch | 中文为主 | cnName（有中文时）/ enName（纯英文片） | cn → en | 国内网盘资源 |
| 人人电影 | 中文为主 | cnName / enName | cn → en | 中文影视站 |
| 低端影视 | 中文为主 | cnName / enName | cn → en | 中文影视站 |
| PanSou | 中文为主 | cnName / enName | cn → en | TG 频道代搜 |
| MultiSite | 中文为主 | cnName / enName | cn → en | 多站聚合 |
| Slowread | 中文为主 | cnName / enName | cn → en | 中文站 |
| WnSearch | 中文为主 | cnName / enName | cn → en | 中文站 |
| 狗狗盘搜 | 中文为主 | cnName / enName | cn → en | 中文站 |
| GitHub | 中文为主 | cnName / enName | cn → en | 中文索引 |

> 网盘搜索词规则：有 cnName 时优先用 cnName；cnName 为空或与 enName 相同时用 enName。
> 也存在大量纯英文名资源（如外语片未翻译），回退到 enName 是必要的。

### 业务场景 × 搜索词选择

| 场景 | 搜索词策略 | 说明 |
|---|---|---|
| 普通搜索（电影/剧集） | 按源语言映射表选词 | 标准流程 |
| 季搜索 | cnName+"第N季" / enName+"S0N" | 中文源加中文季号，英文源加英文季号 |
| 单集搜索 | cnName+集号 / enName+S0NE0N | 需要更精确的匹配 |
| 剧场版/OVA | jpName > enName（精确） | 动画剧场版用日文名最准 |
| 网盘搜索 | 有 cnName 时优先 cnName，否则 enName | 中文优先但不绝对，纯英文片用英文名 |
| 刮削候选 | cnName（豆瓣）/ enName（TMDB）/ jpName（Bangumi） | 各刮削源用对应语言（不在本 TODO 范围） |

---

## 二、UI 设计：源 Tab 切换

### BT/磁力 Tab 结构

```
┌─────────────────────────────────────────────────────────┐
│ [全部] [Prowlarr] [Bitsearch] [磁力熊] [XL720] [Nyaa] [蜜柑] │  ← 源 Tab
├─────────────────────────────────────────────────────────┤
│ [搜索框: 当前 Tab 的搜索词]  [搜索按钮]                      │
│ [筛选器: 当前 Tab 专属]                                     │
├─────────────────────────────────────────────────────────┤
│ 结果列表                                                   │
└─────────────────────────────────────────────────────────┘
```

### 规则

1. **"全部" Tab**：
   - 搜索框 = 用户输入（不自动填充多语言词）
   - 点搜索 → 所有启用源并行搜索，每个源自动用自己的最佳语言词
   - 筛选器 = 现有逻辑（源开关多选 + 分辨率/编码/大小/做种数）

2. **单源 Tab**：
   - 切换到该 Tab 时，搜索框自动填入该源的最佳搜索词（cn/en/jp/original）
   - 用户可修改搜索词，修改只对当前 Tab 生效
   - 点搜索 → 只搜该源
   - 筛选器 = 该源专属（后续 TODO 设计）

3. **网盘 Tab 结构**（同理）：
   - [全部] [PanSearch] [人人电影] [低端影视] [PanSou] ...
   - 网盘源统一填 cnName，用户可修改

4. **搜索词独立性**：
   - 每个 Tab 维护自己的 keyword 状态
   - 在单源 Tab 修改搜索词不影响其他 Tab
   - 在"全部"Tab 搜索时，忽略各单源 Tab 的自定义词，统一用搜索框内容按映射表分发

---

## 三、回退链设计

### 触发条件
- 某个源搜索返回 0 结果时，自动用回退顺序的下一个词再搜一次
- 最多回退 2 次（3 个词：默认 → 回退1 → 回退2）

### 结果合并
- 回退搜索的结果追加到该源的结果列表中（不替换）
- 所有回退轮次的结果统一展示，不区分来自哪个搜索词

### UI 回显
- 搜索框旁边显示实际命中的搜索词标签，如：`[命中: "Inception"] [回退: "盗梦空间"]`
- 如果回退了，显示所有搜过的词（灰色标签），命中的词高亮
- 格式示例：`🔍 "Inception" → "盗梦空间"（2轮，共15条）`

### 回退链在不同模式下的行为

| 模式 | 回退行为 |
|---|---|
| "全部" Tab 搜索 | 每个源独立回退，互不影响 |
| 单源 Tab 搜索 | 该源独立回退 |
| 用户手动修改搜索词后搜索 | 不触发回退（用户明确指定了词） |

---

## 四、数据流设计

### 前端 → 后端

**"全部"模式（SSE 流增强）**：
```
GET /api/search/stream?query=xxx&cn_name=xxx&en_name=xxx&jp_name=xxx
```
- 新增 `jp_name` 参数
- 后端 SSE 流内部为每个源选择最佳搜索词（按映射表）
- 每个源独立回退：0 结果时自动换词再搜
- 这是解决"精准匹配"的核心改造点——现有 SSE 流已经按源分词，增强回退逻辑即可

**单源模式**：
```
GET /api/search/source?source=nyaa&keyword=xxx&fallback_keywords=xxx,yyy
```
- 单源搜索端点，用用户在该 Tab 输入的词直接搜
- `fallback_keywords`（可选）：回退词列表，keyword 搜 0 结果时依次尝试
- 用户手动改过词后不传 fallback_keywords（不自动回退）

### 后端响应（SSE 扩展）

现有 `source_done` 事件扩展：
```json
{
  "type": "source_done",
  "source": "nyaa",
  "status": "done",
  "count": 8,
  "search_keywords": ["進撃の巨人", "Attack on Titan"],  // 新增：实际搜过的词列表
  "hit_keyword": "進撃の巨人",                           // 新增：命中的词（有结果的第一个）
  "results": [...]
}
```

### 前端状态

```typescript
// 每个 Tab 的独立状态
interface SourceTabState {
  keyword: string;           // 当前搜索框内容
  results: SearchResult[];   // 该源的结果
  searchedKeywords: string[]; // 搜过的词列表（含回退）
  hitKeyword: string;        // 命中的词
  searching: boolean;
}

// Tab 状态 map
const [sourceTabs, setSourceTabs] = useState<Record<string, SourceTabState>>({});
```

---

## 五、实现步骤

### Phase 1：后端多语言搜索词分发 + 回退链

- [x] SSE 端点接收 `jp_name`、`season_number` 参数
- [x] 新建 `search_keyword_mapper.py`：源→语言优先级映射 + 回退链词表生成 + 季号拼接
- [x] 重构 `_search_prowlarr()` 和 `_search_direct()`：用 mapper 选词 + 回退链（0 结果换词，最多 3 轮）
- [x] `source_done` 事件新增 `search_keywords` 和 `hit_keyword` 字段
- [x] 单源搜索端点 `GET /api/search/source?source=xxx&keyword=xxx&fallback_keywords=xxx`（JSON 响应）
- [x] 前端 api.ts 扩展 `searchStream` 参数 + 新增 `searchSource` 方法
- [x] 25 个单元测试全绿（mapper 覆盖各源词选择、去重、回退、季号拼接）

### Phase 2：前端源 Tab 切换 + 搜索词填入

- [x] 新建 `SourceTabs.tsx`：源 Tab 切换组件（BT/网盘共用，显示搜索词回显）
- [x] BT 模式增加源 Tab 行（全部 + 已启用的各源）
- [x] 每个 Tab 维护独立的 keyword/results/searchedKeywords/hitKeyword/searching 状态
- [x] 切换 Tab 时自动填入该源的最佳搜索词（前端侧映射）
- [x] "全部"模式搜索走现有 SSE 流（增强：收集 search_keywords/hit_keyword）
- [x] 单源模式搜索调用 `api.searchSource` 端点
- [x] 前端构建通过，getDiagnostics 零报错

### Phase 3：回退链 UI 回显

- [x] SSE source_done 事件的 search_keywords/hit_keyword 已在前端收集到 sourceKeywordInfo
- [x] SourceTabs 组件在每个源 Tab 旁显示命中词小标签
- [x] 单源模式结果统计行显示搜过的词标签（灰色=无结果，蓝色=命中）
- [ ] "全部"模式下，在源状态标签中也显示各源的命中词（待后续优化）

---

## 六、审查发现的问题 & 待决策项

### P0：设计需补充

1. **回退链并发模型**：SSE 流用 ThreadPoolExecutor 并行搜索，回退意味着某个源要等第一轮结果再决定是否重搜。
   - 决策：回退在同一个 future 内部同步完成（即 `_search_direct` 函数内部循环尝试多个词）
   - 影响：该源的 future 耗时会翻倍（最多 3 轮），但不阻塞其他源
   - 超时兜底：单源总超时不变（现有 20s），回退轮次共享这个超时

2. **jpName 数据来源**：当前前端没有 jpName 字段，后端也没接收。
   - 决策：本 TODO 不负责 jpName 的获取（属于 L1 业务接入），但预留参数位
   - 前端 SearchModalProps 新增 `jpName?: string`
   - 后端 SSE 端点新增 `jp_name` 参数
   - jpName 为空时，Nyaa/蜜柑回退到 enName（已在映射表中体现）

3. **单源搜索端点的响应格式**：
   - 决策：单源端点返回普通 JSON（不走 SSE），因为只有一个源，不需要流式推送
   - 回退时前端显示 loading 状态，后端同步完成所有回退轮次后一次性返回
   - 响应包含 `search_keywords` 和 `hit_keyword` 字段

### P1：数据流需补齐

4. **网盘搜索端点扩展**：`/search/pan` 需新增 `cn_name` / `en_name` 参数，后端按"中文优先"规则选词
5. **季号参数传递**：SSE 端点新增 `season_number` 参数，后端为中文源拼"第N季"、英文源拼"S0N"
6. **搜索词分发职责归属**：
   - "全部"模式：后端负责按源分发搜索词（前端只传 cn/en/jp，不管分发逻辑）
   - 单源模式：前端负责填入搜索词（用户可修改），后端直接用传入的词搜
   - 前端 searchTags 保留但定位改变：从"搜索词候选"变为"Tab 切换时的默认词来源"

### P2：实现细节

7. **网盘源列表**：sites/slowread/wnsearch 默认关闭，Tab 中只显示已启用的源
8. **前端状态复杂度**：每个 Tab 独立状态（keyword + results + searchedKeywords），用 `Record<string, SourceTabState>` 管理，注意内存和渲染性能


---

## 七、边界情况

| 情况 | 处理 |
|---|---|
| cnName 和 enName 相同 | 只用一个词，不重复搜，回退链跳过重复词 |
| jpName 为空 | Nyaa/蜜柑回退到 enName |
| 所有名称都为空 | 用用户输入的 query 原文 |
| 回退链所有词都 0 结果 | 显示"未搜到资源"，标签显示所有搜过的词 |
| 用户在单源 Tab 手动改词 | 不触发自动回退（尊重用户意图） |
| 季号/集号拼接 | 只在"全部"模式和自动填入时拼接，用户手动输入不自动加 |
| 回退链中某个词和上一个词相同 | 跳过，不重复搜（如 cnName==enName 时） |
| 单源回退超时 | 共享 20s 总超时，回退轮次用完时间就停止 |
| 源被用户关闭 | "全部"模式下跳过该源，Tab 列表中仍显示但标记为关闭 |
