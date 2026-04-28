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
  - task 缺失、一级分类目录、NAS 根目录、relocator failed 的失败返回
  - `/organize/execute` 的白名单注入、成功归档与失败不归档
  - `/organize/archive-both` 的重新探测、成功归档与失败不归档
  - `/organize/purge-old` 的“无白名单即停止”“无冲突直接返回”“逐个回收旧资源”

- `file_relocator.py`
  - 白名单冲突探测
  - 旧视频 / NFO / 海报 / 目录级 NFO 回收路径
  - `confirm_replace` 白名单兜底
  - `execute_plan` 执行目录与 `action_plan` 透传
  - 真实 RecycleBin 落盘与元数据重载
  - `relocate()` 在引擎未就绪、下载目录未就绪、dry-run 空计划时的失败返回
  - `confirm_replace()` 在旧资源回收失败时立即停止，不继续执行落盘
  - `cancel_replace()` 会递归回收沙盒内所有文件；沙盒缺失时返回 `failed`
  - `archive_both()` 在无冲突时直接归档返回；备份目录重名时当前会自动追加时间戳避让
  - `_recycle_old_files()` 在旧文件已不存在时当前按 no-op 成功处理
  - `_execute_plan()` 在缺 `save_path` 时回退 `download_dir`，执行异常时返回 `failed`

### DownloadManager

- 下载完成触发归位 / 订阅回调
- `submit()`：
  - qB 成功提交后进入 `downloading`
  - Alist 成功提交后进入 `downloading + cloud_download`
  - 下载通道未配置 / 推送失败时进入 `failed`
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

- 通道推荐
  - `seeders >= 5` 且 `size_gb <= 50` -> `qb`
  - 低做种或大体积 -> `alist`
  - 单通道配置时直接返回唯一通道
  - 双通道都未配置时默认 `qb`

- 状态管理分支
  - `get_tasks()` 按 `created_at` 倒序，且先过滤再排序
  - `get_task()` 命中返回任务，未命中返回 `None`
  - `update_status()` 会更新 `status/error` 并立即落盘
  - `archive_task()` 会写入 `archived`，且可同步标记 `organized`
  - `delete_task()` / `delete_tasks()` 只在实际删除时落盘

- 本地持久化 / 查询小分支
  - `_save_debounced()` 超过阈值才触发落盘，否则只保留 dirty
  - `flush()` 只在 dirty 时落盘
  - `_check_local_files_exist()` 只认视频扩展名
  - `_load()` 遇到损坏 JSON 时回退为空任务列表

- 订阅回调 / 对账边界
  - `_notify_subscription_complete()` 在缺 hash 时回退到 `download_url`
  - `category_hint` 为空时回退 `source=unknown`
  - `best_version` 但缺少 `save_path` 时不触发 `_auto_relocate()`
  - 通知发送异常不会中断订阅完成回调
  - `_reconcile_task()` 在 qB hash 仍存在时保持 `downloading`
  - `_reconcile_task()` 对 alist 任务保持原状，等待后续 `sync_progress()`

- 同步 / 写盘回退
  - `sync_progress()` 无状态变化时只走 `_save_debounced()`
  - `sync_progress()` 无活跃任务时也只走 `_save_debounced()`
  - `on_startup()` 会对 alist downloading 任务同样进入 `_reconcile_task()`
  - `_write_json()` 写盘异常只记日志，不向外抛出

- guard / no-op 分支
  - `_relocate_to_save_path()` 在缺 `save_path` / 缺 `download_dir` / `download_dir` 非目录时直接返回
  - `_trigger_local_refresh()` 在媒体库为空 / 扫描结果为空 / 没有新增文件时不写库
  - `_sync_qb_progress()` 在缺客户端或缺 hash 时直接返回
  - `_sync_alist_progress()` 在缺客户端时直接返回
  - `update_status()` / `archive_task()` 对不存在任务也会照常触发落盘
  - `_load()` 在任务文件不存在时回退为空列表

- qB 格式化 / 保底判定
  - `progress >= 1.0` 即使 state 仍是 `downloading` 也直接收口到 `completed`
  - `dlspeed >= 1 MB/s` 时格式化成 `x.y MB/s`
  - `eta >= 100 天` 时当前清空 ETA 展示

- Alist phase / progress 默认
  - undone `progress=0` 时当前保底写成 `0.0`
  - undone 缺省 `state` 时当前仍按 `cloud_download` 处理
  - done 列表里只有非命中任务时当前仍落到 `lost`

- 自动归位补定位回退
  - `media_matcher.match()` 返回空 folder 时，当前不会写回订阅路径，但仍继续 `relocate()`
  - `media_matcher.match()` 抛异常时，当前只记日志，仍继续 `relocate()`
  - `sync_progress()` 遇到未知 `channel` 时当前只更新时间并走 `_save_debounced()`

- submit / 订阅缺失边界
  - `submit()` 当前先写 `created_at`，提交收口后再刷新一次 `updated_at`
  - `_notify_subscription_complete()` 在 `mgr.get()` 拿不到订阅对象时，当前仍会发送普通 `download_complete`

- 排序 / 状态时间戳
  - `get_tasks()` 对空 `created_at` 当前按空串参与排序，实际会排到最后
  - `update_status()` / `archive_task()` 命中任务时当前会刷新 `updated_at`

- 失败态收口
  - `_auto_relocate()` 在 `relocate()` 返回非 `awaiting_confirm/archived` 状态时当前不走 `confirm_replace()`
  - `sync_progress()` 在 qB/alist 任务转成 `lost/unknown` 时当前只触发 `_save_now()`，不误触发归位或订阅回调
  - `_auto_relocate()` 内部 `relocate()` 抛异常时当前只记日志，不向外冒泡
  - `_notify_subscription_complete()` 外层订阅管理器异常当前只记日志，不向外冒泡
  - `_get_qb_hashes()` 在 info 非 200 时当前回退空集合

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

### 下一阶段执行面板

- 已从“继续补隔离层测试”切到“真实环境验证准备”
- 独立执行清单已落到 [download-relocate-real-env-checklist.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-real-env-checklist.md)
- 后续优先顺序固定为：
  - 场景 A：真实 NAS `organize execute`
  - 场景 B：真实 `confirm_replace + execute` 交叠时序
  - 场景 C：真实 qB / Alist 异常小样本
- 2026-04-27 首次尝试场景 A 时确认了运行阻塞：
  - 后端 / qB / Alist 本机端口均未启动
  - NAS 路径当前不可访问
  - 已从历史任务中筛出 `1a607cf1`、`5ad5b6f9` 作为环境恢复后的首批候选样本
- 随后已恢复后端 / qB / Alist / NAS 路径访问，并对候选样本 `1a607cf1` 执行真实 `/organize/dry-run`
  - 返回 `awaiting_confirm`
  - 已真实识别到 `军火女王 Jormungand` 目录下的旧季目录与旧视频冲突
  - 新资源计划落到 `Season 01`
  - 因 `execute` 会真实改动 NAS 文件，当前停在确认前，不自动继续
- 用户确认后，已继续执行真实 `/organize/execute`
  - 任务 `1a607cf1` 已收口到 `archived`，且 `organized=true`
  - `backend/recycle_bin/recycle_bin.json` 已出现该任务的真实回收记录
  - 真实 NAS `dry-run -> execute` 主链路已开证
  - 但对同一任务再次执行 `dry-run` 仍会返回 `awaiting_confirm`，当前只剩 `Season 01` 目录级冲突，属于后续可单独收口的真实环境边角
- 随后对第二个真实样本 `5ad5b6f9`（卡罗尔与星期二）执行了同样流程
  - 真实 `/organize/execute` 后任务同样收口到 `archived`，且 `organized=true`
  - 回收站元数据为该任务新增了 `37` 条真实记录
  - 再次 `dry-run` 仍返回 `awaiting_confirm`，且缩成 `1` 个残留冲突
  - 说明“执行后再次探测仍有目录级残留冲突”已在两个真实样本上复现
- 随后转入只读定位并确认了残留对象
  - 两个真实样本的残留 `coexist_pairs[0].old_file` 都是目标季目录本身，即 `...\\Season 01`
  - `organized=true` 只会跳过下载器状态同步，不会影响 `/organize/dry-run`
  - 当前怀疑点已收窄到 `file_relocator._detect_conflicts_v2()`：目录白名单只覆盖原始种子子目录，没有覆盖当前 `plan` 自己的目标目录
- 已开始最小代码收口
  - 方向：在冲突探测时排除当前 `plan` 的目标目录，避免真实 execute 后再次探测把新建的 `Season 01` 误判成旧资源
  - 保护：本轮只改判定逻辑和隔离测试，不再继续真实 NAS 写盘
- 随后用真实样本回读确认：上一条修复没有打到根因
  - 两个样本在新代码下再次 `dry-run` 仍然都是 `awaiting_confirm + 1`
  - 但 `plan` 本身是完整 24 集，不是“只规划了一集”
  - `old_tree` 里 `Season 01` 子项数量达到 `48`，样本名直接是原始发布组文件名
  - 这说明残留冲突不是“目录误判”，而是 execute 后原始命名文件仍然留在季目录里
- 已定位到真正根因在 `routes/organize.py` 的 `action_plan` 执行分支
  - 当前逻辑只是对 `original_path` 写 `episode.nfo`，然后调用 `reorganize_seasons_by_nfo()` 把原文件搬进季目录
  - 它并没有按 `plan.target_path / target_filename` 去真正重命名视频主文件
  - 所以 execute 后保留下来的仍是原始发布组文件名，后续真实 `dry-run` 继续看到整个 `Season 01` 为旧存量是合理结果
- 已改为“按 action_plan 直接落盘”
  - 新增 helper：按 `original_path -> target_path` 移动视频主文件
  - 同时联动移动并改名同 basename 的 `.nfo`、海报、字幕 sidecar
  - `episode.nfo` 改为写入目标文件，而不是先写原文件再做二次季化
  - 隔离验证：`test_organize_action_plan_execute.py` 已补，和 `test_file_relocator_conflicts.py`、`test_relocate_routes.py` 一起通过
- 随后已切到影子副本验证方案
  - 不再把正式 NAS 作为下一轮 execute 验证场
  - 新增 [download-relocate-shadow-verify-plan.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-shadow-verify-plan.md)，把副本根目录、复制范围、快照、通过/失败判据压成执行面板
  - 新增 `scripts/prepare_shadow_verify.ps1`，用于只复制单个样本目录到工作区 `shadow-verify`
- 影子副本 `青春之旅` 第一轮 execute 继续暴露了更前置的保护缺口
  - `dry-run` 能正常产出标准化 `plan`，但同一批集数被两套源文件同时命中
  - 具体表现是：一套 `.mkv` 和一套 `.mp4` 会同时落到同一季同一集的标准 basename，只是扩展名不同
  - 这说明仅拦截“重复 `target_path`”不够，execute 前还需要拦截“重复逻辑目标”
  - 下一步应在 `routes/organize.py` 执行前按“同目录 + 同 basename（忽略扩展名）” fail-fast，避免副本再次进入半执行
- 现已补上 execute 前双重保护并完成离线验证
  - 新增“重复逻辑目标”判定：同目录 + 同 basename（忽略扩展名）直接拦截
  - 同时保留原有“重复 `target_path`”拦截
  - 用当前工作区代码对影子副本 `青春之旅` 的真实 `dry-run` 结果做离线路由直调，已在写盘前直接 `400`
  - 这次先命中的 actually 是 `Season 00\\青春之旅 - S00E01 - PAGE.0` 的重复 `target_path`，说明样本里除了 `.mkv/.mp4` 双份主线集数外，`SP/NCOP` 也映射到了同一个目标位
  - 当前 `127.0.0.1:8000` 上的在线进程仍是旧代码；如需再做 HTTP 端到端验证，需要重启本地后端后再复跑
- 已补独立端口的 HTTP 端到端验证，避免打断现有 8000
  - 临时起一份 `python -m uvicorn main:app --host 127.0.0.1 --port 8011`
  - 对同一影子副本重新执行 `dry-run -> execute`
  - 结果与离线判断一致：`execute` 返回 `400`
  - 报错详情为 `action_plan 存在重复 target_path（1 个）`，命中 `Season 00\\青春之旅 - S00E01 - PAGE.0.mkv`
  - 说明新保护已经真实落到 HTTP 路由层，当前不再会让这个副本样本继续进入半执行
- 随后开始筛选第二个更干净的影子副本候选
  - 用现有 `8000` 对多个正式库候选做只读 `dry-run` 摘要比对
  - 当前最干净的是 `d673d8fc / 四月是你的谎言`
    - 正式库结果：`folder_type=tv`
    - `tmdb_match.match_source=existing_nfo`
    - `summary.total_videos=23 / will_process=22 / will_skip=1`
    - 离线重复统计：`dup_target=0 / dup_logical=0`
  - 为避免正式库写盘，已把该目录只读复制到 `shadow-verify/samples/april-lie/source`
  - 但当前影子副本还不能复现正式库的判定：
    - 对副本路径做 `dry-run` 时返回 `folder_type=series`
    - `tmdb_match={}`、`plan=[]`、`summary={}`
    - 即使额外包装一层 `四月是你的谎言` 目录，或挂到本地仿真 `视频/动画番/...` 路径下，结果仍相同
  - 当前判断：问题不在正式候选是否干净，而在“本地影子路径仍未保留足够的上下文让 analyzer/scraper 走到与正式库一致的 `existing_nfo -> tv` 分支”
- 随后已定位并修通这个上下文缺口
  - 根因不在 NFO 内容，而在 `shared._get_category_from_path()`：正式库路径能拿到 `动画番 -> tv` 的 `category_hint`，影子副本路径拿不到，于是退回旧结构推断，变成 `folder_type=series`
  - 已补 fallback：当路径不在正式 NAS 根下时，也允许从路径分段中识别已知一级分类目录名
  - 新增 `test_shared_category_hint.py` 锁定：
    - `shadow-verify/library/视频/动画番/...` 能回收到 `tv`
    - 未命中任何分类段的杂路径仍返回空
  - 隔离验证通过后，用当前工作区代码直接调用 `organize_full(dry_run=True)`，`四月是你的谎言` 影子副本已恢复到与正式库一致的核心结果：
    - `folder_type=tv`
    - `tmdb_match.match_source=existing_nfo`
    - `summary.total_videos=23 / will_process=22 / will_skip=1`
- 已继续做影子副本的独立端口实证，不依赖旧的 `8000`
  - 临时起一份 `python -m uvicorn main:app --host 127.0.0.1 --port 8013`
  - 对 `shadow-verify/library/视频/动画番/四月是你的谎言` 执行真实 `dry-run -> execute`
  - 结果：
    - `dry-run`: `folder_type=tv`, `match_source=existing_nfo`, `will_process=22`
    - `execute`: `200 OK`
    - `steps.structure.moved=88`
    - `steps.scrape.nfo_written=22`
  - 随后再次只读 `dry-run` 回看：
    - `folder_type` 仍为 `tv`
    - `tmdb_match` 仍为 `existing_nfo`
    - `analyze.structure_ops=0`
- 已继续收口回看 summary 的幂等口径
  - 根因：`scraper._scrape_tv_v3()` 之前把所有“可映射到集数”的视频都算进 `will_process`
  - 即使文件已经在目标季目录、目标位 episode NFO 已匹配，`actions` 里也仍无条件带 `move_to_season / write_episode_nfo / write_shadow`
  - 现已改为：
    - `move_to_season` 只在 `original_path != target_path` 时出现
    - `write_episode_nfo` 只在目标位 NFO 缺失或 `tmdb_id/season/episode/showtitle` 不匹配时出现
    - `will_process` 只统计核心动作：`move_to_season + write_episode_nfo`
  - 新增 `test_scraper_tv_dry_run_actions.py` 锁定：
    - 已在 `Season 01`
    - episode NFO 已匹配
    - dry-run 只剩 `write_shadow`
    - summary 收口为 `will_process=0 / files_to_move=0 / nfo_to_write=0 / shadows_to_fill=1`
  - 用当前工作区代码回看 `四月是你的谎言` 影子副本：
    - `summary.will_process=0`
    - `summary.nfo_to_write=0`
    - `summary.files_to_move=0`
    - `summary.shadows_to_fill=22`
  - 结论：主链路已经幂等收口；剩余的 `shadows_to_fill` 属于影子名补齐候选，不再代表结构或 NFO 执行残留
- 随后开始真实下载器异常小样本的只读观测
  - 本轮不人为停服务或注入故障，只利用现成真实任务做一次 `sync_progress` 观测
  - qB 样本：`99c57d47 / 集成测试片`
    - 观测前：`backend/download_tasks.json` 中仍是 `status=downloading`
    - 触发：访问 `/download-manager/progress`，后端内部执行一次 `sync_progress`
    - 观测后：任务回退为 `status=unknown`，`progress=0.0`，未误收口到 `completed`，也未触发归位/归档
    - 说明：真实 qB 异常或未命中场景下，当前主链路会保守回退，不会误推进
  - Alist 样本：`499b0bd2 / 妖精的旋律`
    - 观测前后均为 `status=unknown`、`phase=cloud_download`
    - 显式再调用一次 `/download-manager/sync` 后状态不变
    - 说明：现有真实异常样本下，Alist 不会误触发 `completed` 或自动归位
  - 当前不足：
    - 这轮只证明了“异常期间不误收口”
    - 还没有拿到“异常解除后恢复推进”的真实样本
- 随后补了场景 C 的最小代码收口
  - 真实观测暴露出根因：`DownloadManager.sync_progress()` 只轮询 `status == downloading`
  - 这意味着任务一旦因 qB / Alist 短时异常被打成 `unknown`，后续即使下载器恢复，也没有任何自动恢复入口
  - 本轮最小修复：
    - `sync_progress()` 改为同时轮询 `downloading + unknown`
    - 允许 `unknown -> completed` 时继续触发 `_relocate_to_save_path()` 和订阅完成回调
  - 新增保护测试：
    - `test_sync_progress_retries_unknown_qb_task_and_finishes_recovery_flow`
    - `test_sync_progress_retries_unknown_alist_task_until_it_recovers_to_downloading`
  - 本地验证：
    - `python -X utf8 -m pytest backend/test_download_manager_relocate_flow.py -k "sync_progress"`
    - 结果：`9 passed`
  - 当前结论：
    - “异常后永远停在 unknown” 这一恢复缺口已在代码层收口
    - 还差一笔真实环境样本，证明下载器恢复后状态能真实回推进
- 随后补了独立端口的真实恢复实证
  - 现网 `8000` 仍是旧进程：对同一批 `unknown` 任务执行 `/download-manager/sync` 后，`updated_at` 完全不变，说明没有进入新逻辑
  - 为避免打断现网，临时起当前工作区代码到 `127.0.0.1:8014`
  - 观测样本：
    - qB：`99c57d47 / e1927935 / 156f7e94 / 9e17d995 / 12ac52c5 / c3e3b147 / fa9beea5 / 6500e314`
    - Alist：`499b0bd2`
  - 在 `8014` 上执行一次真实 `/download-manager/sync` 后：
    - `99c57d47`：`unknown -> completed`
    - `156f7e94`：`unknown -> completed`
    - `9e17d995`：`unknown -> completed`
    - `12ac52c5`：`unknown -> completed`
    - `c3e3b147`：`unknown -> completed`
    - `e1927935 / fa9beea5 / 6500e314`：仍为 `unknown`，但 `progress/updated_at` 已刷新，说明恢复轮询生效，只是下载器当前状态还不足以收口
    - `499b0bd2`：仍为 `unknown + cloud_download`，`updated_at` 已刷新，说明 Alist 也会继续重试
  - 额外观测：
    - `99c57d47` 在恢复到 `completed` 后，后台真实触发了 `download_complete` 通知
    - 当前运行日志出现 `notification_service` 的 Pydantic 序列化 warning，但不阻断这轮恢复验证；后续如要收口通知层，再单独开任务
  - 当前结论：
    - 场景 C 已拿到真实 qB “异常解除后恢复推进”的证据
    - Alist 仍缺“从 unknown 恢复到 downloading/completed”的真实样本
- 随后继续追 Alist 环境阻塞点，并把现象收窄到离线下载管理接口本身
  - 使用 `backend/config.json` 里的现有 `alist_url + alist_token` 做直连核对
  - 同一 token 下：
    - `GET /api/admin/storage/list` 返回 `200 + application/json`
    - `POST /api/fs/list` 返回 `200 + application/json`
    - `POST /api/admin/task/offline_download/undone` 返回 `200 + text/html`
    - `POST /api/admin/task/offline_download/done` 返回 `200 + text/html`
  - 返回体前缀是 HTML 登录页，不是 Alist API JSON
  - 这说明当前环境里，问题不再是 `sync_progress()` 没有继续轮询 Alist `unknown` 任务，而是“离线下载管理接口本身对这套鉴权/路由不返回 JSON”
  - 因此本轮对 Alist 的真实结论只能收口为：
    - `499b0bd2` 这类 `unknown + cloud_download` 任务在当前代码下会继续进入重试分支
    - 但由于 `offline_download` 管理接口当前不可用，暂时拿不到“恢复到 downloading/completed”的真实环境样本
  - 后续若要继续场景 C，应该先单独排查 Alist 的 `offline_download` 管理接口访问条件，再回到恢复验证
- 随后已定位到真正根因并完成最小代码修复
  - 查 AList V3 当前文档与本机实例行为后确认：
    - 正确任务接口是 `GET /api/task/offline_download/undone`
    - 正确任务接口是 `GET /api/task/offline_download/done`
    - 旧代码误写成了 `POST /api/admin/task/offline_download/...`
  - 这解释了为什么同一 token 能访问 `storage/list`、却在旧路径上只拿到前端 HTML：不是鉴权错，而是路由打错
  - 本轮最小修复：
    - `download_manager._sync_alist_progress()` 改为走官方 `GET /api/task/offline_download/*`
    - Alist 进度值改为兼容 `0-1` 与 `0-100` 两种口径
    - Alist 完成态兼容 `2 / succeeded / completed / done`
    - 匹配规则从“只看完整 download_url”放宽到“download_url、task.id、downloader_hash、download_url 里的 file 文件名”
  - 新增 / 调整隔离保护：
    - Alist 同步相关测试全部切到 `requests.get`
    - 新增“通过 `download_url?file=` 文件名命中 done 列表任务名”的保护样本
  - 本地验证：
    - `python -X utf8 -m pytest backend/test_download_manager_relocate_flow.py -k "sync_alist_progress or sync_progress"`
    - 结果：`24 passed`
  - 当前结论更新为：
    - Alist 之前的 `unknown` 长尾并不只是环境问题，旧代码确实在任务查询路径上有 bug
    - 代码层收口后，下一步应回到独立实例做真实样本复测，确认 `499b0bd2` 这类任务是否能恢复推进
- 随后已在独立 `8014` 当前代码实例上做真实复测
  - 触发方式：`GET /download-manager/progress`
  - 样本：`499b0bd2 / 妖精的旋律`
  - 复测前：
    - `status=unknown`
    - `phase=cloud_download`
    - `error=""`
  - 复测后：
    - `status=lost`
    - `phase=cloud_download`
    - `error="Alist 中未找到对应任务"`
  - 这说明修复后的行为符合当前代码设计：
    - 旧代码因为打错 `/api/admin/task/...`，一直把“查不到真实任务”伪装成 `unknown`
    - 新代码改走 `GET /api/task/offline_download/*` 后，`done/undone` 都为空，于是这笔样本被真实收口到 `lost`
  - 当前结论再收窄一步：
    - `499b0bd2` 不是“等待恢复的 Alist unknown 样本”
    - 它是“旧错误路径掩盖下的实际失联样本”
    - 如果后续还要验证 Alist 的“异常解除后恢复推进”，需要重新找一笔仍存在于 Alist 任务列表里的真实样本
- 随后继续补了 Alist 提交链的真实任务标识缺口
  - 继续只读核对当前环境时发现：
    - 真实 `GET /api/task/offline_download/undone` 返回 `[]`
    - 真实 `GET /api/task/offline_download/done` 返回 `[]`
    - 当前后端任务列表里只剩 1 笔 Alist 历史任务：`499b0bd2`
  - 这说明下一轮真实恢复验证已经不缺“查询路径”，缺的是“提交时是否保存了真实 Alist tid”
  - 继续读代码后确认：
    - `downloader.AlistManager.transfer_link()` 之前只返回 `bool`
    - `download_manager._push_to_alist()` 因此只能伪造 `alist_{task.id}`
    - 即使 Alist 返回了真实任务列表，旧代码也会把真实 tid 丢掉
  - 本轮最小修复：
    - `transfer_link()` 改为返回 `(success, task_id)`
    - 从 `add_offline_download` 返回体里优先提取 `data.tasks[].id` / `data.task.id` / `data.id`
    - `_push_to_alist()` 优先落真实 tid，拿不到时才回退 `alist_{task.id}`
    - 路由层兼容新的返回结构，只继续读取成功位
  - 新增 / 调整隔离保护：
    - 新增 `test_downloader_alist.py`，锁定 `transfer_link()` 能从返回体提取 tid
    - `test_download_manager_relocate_flow.py` 新增“优先保存真实 tid / 缺失时回退旧 marker”保护
  - 本地验证：
    - `python -X utf8 -m pytest backend/test_downloader_alist.py backend/test_download_manager_relocate_flow.py -k "alist or sync_progress"`
    - 结果：`35 passed`
  - 当前结论更新为：
    - Alist 查询链和提交链两侧已都对齐到 AList V3 的真实接口/标识模型
    - 当前缺的已不再是代码路径，而是新的真实 Alist 活跃样本
- 随后继续把“真实 tid”真正接进同步链
  - 既然提交链已经能保存真实 Alist tid，仅靠 `done/undone` 全量列表再猜任务名就不够了
  - 本轮最小收口：
    - `download_manager._sync_alist_progress()` 先尝试 `POST /api/task/offline_download/info?tid=...`
    - 只有当 `downloader_hash` 还是历史伪标识 `alist_*`，或 `info` 查不到任务时，才回退到 `GET /api/task/offline_download/undone|done`
    - `info` 命中后：
      - 完成态直接按 `state` + 本地文件存在性收口到 `completed/local_sync`
      - 非完成态继续留在 `cloud_download`
  - 新增 / 调整隔离保护：
    - “真实 tid 命中 info 后不再扫列表”
    - “真实 tid 查不到时回退列表扫描”
    - “历史 `alist_*` 伪标识不误打 info”
    - 同时把测试基线调成：Alist 历史任务默认 `downloader_hash=alist_{task.id}`
  - 本地验证：
    - `python -X utf8 -m pytest backend/test_download_manager_relocate_flow.py -k "sync_alist_progress or sync_progress"`
    - 结果：`27 passed`
    - `python -X utf8 -m pytest backend/test_downloader_alist.py backend/test_download_manager_relocate_flow.py -k "alist or sync_progress"`
    - 结果：`38 passed`
  - 当前结论再收紧一步：
    - 现在 Alist 的提交链、单任务查询链、列表回退链都已对齐
    - 场景 C 继续往前推进时，已经可以明确区分：
      - 真实 tid 任务本身的状态
      - 历史伪标识任务的兼容回退
      - 真正已经失联的样本
- 随后对工作区大文件做了一轮收口清理，并调整后续验证策略
  - 触发背景：
    - 仓库工作区一度接近 `100 GB`
    - 主要来源不是代码，而是：
      - `shadow-verify` 重视频副本约 `45.64 GB`
      - `.git` loose objects / garbage 约 `32 GB`
      - `backend/recycle_bin` 真实回收残留约 `6.88 GB`
  - 已执行的清理：
    - 删除 `shadow-verify`
    - 删除 `backend/recycle_bin`
    - 删除 `.pytest_cache`、`backend/.pytest_cache`、`frontend/.next` 与一批临时目录
    - 执行 `git gc --prune=now`
  - 清理后工作区目录体积回落到：
    - `frontend` 约 `0.46 GB`
    - `backend` 约 `33 MB`
    - `.git` 约 `7 MB`
  - 这轮清理不改业务代码，但会带来一个明确约束：
    - 旧的重视频 `shadow-verify` 样本和 `recycle_bin` 历史验证残留已不可复用
    - 后续新对话继续这条主线时，不要再回到“复制真实大视频文件”的影子验证方案
  - 后续策略现已固定为：
    - 默认影子验证只保留真实文件名、目录结构、NFO/字幕/海报等 sidecar
    - 视频主文件改成空文件或极小占位文件
    - 只有在必须验证真实 I/O 时，才单独引入 1 个真实样本
- 随后收口一轮由真实验证样本带出的前端 / 媒体库回归
  - 触发现象：
    - `军火女王`、`卡罗尔与星期二` 等真实样本在下载面板里已经是 `archived`，但前端没有 `archived` tab
    - 完成/归档态“查看”按钮发出的 `save_path` 是绝对 NAS 路径，首页原先按相对层级分段查找，导致无法命中媒体库树
    - 首页 `/library/tree` 首屏链路一度退化到分钟级，本地 `8000` 实测约 `22.3s`
  - 本轮最小修法：
    - `DownloadManagerPanel` 补回 `archived` tab
    - 归档态保留“查看”，只把“整理替换”留给 `completed/awaiting_confirm`
    - 首页跳转先按绝对路径精确命中树节点，再按 NAS base path 做兼容回退
    - `routes/library.py` 的树构建不再在首屏实时探测 `movie.nfo/tvshow.nfo` 并读取 NAS 上 NFO，而是只用缓存库数据和树内子节点信息补齐 `clean_name_*`
  - 本地验证：
    - `python -X utf8 -m pytest backend/test_library_tree.py`
    - 结果：`1 passed`
    - `frontend npm run build`
    - 结果：通过
    - `http://127.0.0.1:8000/library/tree`
    - 实测：约 `22.3s -> 7.8s`
    - `frontend npm run test -- home-library-path`
    - 当前环境噪声：`vitest` 启动阶段因 `spawn EPERM` 失败，未形成前端自动化结论
- 继续推进场景 C 时，真实 qB 又暴露出一个更细的恢复缺口
  - 先做只读环境核对：
    - `POST http://127.0.0.1:8000/download-manager/sync` 后，`99c57d47 / e1927935 / 6500e314 / fa9beea5` 的 `updated_at` 都会刷新
    - 但这四笔任务在 `8000` 上仍停在 `status=unknown`
    - 同时直连 qB API 只读核对确认：
      - `99c57d47` 真实状态是 `missingFiles`
      - `e1927935 / 6500e314 / fa9beea5` 真实状态是 `forcedDL`
    - 这说明“继续轮询 unknown”已经生效，但 `_sync_qb_progress()` 在“查到 torrent、只是尚未完成”这一分支没有把状态收回 `downloading`
  - 本轮最小修复：
    - 在 `download_manager._sync_qb_progress()` 中新增恢复逻辑：只要 qB 成功返回 torrent 且未命中完成态，就显式写回 `status=downloading`
    - 不改完成态、丢失态和异常态判定
  - 新增隔离保护：
    - `test_sync_qb_progress_recovers_unknown_task_to_downloading_for_missingfiles_state`
    - `test_sync_qb_progress_recovers_unknown_task_to_downloading_for_forceddl_state`
  - 本地验证：
    - `python -X utf8 -m pytest backend/test_download_manager_relocate_flow.py -k "sync_qb_progress or sync_progress"`
    - 结果：`23 passed`
  - 真实样本只读验证（不改 `8000` 现有进程，也不改任务文件）：
    - 用当前工作区代码直接对 `99c57d47 / e1927935 / 6500e314 / fa9beea5` 调 `_sync_qb_progress()`
    - 结果四笔样本都会从 `unknown` 恢复到 `downloading`
  - 独立 HTTP 端到端验证：
    - 临时起一份 `python -m uvicorn main:app --host 127.0.0.1 --port 8015`
    - 对 `8015` 执行 `POST /download-manager/sync` 后，再读 `/download-manager/tasks`
    - 同一批样本 `99c57d47 / e1927935 / 6500e314 / fa9beea5` 都已恢复为 `status=downloading`
    - 验证后已立即关闭 `8015` 进程，未改动现有 `8000`
  - 本轮剩余阻塞：
    - Alist 当前 `GET /api/task/offline_download/undone` 与 `done` 都为空
    - 因此场景 C 还缺一笔“真实仍活着的 Alist 任务”来验证 `unknown -> downloading/completed`
- 随后直接补造了场景 C 所需的第一笔真实 Alist 活跃样本
  - 提交方式：
    - 不动现有 `8000`，临时起当前工作区代码到 `127.0.0.1:8016`
    - 复用历史 Alist 样本 `499b0bd2` 的真实下载 URL，通过 `/download-manager/submit` 新建 1 笔最小任务
  - 提交结果：
    - 新任务 ID：`85499bc0`
    - 真实 `downloader_hash`：`5xvyCPXpAe5J9_HTL7Kxb`
    - 初始状态：`downloading + cloud_download`
  - 第一轮真实同步现象：
    - 连续 4 次 `POST /download-manager/sync` 后，该任务都会退回 `unknown + cloud_download`
    - 但通过只读直连 Alist API 核对可确认：
      - `GET /api/task/offline_download/done` 已能查到同一个 tid
      - `POST /api/task/offline_download/info?tid=5xvyCPXpAe5J9_HTL7Kxb` 返回 `200 + data=dict`
      - 返回内容包含：`state=7`、`error="http status code 429"`
    - 这说明真实任务并没有“查不到”，而是代码把 `info.data` 的结构读错了
  - 根因定位：
    - `_sync_alist_progress_by_task_id()` 之前假定 `payload.data` 一定是列表，直接取 `items[0]`
    - 真实接口返回的是单个对象 dict，于是命中真实 tid 后抛异常，再被外层吞成 `status=unknown`
  - 本轮最小修复：
    - 兼容 `info.data` 为 dict 或 list 两种结构
    - 当真实 tid 命中且任务尚未完成时，显式把状态收回 `downloading`，而不是保留旧的 `unknown`
  - 新增隔离保护：
    - `test_sync_alist_progress_accepts_dict_payload_from_real_task_info`
  - 本地验证：
    - `python -X utf8 -m pytest backend/test_download_manager_relocate_flow.py -k "sync_alist_progress or sync_progress"`
    - 结果：`28 passed`
  - 独立 HTTP 端到端回归：
    - 临时起 `127.0.0.1:8018`
    - 对同一任务执行 `POST /download-manager/sync`
    - 回读 `/download-manager/tasks` 后，`85499bc0` 已收口为：
      - `status=downloading`
      - `phase=cloud_download`
      - `error=http status code 429`
    - 说明当前代码已能正确表达“真实任务存在，但下载器返回 429”，而不会再误退成 `unknown`
  - 当前结论：
    - 场景 C 现在已经拿到第一笔真实 Alist 活跃样本
    - 这笔样本没有恢复到 `completed`，但已证明“真实 Alist 活跃任务 + 错误返回”不会误收口，也不会再因结构兼容问题退成 `unknown`
- 随后继续对这笔真实 Alist 样本做只读上游核对，确认 `429` 的真实来源
  - 直接在本机对 `85499bc0.download_url` 发起普通 `GET`，结果同样返回 `429`
  - 返回体不是 HTML，而是 Prowlarr 的 XML 错误：
    - `Indexer is disabled till 2026/4/28 19:05:12 due to recent failures.`
  - 更换 `User-Agent / Accept / Referer` 后结果不变，说明不是请求头姿势问题
  - 结论收口：
    - 当前这笔 Alist 活跃样本的剩余问题，不再是 DownloadManager/Alist 同步链路错误
    - 它是上游 Prowlarr 索引器自身进入冷却窗口，导致 `/download?...` 链接本身不可用
    - 因此当前代码能做到的正确行为就是：
      - 保持任务在 `downloading + cloud_download`
      - 暴露真实错误 `http status code 429`
      - 不误收口到 `completed/lost/unknown`

---

## 关联存档点

- 远端分支：`origin/codex-relocate-baseline-checkpoint`
- 提交：`6195eeb` `测试: 补强下载归位闭环验证`

---

## 2026-04-28 补记：归档执行层遗漏 `Subs/Fonts` 跟随归位

- 触发背景：
  - 用户基于真实样本 `卡罗尔与星期二`、`军火女王` 复核下载→归位结果时，确认“新视频替掉旧视频”已经发生
  - 但归档后新资源里的字幕、字体等附属目录没有跟着进入目标季目录
  - 同时 `军火女王` 的双季包还暴露出“附属目录失去季上下文后被误并”的风险
- 根因定位：
  - 自动归档仍走 `download_manager -> file_relocator.confirm_replace() -> routes.organize._apply_action_plan_moves()` 这条执行链
  - 其中 `_apply_action_plan_moves()` 之前只会处理两类文件：
    - 视频本体
    - 与视频同 basename 的 `.nfo / -poster / -thumb / -fanart / 字幕`
  - 白名单里那些“未进 plan、但确实属于新下载资源”的附属文件（例如 `Subs/*.ass`、`Fonts/*.ttf`）只会在 dry-run 树里展示，不会真正落盘
- 本轮最小修法：
  - 给 `_apply_action_plan_moves()` 增加 `base_path + whitelist` 上下文
  - 执行时把白名单中的未处理文件再次过一遍，按下面规则决定落点：
    - 先看它是否处在某个已知源季目录下面；若是，则保留相对层级并归到对应 `Season XX`
    - 再看文件名或路径里是否能解析出季号；若能，则归到对应 `Season XX`
    - 若整个包只有 1 个目标季，则把剩余附属文件默认并入这个季（等价于默认 `Season 01`）
    - 多季且无法判季的共享资源暂不瞎搬，避免再次误并
- 新增隔离验证：
  - `test_apply_action_plan_moves_moves_single_season_extra_dirs_from_whitelist_into_target_season`
  - `test_apply_action_plan_moves_routes_multi_season_extra_dirs_by_source_season_folder`
  - 连同既有回归一起执行：
    - `python -X utf8 -m pytest backend/test_organize_action_plan_execute.py backend/test_relocate_routes.py backend/test_file_relocator_conflicts.py`
    - 结果：`42 passed`
- 当前结论：
  - 这次修的是“执行层漏搬 sidecar/附属目录”的根因，不是前端展示问题
  - 后续如果再出现“多季共享 Fonts 根目录也要复制到各季”这类更激进规则，需要基于真实样本再单独确认，不在本轮最小修复范围内
