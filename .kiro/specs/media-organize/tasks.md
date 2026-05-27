# 实施计划：媒体库整理功能补全 (media-organize)

## 概述

基于设计文档和需求文档，将后端 7 项 P0 任务（快照修复、season.nfo 刮削、CD 分片合并验证、散落季合并执行、刮削候选补 english_title、统一清洗逻辑、刮削搜索词优化）和前端 6 项 P0 任务（SeriesCollectionList、MovieCollectionGrid、TvDetail、DetailDrawer 分发、CandidatePicker/ScrapeInfo 英文名显示）拆分为可执行的编码任务。

## 任务列表

- [x] 1. 后端：快照/回滚机制修复 (organize_history.py + organizer.py)
  - [x] 1.1 增强 OrganizeHistory.create_snapshot 支持 label 和 is_dir 字段
    - 修改 `backend/organize_history.py` 的 `create_snapshot` 方法，新增 `label: str = ""` 参数
    - 每条操作记录增加 `is_dir: bool` 字段，区分文件和目录操作
    - 快照 JSON 结构增加 `label` 字段（"organize" / "rename" / "scrape" / "merge_seasons"）
    - _需求: 1.2, 1.3_

  - [x] 1.2 增强 OrganizeHistory.rollback 支持目录回滚和空目录清理
    - 修改 `backend/organize_history.py` 的 `rollback` 方法
    - 按操作逆序执行回滚，支持 `is_dir=True` 的目录移动回退
    - 回滚完成后检测并清理由整理操作创建的空目录
    - 文件不存在时标记为 failed 并继续回滚其余操作
    - 返回 `{"success": [...], "failed": [...]}`
    - _需求: 2.1, 2.2, 2.3, 2.4_

  - [x] 1.3 增强 OrganizeHistory.list_snapshots 支持 limit 参数
    - 修改 `backend/organize_history.py` 的 `list_snapshots` 方法，新增 `limit: int = 20` 参数
    - 返回按时间倒序排列的快照列表
    - _需求: 1.4_

  - [x] 1.4 在 organizer.organize_folder 中自动创建快照
    - 修改 `backend/organizer.py` 的 `organize_folder` 函数
    - 当 `dry_run=False` 且有实际操作时，调用 `history_m.create_snapshot(ops, label="organize")`
    - 每条 op 记录标注 `is_dir` 字段
    - _需求: 1.1, 1.2, 1.3_

  - [ ]* 1.5 编写快照创建与回滚的单元测试
    - 在 `backend/` 下创建 `test_organize_history.py`
    - 测试 create_snapshot 含 label/is_dir 字段
    - 测试 rollback 逆序执行、空目录清理、文件不存在时 failed 标记
    - 测试 list_snapshots 的 limit 参数和倒序排列
    - **Property 1: 快照自动创建与结构完整性**
    - **Property 2: 快照回滚对称性**
    - **Property 13: 快照列表排序**
    - **验证: 需求 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4**

- [x] 2. 后端：season.nfo 刮削 (scraper.py)
  - [x] 2.1 在 scrape_folder 递归中增加季目录 season.nfo 写入逻辑
    - 修改 `backend/scraper.py` 的 `scrape_folder` 函数
    - 当递归处理 tv 类型文件夹的季子目录时：
      - 识别季目录（`_is_season_dir`）并提取季号（`_extract_season_number`）
      - 从父目录的 tvshow.nfo 读取 tmdb_id
      - 调用 `tmdb_client.get_season_detail(tv_id, season_num)` 获取季详情
      - 调用 `write_season_nfo(season_dir, season_detail)` 写入 season.nfo
      - 下载季封面到 `season_dir/poster.jpg`
      - 跳过已有 season.nfo 的目录（除非 force=True）
      - 确保 seasonnumber 字段值与目录名提取的季号一致
      - TMDB API 错误时记录日志并继续处理下一个季目录
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 2.2 编写 season.nfo 刮削的属性测试
    - **Property 3: season.nfo 完整性与一致性**
    - Mock TMDB 客户端，验证每个季目录都有 season.nfo
    - 验证 seasonnumber 字段值与目录名季号一致
    - 验证 season.nfo 包含 seasonnumber、title、plot、aired 字段
    - **验证: 需求 3.2, 3.3, 3.4, 3.6**

- [x] 3. 检查点 — 确保后端快照和 season.nfo 测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [x] 4. 后端：CD 分片合并执行验证 (organizer.py)
  - [x] 4.1 验证并修复 organize_folder 中 CD 分片的关联文件移动逻辑
    - 审查 `backend/organizer.py` 的 `organize_folder` 中 `_find_associated_files` 函数
    - 确保 CD 分片的关联文件匹配规则正确：仅匹配以 CD 文件基础名开头的文件
    - 确保同组 CD 文件（CD1、CD2）移入同一目标文件夹
    - 确保目标文件夹名由 `_clean_filename_for_folder` 生成
    - 如有 bug 则修复
    - _需求: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 4.2 编写 CD 分片合并的属性测试
    - **Property 4: CD 分片合并完整性**
    - 测试同组 CD 文件及关联文件都在同一目标文件夹
    - 测试非 CD 关联的同名文件不被错误移动
    - **验证: 需求 4.1, 4.2, 4.3, 4.4**

- [x] 5. 后端：散落季合并执行 (organizer.py + main.py)
  - [x] 5.1 在 organizer.py 中新增 merge_scattered_seasons 函数
    - 在 `backend/organizer.py` 中新增 `merge_scattered_seasons(scattered_issue: Dict, dry_run: bool = True) -> Dict`
    - 接收 analyzer 产出的 `scattered_seasons` issue
    - `dry_run=True` 时返回预览操作列表，不修改文件系统
    - `dry_run=False` 时：
      - 以 `core_name` 创建父目录（如不存在）
      - 将所有散落季目录移入父目录
      - 目标已存在同名子目录时跳过并标记 skip
      - 保留已有的 tvshow.nfo 不覆盖
    - 创建快照（label="merge_seasons"）
    - _需求: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 5.2 在 main.py 中新增 /organize/merge-seasons API 端点
    - 新增 `POST /organize/merge-seasons` 端点
    - 接收 `path`（媒体库根路径）和 `dry_run` 参数
    - 调用 `analyzer.analyze_library` 获取 `cross_folder_issues`
    - 对每个 `scattered_seasons` issue 调用 `merge_scattered_seasons`
    - 返回合并结果
    - _需求: 5.1_

  - [ ]* 5.3 编写散落季合并的属性测试
    - **Property 5: 散落季合并正确性**
    - **Property 6: 散落季 dry_run 无副作用**
    - 测试 dry_run 模式返回正确的 ops 列表且文件系统不变
    - 测试执行后所有季目录位于同一父目录
    - **验证: 需求 5.2, 5.3, 5.5**

- [x] 6. 后端：刮削候选补 english_title (main.py + tmdb_client.py)
  - [x] 6.1 修改 /scrape/candidates 端点为每个候选项补充 english_title
    - 修改 `backend/main.py` 的 `scrape_candidates` 函数
    - 对每个候选项：
      - 如果 `original_title` 为拉丁字符（`_is_latin`），直接用作 `english_title`
      - 否则调用 `client._get_english_title(media_type, tmdb_id, original_title)` 获取
      - TMDB 限流时 `english_title` 设为空字符串，不阻塞其他候选项
    - 每个候选项返回中包含 `english_title` 字段
    - _需求: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 6.2 编写 english_title 候选项的属性测试
    - **Property 7: english_title 候选项完整性**
    - Mock TMDB 客户端，验证所有候选项都有 english_title 字段
    - 验证拉丁字符 original_title 直接作为 english_title
    - **验证: 需求 6.1, 6.2**

- [x] 7. 后端：统一清洗逻辑 + 刮削搜索词优化 (organizer.py + main.py)
  - [x] 7.1 修改 generate_standard_name 复用 _clean_filename_for_folder
    - 修改 `backend/organizer.py` 的 `generate_standard_name` 函数
    - 当没有刮削数据时，优先用 `_clean_filename_for_folder(filename)` 清洗
    - 清洗结果为空时回退到 `parse_filename` 的 `clean_name` 或 `folder_title`
    - _需求: 7.1, 7.2, 7.3_

  - [x] 7.2 修改 /scrape/candidates 搜索词构造使用 _clean_filename_for_folder
    - 修改 `backend/main.py` 的 `scrape_candidates` 函数的搜索词构造逻辑
    - 优先用 `_clean_filename_for_folder(name)` 清洗后的结果作为搜索词
    - 清洗结果为空或长度不足 2 字符时回退到 `parse_filename` 的 `clean_name`
    - `clean_name` 也不足时使用去扩展名的原始名
    - _需求: 8.1, 8.2, 8.3_

  - [ ]* 7.3 编写清洗逻辑和搜索词优化的属性测试
    - **Property 8: 清洗函数统一使用与幂等性**
    - **Property 9: 搜索词清洗降级链**
    - 测试 `_clean_filename_for_folder` 幂等性
    - 测试搜索词降级链：clean → parse_filename → 原始名
    - **验证: 需求 7.1, 7.3, 8.1, 8.2, 8.3**

- [x] 8. 检查点 — 确保所有后端任务测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [x] 9. 前端：types/index.ts 类型扩展
  - [x] 9.1 扩展 OrganizeSnapshot 类型支持 label 和 is_dir
    - 修改 `frontend/types/index.ts` 的 `OrganizeSnapshot` 接口
    - ops 中每条记录增加 `is_dir?: boolean` 字段
    - 顶层增加 `label?: string` 字段
    - _需求: 1.2, 1.3_

  - [x] 9.2 新增 ScrapeCandidate 类型包含 english_title
    - 在 `frontend/types/index.ts` 中新增 `ScrapeCandidate` 接口
    - 包含 `tmdb_id`, `media_type`, `title`, `original_title`, `english_title`, `year`, `overview`, `poster_url`, `popularity` 字段
    - _需求: 6.1_

- [x] 10. 前端：SeriesCollectionList 组件 (新建)
  - [x] 10.1 创建 SeriesCollectionList 组件
    - 新建 `frontend/components/detail/SeriesCollectionList.tsx`
    - Props: `node: FolderNode`, `onSelectItem: (video: VideoInfo) => void`, `selectedPath: string | null`
    - 布局：每个子项显示小封面（60px 宽）、标题、年份和时长
    - 点击子项触发 `onSelectItem` 回调并高亮选中项
    - 首次渲染默认不选中任何子项
    - 从 `node.children`（子文件夹）或 `node.videos`（直接视频）获取子项列表
    - 每个子项的封面通过 `api.getLocalPoster(path)` 加载
    - _需求: 10.1, 10.2, 10.4_

- [x] 11. 前端：MovieCollectionGrid 组件 (新建)
  - [x] 11.1 创建 MovieCollectionGrid 组件
    - 新建 `frontend/components/detail/MovieCollectionGrid.tsx`
    - Props: `node: FolderNode`, `onSelectItem: (video: VideoInfo) => void`
    - 布局：2 列网格排列子项，每个卡片显示独立封面和标题
    - 点击卡片触发 `onSelectItem` 回调进入子项详情
    - 封面固定（不跟随选中项）
    - _需求: 11.1, 11.2, 11.3_

- [x] 12. 前端：TvDetail 组件 (新建)
  - [x] 12.1 创建 TvDetail 组件
    - 新建 `frontend/components/detail/TvDetail.tsx`
    - Props: `node: FolderNode`, `onRefresh: () => void`, `onSearch: (q: string) => void`
    - 从 `node.children` 提取季子目录
    - 有季子目录时：显示季 tab 切换界面 + 对应季的集列表
    - 无季子目录但有视频时：单季模式直接显示集列表，不显示 tab
    - 切换季 tab 时更新集列表和封面为当前季内容（封面跟随当前季）
    - 季封面从季目录的 poster.jpg 加载（通过 `api.getLocalPoster`）
    - _需求: 12.1, 12.2, 12.3, 12.4_

- [x] 13. 前端：DetailDrawer folder_type 分发 (修改现有)
  - [x] 13.1 修改 FolderDetail 按 folder_type 分发到对应展示组件
    - 修改 `frontend/components/detail/DetailDrawer.tsx` 的 `FolderDetail` 函数
    - 读取 `node.folder_type`，根据类型分发：
      - `"movie"` → 保持当前 FolderDetail 逻辑（MovieDetail）
      - `"tv"` → 渲染 TvDetail 组件
      - `"series_collection"` → 渲染 SeriesCollectionList 组件 + 封面跟随选中子项
      - `"movie_collection"` / `"variety"` / `"misc"` → 渲染 MovieCollectionGrid 组件 + 封面固定
      - 空或未知值 → 回退到默认 FolderDetail 布局
    - 保留现有的操作按钮（搜索升级、刮削、一键整理等）
    - _需求: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 13.2 编写 folder_type 分发的属性测试
    - **Property 10: folder_type 分发正确性**
    - **Property 11: 封面跟随规则**
    - **验证: 需求 9.1-9.5, 10.3, 11.3**

- [x] 14. 前端：CandidatePicker 和 ScrapeInfo 英文名显示 (修改现有)
  - [x] 14.1 修改 CandidatePicker 显示 english_title
    - 修改 `frontend/components/detail/DetailDrawer.tsx` 中的 CandidatePicker 组件
    - 候选列表每项增加 english_title 显示
    - 当 `english_title` 存在且不等于 `title` 时，在标题下方显示 english_title（text-xs text-slate-500）
    - 当 `english_title` 为空或等于 `title` 时不显示
    - _需求: 13.1, 13.2, 13.3_

  - [x] 14.2 修改 ScrapeInfo 显示 english_title
    - 修改 `frontend/components/detail/DetailDrawer.tsx` 中的 ScrapeInfo 组件
    - 在标题信息中增加 english_title 显示
    - 显示逻辑与 CandidatePicker 保持一致
    - _需求: 14.1, 14.2, 14.3, 14.4_

  - [ ]* 14.3 编写 english_title 前端显示一致性测试
    - **Property 12: english_title 前端显示一致性**
    - **验证: 需求 13.2, 13.3, 14.2, 14.3, 14.4**

- [x] 15. 前端 API 层补充
  - [x] 15.1 在 api.ts 中新增 merge-seasons API 调用
    - 修改 `frontend/lib/api.ts`
    - 新增 `mergeScatteredSeasons: (path: string, dryRun: boolean) => ...` 方法
    - 调用 `POST /organize/merge-seasons?path=...&dry_run=...`
    - _需求: 5.1_

- [x] 16. 最终检查点 — 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

## 备注

- 标记 `*` 的任务为可选测试任务，可跳过以加速 MVP
- 每个任务引用了具体的需求编号，确保可追溯
- 检查点确保增量验证
- 属性测试验证设计文档中的 Correctness Properties
- 单元测试验证具体示例和边界情况
