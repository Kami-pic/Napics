---
inclusion: fileMatch
fileMatchPattern: "**/routes/*.py,**/main.py"
---

# API 约定

## 路由命名
- RESTful 风格，小写 + 连字符：`/library/tree`、`/download-manager/task`
- 资源操作用对应 HTTP 方法：GET 查询、POST 创建/操作、DELETE 删除
- 批量操作路由加 batch 前缀或后缀：`/batch-scrape`、`/batch-download`

## 请求格式
- GET 参数用 query string：`/scan?path=xxx`
- POST 请求体用 JSON，复杂参数用 Pydantic BaseModel 定义
- 简单 POST 可用 `req: dict` 接收（项目中已有大量此模式）

## 响应格式
- 成功：`{"status": "ok", ...}` 或直接返回数据列表/对象
- 失败：`{"status": "error", "message": "描述"}` 或抛 HTTPException
- 流式响应（扫描/整理）：SSE 格式，`data: {"type": "start|progress|done|error", ...}\n\n`

## 错误处理
- 参数校验失败：返回 400 + 错误描述
- 资源不存在：返回 `{"status": "not_found"}`
- 服务端异常：try-except 捕获，返回 500 + 错误信息，不让异常裸抛
