---
name: ai-business-scenes
description: >
  AI 业务场景编排技能：三个一期场景（文件名解析/刮削候选匹配/媒体库诊断）的接入规范、prompt 设计、降级策略。
  Use when modifying AI scene behavior, tuning prompts, adding new scenes,
  debugging AI output quality, or adjusting fallback logic.
  Depends on ai-client-infra (AIClient/chat_json/schema validation).
  Do NOT modify ai_client.py internals from here — that's ai-client-infra's scope.
---

# AI 业务场景编排

> 三个一期场景的完整规范：接入点、数据流、prompt 设计、降级策略、可见性标记。
> 所有场景遵循"AI 是增强不是依赖"原则——关闭或失败时静默降级，不影响主流程。

## 总体架构

```
业务流程（整理/刮削/诊断）
  → 检查 client.is_feature_enabled("scene_name")
    → False → 走非 AI 路径（现有逻辑）
    → True  → ai_prompts.prompt_xxx() → messages
              → client.chat_json(messages, schema=XXX_SCHEMA)
                → 成功 → 用 AI 结果继续，标记 ai_parsed/ai_selected
                → 失败(None) → 走非 AI 路径
```

## 场景 1：文件名智能解析

### 接入点
整理流水线 Step 3，正则提取集号/片名失败时的 fallback。

### 数据流
```
文件名 → 正则提取 → 成功 → 正常流程
                   → 失败 → is_feature_enabled("extract_episode")?
                             → No  → 跳过该文件
                             → Yes → ai_extract_episode(filename)
                                     → 成功 → 用 AI 结果，标记 ai_parsed=true
                                     → 失败 → 跳过该文件
```

### 函数签名
```python
# 单文件
ai_extract_episode(filename: str) -> Optional[dict]
# 返回: {"clean_name", "year", "season", "episode", "absolute_episode", "ai_parsed": True}

# 批量（一次最多 10 个，超过分批并发 max_workers=3）
ai_extract_episode_batch(filenames: List[str]) -> List[Optional[dict]]
# 批量失败时自动 fallback 到逐个解析
```

### Prompt 设计要点
- system: "你是一个视频文件名解析器。只返回合法的 JSON 对象，不要任何解释。"
- 核心约束："如果无法判断，对应字段必须填 null，绝不猜测"
- clean_title 要求去掉字幕组、编码、分辨率等标签
- 批量 prompt 用 index 映射回原始位置

### Schema
```python
EXTRACT_EPISODE_SCHEMA = {
    "clean_title": {"type": str, "required": True},
    "year": {"type": str, "required": False},
    "season": {"type": int, "required": False},
    "episode": {"type": int, "required": False},
    "absolute_episode": {"type": int, "required": False},
}
```

### 降级策略
| 情况 | 行为 |
|------|------|
| AI 关闭 | 直接返回 None，跳过该文件 |
| API 超时(20s) | 返回 None，跳过该文件 |
| JSON 解析失败 | 返回 None，跳过该文件 |
| clean_title 太短(<2字符) | 返回 None（_normalize_extract_result 兜底） |
| 批量调用失败 | 自动 fallback 到逐个调用 |

### 实测表现（豆包 lite）
- 纯乱码文件名 → 正确返回 None
- 中文电影（让子弹飞.2010.BluRay.1080p.mkv）→ 正确提取名称+年份，season/episode=null
- 日文动画绝对集数（Bocchi the Rock 07）→ 正确识别 absolute_episode=7
- 极简文件名（S01E01.mkv）→ 返回 None（clean_title 为空）
- 中英混合（权力的游戏.Game.of.Thrones.S08E06）→ 正确解析 S8E6

## 场景 2：刮削候选智能匹配

### 接入点
批量刮削（`/scrape/batch`）时，TMDB 返回多个候选的自动选择。单个刮削仍走手动选择。

### 数据流
```
TMDB 搜索 → 1 个候选 → 直接用（不调 AI）
           → 0 个候选 → 跳过（不调 AI）
           → 多个候选 → is_feature_enabled("scrape_candidate")?
                         → No  → 取第一个（现有逻辑）
                         → Yes → ai_select_scrape_candidate(folder, files, candidates)
                                 → confidence=high/medium → 用 AI 选择
                                 → confidence=low → 标记"需人工确认"
                                 → index=-1 → 跳过（所有候选都不匹配）
                                 → 失败(None) → 取第一个
```

### 函数签名
```python
ai_select_scrape_candidate(
    folder_name: str,
    file_list: List[str],
    candidates: List[dict],
) -> Optional[dict]
# 返回: {"selected_index", "confidence", "reason", "ai_selected": True}
# 候选 <= 1 时直接返回 None（不调 AI）
```

### Prompt 设计要点
- 传入文件夹名 + 文件列表（最多 15 个）提供上下文
- 候选列表最多 10 个，只传 title/original_title/year/overview(前100字)/media_type
- confidence 三档：high（标题+年份吻合）、medium（有歧义）、low（不确定）
- 允许返回 selected_index=-1 表示"所有候选都不匹配"

### Schema
```python
SELECT_CANDIDATE_SCHEMA = {
    "selected_index": {"type": int, "required": True},
    "confidence": {"type": str, "required": True},
    "reason": {"type": str, "required": True},
}
```

### 降级策略
| 情况 | 行为 |
|------|------|
| AI 关闭 | 返回 None，走现有逻辑（取第一个） |
| 候选 <= 1 | 直接返回 None，不调 AI |
| API 超时(20s) | 返回 None，取第一个 |
| index 越界 | 返回 None，取第一个 |
| confidence=low | 返回结果但标记需人工确认 |

### 实测表现（豆包 lite）
- 新世纪福音战士（TV版 vs 电影 vs 新剧场版）→ 正确选 TV 版，confidence=high
- 蝙蝠侠（1989 vs 2022，文件名含 2022）→ 正确选 2022 版
- 完全不匹配的候选 → index=-1，confidence=low

## 场景 3：媒体库健康诊断

### 接入点
独立端点 `POST /ai/diagnosis`，用户在设置页或诊断面板主动触发。

### 数据流
```
用户点击"AI 诊断"
  → ai_library_diagnosis()
    → _collect_library_stats(library) → 统计数据（不含隐私）
    → _collect_library_issues(library) → 问题列表（只传文件名，不传路径）
    → prompt_library_diagnosis(stats, issues) → messages
    → client.chat_json(messages, schema=DIAGNOSIS_SCHEMA, timeout=60)
    → 返回诊断报告
```

### 函数签名
```python
ai_library_diagnosis() -> Optional[dict]
# 返回: {"health_score": int, "priorities": [...], "summary": str}
```

### 统计数据收集（_collect_library_stats）
- total_videos：总视频数
- scrape_coverage：刮削覆盖率（has_nfo 计数/百分比）
- poster_coverage：海报覆盖率
- resolution_distribution：4K/1080p/720p/SD/未知 分布
- codec_distribution：编码分布

### 问题列表收集（_collect_library_issues）
- missing_nfo：缺失 NFO（count + 5 个文件名示例）
- low_resolution：低分辨率
- missing_poster：缺失海报
- low_quality_score：质量分过低（<20）

### Schema
```python
DIAGNOSIS_SCHEMA = {
    "health_score": {"type": int, "required": True},
    "priorities": {"type": list, "required": True},
    "summary": {"type": str, "required": True},
}
```

### Prompt 设计要点
- 紧凑格式（不用 indent=2），减少 token
- priorities 最多 5 条，按严重程度排序
- action 可选值：batch_scrape / batch_upgrade / organize / cleanup / manual
- summary 控制在 100 字以内
- temperature=0（确定性输出）

### 降级策略
| 情况 | 行为 |
|------|------|
| AI 关闭 | 返回 None，前端提示"AI 诊断未启用" |
| 媒体库为空 | 直接返回默认结果（health_score=0，"媒体库为空"） |
| API 超时(60s) | 返回 None，前端提示"诊断超时" |

### 隐私保护
- 不传完整文件路径，只传文件名
- 不传账号、密钥、内部 URL
- 统计数据只有数字和分布，无个人信息

### 实测表现（豆包 lite）
- 3302 条媒体库 → health_score=60，3 条优先建议（缺海报/低分辨率/缺NFO），耗时 31-36s

## 可见性标记规范

所有 AI 参与的结果必须有标记，让用户知道哪些是 AI 辅助的：

| 场景 | 后端标记字段 | 前端展示 |
|------|-------------|----------|
| 文件名解析 | `ai_parsed: true` | 整理预览/结果页显示 🤖 |
| 候选匹配 | `ai_selected: true` + `confidence` | 批量刮削结果显示 🤖 + 置信度色标 |
| 诊断 | 整个结果都是 AI 生成 | 诊断面板标题带 🤖 |

## Prompt 调优指南

1. system 角色固定为"精确的 JSON 生成器"，减少废话
2. 用户消息中明确"只返回 JSON，不要任何解释"
3. 返回格式用内联示例而非多行模板（减少 token）
4. 约束条件用"规则"列表，每条一行
5. temperature=0 用于需要确定性的场景（解析、匹配），0.3 用于需要创造性的场景（推荐）
6. 调优后必须跑一轮真实 API 测试验证
