# 项目协作入口

## 项目定位

本项目是 **Napics** — 面向 NAS 高阶用户的 AI 媒体资产管理与整理系统（公开版）。

从私有自用版 `nas-video-upgrader` fork 而来，当前阶段目标是**插件化改造**：
将核心能力与外部服务解耦，形成 Core + Plugin + Private 三层结构。

完整改造计划见：`.kiro/docs/nas-video-upgrader-pluginization-plan-v2.md`

## 开工入口

- 新对话开始只按这个顺序进入：`AGENTS.md` → `.kiro/steering/ai-rules.md` → `.kiro/steering/project-structure.md` → 当前 TODO
- 开工前先写清当前 task：
  - 本轮目标是什么（对应 V2 方案的哪个 Phase）
  - 本轮只做哪一种改动
  - 本轮明确不碰哪些区域
  - 预期行为是否等价

## 当前阶段

插件化改造（按 V2 方案 Phase 顺序推进）：

```
Phase 1: 边界审计 → docs/pluginization-audit.md
Phase 2: 建立 Provider 契约与 Registry
Phase 3: 迁移 BT 直搜源
Phase 4: 迁移 RSS 源
Phase 5: 迁移 MetadataProvider
Phase 6: 迁移 Prowlarr
Phase 7: 迁移 qB / OpenList
Phase 8: 网盘源私有化
Phase 9: 前端 Provider 动态感知
```

每一轮只允许做一种改动。不允许跨 Phase 混合执行。

## 文档分层

- `.kiro/steering/`：规则主源
- `.kiro/docs/*-todo.md`：当前总览、可勾选任务、下一步
- `.kiro/docs/_one-off/`：临时过程记录 / 一次性阶段记录
- `.kiro/knowledge/devlog.md`：阶段归档
- `.kiro/knowledge/project-memory.md` / 领域 knowledge：长期有效的业务规则和跨模块约定

## 沟通节奏

- 进入执行态后，默认连续完成 `排查 → 改代码/补测试 → 验证 → 更新文档/提交` 这一整段，再集中向用户汇报
- 不要每推进一点就中途回复；中间进度更新只在确有必要时才发
- 只有以下情况才提前停下：
  - 需要用户做明确决策
  - 涉及删除、批量改动、部署/配置变更等高风险操作
  - 遇到依赖本地之外信息、当前无法自行解开的真实阻塞
  - 已经收口到一个可提交的明确里程碑

## 常用命令

- 后端测试：`cd backend && python -X utf8 -m pytest test_*.py`
- 前端测试：`cd frontend && npm run test`
- 前端构建：`cd frontend && npm run build`
- 完整验证：依次执行后端测试 → 前端测试 → 前端构建

## 每轮执行格式

每轮开始前必须写清：

```
本轮目标：
本轮对应 Phase：
本轮涉及文件：
本轮不碰范围：
预期行为是否等价：
验证命令：
```

每轮完成后必须输出：

```
变更摘要：
行为是否变化：
新增/修改文件：
测试结果：
遗留问题：
下一步建议：
```

## Git 策略

- task 完成且验证通过：自动本地 `commit`，commit message 按规范生成（中文，多行）
- push 必须用户明确指令才执行
- 默认禁止使用 `git add .` / `git add -A` / `git commit -a`，必须逐文件暂存
- 提交前必须执行并核对 `git diff --cached --name-only`
- 多 agent 并行时：只提交当前对话中由自己直接修改并验证过的文件

## 插件化阶段禁止事项

1. 边迁移边修改搜索评分逻辑
2. 边迁移边新增 provider
3. 边迁移边修复非阻塞 bug
4. 将 provider 内部逻辑泄漏到 Core
5. 用裸 dict 替代 DTO
6. 在 route 中直接调用具体资源站
7. 在 Core 中出现具体资源站名称
8. 将网盘搜索源放进公开核心
9. 为了兼容旧代码继续扩大 `shared.py` 单例污染
10. 在插件化阶段同时做目录大重组
11. 在插件化阶段同时做 Docker 化

## 收尾清单

- task 收尾默认检查：
  - 已更新本轮任务对应的 TODO / 设计文档
  - 若本轮已到阶段收口时点，已更新 `knowledge/devlog.md`
  - 已判断是否需要更新 `project-memory.md`
  - 验证通过后自动本地 `commit`

## 机械约束

- 改 `backend/` 或 `frontend/` 代码时，提交里必须同时包含本轮相关的 TODO / 设计文档 / knowledge 之一
- hook 统一放在 `.kiro/hooks/`
- 检查脚本统一放在 `scripts/`
