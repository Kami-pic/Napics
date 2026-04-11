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

### 9. organizer.py — 1862 行 ⚠️
- 分类 + 重命名 + 结构整理 + V3 整理 + 影子名
- 建议拆为：organizer.py（分类+入口）+ renamer.py（重命名）+ structure_organizer.py（结构整理）

### 10. routes/organize.py — 1306 行 ⚠️
- 路由文件严重超标（上限 400 行）
- 建议拆为：routes/organize.py（整理路由）+ routes/rename.py（重命名路由）+ routes/analyze.py（分析路由）

### 11. routes/scrape.py — 1169 行 ⚠️
- 刮削 + 代理 + 候选搜索 + 详情多源 + 海报管理
- 建议拆为：routes/scrape.py（刮削核心）+ routes/media_info.py（详情多源）+ routes/poster.py（海报管理）

### 12. scraper.py — 1193 行 ⚠️
- NFO 读写 + 海报下载 + 递归刮削
- 建议拆为：scraper.py（入口+递归刮削）+ nfo_writer.py（NFO 读写）+ poster_downloader.py（海报下载）

### 13. tmdb_client.py — 908 行
- 单一职责（TMDB API 客户端），功能自洽
- 暂不拆

### 14. analyzer.py — 941 行
- 独立分析层，功能自洽
- 暂不拆
