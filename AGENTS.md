# 项目协作入口

## 开工入口

- 新对话开始只按这个顺序进入：`AGENTS.md` → `.kiro/steering/ai-rules.md` → `.kiro/steering/project-structure.md` → 当前 TODO
- 开工前先写清当前 task：
  - 本轮目标是什么
  - 本轮只做哪一种改动
  - 本轮明确不碰哪些区域

## 文档分层

- `.kiro/steering/`：规则主源
- `.kiro/docs/*-todo.md`：当前总览、可勾选任务、下一步
- `docs/_one-off/`：临时过程记录 / 一次性阶段记录
- `knowledge/devlog.md`：阶段归档
- `project-memory.md` / 领域 knowledge：长期有效的业务规则和跨模块约定

## 常用命令

- 后端启动：`cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000`
- 后端测试：`cd backend && python -X utf8 -m pytest test_*.py`
- 前端启动：`cd frontend && npm run dev`（端口 3031）
- 前端测试：`cd frontend && npm run test`
- 前端构建：`cd frontend && npm run build`
- 完整验证：依次执行后端测试 → 前端测试 → 前端构建

## Git 策略

- task 完成且验证通过：自动本地 `commit`，commit message 按规范生成（中文，多行）
- push 必须用户明确指令才执行
- PR / 合并 / 发布 / 高风险配置修改：必须用户确认后才能执行

## 收尾清单

- task 收尾默认检查：
  - 当前 TODO 已更新
  - 临时过程记录已写入 `docs/_one-off/`，或本轮已判定无需新增
  - 若本轮已到阶段收口时点，已更新 `knowledge/devlog.md`
  - 已判断是否需要更新 `project-memory.md` / 对应 knowledge
  - 已判断是否需要新增规则 / hook / skill（如果本轮有可复用的模式）
  - 验证通过后：
    - task 完成 -> 自动本地 `commit`
    - 阶段完成 -> 自动 `push` 存档分支

## 机械约束

- 改 `backend/` 或 `frontend/` 业务代码时，提交里必须同时包含 TODO 更新
- 改主链路或跨模块规则时，提交里必须同时包含 knowledge 或 `_one-off/` 记录更新
- hook 统一放在 `.kiro/hooks/`
- 检查脚本统一放在 `scripts/`
