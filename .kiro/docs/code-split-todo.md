# [TODO] 代码拆分清单

> 按优先级排序。前端 .tsx 上限 300 行，后端路由上限 400 行。
> 拆分原则：先拆后写，功能自洽的模块即使行数多也不强制拆。

## 前端（优先级高 → 低）

### 1. SearchModal.tsx — 855 行 ⚠️
- 搜索弹窗 + 结果列表 + 筛选面板 + 季级搜索 + 下载操作
- 建议拆为：SearchModal（入口）+ SearchResultList + SeasonSearchPanel + SearchActions

### 2. CardGrid.tsx — 573 行 ⚠️
- 卡片渲染 + 展开面板 + CardPoster + 系列合并 + 季展开
- 建议拆为：CardGrid（入口）+ CardPoster（独立）+ ExpandPanel + SeasonExpand

### 3. BatchUpgradePanel.tsx — 530 行 ⚠️
- 批量升级任务列表 + 结果展示 + 操作按钮 + 筛选
- 建议拆为：BatchUpgradePanel（入口）+ UpgradeTaskList + UpgradeResultRow

### 4. DoubanRecommend.tsx — 427 行 🗑️
- 已被 DiscoverPage 替代，标记废弃，已加入 .gitignore

### 5. DownloadManagerPanel.tsx — 364 行
- 下载列表 + 任务详情 + 操作按钮
- 可拆：DownloadTaskRow 独立

### 6. manage/page.tsx — 359 行
- 管理页面多个功能区
- 可拆：各功能区独立组件

### 7. SettingsModal.tsx — 341 行
- 多个设置分区（基础/搜索/下载/高级）
- 可拆：每个分区独立组件

### 8. search/FilterBar.tsx — 338 行
- 筛选条件较多
- 可拆：FilterGroup 独立

## 后端（优先级高 → 低）

### 9. organizer.py — 1862 行 ⚠️ [已完成 ✅]

当前职责混杂：分类判定 + 重命名 + 影子名生成 + 季目录整理 + 结构整理 + 归档。
拆为 3 个文件，organizer.py 保留分类核心 + 对外入口（约 550 行）。

#### 拆出 → renamer.py（重命名 + 影子名，约 570 行）
- [x] 迁移 `generate_standard_name()` — 标准文件名生成
- [x] 迁移 `_is_mostly_latin()` / `_extract_english_from_filename()` — 英文名提取辅助
- [x] 迁移 `rename_videos_in_folder()` — 重命名主逻辑
- [x] 迁移 `generate_shadow_name_from_nfo()` — 视频级影子名
- [x] 迁移 `generate_folder_shadow_name()` — 文件夹级影子名
- [x] organizer.py 顶部 re-export 保持对外兼容
- [x] 延迟导入 organizer 分类函数避免循环依赖

#### 拆出 → structure_organizer.py（季目录整理 + 结构整理 + 归档，约 780 行）
- [x] 迁移 `reorganize_seasons()` — 按 NFO 重组季目录
- [x] 迁移 `reorganize_seasons_by_nfo()` — 纯 NFO 驱动的季重组
- [x] 迁移 `wrap_loose_videos_in_category()` — 散落视频封装
- [x] 迁移 `organize_folder()` — 单文件夹整理入口
- [x] 迁移 `merge_scattered_seasons()` — 散落季合并
- [x] 迁移 `smart_archive_plan()` / `smart_archive_recursive()` / `execute_archive_plan()` — 归档三件套
- [x] organizer.py 顶部 re-export 保持对外兼容
- [x] 延迟导入 organizer 分类函数避免循环依赖

#### 验证
- [x] `python -c "import organizer; print('OK')"` 无报错
- [x] `python -c "from organizer import classify_folder, rename_videos_in_folder, reorganize_seasons, smart_archive_plan; print('OK')"` 兼容性检查
- [x] `python -c "from main import app; print('OK')"` 整个后端入口正常

### 10. routes/organize.py — 1306 行 ⚠️ [已完成 ✅]

拆为 3 个路由文件。

#### 拆出 → routes/relocate.py（归位替换路由，约 480 行）
- [x] 迁移 RelocateRequest / ExecuteRelocateRequest 数据模型
- [x] 迁移 _build_old_tree / _build_new_tree / _build_plan_tree 树构建辅助
- [x] 迁移 organize_dry_run / organize_execute / organize_archive_both / organize_purge_old

#### 拆出 → routes/analyze.py（分析路由，约 50 行）
- [x] 迁移 analyze_folder_api / analyze_library_api / classify_path

#### routes/organize.py 保留（约 800 行）
- [x] 重命名 + 整理 + 历史 + 流式整理

#### 验证
- [x] main.py 注册新路由
- [x] 20 个关键路由全部正确注册
- [x] 测试通过

### 11. routes/scrape.py — 1169 行 ⚠️ [已完成 ✅]

拆为 3 个路由文件。

#### 拆出 → routes/media_info.py（候选搜索 + 详情多源，约 450 行）
- [x] 迁移 scrape_candidates / scrape_douban_candidates / scrape_douban_select / scrape_bangumi_candidates / scrape_bangumi_select
- [x] 迁移 get_media_info / _try_douban_detail / _format_douban_detail / _try_bangumi_detail / _format_bangumi_detail / _try_tmdb_detail
- [x] 迁移 AddMediaRequest 数据模型

#### 拆出 → routes/poster.py（海报管理 + 图片代理，约 230 行）
- [x] 迁移 proxy_image / get_local_poster / upload_poster / set_poster_from_url / delete_poster

#### routes/scrape.py 保留（约 450 行）
- [x] 影子名 + 索引器优先级 + 刮削核心

#### 验证
- [x] main.py 注册新路由
- [x] 20 个关键路由全部正确注册
- [x] 测试通过

### 12. scraper.py — 1193 行 ⚠️ [已完成 ✅]

NFO 读写 + 海报下载 + 递归刮削混在一起。拆为 3 个文件，scraper.py 保留递归刮削主逻辑。

#### 拆出 → nfo_handler.py（NFO 读写，约 250 行）
- [x] 迁移 `read_nfo()`（L16-98）— 读取文件夹级 NFO
- [x] 迁移 `read_video_nfo()`（L99-139）— 读取视频级 NFO
- [x] 迁移 `_text()`（L140-145）— XML 文本提取辅助
- [x] 迁移 `write_movie_nfo()` / `_write_movie_nfo_for_video()`（L146-200）
- [x] 迁移 `write_tvshow_nfo()`（L201-217）
- [x] 迁移 `write_season_nfo()`（L218-228）
- [x] 迁移 `write_episode_nfo()`（L229-245）
- [x] 迁移 `_add()` / `_write_xml()`（L246-259）— XML 写入辅助
- [x] scraper.py 顶部 re-export 保持兼容
- [x] _is_category_folder 迁移到 nfo_handler.py（read_nfo fallback 依赖）

#### 拆出 → poster_downloader.py（海报下载，约 30 行）
- [x] 迁移 `download_poster()`（L260-280）
- [x] scraper.py re-export `download_poster`

#### 验证
- [x] `python -c "import scraper; print('OK')"` 无报错
- [x] `python -c "from scraper import read_nfo, download_poster, scrape_folder; print('OK')"` 兼容性检查

### 13. tmdb_client.py — 908 行 [暂不拆]
- 单一职责（TMDB API 客户端），功能自洽
- parse_filename / ScrapeResult 虽被大量引用，但通过 `from tmdb_client import` 用着没问题
- 后续如果超过 1200 行再考虑拆出 media_utils.py

### 14. analyzer.py — 941 行 [暂不拆]
- 独立分析层，纯读取诊断，功能自洽
- 所有函数围绕 `analyze_folder()` / `analyze_library()` 两个入口展开
- 内部 `_diagnose_*` 系列函数虽多但职责单一（结构/刮削/影子名/质量/重命名诊断）
- 依赖 organizer 的分类函数，拆分 organizer 后 import 路径不变（re-export 兼容）
- 后续如果新增诊断维度导致超过 1200 行，再考虑拆出 `diagnostics.py`

---

## 后端拆分执行顺序

> 依赖关系决定顺序：scraper 被 organizer 依赖 → organizer 被 routes 依赖

1. **scraper.py → nfo_handler.py + poster_downloader.py**（最底层数据获取层，无下游依赖风险）
2. **organizer.py → renamer.py + structure_organizer.py**（依赖 scraper，拆完后路由层 import 不受影响）
3. **routes/scrape.py → routes/media_info.py + routes/poster.py**（纯路由层，互不依赖）
4. **routes/organize.py → routes/relocate.py + routes/analyze.py**（纯路由层）

每拆完一个文件，立即运行验证项，确认无回归再进入下一个。
