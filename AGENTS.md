# Napics

面向 NAS 高阶用户的 AI 媒体资产管理与整理系统。

## 技术栈

- 后端：Python 3 + FastAPI + Uvicorn（数据持久化用 JSON 文件，无数据库）
- 前端：Next.js 16 + React 19 + Tailwind CSS 4
- 外部服务：TMDB / Prowlarr / qBittorrent / OpenList(Alist) / 豆瓣 / Bangumi

## 开发环境

```bash
# 后端
cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8001

# 前端
cd frontend && npm run dev

# 测试（后端）：必须指定具体测试文件，不要跑 pytest tests/
cd backend && python -X utf8 -m pytest tests/test_playback_subtitles.py

# 测试（前端）
cd frontend && npm test
```

前端测试基建（`vitest.config.ts`、`__tests__/`）与后端测试基建（`conftest.py`、`pytest.ini`、`test_support/`）均在版本控制内，未被 `.gitignore` 排除。
前端 `npm test`（即 `vitest --run`）可直接使用。
后端**必须按文件名指定测试**：`tests/test_api_rename.py` 在收集期就会发出真实 HTTP 请求，因此 `pytest tests/` 全量收集不可用。

## 目录结构

```
├── backend/          # Python 后端
│   ├── main.py       # FastAPI 入口
│   ├── routes/       # 路由层（按业务域拆分）
│   ├── core/         # 核心常量与规则
│   ├── tests/        # 测试
│   └── ...           # 业务模块
├── frontend/         # Next.js 前端
│   ├── app/          # 页面路由
│   ├── components/   # UI 组件
│   ├── hooks/        # 自定义 hooks
│   ├── lib/          # 工具函数与 API
│   └── types/        # 类型定义
└── scripts/          # 辅助脚本
```

## 编码规范

- Python：snake_case，Pydantic BaseModel，中文注释
- 前端：PascalCase 组件，Tailwind CSS
- 前端单文件不超过 300 行，后端路由不超过 400 行
- 所有外部服务凭据走 `backend/config.json`，不允许硬编码
