# [一次性] 下载→归位闭环工作记录

> 用途：保留这条主线的详细推进记录。  
> 原则：TODO 只保留当前进度和可执行项；详细回合检查统一沉淀到这里。  
> 对应 TODO：`optimization-stabilization-todo.md`

---

## 主线范围

本记录对应的主线是：

`下载完成 → 本地转移 → 局部刷新 → 自动归位 → confirm/execute → 回收站/持久化`

---

## 已完成的业务修复

### 2026-04-24

- 修复 `/organize/archive-both` 与 `/organize/purge-old` 传给 `FileRelocator.relocate()` 的白名单格式，统一为“路径字符串白名单”
- 修复 `/organize/dry-run` 在 qB 文件列表缺失时错误迭代整个 `action_plan` 的 fallback 逻辑
- 修复 `confirm_replace()` 在 plan 未携带 `whitelist` 时不会回退磁盘扫描白名单的问题
- 修复 `_execute_plan()` 落盘执行目录与前序 dry-run / confirm 不一致的问题，当前优先使用 `save_path`
- 修复 `confirm_replace()` → `_execute_plan()` → `organize_full()` 没有显式透传 `action_plan` 的问题

---

## 已完成的测试补强

### 路由 / Relocator

- `routes/relocate.py`
  - `/organize/dry-run` 的 `old_tree/new_tree/plan_tree`
  - `/organize/execute` 的白名单注入、成功归档与失败不归档
  - `/organize/archive-both` 的重新探测与成功归档
  - `/organize/purge-old` 的“无白名单即停止”和“逐个回收旧资源”

- `file_relocator.py`
  - 白名单冲突探测
  - 旧视频 / NFO / 海报 / 目录级 NFO 回收路径
  - `confirm_replace` 白名单兜底
  - `execute_plan` 执行目录与 `action_plan` 透传
  - 真实 RecycleBin 落盘与元数据重载

### DownloadManager

- 下载完成触发归位 / 订阅回调
- `_auto_relocate()`：
  - 线程名与 daemon 参数
  - 本地路径缺失时先补定位再归位
  - `awaiting_confirm` 时继续 `confirm_replace()`
  - `archived` 时不重复确认
  - 真实双线程并发启动观测

- `sync_progress()`：
  - qB / Alist 从 `downloading -> completed` 时触发 `_relocate_to_save_path()`
  - 订阅任务场景继续调用 `_notify_subscription_complete()`

- qB 状态映射
  - `pausedUP` / `stalledUP` -> `completed`
  - `missingFiles` -> `downloading`
  - 查不到 hash -> `lost`
  - 登录失败 / info 非 200 -> `unknown`
  - info 请求超时 / payload 非法 -> `unknown`
  - `organized=True` 时跳过 qB 查询
  - 提交成功且拿到新 hash / 提交成功但暂未拿到 hash / 提交失败 / 提交抛异常

- Alist 状态映射
  - undone `state!=2` -> `cloud_download`
  - undone `state=2` -> `local_sync`
  - done + 本地文件存在 -> `completed`
  - done + 本地文件缺失 -> `local_sync`
  - undone 请求失败 -> `unknown`
  - undone 请求超时 / done payload 非法 -> `unknown`
  - undone 空 + done 非 200 -> `lost`
  - undone 空 + done 抛异常 -> `unknown`
  - 两边都找不到任务 -> `lost`
  - transfer_link 成功 / 失败 / 抛异常

- 启动恢复 / 对账
  - 残留 `pending` -> `failed`
  - `downloading` -> `_reconcile_task()`
  - 无 downloader hash -> `lost`

- 本地转移 / 刷新 / 持久化
  - 文件真实从 `download_dir` 移到 `save_path`
  - 同名目标跳过、不覆盖
  - 本地移动异常时保留 `downloading` 并记录 `task.error`
  - `_trigger_local_refresh()` 真实后台线程写库观测
  - `download_tasks.json` 真实落盘后重载字段不漂移
  - 升级型电影订阅下载完成时标记 `completed` 并发 `upgrade_complete`

---

## 兼容性清理

### 2026-04-24

- `backend/recycle_bin.py`：`dict()` -> `model_dump()`
- `backend/download_manager.py`：`dict()` -> `model_dump()`

目的：

- 消除 Pydantic V2 废弃 warning
- 不改变当前业务行为

---

## 当前结论

### 这条主线已经证明的部分

- 路由闭环可跑
- 归位器关键参数传递一致
- 回收站和任务队列可真实落盘
- 下载完成后的本地转移、局部刷新、订阅回调可观测
- 自动归位至少能在真实后台线程中并发启动
- 一批已知长尾状态已有明确当前映射

### 这条主线还没证明的部分

- 真实 NAS 上的 `organize execute` 落盘与封箱
- 真实线程下 `confirm_replace + execute` 的交叠时序
- 真实 qB / Alist 在超时、重试、返回结构变化下的更复杂异常

---

## 关联存档点

- 远端分支：`origin/codex-relocate-baseline-checkpoint`
- 提交：`6195eeb` `测试: 补强下载归位闭环验证`
