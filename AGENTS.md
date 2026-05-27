# Napics

面向 NAS 高阶用户的 AI 媒体资产管理与整理系统。

## 技术栈

- 后端：Python 3 + FastAPI + Uvicorn（数据持久化用 JSON 文件，无数据库）
- 前端：Next.js 16 + React 19 + Tailwind CSS 4
- 外部服务：TMDB / Prowlarr / qBittorrent / OpenList(Alist) / 豆瓣 / Bangumi

## 开发环境

```bash
# 后端
cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend && npm run dev

# 测试
cd backend && python -X utf8 -m pytest tests/
cd frontend && npx vitest --run
```

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
