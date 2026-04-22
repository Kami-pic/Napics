[当前]

# AI 能力集成设计方案

> 为 NAS 影视媒体库管理工具引入 LLM 能力，提升整理、刮削、搜索等核心流程的智能化水平。
> 最后更新：2026-04-22（合并评审意见 + GPT 反馈后 v3）

## 一、背景与目标

### 现状
- `ai_organizer.py` 有两个函数（整理建议 + 文件名提取），直接调 OpenAI 兼容 API
- `config.json` 已有 `openai_api_key` / `openai_base_url` / `openai_model` 三个字段（均为空）
- 前端 `SmartManager.tsx` 有 AI 建议 UI 壳，但后端路由未完整对接
- 整体处于"预留了接口但没实际运行"的状态

### 目标
- 建立统一的 AI 客户端层，支持火山引擎豆包 / DeepSeek / 任意 OpenAI 兼容服务
- 分场景接入 AI 能力，每个场景独立可开关
- AI 始终作为"增强辅助"，关闭或失败时不影响现有功能

## 二、AI 服务商适配

### 目标服务商

| 服务商 | base_url | 模型示例 | 特点 |
|--------|----------|----------|------|
| 火山引擎豆包 | `https://ark.cn-beijing.volces.com/api/v3` | Doubao-pro-32k / Doubao-lite-32k | 国内直连、中文优化、需创建推理接入点(endpoint) |
| DeepSeek | `https://api.deepseek.com` | deepseek-chat / deepseek-reasoner | 性价比极高、OpenAI 完全兼容 |
| 其他兼容服务 | 用户自定义 | 任意 | 通过 base_url + model 自由配置 |

### 兼容性说明
- 三家都兼容 OpenAI `/v1/chat/completions` 格式
- 豆包的 model 字段填的是"推理接入点 ID"（如 `ep-20240xxx-xxxxx`），不是模型名
- DeepSeek 的 model 字段填模型名（如 `deepseek-chat`）
- 统一用 `requests` 直接调 HTTP，不引入 openai SDK（项目一贯风格，减少依赖）

## 三、架构设计

### 3.1 新增文件

```
backend/
├── ai_client.py          # [新建] 统一 AI 客户端（替代 ai_organizer.py 的 HTTP 调用部分）
├── ai_prompts.py         # [新建] 所有 prompt 模板集中管理
├── ai_organizer.py       # [重构] 只保留业务编排，HTTP 调用下沉到 ai_client.py
└── routes/tools.py       # [修改] AI 相关路由补全
```

### 3.2 ai_client.py — 统一客户端

```python
"""统一 AI 客户端，封装 OpenAI 兼容 API 调用。"""

class AIClient:
    """无状态客户端，每次从 config 读取最新配置。"""

    def __init__(self, config: dict):
        self.api_key = config.get("openai_api_key", "")
        self.base_url = config.get("openai_base_url", "").rstrip("/")
        self.model = config.get("openai_model", "")
        self.master_enabled = config.get("ai_enabled", False)
        self.features = config.get("ai_features", {})
        self.enabled = bool(self.master_enabled and self.api_key and self.base_url and self.model)

    def is_feature_enabled(self, feature_name: str) -> bool:
        """检查某个 AI 场景是否生效：master switch ON + 场景开关 ON + 凭据完整"""
        return self.enabled and self.features.get(feature_name, False)

    def chat(self, messages: list[dict], temperature=0, timeout=20) -> str | None:
        """发送 chat completion 请求，返回文本内容。失败返回 None。"""
        ...

    def chat_json(self, messages: list[dict], temperature=0, timeout=20,
                  schema: dict | None = None) -> dict | None:
        """发送请求并解析 JSON 响应。失败返回 None。
        1. 内部调用 _extract_json() 兼容各种模型的输出格式差异
        2. 如果传入 schema，用 _validate_schema() 校验必填字段和类型
           校验失败视为调用失败，返回 None 并记日志"""
        ...

def _extract_json(text: str) -> dict | None:
    """从 AI 响应文本中提取 JSON。
    兼容：直接 JSON / markdown 代码块包裹 / 前后有废话等情况。
    独立函数，方便后续针对不同模型的输出格式持续调优。"""
    ...

def _validate_schema(data: dict, schema: dict) -> bool:
    """轻量 schema 校验：检查必填字段是否存在、值类型是否匹配。
    不引入 jsonschema 库，手写简单校验即可。
    schema 格式示例：{"clean_title": {"type": str, "required": True}, "year": {"type": str, "required": False}}"""
    ...

def get_ai_client() -> AIClient:
    """从 shared.config_m 获取配置，构造客户端实例。"""
    ...
```

核心设计决策：
- 不缓存客户端实例（配置可能随时改），每次调用从 config 构造
- `_extract_json` 独立为工具函数，不同模型返回格式差异大，需要持续调优
- 所有异常内部 catch，对外只返回 None（调用方不需要处理异常）
- 日志记录每次调用的耗时和 token 用量（如果响应中有 usage 字段）

### 3.3 AI 调用计量

`ai_client.py` 内置轻量计量机制（内存计数器，重启清零）：

```python
# 每个场景独立统计
_usage_stats = {
    "extract_episode": {"calls": 0, "tokens": 0, "errors": 0},
    "scrape_candidate": {"calls": 0, "tokens": 0, "errors": 0},
    ...
}

def get_usage_stats() -> dict:
    """返回各场景的调用统计，供 /ai/status 端点使用。"""
    ...
```

- 前端设置页 AI 区域底部展示"本次运行 AI 用量"（调用次数 + token 消耗）
- 不做持久化（重启清零），够用且简单
- 后续如果需要月度统计，再加 JSON 持久化

### 3.4 ai_prompts.py — Prompt 模板集中管理

```python
"""所有 AI prompt 模板。集中管理便于调优和版本控制。"""

# 每个场景一个函数，返回 messages 列表

def prompt_extract_episode(filename: str) -> list[dict]:
    """场景1：从乱码文件名提取结构化信息"""
    ...

def prompt_select_scrape_candidate(folder_name: str, file_list: list[str],
                                     candidates: list[dict]) -> list[dict]:
    """场景2：从刮削候选中选择最佳匹配"""
    ...

def prompt_library_diagnosis(stats: dict, issues: list[dict]) -> list[dict]:
    """场景3：媒体库健康诊断"""
    ...

def prompt_search_recommend(query: str, results: list[dict],
                             local_info: dict) -> list[dict]:
    """场景4：搜索结果智能推荐"""
    ...

def prompt_natural_language_search(user_input: str) -> list[dict]:
    """场景5：自然语言转结构化搜索"""
    ...

def prompt_subscribe_recommend(library_profile: dict,
                                 trending: list[dict]) -> list[dict]:
    """场景6：订阅智能推荐"""
    ...
```

### 3.5 config.json 扩展

现有字段保持不变（向后兼容），新增 AI 场景开关：

```json
{
  "openai_api_key": "sk-xxx 或火山引擎 API Key",
  "openai_base_url": "https://ark.cn-beijing.volces.com/api/v3",
  "openai_model": "ep-20240xxx-xxxxx",
  "ai_enabled": true,
  "ai_features": {
    "extract_episode": true,
    "scrape_candidate": true,
    "library_diagnosis": true,
    "search_recommend": false,
    "natural_search": false,
    "subscribe_recommend": false
  }
}
```

- `ai_enabled`：全局总开关（master switch），false 时所有 AI 场景一键关闭，不论各场景开关状态
- `ai_features` 不存在时默认全部关闭（兼容旧配置）
- 场景生效条件：`ai_enabled=true` AND `ai_features.xxx=true` AND API Key/URL/Model 均非空
- 一期场景默认 true（配置了 API Key 即生效），二期场景默认 false

## 四、AI 场景详细设计

### 场景 1：乱码文件名智能解析（一期）

**接入点**：整理流水线 Step 3，正则提取失败时的 fallback

**流程**：
```
文件名 → 正则提取 → 成功 → 正常流程
                   → 失败 → AI 开启？ → 否 → 跳过该文件
                                      → 是 → ai_extract_episode(filename)
                                              → 成功 → 用 AI 结果继续
                                              → 失败 → 跳过该文件
```

**输入**：单个文件名字符串
**输出**：`{"clean_title": str, "year": str|None, "season": int|None, "episode": int|None, "absolute_episode": int|None}`

**约束**：
- AI 只做"提取"，不做"猜测"。prompt 明确要求无法判断的字段填 null
- 单次调用，不重试（整理流水线对延迟敏感）
- timeout 15 秒，超时视为失败
- 现有 `ai_organizer.ai_extract_episode` 逻辑基本可用，重构为调用 ai_client

**批量优化**：
- 整理流水线中如果有多个文件名需要 AI 解析，使用**批量 prompt**（一次传最多 10 个文件名，让 AI 批量返回数组）
- 超过 10 个时分批，批次间用 `ThreadPoolExecutor(max_workers=3)` 并发
- 单个文件的 fallback 场景仍用单次调用

**AI 可见性标记**：
- 整理结果中，AI 解析成功的文件标记 `ai_parsed: true`
- 前端整理预览/结果页对这些项显示 🤖 小标签，让用户知道"这个是 AI 帮你搞定的"

**改动范围**：
- `ai_organizer.py`：重构 `ai_extract_episode`，改用 `ai_client.chat_json`；新增 `ai_extract_episode_batch`
- `scraper.py`：Step 3 的集号提取失败分支，加 AI fallback 调用
- 前端整理预览组件：识别 `ai_parsed` 字段，显示 🤖 标记

### 场景 2：刮削候选智能匹配（一期）

**接入点**：批量刮削时，TMDB 返回多个候选的自动选择

**流程**：
```
TMDB 搜索 → 1 个候选 → 直接用
           → 0 个候选 → 跳过
           → 多个候选 → AI 开启？ → 否 → 取第一个（现有逻辑）
                                   → 是 → AI 选择最佳候选
                                           → 返回候选 index
```

**输入**：
- 文件夹名 + 文件列表（提供上下文）
- TMDB 候选列表（id, title, original_title, year, overview 前100字）

**输出**：`{"selected_index": int, "confidence": "high"|"medium"|"low", "reason": str}`

**约束**：
- 候选列表最多传 10 个（节省 token）
- confidence=low 时不自动选择，标记为"需人工确认"
- 仅在批量刮削（`/scrape/batch`）中启用，单个刮削仍走手动选择

**AI 可见性标记**：
- 批量刮削结果中，AI 选择的项标记 `ai_selected: true` + `ai_confidence` + `ai_reason`
- 前端批量刮削结果展示中，显示 🤖 标记和置信度色标（high=绿/medium=黄/low=红）

**改动范围**：
- `ai_prompts.py`：新增 `prompt_select_scrape_candidate`
- `scraper.py`：批量刮削的候选选择逻辑加 AI 分支
- 前端批量刮削结果组件：标记 AI 选择项和置信度

### 场景 3：媒体库健康诊断（一期）

> 评审调整：从原二期提前到一期。实现简单、用户感知强、token 消耗低，适合作为"AI 配置成功后的首次体验"。

**接入点**：现有 `/analysis/report` 的增强版，新增独立端点

**流程**：
```
用户点击"AI 诊断" → 收集媒体库统计信息 + 现有规则检查结果
                   → AI 分析 → 返回优先级排序的建议列表
                   → 前端展示诊断报告卡片
```

**首次体验引导**：
- 设置页测试连接成功后，弹出提示"要不要试试 AI 诊断你的媒体库？"
- 点击后直接跳转到诊断面板，让用户立刻感受到 AI 的价值

**输入**：
- 媒体库统计：总数、分辨率分布、编码分布、刮削覆盖率、目录结构问题数
- 规则检查结果：缺失 NFO 列表、命名不规范列表、孤立文件列表（各取 top 10 示例）

**输出**：
```json
{
  "health_score": 85,
  "priorities": [
    {"category": "刮削缺失", "severity": "high", "count": 23, "suggestion": "...", "action": "batch_scrape"},
    {"category": "低分辨率", "severity": "medium", "count": 15, "suggestion": "...", "action": "batch_upgrade"}
  ],
  "summary": "一段话总结"
}
```

**约束**：
- 不传具体文件路径给 AI（隐私 + token 节省），只传统计数据和示例文件名
- 诊断结果缓存 1 小时（媒体库短时间内不会大变）
- `action` 字段对应前端可执行的操作按钮

**改动范围**：
- `ai_prompts.py`：新增 `prompt_library_diagnosis`
- `routes/tools.py`：新增 `POST /ai/diagnosis` 端点
- 前端新增 AI 诊断面板组件（可嵌入 SmartManager 或独立页面）

### 场景 4：搜索结果智能推荐（二期）

> 评审调整：从原一期移到二期。高频调用 token 消耗大，现有 smart filter + 评分体系已提供不错的排序，边际价值相对低。SSE 流改动前后端联调复杂度高。
> 异步增强约束：AI 推荐必须异步执行，不阻塞搜索结果展示。搜索结果先出，AI 推荐后追加。

**接入点**：BT 搜索结果返回后，标记"AI 推荐"

**流程**：
```
搜索完成 → 结果列表 → AI 开启？ → 否 → 正常展示
                                 → 是 → 取 top 20 结果摘要 → AI 分析
                                         → 返回推荐 index 列表 + 理由
                                         → 前端标记 ⭐ AI 推荐
```

**输入**：
- 搜索关键词 + 用户媒体库中该影片的现有质量信息
- top 20 结果摘要（title, size, seeders, quality_score, match_score）

**输出**：`{"recommended": [{"index": int, "reason": str}], "summary": str}`

**约束**：
- 异步执行，不阻塞搜索结果展示（搜索结果先出，AI 推荐后追加）
- 前端用独立的 API 端点拉取推荐结果（或 SSE 追加事件）
- 每次搜索最多推荐 3 个
- 推荐理由简短（一句话），前端 tooltip 展示

**改动范围**：
- `ai_prompts.py`：新增 `prompt_search_recommend`
- `routes/search.py`：SSE 流新增 `ai_recommend` 事件类型
- `search_helpers.py`：新增 `get_ai_recommendation` 函数
- 前端 SearchModal：结果卡片增加 ⭐ 标记 + tooltip

### 场景 5：自然语言搜索（二期）

> 异步增强约束：AI 解析异步执行，解析期间前端显示加载态，解析失败时 fallback 到原始文本直接搜索，不阻塞用户操作。

**接入点**：搜索框增加"智能搜索"模式

**流程**：
```
用户输入自然语言 → AI 解析 → 结构化搜索条件
                           → 调用豆瓣搜索 / TMDB discover
                           → 返回结果
```

**输入**：用户自然语言（如"去年的韩国犯罪片，宋康昊演的"）

**输出**：
```json
{
  "parsed": {
    "title_hint": "宋康昊",
    "year_range": [2025, 2025],
    "region": "韩国",
    "genre": "犯罪",
    "cast": ["宋康昊"]
  },
  "search_strategy": "douban_search",
  "search_query": "宋康昊 犯罪 2025"
}
```

**约束**：
- AI 只做"意图解析"，实际搜索仍走现有通道
- 解析失败时 fallback 到原始文本直接搜索
- 前端搜索框旁增加 🪄 按钮切换智能模式

**改动范围**：
- `ai_prompts.py`：新增 `prompt_natural_language_search`
- `routes/search.py` 或 `routes/discover.py`：新增 `POST /ai/parse-search` 端点
- 前端 SearchModal / DiscoverPage：增加智能搜索入口

### 场景 6：订阅智能推荐（二期）

> 异步增强约束：AI 推荐异步生成，发现页主内容（热榜/探索）正常加载，AI 推荐区域独立加载态，失败时该区域隐藏，不影响页面其他部分。

**接入点**：发现页新增"AI 为你推荐"区域

**流程**：
```
用户打开发现页 → 后台分析媒体库画像（类型/地区/年代偏好）
              → 结合当前热门数据 → AI 生成个性化推荐
              → 前端展示推荐卡片（带推荐理由）
```

**输入**：
- 媒体库画像：类型分布 top5、地区分布 top5、平均评分、最近入库的 10 部
- 当前热门：豆瓣热榜 top 20 + TMDB trending top 20

**输出**：
```json
{
  "recommendations": [
    {"title": "...", "source": "douban_hot", "source_index": 3, "reason": "你喜欢犯罪片，这部韩国新片口碑不错"}
  ]
}
```

**约束**：
- 推荐结果缓存 24 小时
- 最多推荐 10 部
- AI 只从已有的热门列表中筛选推荐（不凭空生成片名，避免幻觉）
- 推荐理由必须关联到用户的观影偏好

**改动范围**：
- `ai_prompts.py`：新增 `prompt_subscribe_recommend`
- `discover_enrich.py`：新增媒体库画像分析函数
- `routes/discover.py`：新增 `GET /ai/recommend` 端点
- 前端发现页：新增 AI 推荐 tab 或区域

## 五、前端设置页 AI 配置

在现有设置页新增"AI 助手"配置区域：

```
┌─────────────────────────────────────────┐
│  🤖 AI 助手                     [总开关 ●]│
│                                          │
│  服务商预设：[豆包 ▾] [DeepSeek ▾] [自定义]│
│                                          │
│  API Key:    [sk-xxxxx____________]      │
│  Base URL:   [https://ark.cn-bei...]     │
│  模型/接入点: [ep-2024xxxx_______]        │
│                                          │
│  [测试连接]  ✅ 连接成功，模型响应正常      │
│  → 💡 试试 AI 诊断你的媒体库？            │
│                                          │
│  ── 功能开关 ──                           │
│  ☑ 文件名智能解析    整理时自动识别乱码文件名│
│  ☑ 刮削候选匹配      批量刮削时自动选择最佳  │
│  ☑ 媒体库诊断        AI 分析媒体库健康状况   │
│  ☐ 搜索结果推荐      标记最值得下载的资源    │
│  ☐ 自然语言搜索      用自然语言描述想找的片   │
│  ☐ 订阅推荐          根据观影偏好推荐新片    │
│                                          │
│  ── 本次运行用量 ──                       │
│  调用 12 次 · 消耗约 8,400 tokens          │
└─────────────────────────────────────────┘
```

- 顶部总开关（master switch）：关闭后整个 AI 区域灰显，所有场景一键停用
- 总开关关闭时场景开关状态保留但不生效，重新打开后恢复之前的配置

**服务商预设**：选择后自动填充 base_url，用户只需填 API Key 和模型名
- 豆包：`https://ark.cn-beijing.volces.com/api/v3`（附引导提示：需先在火山引擎控制台创建推理接入点，获取 ep-xxx 格式的接入点 ID）
- DeepSeek：`https://api.deepseek.com`
- 自定义：手动填写

**测试连接**：调用 `POST /ai/test` 端点，发送一个简单的 hello 请求验证配置是否正确。成功后引导用户体验 AI 诊断。

## 六、API 端点规划

```
# 一期
POST /ai/test                    — 测试 AI 连接
GET  /ai/status                  — 获取 AI 配置状态、各场景开关、调用统计
POST /ai/diagnosis               — 媒体库 AI 诊断

# 一期（集成到现有流程，无独立端点）
# - 文件名解析：集成到整理流水线内部
# - 刮削候选：集成到批量刮削内部

# 二期
POST /ai/parse-search            — 自然语言搜索解析
GET  /ai/recommend               — AI 个性化推荐
# - 搜索推荐：集成到 SSE 搜索流内部
```

## 七、实施计划

### 一期：核心能力层（预计 3-4 个工作日）

**范围**：基础设施 + 场景 1（文件名解析）+ 场景 2（刮削候选）+ 场景 3（媒体库诊断）+ 前端设置页

| 步骤 | 内容 | 验证 |
|------|------|------|
| 1 | 新建 `ai_client.py`，实现 `AIClient.chat` / `chat_json` / `_extract_json` / 计量 | 单元测试 mock HTTP |
| 2 | 新建 `ai_prompts.py`，实现场景 1/2/3 的 prompt | 人工审查 prompt 质量 |
| 3 | 重构 `ai_organizer.py`，改用 ai_client | 现有调用不受影响 |
| 4 | 场景 1 接入整理流水线（含批量 prompt + 并发） | 用 sandbox_real 中的乱码文件名测试 |
| 5 | 场景 2 接入批量刮削 | 用已知多候选的影片测试 |
| 6 | 场景 3 媒体库诊断端点 + 前端面板 | 诊断报告内容合理性 |
| 7 | 前端设置页 AI 配置区域（预设/测试/开关/用量） | 配置 → 测试连接 → 开关生效 |
| 8 | `config.json` 扩展 + 路由注册 + 前后端适配 | getDiagnostics + 构建 |

### 二期：智能体验层（预计 3-4 个工作日）

**范围**：场景 4（搜索推荐）+ 场景 5（自然语言搜索）+ 场景 6（订阅推荐）+ SmartManager 重构

| 步骤 | 内容 | 验证 |
|------|------|------|
| 1 | 场景 4 搜索推荐（SSE 集成） | 搜索后观察 AI 推荐事件 |
| 2 | 场景 5 自然语言搜索 | 多种自然语言输入测试 |
| 3 | 场景 6 订阅推荐 | 推荐结果与媒体库偏好相关性 |
| 4 | SmartManager 重构 | 整合新 AI 能力到智能管家面板 |

## 八、设计原则

1. **AI 是增强不是依赖**：所有 AI 场景都有非 AI 的 fallback 路径，关闭 AI 后系统功能完整
2. **最小 token 消耗**：只传必要信息给 AI，大列表截断，长文本摘要；批量场景用批量 prompt 减少调用次数
3. **失败静默**：AI 调用失败不弹错误，静默降级到非 AI 路径，只记日志
4. **prompt 集中管理**：所有 prompt 在 `ai_prompts.py` 一个文件，方便调优和版本对比
5. **不引入新依赖**：用 `requests` 直接调 HTTP，不引入 openai/langchain 等 SDK
6. **隐私保护**：不传完整文件路径给 AI，只传文件名和统计数据
7. **AI 可见性**：所有 AI 参与的操作在结果中标记（🤖），让用户知道哪些是 AI 帮忙的

## 九、风险与缓解

| 风险 | 缓解 |
|------|------|
| AI 幻觉（编造不存在的影片信息） | prompt 严格约束"只提取不猜测"，输出校验 |
| 响应延迟影响用户体验 | 异步调用 + 超时兜底（15-20s），搜索推荐不阻塞结果展示 |
| 批量场景串行延迟（50 个文件 × 15s） | 批量 prompt（一次传 10 个）+ ThreadPoolExecutor(max_workers=3) 并发 |
| token 费用失控 | 每个场景限制输入长度，内置调用计量，可按场景关闭 |
| 服务商 API 不稳定 | 内置重试（仅 1 次）+ 超时 + 静默降级 |
| 豆包接入点 ID 用户不会填 | 设置页豆包预设附图文引导，链接到火山引擎控制台 |
| 不同模型 JSON 输出格式差异 | `_extract_json` 独立函数，兼容多种格式，持续调优 |

## 十、评审记录

### 2026-04-22 内部评审（v1 → v2）

**主要调整**：
1. 场景优先级重排：场景 3（搜索推荐）移到二期，场景 4（媒体库诊断）提前到一期
2. 新增 AI 调用计量机制（内存计数器，前端展示用量）
3. 新增批量调用优化策略（批量 prompt + 并发）
4. `_extract_json` 从 `chat_json` 中独立为工具函数
5. 新增 AI 可见性标记设计（🤖 标签）
6. 设置页增加首次体验引导（测试连接成功 → 引导 AI 诊断）
7. 豆包预设增加接入点创建引导说明

### 2026-04-22 GPT 外部评审（v2 → v3）

**新增/强化**：
1. 新增全局 AI master switch（`ai_enabled` 字段），一键关闭全部 AI
2. `chat_json` 增加 schema 校验层（`_validate_schema`），不只做 JSON 提取
3. `AIClient` 新增 `is_feature_enabled(feature_name)` 方法，统一判断场景是否生效
4. 二期三个场景显式标注"异步增强约束"，明确不阻塞主流程
5. 前端设置页顶部增加总开关，关闭后整个 AI 区域灰显
