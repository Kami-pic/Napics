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

## 沟通节奏

- 进入执行态后，默认连续完成 `排查 → 改代码/补测试 → 验证 → 更新文档/提交` 这一整段，再集中向用户汇报
- 不要每推进一点就中途回复；中间进度更新只在确有必要时才发
- 只有以下情况才提前停下：
  - 需要用户做明确决策
  - 涉及删除、批量改动、部署/配置变更等高风险操作
  - 遇到依赖本地之外信息、当前无法自行解开的真实阻塞
  - 已经收口到一个可提交的明确里程碑

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
- 多 agent 并行时：只 `git add / commit / 总结` 当前对话中由自己直接修改并验证过的文件
- 其他 agent 或用户正在处理的改动默认视为外部范围：不混入自己的提交，不在自己的总结里打包汇总
- 默认禁止使用 `git add .` / `git add -A` / `git commit -a`。除非用户明确要求全量提交，否则必须逐文件暂存本轮文件
- 提交前必须执行并核对 `git diff --cached --name-only`，确认 staged 文件只包含本轮自己直接修改且已验证过的文件
- 若工作区已有其他改动，只记录为“外部未提交改动”，不要代为暂存、提交或总结为本轮成果

## 收尾清单

- task 收尾默认检查：
  - 已更新本轮任务对应的 TODO / 设计文档；不要为了过 hook 固定修改 stabilization TODO
  - 临时过程记录已写入 `docs/_one-off/`，或本轮已判定无需新增
  - 若本轮已到阶段收口时点，已更新 `knowledge/devlog.md`
  - 已判断是否需要更新 `project-memory.md` / 对应 knowledge
  - 已判断是否需要新增规则 / hook / skill（如果本轮有可复用的模式）
  - 验证通过后：
    - task 完成 -> 自动本地 `commit`
    - 阶段完成 -> 自动 `push` 存档分支
    - 接下来要做什么

## 机械约束

- 改 `backend/` 或 `frontend/` 业务代码时，提交里必须同时包含本轮相关的 TODO / 设计文档 / `_one-off` 记录 / knowledge 之一；不要求固定更新 `optimization-stabilization-todo*.md`
- 改主链路或跨模块规则时，提交里必须同时包含 knowledge 或 `_one-off/` 记录更新
- hook 统一放在 `.kiro/hooks/`
- 检查脚本统一放在 `scripts/`
- 并行协作时若发现工作区有他人改动，只围绕自己本轮范围做最小暂存；提交前必须再次核对 staged 文件集
