---
name: sse-streaming
description: >
  SSE 流式通信模式：后端 generator → 事件流 → 前端增量追加 + 竞态保护。
  Use when implementing new SSE endpoints, debugging streaming issues,
  or adding progress reporting to long-running operations.
---

# L9 SSE 流式通信

> 搜索/扫描/整理等长任务都用 SSE 推送进度和结果。

## 后端模式

```python
@router.get("/api/search/stream")
async def search_stream(query: str, ...):
    def _generate():
        for event in search_all_sources_iter(keywords, ...):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: {\"type\": \"all_done\"}\n\n"
    return StreamingResponse(_generate(), media_type="text/event-stream")
```

**关键点**：
- generator 函数内部不能 await（FastAPI StreamingResponse 用同步 generator）
- `ensure_ascii=False` 保证中文不被转义
- 每个事件以 `data: ` 开头，`\n\n` 结尾
- 最后发 `all_done` 事件通知前端关闭连接

## 前端模式

```typescript
const es = new EventSource(`/api/search/stream?query=${query}`);
activeEsRef.current = es;  // 竞态保护

es.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.type === "all_done") { es.close(); return; }
  if (data.type === "source_done") {
    setResults(prev => [...prev, ...data.results]);  // 增量追加
  }
};

es.onerror = () => { es.close(); };
```

**竞态保护**：
- `activeEsRef` 跟踪当前 EventSource
- 新搜索开始时关闭旧连接：`activeEsRef.current?.close()`
- 防止旧搜索的结果混入新搜索

## 超时处理

| 层级 | 超时 | 处理 |
|------|------|------|
| 后端 as_completed | 65s | 超时的源推送 `source_failed` 事件 |
| 前端 EventSource | 90s | 超时后 `es.close()` + 显示部分结果 |
| 单源内部 | 各源不同（12-60s） | 超时返回空结果 |

## 项目中的 SSE 端点

| 端点 | 用途 | 事件类型 |
|------|------|---------|
| `/api/search/stream` | BT 全源搜索 | source_done / source_failed / all_done |
| `/scan` | NAS 目录扫描 | progress / done |
| `/quick-sync` | 快速同步 | progress / done |
| `/organize/full` | 流式整理 | step / done |

## 踩坑经验

- Pydantic model 的 quality 字段无法 `json.dumps` 序列化 → 先 `.model_dump()` 再序列化
- `queue.get` 阻塞 SSE generator → 改用 `as_completed` 天然流式
- 前端 `EventSource` 不支持 POST → 搜索参数只能走 query string
