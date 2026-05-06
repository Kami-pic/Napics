<!-- 本文件是 .kiro/ 配置的精简摘要，适用于任何 AI 编码工具。完整规则见 .kiro/steering/。上次同步：2026-05-06 -->

# AI_GUIDE.md

> 项目 AI 协作指南，适用于 Cursor / Claude Code / Copilot / CLI 等任何工具。
> 首次对话或续写项目时，请先阅读 `AGENTS.md`，再阅读本文件。

## 项目概述

NAS 视频媒体管理系统。Python FastAPI 后端 + Next.js 前端，管理本地 NAS 上的视频资源，
提供刮削、整理、搜索、下载、发现推荐、订阅等功能。

## 技术栈

- 后端：Python 3 + FastAPI + Uvicorn，数据持久化用 JSON 文件（无数据库）
- 前端：Next.js 16 + React 19 + Tailwind CSS 4
- 外部服务：TMDB（需代理）/ Prowlarr(:9696) / qBittorrent(:8080) / Alist(:5244) / 豆瓣 / Bangumi

## 开发环境

- 后端启动：`cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000`（不用 --reload）
- 前端启动：`cd frontend && npm run dev`
- 后端测试：`cd backend && pytest test_*.py`
- 前端测试：`cd frontend && npx vitest --run`
- NAS 路径通过 SMB 挂载（\\DS218play\share\视频\），注意超时和编码

## 行为准则

- 所有回复、注释、思考过程必须 100% 中文
- 出错不道歉，直接修复；不完整加 TODO 标记
- 方案讨论时独立思考，不迎合式附和
- 修复 bug 最多猜 1 次，无效立即加日志科学排查
- 写完代码必须自测，不允许"没报错就算完成"
- 全量操作/脚本执行必须等用户确认

## 编码规范

- Python：snake_case，Pydantic BaseModel，双引号，中文注释
- 前端：PascalCase 组件，Tailwind CSS，不用 CSS Modules
- 单文件上限：前端 300 行，后端路由 400 行，超过必须拆分
- 先拆后写，不允许先堆后拆
- 前后端类型对齐：folder_type 枚举值和 interface 字段名必须一致（snake_case）

## 代码结构

- 后端分层：main.py（薄壳）→ routes/*（参数校验）→ 业务层 → 数据获取层 → shared.py（单例源）
- 路由路径不可变，前端 api.ts 直接对应后端路由
- shared.py 是唯一的单例源，不要创建 /api/v1/ 前缀
- 所有外部服务凭据走 config.json，不允许硬编码

## 知识库（.kiro/knowledge/）

修改业务代码前，先读 `project-memory.md` 获取领域索引和核心红线，按需深入：

| 领域 | 文件 |
|------|------|
| 跨域知识+核心红线 | project-memory.md |
| 整理流水线 | organize-pipeline-v3.md |
| 网盘搜索 | pan-search-pipeline.md |
| BT 搜索 | bt-search-pipeline.md |
| 下载归位替换 | download-replace-pipeline.md |
| 发现推荐 | discover-recommend.md |
| 订阅系统 | subscribe-system.md |
| 滚动交互 | scroll-damping-interaction.md |
| API 清单 | api-reference.md |
| 数据结构 | data-models.md |
| 开发日志 | devlog.md |

## 提交规范

- 里程碑完成后提交，提交前更新本轮任务对应的 TODO / 设计文档 / `_one-off` 记录 / knowledge
- commit message 中文多行：第一行 `类型: 描述`，body 写变更要点和踩坑
- 严禁提交 node_modules/venv/dist/__pycache__
- 默认禁止 `git add .` / `git add -A` / `git commit -a`；除非用户明确要求全量提交，否则逐文件暂存
- 提交前必须核对 `git diff --cached --name-only`，只提交当前对话中直接修改并验证过的文件
- 文档检查只要求更新本轮相关文档，不要为了过 hook 固定修改 stabilization TODO

## 记忆写入纪律

- 问自己"这条信息 3 个月后还有用吗？"——是则写入 knowledge，否则写 TODO 或不记录
- 跨模块的写 project-memory.md，特定领域的写对应 knowledge 文件
- 更新时直接覆写旧内容，不保留矛盾的历史版本
- 不写：实现细节、通用编程知识、调试中间状态
