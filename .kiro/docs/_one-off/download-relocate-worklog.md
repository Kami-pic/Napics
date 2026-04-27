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

---

## 关联存档点

- 远端分支：`origin/codex-relocate-baseline-checkpoint`
- 提交：`6195eeb` `测试: 补强下载归位闭环验证`
