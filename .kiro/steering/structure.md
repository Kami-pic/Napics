---
inclusion: fileMatch
fileMatchPattern: "**/*.{py,tsx,ts,js}"
---

# 代码结构

## 目录布局
```
├── backend/                # Python 后端
│   ├── main.py             # FastAPI 入口（薄壳），只注册路由
│   ├── shared.py           # 全局单例 + 共享辅助函数
│   ├── routes/             # 路由层（按业务域拆分）— 只做参数校验和调用业务层
│   │   ├── library.py      # /scan /sync（扫描与同步）
│   │   ├── library_tree.py # /library/tree（目录树构建）
│   │   ├── library_crud.py # /library /library/* CRUD + completeness + quality + clean-name
│   │   ├── scrape.py       # /scrape /scrape/select /scrape/read /media/shadow-name（刮削搜索/读取/选择）
│   │   ├── scrape_execute.py # /scrape/execute /scrape/batch /scrape/delete-scrape（刮削执行）
│   │   ├── media_info.py   # /scrape/candidates /scrape/douban /scrape/bangumi（候选搜索+选择确认）
│   │   ├── media_detail.py # /media/info（详情多源获取：TMDB/豆瓣/Bangumi）
│   │   ├── poster.py       # /scrape/poster /proxy/image /scrape/upload-poster /scrape/poster-url /scrape/delete-poster
│   │   ├── organize.py     # /organize/rename /organize/full /organize/rollback（整理+重命名+历史）
│   │   ├── rename.py       # /rename（手动重命名，从 organize.py 拆分）
│   │   ├── organize_stream.py # /organize/full-stream（SSE 流式整理，从 organize.py 拆分）
│   │   ├── relocate.py     # /organize/dry-run /organize/execute /organize/archive-both /organize/purge-old（归位替换）
│   │   ├── analyze.py      # /analyze/folder /analyze/library /organize/classify（分析诊断）
│   │   ├── search.py       # /api/search /api/search/stream /search/pan /alist/* /search/sources（主搜索+流式+网盘+源管理）
│   │   ├── search_single.py # /api/search/source /search/single（单源搜索+单关键词搜索）
│   │   ├── download.py     # /download* /batch-search /batch-download
│   │   ├── config.py       # /config/* /no-scrape /cache/*
│   │   ├── discover.py     # /douban/* /movie/poster /add-media /discover/*
│   │   ├── system.py       # /recycle-bin/* /torrent-blacklist/* /api/system/*
│   │   └── tools.py        # /batch_manage /ai/* /play
│   ├── config_manager.py   # 配置管理（AppConfig）
│   ├── discover_enrich.py  # 发现推荐业务层（enrich_cache + 清洗名注入 + 本地状态注入）
│   ├── organize_executor.py # Action Plan 执行器（文件操作+路径计算，从 routes/organize.py 拆分）
│   ├── organizer.py        # 文件夹分类判定核心（~550 行）+ re-export renamer/structure_organizer
│   ├── renamer.py          # 重命名 + 影子名生成（从 organizer.py 拆分）
│   ├── structure_organizer.py # 季目录整理 + 结构归位 + 归档清理（从 organizer.py 拆分）
│   ├── scraper.py          # 递归刮削入口 + 电影刮削 + 单文件/批量刮削 + re-export
│   ├── scraper_tv.py       # TV 系列刮削（_scrape_tv_v3/_scrape_tv/_scrape_collection，从 scraper.py 拆分）
│   ├── nfo_handler.py      # NFO 读写（从 scraper.py 拆分）
│   ├── poster_downloader.py # 海报下载（从 scraper.py 拆分）
│   ├── analyzer.py         # 独立分析层（纯读取诊断）
│   ├── file_relocator.py   # 整理替换归位器（两段式推演+落盘）
│   ├── searcher.py         # Prowlarr 搜索 + 增强匹配
│   ├── download_manager.py # 下载任务队列 + 生命周期管理
│   ├── downloader.py       # qBittorrent + Alist 客户端
│   ├── pan_search_service.py # 网盘搜索聚合
│   ├── search_service.py    # 搜索服务（统一搜索逻辑，SSE/订阅/单源共用）
│   ├── search_helpers.py    # 搜索辅助（enrich/junk标记/直搜源合并）
│   ├── search_keyword_mapper.py # 多语言搜索词映射 + 回退链
│   ├── search_query_builder.py  # 搜索词构造（cn/en/original 多策略）
│   ├── completeness.py     # 季集完整性检测（TMDB 差集 + 缓存）
│   ├── recycle_bin.py      # 回收站管理（move_to_bin + 恢复 + 清理）
│   ├── core/
│   │   └── constants.py    # 统一规则中心（扩展名/白名单/NFO 名等静态规则）
│   ├── bt_scraper_*.py      # BT 直搜源爬虫（继承 ScraperBase）
│   ├── pan_scraper_*.py     # 网盘爬虫（继承 ScraperBase）
│   ├── rss_source_*.py      # RSS 源（继承 RSSSourceBase，订阅系统用）
│   ├── _*.py               # 一次性脚本（调试/批处理/迁移），已移入 _scripts/ 目录
│   └── test_*.py           # 测试脚本，已移入 tests/ 目录
├── frontend/               # Next.js 前端
│   ├── app/                # 页面路由（page.tsx、layout.tsx、manage/）
│   ├── components/         # UI 组件（ai/detail/download/layout/manage/media/search/settings）
│   │   ├── media/          # CardGrid + CardPoster + EpisodeList + ExpandPanel + DiscoverPage（瘦壳）+ useDiscoverState + useDiscoverSubscribe 等
│   │   ├── search/         # SearchModal（瘦壳）+ useSearchState + SearchHeader + EpisodeTable + PanFilterBar + PanResultsView + FilterBar + BatchUpgradePanel
│   │   └── detail/         # DetailDrawer（瘦壳）+ 11 个独立子组件
│   ├── hooks/              # 自定义 hooks（useLibrary.ts）
│   ├── lib/                # 工具函数（api/（按领域拆分的 API 子模块）、folderTypes.ts、utils.ts、mediaColors.ts）
│   ├── types/              # 类型定义（index.ts）
│   └── __tests__/          # vitest 测试（split-components.test.tsx）
├── .kiro/                  # AI 协作配置（见 project-structure.md）
├── start.bat / stop.bat    # 启动/停止前后端
├── start_all.bat / stop_all.bat  # 启动/停止全部服务
└── restart.bat             # 重启前后端（支持 silent 参数）
```

## 后端分层架构

```
入口层        main.py（薄壳，只注册路由）
              ↓
路由层        routes/*（参数校验 + 调用业务层，不写业务逻辑）
              ↓
业务逻辑层    organizer.py（分类判定）/ renamer.py（重命名+影子名）/ structure_organizer.py（结构整理+归档）/ organize_executor.py（Action Plan 执行）/ analyzer.py / file_relocator.py / download_manager.py / ai_organizer.py / discover_enrich.py（发现推荐 enrich）/ completeness.py（季集完整性）
              ↓
数据获取层    tmdb_client.py / douban_client.py / douban_api_v2.py / bangumi_client.py / searcher.py / scraper.py / nfo_handler.py / poster_downloader.py
              ↓
基础设施层    config_manager.py / downloader.py / scraper_base.py / quality_parser.py / core/constants.py / recycle_bin.py
              ↓
共享层        shared.py（单例初始化 + 辅助函数，所有层的依赖注入源）
```

### 各层职责边界

| 层 | 职责 | 禁止 |
|---|---|---|
| 路由层 routes/* | 接收请求、参数校验、调用业务层、返回响应 | 不写超过 20 行的业务逻辑函数 |
| 业务逻辑层 | 核心算法、状态管理、流程编排 | 不直接处理 HTTP 请求/响应 |
| 数据获取层 | 外部 API 调用、文件读写、数据解析 | 不做业务决策 |
| 基础设施层 | 配置、客户端封装、通用工具 | 不依赖业务层 |
| 共享层 shared.py | 单例初始化、依赖注入 | 不写业务逻辑 |

### 新增代码的放置规则

- 新增路由：放到对应业务域的 routes/*.py 中
- 新增业务逻辑：放到对应的业务模块中（organizer.py / download_manager.py 等）
- 如果现有模块职责已经很重（超过 1000 行且包含多个不相关功能），允许拆出独立模块
- 拆分信号：一个文件里有多个不相关的功能域（如 organizer.py 同时管分类和影子名）
- 不拆信号：逻辑自洽、只服务于一个功能的模块，即使行数多也不强制拆
- Pydantic 数据模型定义在使用它的模块中，不要跨文件定义后忘记导入
- 路由文件中的辅助函数如果超过 20 行，应该下沉到业务层

## 关键约束
- 路由路径不可变，前端 api.ts 中所有路径直接对应后端路由
- shared.py 是唯一的单例源，路由文件通过 `from shared import config_m, ...` 获取依赖
- 不要创建 /api/v1/ 前缀，所有路由直接挂在根路径
- 所有外部服务凭据走 config.json，不允许硬编码
- 调试必须在 backend/ 目录下执行，确保 ConfigManager 能读到 config.json

## 约定
- `_` 开头的 .py 文件是一次性脚本，不要引用也不要维护
- `test_` 开头的是测试脚本
