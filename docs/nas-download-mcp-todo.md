`[当前]`

# NAS Download MCP（上层编排 MCP）— 最终执行 TODO

> 本文件由用户的 `NAS_DOWNLOAD_MCP_SPEC.md` 改写而来，是**本对话唯一执行依据**。
> 与 `docs/napics-mcp-server-todo.md`（下层 napics-mcp，另一个对话在做）是**上下游两层关系，不是二选一**。

---

## 0. 边界（已与用户逐条定死，开工前必读）

**本对话只做上层 `nas-download-mcp`。** 下层 `napics-mcp` 和 napics backend 的改动归**另一个对话**，本文件只钉它们的**对接契约**，不实现。

- **上层职责**：接结构化下载意图 → 管容器生命周期（开关 kami-pic/prowlarr 省内存）→ 跑有状态 Task（SQLite 持久化 / 崩溃恢复）→ 搜片+创建下载（HTTP 调 napics agent 端点）→ **qB 监控/测速探测/删种（上层直连 qB）** → 下完推送 → cleanup 关容器。
- **qB 全归上层**：监控进度、测速探测淘汰、删种，全部上层直连 qB Web API。napics 不碰 qB 的这些动作（napics 只负责"把种子推进 qB 建任务"）。
- **napics 尽量少改**：上层能自己干的（qB 直连、probe）绝不去改 napics。上层只消费 napics 已有/在建的 `/api/agent/*` 三个端点。
- **测速探测：做**（batch 试速、下不动换下一批），归上层直连 qB 实现。
- **部署**：上层是 **Streamable HTTP 常驻服务**，NAS Docker 部署，监听 `0.0.0.0:8787`，Hermes/DSH/Codex 经 `http://192.168.100.111:8787/mcp` 共享调用。

### 为什么上层用 HTTP 常驻、下层用 stdio（部署形态不同是因为职责不同）
- 上层要**管容器 + 跑几小时的长任务**，必须常驻：agent 提交任务后可以断开，几小时后回来查进度。stdio MCP 被 agent 当子进程临时拉起、agent 关了就没了，扛不住长任务。
- 上层是**多 agent 共享的编排入口**（spec §4），HTTP 一个地址谁都能连；stdio 做不到共享。
- 下层 napics-mcp **无状态**（搜一下/建个下载就返回），同机 stdio 被谁需要谁拉起，合理。
- 上层→napics **直接 HTTP 调 `/api/agent/*`**，不经过下层 stdio MCP：让常驻 HTTP 服务再去当另一个 stdio 进程的客户端很别扭，HTTP→HTTP 最干净。下层 napics-mcp 是"给 agent 直接用的另一个入口"，与上层平行，不是上层下游。

### 最终架构
```
Hermes / DSH / Codex
      │  Streamable HTTP MCP  (http://192.168.100.111:8787/mcp)
      ▼
nas-download-mcp  (NAS Docker 常驻; Task/SQLite/ServiceManager/probe/cleanup/推送)
      │
      ├── HTTP ──▶ napics /api/agent/*   搜片 / 创建下载 / 整理     ← napics 侧最小改动（另一对话）
      ├── HTTP ──▶ qB /api/v2/*          监控 / 测速探测 / 删种      ← 上层自己直连
      └── docker socket ──▶ start/stop kami-pic, prowlarr          ← 省内存
```
> 核心原则：**Agent 做判断，上层 MCP 做编排 + 容器 + qB 监控，napics 做搜索/创建下载/整理，Prowlarr 做资源搜索，qB 做下载。**

---

## 1. NAS 环境（已核实）

```
NAS IP        192.168.100.111
napics        http://192.168.100.111:3032 (前端) / :8001 (后端 API)   docker: kami-pic
prowlarr      http://192.168.100.111:9696                              docker: prowlarr
qBittorrent   http://192.168.100.111:8085  飞牛 OS 官方应用            MCP 直连，不启停
```
> 注意：napics **后端 API 在 :8001**（:3032 是前端代理）。agent 端点路径是 `/api/agent/*`，
> 上层应直连后端 :8001，不要走前端 :3032 代理（省一跳、避开前端鉴权）。若 NAS 上后端只监听
> 127.0.0.1，则上层容器需与 napics 同 docker 网络或用 host 网络；部署时确认（§14）。

---

## 2. napics 侧对接契约（**归另一个对话实现**，本文件只钉死，上层按此假设已提供）

> ✅ 已核实：`backend/routes/agent.py` 里 `/api/agent/search`、`/api/agent/process`、`/api/agent/health`
> **另一个对话已经写好**。`/download-manager/submit` 也已支持 `idempotency_key`。上层直接依赖。

### 2.1 搜索 `GET /api/agent/search`（已存在）
入参 query string：`query`(必), `media_type`, `title`, `year`, `season`, `limit`。
返回：
```json
{ "query": "...", "total": 12, "results": [ Resource, ... ] }
Resource {
  title, source, indexer, download_url, size_gb, seeders, leechers,
  resolution, codec, release_group, has_chinese_sub, score
}
```
- `size_gb` 用来筛 `<50g`；`resolution`（如 "2160p"）用来筛 `4k`。**筛选由上层做**，napics 只返回全量+排序。
- 字段语义：`source`=片源类型（BluRay/WEB-DL/Remux…，来自 `quality.source`）；`indexer`=索引器/站点名。两者别混用——去重/黑名单应按 `indexer`（站点），不是 `source`。
- 未装搜索插件时返回 `{total:0, results:[], error:"no_source"}`——上层要识别并回 `NO_RESULTS`/`SOURCE_MISSING`。

### 2.2 创建下载 `POST /download-manager/submit`（已存在，带幂等）
入参 body：`{media_name, download_url, save_path, channel:"qb", idempotency_key, is_season_pack?, season_number?}`
或用 `Idempotency-Key` header（body 优先）。
返回：`{ "success": bool, "task": { ...DownloadTask } }`
- **上层拿 qb_hash 的字段 = `task.downloader_hash`**（qB torrent infohash，`DownloadTask` 里真实存在）。**可能为空**：napics `_push_to_qb` 拿 hash 靠"加种前后 hash 集合差集 + 轮询"，magnet 解 btih 更可靠（归下层改进）。**并发多种子（probe 一批 3 条同时 submit）最容易触发差集脏 → 空 hash**，上层必须处理，见 §6 回落。
- **空 hash 回落匹配**：上层用自己的 qB 直连 `torrents/info` 全量，按 `media_name` 双向包含匹配（参考 napics `download.py::sync_from_qb` 的 `name_lower in qb_name or qb_name in name_lower`）。⚠️ 整季/多结果易撞名，最好带 `save_path` 或 size 二次校验；匹配不到则该候选判 probe 失败，不计入测速。
- `task.id` = napics 8 位 task_id（`/process` 的 task_id 入参用它）。
- `success:false` 时 `task.error` / 顶层 error 给原因；下载 URL 进黑名单也会 false。

### 2.3 后处理 `POST /api/agent/process`（已存在）
入参二选一：`{path}` 或 `{task_id}`。返回：
```json
{ "status": "processed" | "partial" | "failed", "library_path": "...", "files": ["..."] }
```
- `partial` = 未配 TMDB，只整理未刮削。上层照实回报，不当成 processed 成功。
- 需要 `X-Agent-Token`（若 napics 配了 `agent_api_token`）。
- **上层只消费 `{status, library_path, files}` 三个出参，不关心 napics 内部实现**（内部两段式 dry_run→执行、library_path/files 重扫组装都是 napics 的事，已由另一对话在 `agent.py::agent_process` 落地，上层不复现）。

### 2.4 探活 `GET /api/agent/health`（已存在）
返回 `{ok:true, service:"napics"}`。**qB 可达性上层自己直连判定，不依赖这个。**

### 2.5 认证（已核实）
napics agent 写端点（/process、submit）过 `X-Agent-Token`（对应 napics `config.agent_api_token`，留空则不校验）。
上层配置 `NAPICS_AGENT_TOKEN` 带上。napics 的 `AccessControlMiddleware` 是浏览器 cookie 门，默认关闭；
**上层直连后端 :8001 的 agent 端点，不吃 cookie**。✅ 已核实：`/api/agent/` 已在 `main.py` 的 `AccessControlMiddleware` 白名单里、`config.agent_api_token` 字段也已存在——即便 NAS 设了访问密码，agent 端点也不被 cookie 门挡。此项无待办。

---

## 3. 上层 MCP Tools（对 Hermes 暴露）

第一版：
```
download_movie          创建下载任务（异步，立刻返回 task_id）
get_download_task       查单个任务状态
list_download_tasks     列任务
cancel_download_task    取消 + cleanup
```
辅助：
```
get_system_status       容器/服务健康 + 当前活跃任务
cleanup_orphaned_tasks  管理员：启动时自动跑一次，清理孤儿
```

### 3.1 download_movie
入参（**只吃结构化，语言理解归 Hermes**）：
```json
{
  "title": "泰坦尼克号",
  "media_type": "movie",         // movie | tv
  "year": 1997,
  "original_title": "Titanic",
  "original_language": "en",
  "queries": ["Titanic 1997"],   // agent 拼好的搜索词，可多个（回退）
  "constraints": {               // 上层据此筛选候选（agent 也可自己筛好只传一条 download_url）
    "min_resolution": "2160p",   // "4k"
    "max_size_gb": 50
  },
  "season": null,                // tv
  "interactive": true            // 不确定时是否走 WAITING_USER
}
```
最小输入 `{ "title": "...", "queries": ["..."] }`。
返回：`{ "task_id": "task-20260908-abc123", "status": "starting" }`（**不阻塞几小时**，见 §4 Task）。

### 3.2 get_download_task
`{task_id}` → `{task_id, status, stage, progress, speed_bytes, eta_seconds, message, selected_resource?}`

### 3.3 list_download_tasks
`{status?}` → `{tasks:[...]}`。status 支持 `running|completed|failed|...`。

### 3.4 cancel_download_task
`{task_id, delete_download?}` → 停 workflow → 删 qB 种子 →（可选）调 napics 删 task 记录 → cleanup 关容器 → `CANCELLED`。

### 3.5 get_system_status
```json
{
  "napics": {"container":"kami-pic","running":true,"healthy":true},
  "prowlarr": {"container":"prowlarr","running":true,"healthy":true},
  "qbittorrent": {"managed":false,"reachable":true},
  "active_task": "task-123"
}
```

---

## 4. Task 状态机（上层自有，SQLite 持久化）

```
CREATED → STARTING_SERVICES → SERVICES_READY → SEARCHING → RESOURCE_SELECTION
→ PROBING_RESOURCES → DOWNLOADING → PROCESSING → COMPLETED → CLEANING_UP → SERVICES_STOPPED
```
分支：`WAITING_USER`（选片/选资源）；终态 `COMPLETED | FAILED | CANCELLED | TIMEOUT | RETRY_EXHAUSTED`。
任何阶段异常 → `FAILED` → **必经 CLEANING_UP → SERVICES_STOPPED**（§8 finally）。

对 Hermes 暴露的统一状态（屏蔽 qB/napics 原始串）：
```
starting | searching | selecting | probing | downloading | processing | completed
| waiting_user | failed | cancelled | timeout | exhausted
```

---

## 5. ServiceManager（容器生命周期 — 上层独有，spec 核心，todo 曾漏）

```python
class ServiceManager:
    async def ensure_started(self): ...   # start kami-pic → wait napics health → start prowlarr → wait prowlarr health → check qB
    async def wait_healthy(self): ...
    async def stop(self): ...             # stop prowlarr → stop kami-pic（顺序反向）
    async def cleanup(self): ...          # best-effort，单个失败不阻断其它
```
- 启动顺序：① `docker start kami-pic` → ② 等 napics health（`GET :8001/api/agent/health` 返回 `ok:true`，**不能只判 TCP 端口**）→ ③ `docker start prowlarr` → ④ 等 prowlarr health（`GET :9696` 200，或 `/api/v1/health`）→ ⑤ 检查 qB 可达（`GET :8085` 能登录）。
- **qB 不可达 → FAILED → cleanup**（qB 是飞牛官方应用，上层不启停，但必须探活）。
- **Service Ownership**：Task 记录每个容器 `started_by_task`（本任务是否亲手启动）。策略 `STOP_SERVICES_AFTER_TASK=true`（用户要"下完释放内存"）——即便任务开始时容器本已在跑，结束也停。
- **并发锁**：第一版同一时间只允许一个下载 workflow（`asyncio.Lock` + SQLite `service_locks` 持久化）。原因：Task B 不能让 Task A 正在用的 prowlarr 被 stop。

### Docker Adapter（白名单，防注入）
```python
ALLOWED_CONTAINERS = {"napics": "kami-pic", "prowlarr": "prowlarr"}   # qB 不在内
```
只允许 `start / stop / inspect` 白名单容器。**禁止** `exec / rm / run / pull / prune`，禁止 agent 传任意 container name。走 docker socket（`/var/run/docker.sock`）或 docker SDK。

---

## 6. 测速探测 Probe（上层直连 qB，保留）

> **仅适用于 qb 通道**：probe 靠 qB 的 `dlspeed`/`torrents/info`，网盘转存(alist)没有"测速淘汰"语义。第一版 `download_movie` 固定走 qb。

- `PROBE_BATCH_SIZE=3`：从候选（agent 已筛/排序）取前 3 条，**同时**经 napics `/download-manager/submit` 推进 qB，各拿一个 hash（submit 一条建一个 napics task，3 条=submit 3 次=3 个 napics task_id + 3 个 qb_hash）。
- **拿 hash 的坑（H3）**：并发 submit 最容易触发 napics "差集拿空 hash"（§2.2）。**优先选 magnet 候选**（btih 可直接拿 infohash）；非 magnet 候选 submit 后 hash 为空时，按 §2.2 的回落匹配（`torrents/info` 全量 + media_name 双向包含 + save_path/size 二次校验）补 hash；仍匹配不到则该候选判 probe 失败、不计入测速。
- 每 `PROBE_INTERVAL=5s` 直连 qB `GET /api/v2/torrents/info?hashes=...` 查 `dlspeed`。
- 有效阈值 `PROBE_MIN_SPEED=10KB/s`；探测超时 `PROBE_TIMEOUT=120s`。
- **不是第一个过阈值就停**：设 `STABILIZATION_WINDOW=10s`，多个达标时取速度最高者（20KB/s vs 5MB/s 选后者）。
- 选定一条 → **删掉同批其它种子**（qB delete，deleteFiles=true 删的是 probe 下的临时数据；**禁止删媒体库已有文件**）→ 进 DOWNLOADING。
- 整批全失败（连续 120s ≤10KB/s）→ cleanup 本批 → 下一批 R4/R5/R6 → 资源耗尽 → `RETRY_EXHAUSTED` → cleanup。
- 进入正式 DOWNLOADING 后**不再用 10KB/120s 判失败**（资源已证明可用），只监控进度。

### qB 直连客户端（各能力的真实参考位置 — 别统一照抄 downloader.py，它没有 info/delete）
> ⚠️ napics 的 qB 能力**散在两个文件**，delete 则**全项目没有**、必须上层自写：
- **登录 / 加种**：参考 `backend/downloader.py::QBittorrentClient`——`_login`(表单 `username/password` → cookie session，403 重登)、`add_torrent`(POST `/api/v2/torrents/add`，`urls`+`savepath`)。
- **查进度 / state 解析**：参考 `backend/download_provider_adapter.py`——`_progress_qb`(GET `/api/v2/torrents/info`，params `{"hashes": h}`，取 `item["state"]/progress/dlspeed`)、`_format_qb_speed`、`_format_qb_eta`。**info 不在 downloader.py**。
- **删种：napics 侧不存在，上层自己实现**——`POST /api/v2/torrents/delete`，data `hashes=<hash>&deleteFiles=<bool>`（同一 cookie session）。
- state → 统一枚举映射（上层维护）：`stalledDL→stalled`, `downloading/metaDL→downloading`, `pausedDL→paused`, `uploading/pausedUP/stalledUP/(progress==1)→completed`, `error/missingFiles→failed`。
- **qB url 两套要一致（M1）**：上层的 `QB_URL`（§14）与 napics 的 `config.qb_url()` 是两套配置，必须指向**同一个 qB 实例**——否则上层监控的种子和 napics submit 的种子不在同一个 qB 里。8085 是飞牛官方 qB 默认，非 napics 硬编码。

---

## 7. 下载完成判定 + 后处理 + 推送

- qB `completed` **不是最终成功**：还要调 napics `POST /api/agent/process`（§2.3）等 `processed`。
- `PROCESSING_TIMEOUT=1800s`，超时 → `TIMEOUT` → cleanup。
- `DOWNLOAD_TIMEOUT=0`（无限等，电影大小差异大；以后可改 12h/24h）。
- `processed`（或 `partial` 明确标注）→ **推送**（见 §9）→ `COMPLETED` → cleanup 关容器。

---

## 8. Cleanup 铁律（finally，非正常分支）

```python
async def run(task):
    try:
        await services.ensure_started(); await services.wait_healthy()
        resource = await search_and_probe()
        await download(resource); await process()
        await notify_success(task); task.complete()
    except Exception as exc:
        task.fail(exc); await notify_failure(task)
    finally:
        await cleanup()   # 停 workflow → 清 probe 种子 → stop prowlarr → stop kami-pic → 更新 Task
```
- **禁止 `if success: cleanup()`**——异常时容器会一直占内存。
- cleanup best-effort：`docker stop prowlarr` 失败不能阻止 `docker stop kami-pic`，逐个记 `cleanup_status`。
- 崩溃恢复：MCP 启动时 `cleanup_orphaned_tasks` 读 SQLite，`PROBING` 的清 probe 种子+停服务；`DOWNLOADING` 的按 `RECOVER_ACTIVE_DOWNLOAD=true` 恢复监控。

---

## 9. 推送（spec 未定，本 todo 补：用户要"下载完毕发推送"）
- 第一版**待用户定渠道**：Bark / Telegram / 飞牛通知 / 本 crew send_message。先做成可插拔 `notifier`（成功/失败/需要用户输入 三种事件），渠道用 env 配。
- ⚠️ 这是本文件唯一还没定的实现细节，动到 §9 时确认；不阻塞 §1-§8 骨架。

---

## 10. SQLite（`data/tasks.db`）
表：`tasks / task_events / resources / probe_batches / service_locks`（字段照 spec §48-51）。
- `tasks`: id, media_type, title, year, original_title, original_language, status, current_stage, napics_task_id, qb_hashes_json, created_at, updated_at, error_code, error_message, cleanup_status。
  > `qb_hashes_json` 复数：probe 一批同时持有 3 个 qB hash（与 napics 单数 `downloader_hash` 不同是故意的），选定后收敛为 1。
- `task_events`: 全生命周期事件（SERVICE_STARTED/SEARCH_*/PROBE_*/RESOURCE_SELECTED/DOWNLOAD_*/PROCESSING_*/CLEANUP_*/TASK_*）。

---

## 11. 错误契约
工具失败返回 `{error:{code,message,retryable}}`，不抛裸异常。
码：`NAPICS_UNAVAILABLE QB_UNAVAILABLE PROWLARR_UNAVAILABLE SERVICE_START_FAILED SEARCH_FAILED NO_RESULTS SOURCE_MISSING DOWNLOAD_FAILED DOWNLOAD_NOT_FOUND PROBE_EXHAUSTED PROCESS_FAILED PROCESS_PARTIAL CANCEL_FAILED AUTH_FAILED INTERNAL_ERROR`。

## 12. 安全红线
- 上层 **不读** napics `backend/config.json`（明文凭据），自己 env 一套。
- 返回/日志 **禁止** 出现 qB 密码、prowlarr/tmdb key、cookie、Authorization、agent token。
- Docker adapter 只白名单 start/stop/inspect kami-pic+prowlarr。
- 第一版只监听 NAS LAN，不暴露公网；将来公网需 HTTPS+认证+Tailscale。

## 13. 工程形态
```
nas-download-mcp/           # 独立目录，部署在 NAS
├── src/
│   ├── server.py           # FastMCP(Streamable HTTP) + 工具注册
│   ├── workflow.py         # Task 状态机 + run() finally cleanup
│   ├── service_manager.py  # 容器生命周期
│   ├── adapters/
│   │   ├── napics.py       # HTTP 调 /api/agent/* + /download-manager/submit
│   │   ├── qb.py           # 直连 qB (login/info/delete)
│   │   └── docker.py       # 白名单 docker
│   ├── probe.py            # 测速探测
│   ├── notifier.py         # 推送（可插拔）
│   ├── db.py               # SQLite
│   ├── models.py           # DTO
│   └── config.py
├── data/  logs/  tests/
├── Dockerfile  docker-compose.yml  requirements.txt  .env.example  README.md
```
- 语言 Python 3.10+，MCP 用官方 `mcp` SDK 的 `FastMCP`（Streamable HTTP transport），HTTP 客户端 `httpx`。

## 14. .env
```
MCP_HOST=0.0.0.0
MCP_PORT=8787
NAPICS_API_BASE=http://192.168.100.111:8001     # 后端，非 3032 前端
NAPICS_AGENT_TOKEN=
NAPICS_CONTAINER=kami-pic
PROWLARR_CONTAINER=prowlarr
QB_URL=http://192.168.100.111:8085
QB_USERNAME=admin
QB_PASSWORD=
PROBE_BATCH_SIZE=3
PROBE_INTERVAL_SECONDS=5
PROBE_TIMEOUT_SECONDS=120
PROBE_MIN_SPEED_BYTES=10240
STABILIZATION_WINDOW_SECONDS=10
PROCESSING_TIMEOUT_SECONDS=1800
DOWNLOAD_TIMEOUT_SECONDS=0
STOP_SERVICES_AFTER_TASK=true
RECOVER_ACTIVE_DOWNLOAD=true
DATABASE_PATH=/app/data/tasks.db
LOG_PATH=/app/logs
NOTIFY_CHANNEL=                                  # bark|telegram|fnos|crew（§9 待定）
```
> 部署确认点：napics 后端 :8001 是否对上层容器可达（若只听 127.0.0.1，上层用 host 网络或同 docker 网络）。docker.sock 挂载给上层容器。

## 15. docker-compose（上层容器）
```yaml
services:
  nas-download-mcp:
    build: .
    container_name: nas-download-mcp
    ports: ["8787:8787"]
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - /var/run/docker.sock:/var/run/docker.sock
    restart: unless-stopped
```

---

## 16. 实施顺序（一件一提交）
1. 工程骨架：server.py(FastMCP HTTP) + config.py + db.py(SQLite 建表) + models.py(DTO/状态枚举/错误契约)
2. adapters：qb.py(login/info/delete + state 映射) → napics.py(search/submit/process) → docker.py(白名单 start/stop/inspect)
3. service_manager.py：ensure_started/wait_healthy/stop/cleanup + 并发锁
4. probe.py：batch 试速 + 稳定窗口 + 淘汰
5. workflow.py：Task 状态机 + run() try/finally cleanup + 崩溃恢复
6. notifier.py：§9（渠道待用户定）
7. 工具层：download_movie / get_download_task / list_download_tasks / cancel_download_task / get_system_status / cleanup_orphaned_tasks
8. 测试（§17）+ Dockerfile/compose + README（如何在 Hermes 注册 HTTP MCP）

## 17. 测试（对 mock napics + mock qB，端到端连真实）
TC: start 容器 / health / prowlarr 挂 / qB 挂 / 搜索 / 零结果 / probe 3 条 / 一条>阈值 / 全<阈值下一批 / 耗尽 / 下载完成 / processing 完成 / processing partial(未配TMDB) / 取消 / MCP 重启孤儿清理 / cleanup 部分失败 / 幂等重复提交 / 并发锁拒第二任务。

## 18. Definition of Done
```
[ ] Streamable HTTP MCP，Hermes 能连 :8787/mcp
[ ] download_movie 立刻返回 task_id，不阻塞
[ ] MCP 能 start/stop kami-pic + prowlarr（白名单）
[ ] MCP 不控制 qB 启停，但探活；qB 挂→FAILED→cleanup
[ ] 搜片走 napics /api/agent/search，上层按 4k/<50g 筛
[ ] 创建下载走 napics /download-manager/submit（幂等），拿 downloader_hash
[ ] Probe：3 条并发试速、10KB/120s、稳定窗口取最快、淘汰其余（禁删媒体库文件）
[ ] 正式下载直连 qB 监控进度
[ ] 完成后调 napics /api/agent/process 等 processed（partial 如实标注）
[ ] 完成/失败/取消 都推送
[ ] 成功/失败/取消/崩溃 都经 finally cleanup 关容器（释放内存）
[ ] SQLite 持久化 + 崩溃恢复
[ ] 不泄露任何凭据
```

---
> 未在第一版做：BookForge/有声书、TV 追更复杂逻辑、多用户权限、公网 API、LLM 网关。见 spec §81-82。
