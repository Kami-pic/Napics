---
name: two-phase-commit
description: >
  两段式提交模式：dry-run 预览 → 用户确认 → 执行落盘 + 回滚能力。
  Use when implementing destructive operations that need user confirmation,
  or when adding new organize/relocate/cleanup workflows.
---

# L8 两段式提交

> 任何有破坏性的操作（移动文件、删除、替换）都应该先预览再执行。

## 模式

```
Phase 1: dry-run（推演）
  → 完整执行计算逻辑，严禁落盘
  → 返回 Action Plan（JSON 结构，描述将要做什么）
  → 前端展示预览面板

Phase 2: execute（执行）
  → 用户确认后，按 Plan 执行物理操作
  → 每步操作记录到 snapshot（用于回滚）
  → 失败时部分回滚或标记失败
```

## 项目中的实例

### 整理流水线（/organize/full）
- `dry_run=true`：跑 Step 0-3 的计算逻辑，返回 tmdb_match + plan + summary
- `dry_run=false`：按 plan 执行 Step 0-5（封装/归档/刮削/归位/影子名）
- 回滚：organize_history.py 记录 snapshot，支持 `/organize/rollback`

### 归位替换（file_relocator.py）
- `relocate(task)`：推演阶段，扫描下载目录 + 匹配旧资源 + 生成冲突对列表
- `confirm_replace(task, plan)`：执行替换，旧资源入回收站
- `archive_both(task, conflicts)`：两者都保留
- `cancel_replace(task)`：不做任何操作

### AI 智能管家（SmartManager.tsx）
- AI Scan → 生成建议列表（预览）
- Confirm AI Plan → 执行建议
- History → 回滚

## 设计要点

| 要点 | 说明 |
|------|------|
| Plan 是纯数据 | JSON 结构，不含函数引用，可序列化传给前端 |
| 推演和执行用同一套逻辑 | 避免推演和执行结果不一致 |
| 回滚记录 | 每步操作记录 before/after 状态，支持逆向操作 |
| 部分失败 | 某步失败不中断整体，标记失败项继续后续步骤 |
| 回收站兜底 | 删除操作先移到回收站，可配置保留天数后再真删 |
