# napics-mcp

napics 的 MCP server（stdio transport）。把 napics 的「搜片 → 创建下载 → 后处理」
和 qBittorrent 的「监控进度 → 删种」暴露成 MCP 工具，供上层 agent
（hermes / codex / kiro）调用。

本层**只做转发与协议转换**：不做自然语言理解、不做业务判断、不做筛选。
「4k 且 <50g」这类筛选由上层 agent 拿到 `napics_search` 的 results 后自己做。

## 架构（方案 A）

```
上层 agent (hermes/codex/kiro)
   │  MCP 协议 (stdio)
   ▼
napics-mcp  ← 本工程
   ├── 搜片 / 创建下载 / 后处理 ──HTTP──▶ napics Agent API (:8001)
   └── 查进度 / 删种           ──HTTP──▶ qBittorrent Web API (:8080)  直连
```

MCP 连**两个后端**：napics（搜索+创建下载+整理）与 qB（监控+删种）。
它与上层 agent **同机**，用 stdio 拉起，不给 NAS 单开 HTTP MCP 端口。

## 工具

| 工具 | 作用 |
|---|---|
| `napics_health()` | 探活：napics + qB 可达性 |
| `napics_search(query, media_type, title, year, keywords, season, limit)` | 搜片，返回全量候选（含 size_gb/resolution/download_url） |
| `napics_download(download_url, media_name, idempotency_key, save_path)` | 创建下载，返回 task_id + qb_hash。同 idempotency_key 不重复下载 |
| `napics_download_status(qb_hash)` | 查进度（直连 qB），统一状态枚举 |
| `napics_cancel_download(qb_hash, delete_files)` | 删种（直连 qB） |
| `napics_process(task_id \| path, media_name)` | 下载完成后刮削+整理归位。未配 TMDB 时返回 `partial` |

统一状态枚举：`queued / downloading / stalled / paused / completed / processing /
processed / partial / failed / cancelled / unknown`。上层永远看不到 qB 原始 state。

失败返回统一错误结构，绝不抛裸异常：
```json
{"error": {"code": "NAPICS_UNAVAILABLE", "message": "...", "retryable": true}}
```

## 配置（全走环境变量）

MCP **不读** napics 的 `config.json`（明文凭据），自己一套配置：

| 变量 | 默认 | 说明 |
|---|---|---|
| `NAPICS_API_BASE` | `http://127.0.0.1:8001` | napics 后端。上层跑本地 PC 时填 NAS 局域网 IP |
| `NAPICS_AGENT_TOKEN` | 空 | napics 设了 `agent_api_token` 时必填，走 X-Agent-Token |
| `QB_URL` | `http://127.0.0.1:8080` | qBittorrent Web UI |
| `QB_USERNAME` | `admin` | |
| `QB_PASSWORD` | 空 | qB 密码 |
| `MCP_HTTP_TIMEOUT` | `15` | HTTP 超时（秒） |

## 安装 / 运行

```bash
cd napics-mcp
pip install -r requirements.txt          # mcp<2 (FastMCP), httpx, pydantic
python server.py                          # stdio，一般由上层 agent 作为子进程拉起
```

## 在上层 agent 里注册

以 Claude Desktop / codex 风格的 `mcpServers` 配置为例（各家 key 名略有出入，
但都是「命令 + 参数 + 环境变量」三件套）：

```json
{
  "mcpServers": {
    "napics": {
      "command": "python",
      "args": ["C:/Users/shenq/napics/napics-mcp/server.py"],
      "env": {
        "NAPICS_API_BASE": "http://192.168.100.111:8001",
        "NAPICS_AGENT_TOKEN": "<napics config 里设的 agent_api_token>",
        "QB_URL": "http://192.168.100.111:8080",
        "QB_USERNAME": "admin",
        "QB_PASSWORD": "<qB 密码>"
      }
    }
  }
}
```

- 上层 agent 跑在 **本地 PC**：`NAPICS_API_BASE`/`QB_URL` 填 NAS 的局域网 IP。
- 上层 agent 跑在 **NAS 本机**：填 `127.0.0.1`。

## 典型调用链（上层 agent 视角）

```
napics_search("Titanic 1997", media_type="movie")
  → 候选列表（含 size_gb/resolution/download_url）
  → 上层自己筛出 resolution=2160p 且 size_gb<50 的一条
napics_download(download_url, "泰坦尼克号", idempotency_key=hash(title+year+url))
  → {task_id, qb_hash, status}
轮询 napics_download_status(qb_hash) 直到 status=="completed"
napics_process(task_id=...)
  → {status, library_path, files[]}   # status 可能是 partial（未配 TMDB）
```

## 测试

```bash
cd napics-mcp
python -m pytest tests -q
```

全部用 mock（httpx MockTransport + 注入 fake client），不连真实 napics / qB。
端到端（连真 napics+qB）见 `docs/napics-mcp-server-todo.md` §7。

## 依赖 napics 侧的端点（对话 B 已落地）

- `GET  /api/agent/search` — 展平的 Resource DTO
- `POST /download-manager/submit` — 带 Idempotency-Key
- `POST /api/agent/process` — 无状态刮削整理
- `GET  /api/agent/health`
