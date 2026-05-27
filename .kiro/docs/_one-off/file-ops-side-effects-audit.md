# [一次性] 文件操作入口与副作用盘点

> 对应 TODO：`.kiro/docs/file-ops-test-baseline-todo.md` 阶段 1。  
> 本轮只盘点，不修改业务逻辑、不移动文件、不做目录重组。

---

## 1. 盘点范围

本轮用静态搜索覆盖以下副作用调用：

- `os.rename` / `os.remove` / `os.replace`
- `shutil.move` / `shutil.copy2` / `shutil.copytree`
- `RecycleBin.move_to_bin` / `restore` / `cleanup_expired`
- `config_m.save_library`
- `write_movie_nfo` / `write_tvshow_nfo` / `write_episode_nfo` / `write_season_nfo`
- `download_poster`
- `organize_history` snapshot / rollback

排除范围：

- `backend/_*.py` 历史调试脚本
- `backend/test_*.py` 测试文件自身的临时文件操作
- 非文件副作用的普通 JSON 缓存写入，如 AI / 搜索缓存

---

## 2. 入口 × 副作用矩阵

| 入口 | 主要代码 | 文件 rename/move/delete | NFO 同步 | poster/fanart 同步 | media_library 更新 | recycle_bin 记录 | organize_history | download_tasks 状态 | 当前测试覆盖 | 风险等级 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 手动重命名 | `routes/rename.py::rename_item` | 是：文件/文件夹 `os.rename` | 是：同名前缀 `.nfo` | 是：同名前缀海报/图 | 是：`config_m.save_library` | 否 | 否 | 否 | 路由注册/旧 API 测试为主，缺少副作用矩阵测试 | 高 |
| 批量删除 | `routes/tools.py::batch_manage(delete)` | 是：通过回收站移动文件/目录 | 间接：随目录或单文件入回收站 | 间接：随目录或单文件入回收站 | 是：删除库记录 | 是：`move_to_bin` | 否 | 否 | 未看到专门覆盖批量删除副作用的正式测试 | 高 |
| 批量移动 | `routes/tools.py::batch_manage(move)` | 是：`shutil.move` 文件/目录/封装目录 | 是：散装文件同名前缀移动 | 是：散装文件同名前缀移动 | 是：路径重写后保存 | 否 | 否 | 否 | 未看到专门覆盖批量移动副作用的正式测试 | 高 |
| 批量复制 | `routes/tools.py::batch_manage(copy)` | 是：`copytree` / `copy2` | 间接：封装目录复制 | 间接：封装目录复制 | 否 | 否 | 否 | 否 | 未看到专门覆盖复制行为的正式测试 | 中 |
| 从库移除 | `routes/tools.py::batch_manage(remove)` | 否 | 否 | 否 | 是：移除记录 + excluded_paths | 否 | 否 | 否 | 未看到专门覆盖 remove/exclude 的正式测试 | 中 |
| 整理替换 dry-run | `routes/relocate.py::organize_dry_run` + `FileRelocator.relocate` | 否 | 否 | 否 | 否 | 否 | 否 | 否 | `test_relocate_routes.py` 覆盖错误分支/返回结构 | 中 |
| 确认替换 | `routes/relocate.py::organize_execute` + `FileRelocator.confirm_replace` | 是：旧资源入回收站，新资源执行整理 plan | 是：经 `organize_full` 写入 | 是：旧资源回收 + 新 poster 下载/移动 | 是：经 `_sync_library_paths` / shadow 写入 | 是：`_recycle_old_files` | 部分：整理执行链可能写 history | 是：成功后 `archive_task(organized=True)` | `test_file_relocator_conflicts.py` + `test_relocate_routes.py` 覆盖较强 | 最高 |
| 共存归档 | `routes/relocate.py::organize_archive_both` + `FileRelocator.archive_both` | 是：旧资源 `os.rename` 到 `[旧资源备份]` | 否 | 否 | 否 | 否 | 否 | 是：成功后归档任务 | `test_relocate_routes.py` 覆盖路由编排；文件实体覆盖有限 | 高 |
| 只清理旧资源 | `routes/relocate.py::organize_purge_old` | 是：旧资源回收 | 间接：`_recycle_old_files` 回收 NFO | 间接：`_recycle_old_files` 回收海报 | 否 | 是 | 否 | 否 | `test_relocate_routes.py` 覆盖防误删与 recycle 调用 | 高 |
| 一键整理执行 | `routes/organize.py::organize_full(dry_run=False)` | 是：wrap / action_plan / archive move/remove | 是：写 movie/tv/episode/season NFO | 是：下载 poster/fanart | 是：`_sync_library_paths`、shadow 写入 | 否 | 是：archive/wrap/structure 子链可能写 | 否 | `test_organize_action_plan_execute.py`、`test_subtitle_flatten.py`、`test_plan_tree_preview.py` 有重点覆盖 | 最高 |
| Action Plan 文件移动 | `organize_executor._apply_action_plan_moves` | 是：视频/字幕/附属文件 move，清理空壳目录 | 是：同名前缀 `.nfo` move | 是：同名前缀 poster/fanart move | 否：调用方负责 `_sync_library_paths` | 否 | 否 | 否 | `test_subtitle_flatten.py` 覆盖字幕/附属文件规则较强 | 高 |
| 结构整理 | `structure_organizer.reorganize_*` / `wrap_*` / `merge_*` | 是：move / rename_dir / remove | 是：部分关联文件移动 | 是：部分关联文件移动 | 调用方可能同步，函数自身不统一 | 否 | 是：部分执行后 `create_snapshot` | 否 | `test_code_split.py` 以导入/dry-run 为主，执行副作用覆盖不足 | 高 |
| 视频批量重命名 | `renamer.rename_videos_in_folder` | 是：视频和季目录 `os.rename` | 是：同名前缀 `.nfo` | 是：同名前缀 poster/fanart/thumb | 否：调用方负责保存 | 否 | 否 | 否 | `test_code_split.py` 覆盖生成逻辑，执行副作用覆盖不足 | 高 |
| 刮削选择写入 | `routes/scrape.py::_write_scrape_result` | 是：删除旧 NFO/poster | 是：写 movie/tv/episode NFO | 是：下载 poster/fanart | 是：单视频文件夹 shadow 写入 | 否 | 否 | 否 | `test_scraper_tv_dry_run_actions.py` 覆盖 TV dry-run；选择写入副作用覆盖不足 | 高 |
| 媒体详情重新匹配 | `routes/media_info.py` 相关写入函数 | 是：删除旧 NFO/poster | 是 | 是 | 不完全统一 | 否 | 否 | 否 | 详情匹配测试偏匹配逻辑，写盘副作用覆盖不足 | 中高 |
| 下载完成转移 | `download_manager._relocate_to_save_path` | 是：沙盒到 `save_path` 的 `shutil.move` | 间接：原样移动 | 间接：原样移动 | 是：后台局部刷新 `save_library` | 否 | 否 | 是：任务状态/持久化 | `test_download_manager_relocate_flow.py` 覆盖较强，但转移后库刷新仍需重点关注 | 高 |
| 回收站移动/恢复/清理 | `recycle_bin.py` | 是：`shutil.move` / `os.remove` | 间接：按文件/目录整体处理 | 间接：按文件/目录整体处理 | 否 | 是：集中元数据 | 否 | 否 | `test_recycle_bin.py` 覆盖动态落盘/恢复/过期清理 | 高 |
| 整理历史回滚 | `organize_history.py` | 是：`shutil.move` 回滚路径 | 间接：按记录整体回滚 | 间接：按记录整体回滚 | 否 | 否 | 是 | 否 | 未看到专门回滚链路强覆盖 | 高 |
| 海报上传/删除 | `routes/poster.py` | 是：删除/写入 poster 文件 | 否 | 是 | 可能通过前端树刷新体现 | 否 | 否 | 否 | 前端已有树刷新测试；后端文件副作用覆盖不清晰 | 中 |
| 发现页预入库 | `routes/discover.py::add_media` | 是：创建目录/写文件 | 是：写 movie NFO | 是：下载 poster | 可能依赖后续扫描 | 否 | 否 | 否 | 未看到该入口的文件副作用专门测试 | 中 |

---

## 3. 当前测试覆盖判断

覆盖较强：

- `test_file_relocator_conflicts.py`
  - 覆盖 `FileRelocator` 冲突探测、旧资源回收、取消替换、缺失旧文件、回收失败中止等。
- `test_relocate_routes.py`
  - 覆盖 `organize_execute` / `archive_both` / `purge_old` 的路由编排、防误删分支和 `archive_task` 调用。
- `test_recycle_bin.py`
  - 覆盖回收站默认落盘目录、目录回收、过期清理。
- `test_subtitle_flatten.py`
  - 覆盖 Action Plan 中字幕扁平化、附属文件提升、白名单路径解析。
- `test_organize_action_plan_execute.py`
  - 覆盖 Action Plan 执行后的视频/字幕/poster 目标落点。

覆盖不足：

- `routes/rename.py::rename_item`
  - 缺少“文件/文件夹重命名后，视频、NFO、poster、media_library 同步”的组合测试。
- `routes/tools.py::batch_manage`
  - 删除、移动、复制、remove 四类行为副作用大，但未看到专项测试矩阵。
- `structure_organizer.py`
  - dry-run 和导入覆盖较多，真实执行后的 history / sidecar / 路径同步覆盖不足。
- `renamer.py`
  - 标准名生成覆盖较多，真实 `dry_run=False` 文件副作用覆盖不足。
- `routes/scrape.py::_write_scrape_result`
  - 刮削写入、旧 NFO/poster 删除、单视频 shadow 写入缺少组合测试。
- `organize_history.py`
  - snapshot 清理和 rollback 文件移动缺少独立强覆盖。

---

## 4. 具体风险场景

### 场景 A：手动重命名漏同步 sidecar

入口：`routes/rename.py::rename_item`

如果视频 `Old.mkv` 被改成 `New.mkv`，但 `Old.nfo` / `Old-poster.jpg` 没同步改名：

- 详情页可能读不到视频级 NFO
- Jellyfin/Emby 类外部媒体库会把视频和元数据拆成两套
- `media_library.json` 记录看似正确，但磁盘 sidecar 仍停在旧名

当前风险：代码有同步逻辑，但异常被吞掉；缺少测试证明所有 sidecar 都被覆盖。

### 场景 B：批量移动只改文件，不改媒体库路径

入口：`routes/tools.py::batch_manage(move)`

如果 `shutil.move` 成功，但 `media_library.json` 的 `file_path` / `folder_name` 没同步：

- 首页树仍指向旧路径
- 详情页播放、刮削、搜索升级入口拿到旧路径
- 下次扫描可能出现重复记录或“旧记录 + 新记录”并存

当前风险：代码有 `path_map` / `dir_map` 更新，但封装文件夹、散装文件、同名 sidecar 三条路径分支复杂，缺少专项测试。

### 场景 C：确认替换漏回收 NFO 或 poster

入口：`FileRelocator.confirm_replace` / `_recycle_old_files`

如果只回收旧视频，没有回收旧 episode NFO / 同名 poster / season poster：

- 新旧资源元数据会混在同一目录
- 新视频可能展示旧封面或旧分集标题
- 用户以为“替换成功”，实际媒体库里残留旧资源证据

当前风险：该链路已有较强测试，但 `_recycle_old_files` 的目录级额外文件规则仍是高风险点，后续改动必须保持测试保护。

### 场景 D：整理执行移动文件后未同步 library

入口：`routes/organize.py::organize_full(dry_run=False)` / `_apply_action_plan_moves`

如果 Action Plan 把视频移动到 `Season 01`，但 `_sync_library_paths` 未覆盖某类 op：

- 文件实际存在于新位置
- 前端仍显示旧路径
- 完整性检测、搜索升级、刮削入口可能基于旧路径失败

当前风险：Action Plan 执行已有测试，但 `_sync_library_paths` 本身不是统一事务接口；后续新 op 类型很容易漏同步。

### 场景 E：回收站恢复不更新媒体库

入口：`recycle_bin.restore`

如果用户从回收站恢复文件，文件回到原始路径，但 `media_library.json` 没有对应记录：

- 文件在磁盘存在，前端仍看不到
- 需要额外扫描才能恢复视图

当前判断：这可能是当前设计选择，不一定是 bug；但应在矩阵中明确“restore 只恢复磁盘，不同步 library”，避免误以为它是完整撤销。

---

## 5. 最值得先补测试的入口

按风险和当前覆盖缺口排序：

1. `routes/tools.py::batch_manage(move/delete/remove/copy)`
   - 用户可直接触发，副作用最大，当前测试缺口明显。
   - 建议先补 move/delete 两类，不碰 copy。

2. `routes/rename.py::rename_item`
   - 手动重命名是高频入口，涉及视频、文件夹、sidecar、library 多联动。
   - 建议补两个样本：单视频电影文件夹、TV 分集文件。

3. `routes/scrape.py::_write_scrape_result`
   - 刮削选择会删除旧 NFO/poster 并写新数据。
   - 建议补单视频文件夹和分集文件两个样本。

4. `organize_history.py` rollback
   - 回滚是安全底座，但当前缺少强覆盖。
   - 建议在文件事务层前补最小 snapshot → rollback 测试。

---

## 6. 进入阶段 2 的建议

阶段 2 不应修业务测试，先分类测试噪声：

- 正式测试：`backend/test_*.py`
- 调试脚本：`backend/_test_*.py`、`backend/_check_*.py`、`backend/_debug_*.py`、`backend/_fix_*.py`、`backend/_verify_*.py`、`backend/_batch_*.py`

本轮已观察到 backend 根目录存在大量 `_` 前缀历史脚本，适合在阶段 2 中纳入 pytest ignore 方案；不要把它们当正式测试逐个修。

---

## 7. 结论

当前还不适合直接实现 `backend/core/file_ops/`。

原因：

- 文件副作用入口多于预期，且分布在 route、业务层、下载管理、回收站、刮削写入中。
- 最高风险链路已有一部分保护，但手动重命名和批量管理这种用户高频入口覆盖不足。
- 先补测试噪声治理，否则后续文件事务层迁移无法用完整测试闭环证明等价。

推荐下一步：

1. 进入阶段 2：测试噪声分类。
2. 阶段 3 只做 pytest 收集治理。
3. 之后优先补 `batch_manage` 和 `rename_item` 的副作用测试，再考虑局部文件事务层。
