---
inclusion: fileMatch
fileMatchPattern: "**/*.{py,tsx,ts,js,json}"
---

# 技术栈

## 后端
- Python 3 + FastAPI + Uvicorn
- 数据持久化：JSON 文件（media_library.json、config.json、download_tasks.json 等）
- 无数据库，无 ORM
- 依赖：fastapi, uvicorn, pydantic, requests, python-multipart, ffprobe-python

## 前端
- Next.js 16 + React 19 + Tailwind CSS 4
- 目录：frontend/（app/components/hooks/lib/types）

## 外部服务
- TMDB API — 影视元数据（需代理 http://127.0.0.1:7897）
- Prowlarr (localhost:9696) — BT 索引器聚合搜索
- qBittorrent (localhost:8080) — BT 下载
- Alist (localhost:5244) — 网盘挂载管理（夸克/阿里/百度/115/PikPak）
- 豆瓣/Bangumi — 补充刮削源

## 依赖管理
- 后端：新增 Python 依赖必须同步更新 backend/requirements.txt
- 前端：新增 npm 依赖通过 npm install --save 或 --save-dev 自动更新 package.json
- 不允许代码中 import 了某个包但 requirements.txt / package.json 里没有记录
- 后端当前缺失的依赖（待补）：beautifulsoup4、lxml

## 架构约束
- 后端模块化入口 main.py（薄壳）+ routes/ 路由模块 + shared.py 共享层
- 启动方式：`cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000`
- 不用 --reload 启动 uvicorn（会导致 import 链路崩溃）
- NAS 路径通过 SMB 访问（\\DS218play\share\视频\），注意超时和编码问题
- JSON 文件读写需考虑并发安全和备份
- 所有外部服务凭据必须走 config.json，不允许硬编码
