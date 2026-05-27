---
name: ai-client-infra
description: >
  AI 客户端基础设施技能：统一封装 OpenAI 兼容 API 调用，提供 chat/chat_json/JSON提取/schema校验/调用计量。
  Use when adding new AI scenes, modifying AI client behavior, debugging API call failures,
  or adjusting timeout/retry/schema validation logic.
  This is the foundation layer — all AI business scenes depend on it.
  Do NOT put business logic (prompt templates, scene-specific orchestration) here.
---

# AI 客户端基础设施

> 统一封装 OpenAI 兼容 API 调用，支持火山引擎豆包 / DeepSeek / 任意兼容服务。
> 所有 AI 业务场景通过此层调用 LLM，不直接发 HTTP 请求。

## 架构

```
config.json
  ├── openai_api_key / openai_base_url / openai_model  — 凭据
  ├── ai_enabled                                        — 全局总开关
  └── ai_features.{scene_name}                          — 场景级开关
        ↓
ai_client.py
  ├── AIClient(config)          — 无状态客户端，每次从 config 构造
  │     ├── .enabled             — master ON + 凭据完整
  │     ├── .is_feature_enabled(name) — master + 场景 + 凭据 三重判断
  │     ├── .chat(messages, ...) → str | None
  │     └── .chat_json(messages, schema=...) → dict | None
  ├── _extract_json(text)       — 从 AI 响应提取 JSON（兼容多种格式）
  ├── _validate_schema(data, schema) — 轻量字段+类型校验
  ├── get_usage_stats()         — 场景级调用统计
  └── get_ai_client()           — 从 shared.config_m 构造实例
        ↓
ai_prompts.py                   — prompt 模板集中管理（业务层，不在此 skill 范围）
ai_organizer.py                 — 业务编排（不在此 skill 范围）
```

## 核心设计决策

| 决策 | 理由 |
|------|------|
| 不缓存客户端实例 | 用户可能随时在设置页改配置，每次调用从 config 构造保证最新 |
| 不引入 openai SDK | 项目一贯用 requests 直接调 HTTP，减少依赖 |
| 异常内部 catch | 对外只返回 None，调用方不需要 try-except |
| _extract_json 独立函数 | 不同模型输出格式差异大，需要持续调优 |
| schema 校验可选 | chat_json 的 schema 参数可选，简单场景不需要 |
| 计量用内存计数器 | 重启清零，够用且简单，后续需要再加持久化 |

## _extract_json 兼容策略

按优先级尝试：
1. 直接 `json.loads(text)` — 模型直接返回 JSON（若结果是 list，自动包装为 `{"items": list}`）
2. 正则提取 ` ```json ... ``` ` 或 ` ``` ... ``` ` 中的 `{...}` 对象 — markdown 代码块包裹
3. 正则提取 ` ```json ... ``` ` 或 ` ``` ... ``` ` 中的 `[...]` 数组 — 代码块包裹数组（自动包装为 `{"items": list}`）
4. 找第一个 `{` 到最后一个 `}` — 前后有废话

已知限制：多个独立 JSON 对象（`{"a":1} 然后 {"b":2}`）会提取失败，但实际 AI 响应不会出现此场景。

## _validate_schema 格式

```python
schema = {
    "field_name": {"type": str, "required": True},   # 必填 + 类型校验
    "optional_field": {"type": int, "required": False}, # 可选，null 合法
    "any_type": {"type": None, "required": True},     # 必填但不校验类型
}
```

- 必填字段缺失 → 校验失败
- 非必填字段缺失或为 null → 通过
- 类型不匹配 → 校验失败

## 调用计量

```python
_usage_stats = {
    "extract_episode": {"calls": 3, "tokens": 1500, "errors": 0},
    "scrape_candidate": {"calls": 1, "tokens": 662, "errors": 0},
    ...
}
```

- 每次 chat/chat_json 自动记录
- scene 参数标识场景（必传）
- token 从响应的 usage.total_tokens 读取（部分模型不返回则为 0）
- 前端通过 `GET /ai/status` 读取展示

## 服务商差异

| 服务商 | base_url | model 字段 | 注意事项 |
|--------|----------|------------|----------|
| 豆包 | `https://ark.cn-beijing.volces.com/api/v3` | 推理接入点 ID（ep-xxx） | 需先在火山引擎控制台创建接入点 |
| DeepSeek | `https://api.deepseek.com` | 模型名（deepseek-chat） | 直接填模型名 |
| 自定义 | 用户填写 | 用户填写 | 必须兼容 /chat/completions 端点 |

## 超时基准（豆包 doubao-seed-2-0-lite-260215）

| 场景 | 超时设置 | 实测耗时 | 说明 |
|------|----------|----------|------|
| 文件名解析 | 20s | 5-15s | 长文件名偶发接近 15s |
| 候选匹配 | 20s | 5-13s | 候选数量影响 |
| 媒体库诊断 | 60s | 31-36s | 输出结构复杂，生成慢 |
| 测试连接 | 10s | 5-10s | 极简 prompt |

## 新增 AI 场景的接入步骤

1. `ai_prompts.py`：新增 `prompt_xxx()` 函数 + `XXX_SCHEMA` 字典
2. `ai_organizer.py`：新增业务函数，调用 `client.chat_json(messages, schema=XXX_SCHEMA, scene="xxx")`
3. `config_manager.py`：`AIFeaturesConfig` 加字段（默认 False）
4. `routes/tools.py` 或对应路由：加端点或在现有流程中加 AI 分支
5. 前端 `SettingsModal`：`AI_FEATURE_LIST` 加一行
6. 测试：mock 测试 + 真实 API 测试各一轮
