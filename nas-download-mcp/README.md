# nas-download-mcp

给 Hermes / DSH / Codex 等 AI agent 用的 **NAS 媒体下载编排 MCP**。上层编排层：接结构化下载意图 → 开关 NAS 上的 docker 容器（napics/prowlarr）省内存 → 搜片+创建下载（调 napics）→ qB 直连监控/测速/删种 → 下完推送 → 关容器。

自然语言理解归上层 agent；本 MCP 只吃结构化参数、做编排。

## 架构

```
Hermes / DSH / Codex
      │  Streamable HTTP MCP  (http://192.168.100.111:8787/mcp)
      ▼
nas-download-mcp  (NAS Docker 常驻; Task/SQLite/ServiceManager/probe/cleanup)
      ├── HTTP ──▶ napics /api/agent/*   搜片 / 创建下载 / 整理
      ├── HTTP ──▶ qB /api/v2/*          监控 / 测速探测 / 删种（上层直连）
      └── docker socket ──▶ start/stop kami-pic, prowlarr
```

原则：**Agent 做判断，本 MCP 做编排 + 容器 + qB 监控，napics 做搜索/创建下载/整理。**

## 工具

| 工具 | 作用 |
|---|---|
| `download_movie` | 创建下载任务，立刻返回 `task_id`（后台跑，不阻塞） |
| `get_download_task` | 查单任务状态/进度 |
| `list_download_tasks` | 列任务 |
| `cancel_download_task` | 取消 + 删种 + 关容器 |
| `get_system_status` | 容器/服务健康 + 活跃任务 |
| `cleanup_orphaned_tasks` | 清理 MCP 重启后的孤儿任务（启动自动跑一次） |

## 部署（NAS Docker）

```bash
cp .env.example .env
# 填 QB_PASSWORD（必填）、NAPICS_AGENT_TOKEN（若 napics 配了）、NOTIFY_CHANNEL（可选）
docker compose up -d
```

访问 `http://192.168.100.111:8787/mcp`。

依赖 docker socket（挂载在 compose 里）才能启停容器；白名单只允许 `kami-pic`/`prowlarr` 的 start/stop/inspect（见 `src/adapters/docker_adapter.py`），不暴露 exec/rm/run。

> ⚠️ `.env` 里 `QB_URL` 必须和 napics 里配的 qB 指向**同一个 qB 实例**——本 MCP 直连 qB 监控的种子，就是 napics 推进 qB 的那些。

## 在 Hermes 注册（Streamable HTTP MCP）

```json
{
  "mcpServers": {
    "nas-download": {
      "url": "http://192.168.100.111:8787/mcp",
      "transport": "streamable-http"
    }
  }
}
```

典型对话："帮我下载一部 4K、小于 50G 的《泰坦尼克号》" → agent 判定 `Titanic 1997` → 调 `download_movie(title="泰坦尼克号", queries=["Titanic 1997"], min_resolution="2160p", max_size_gb=50)` → 轮询 `get_download_task`。

## 本地开发

```bash
pip install -r requirements.txt
# 填好环境变量后
python src/server.py
```

## 与下层 napics-mcp 的关系

本 MCP 是**上层编排层**（有状态、常驻、管容器）。另有一个**下层 `napics-mcp`**（stdio、无状态，贴 napics 的搜/下/删种工具），是给 agent 直接用的另一个入口，与本 MCP 平行——本 MCP 直接 HTTP 调 napics `/api/agent/*`，不经过它。契约见 `../docs/nas-download-mcp-todo.md`。
