# [一次性] organize dry-run / execute 独立基线摘要

> 对应执行面板：`optimization-stabilization-todo-v2.md`  
> 目标：把 V1 中长期挂起的 `organize dry-run / execute 基线` 从下载主线里拆出来，形成独立收口判断。  
> 结论日期：2026-05-06

---

## 1. 范围

本摘要只覆盖整理相关的用户可触发路径：

- 下载任务归位预览：`/organize/dry-run`
- 下载任务确认执行：`/organize/execute`
- 共存归档：`/organize/archive-both`
- 旧资源清理：`/organize/purge-old`
- 一键完全整理：`/organize/full` dry-run / execute
- 前端预览树：`old_tree` / `new_tree` / `plan_tree`

本摘要不重新执行正式 NAS 写盘；正式样本证据沿用真实环境清单。

---

## 2. 已有真实样本证据

来源：[download-relocate-real-env-checklist.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-real-env-checklist.md)

- 场景 A 样本 `1a607cf1 / 军火女王 Jormungand`
  - 已执行真实 `dry-run -> execute`
  - 任务收口：`status=archived`、`organized=true`
  - 回收站写入真实回收记录
- 场景 B 样本 `5ad5b6f9 / 卡罗尔与星期二 CAROLE & TUESDAY`
  - 已执行真实 `dry-run -> execute`
  - 任务收口：`status=archived`、`organized=true`
  - 回收站写入 `37` 条真实记录

当前结论：

- 真实 NAS 上 `dry-run -> execute -> archived` 主链已开证。
- 两笔真实样本均未出现状态回跳。
- “执行后再次 dry-run 仍残留目录级冲突”已被记录为后续边角观察，不再阻塞主链基线。

---

## 3. 隔离测试保护面

当前已有测试覆盖以下行为：

- [test_relocate_routes.py](/C:/Users/shenq/nas-video-upgrader/backend/test_relocate_routes.py)
  - `dry-run` 返回 `plan/coexist_pairs/old_tree/new_tree/plan_tree`
  - qB 文件列表白名单透传
  - 缺 qB 文件列表时从 `action_plan` 回退构造新树
  - `execute` 注入白名单并成功后归档任务
  - `execute` 失败时不误归档
  - `archive_both` 执行前重新探测，失败时不误归档
  - `purge_old` 缺新文件识别时停止，避免误删
  - 缺任务、一级分类目录、NAS 根目录等保护分支
- [test_organize_action_plan_execute.py](/C:/Users/shenq/nas-video-upgrader/backend/test_organize_action_plan_execute.py)
  - `action_plan` 按 `target_path` 落盘
  - 逻辑目标重复、目标路径重复在写盘前拦截
  - 字幕、字体、SPs/CDs/OAD 等附属资源跟随计划归位
  - 季目录上下文、单季/多季附属目录处理
- [test_plan_tree_preview.py](/C:/Users/shenq/nas-video-upgrader/backend/test_plan_tree_preview.py)
  - `plan_tree` 中字幕扁平化到 `Season XX`
  - `Fonts` / `SPs` 等非字幕附属目录保持根级展示
- [test_organize_full_action_plan.py](/C:/Users/shenq/nas-video-upgrader/backend/test_organize_full_action_plan.py)
  - `/organize/full` execute 使用显式 `action_plan`
  - 显式计划场景不再依赖 request body 二次读取
- [test_subtitle_flatten.py](/C:/Users/shenq/nas-video-upgrader/backend/test_subtitle_flatten.py)
  - 字幕扁平化和按集号改名回归样本
- [test_season_dir_no_nest.py](/C:/Users/shenq/nas-video-upgrader/backend/test_season_dir_no_nest.py)
  - `save_path` 已是季目录时不再嵌套 `Season XX`

---

## 4. 基线判断

`organize dry-run / execute` 独立基线当前可以标为已收口，理由：

- 用户主路径已有真实样本证明：两笔任务从 `awaiting_confirm` 收口到 `archived`。
- 路由返回结构已有快照型断言，前端预览依赖字段不会静默变形。
- `action_plan` 的执行层关键风险已补隔离测试：目标落盘、重复拦截、字幕/附属文件、季目录不嵌套。
- 高风险真实写盘不需要为了 V2 再重复执行；后续只在出现新回归时按轻量影子副本策略复现。

---

## 5. 仍保留的观察项

- 更复杂的 `confirm_replace + execute` 交叠时序。
- 执行后再次 `dry-run` 仍残留目录级冲突的边角现象。
- 更复杂真实 NAS 样本中的文件系统权限、网络抖动、下载器返回不一致。

这些项继续作为观察项存在，不再阻塞 V2 收口。

---

## 6. 本轮验证命令

```powershell
cd backend
python -X utf8 -m pytest test_relocate_routes.py test_organize_action_plan_execute.py test_plan_tree_preview.py test_organize_full_action_plan.py test_subtitle_flatten.py test_season_dir_no_nest.py
```

