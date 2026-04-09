---
inclusion: fileMatch
fileMatchPattern: "**/*.{py,tsx,ts,js}"
---

# 代码结构

## 目录布局
```
├── backend/                # Python 后端
│   ├── main.py             # FastAPI 入口（67 行薄壳），注册路由
│   ├── shared.py           # 全局单例 + 共享辅助函数
│   ├── routes/             # 路由模块（按业务域拆分，104 个路由）
│   │   ├── library.py      # /library/* /scan /sync
│   │   ├── scrape.py       # /scrape/* /media/shadow-name
│   │   ├── organize.py     # /organize/* /analyze/* /rename
│   │   ├── search.py       # /api/search /search/* /alist/*
│   │   ├── download.py     # /download* /batch-search /batch-download
│   │   ├── config.py       # /config/* /no-scrape /cache/*
│   │   ├── discover.py     # /douban/* /movie/poster /add-media
│   │   ├── system.py       # /recycle-bin/* /torrent-blacklist/* /api/system/*
│   │   └── tools.py        # /batch_manage /ai/* /play
│   ├── config_manager.py   # 配置管理（AppConfig）
│   ├── organizer.py        # 文件夹分类 + 重命名 + 结构整理
│   ├── scraper.py          # NFO/海报读写 + 递归刮削
│   ├── analyzer.py         # 独立分析层（纯读取诊断）
│   ├── searcher.py         # Prowlarr 搜索 + 增强匹配
│   ├── download_manager.py # 下载任务队列 + 生命周期管理
│   ├── downloader.py       # qBittorrent + Alist 客户端
│   ├── pan_search_service.py # 网盘搜索聚合
│   ├── _*.py               # 一次性脚本（调试/批处理/迁移），不属于核心代码
│   └── test_*.py           # 测试脚本
├── frontend/               # Next.js 前端
│   ├── app/                # 页面路由（page.tsx、layout.tsx、manage/）
│   ├── components/         # UI 组件（ai/detail/download/layout/manage/media/search/settings）
│   ├── hooks/              # 自定义 hooks（useLibrary.ts）
│   ├── lib/                # 工具函数（api.ts、folderTypes.ts、utils.ts）
│   └── types/              # 类型定义（index.ts）
├── .kiro/                  # AI 协作配置（见 project-structure.md）
├── start.bat               # 启动前后端
├── stop.bat                # 停止前后端
├── start_all.bat           # 启动全部服务（含 Alist/qB/Prowlarr）
├── stop_all.bat            # 停止全部服务
└── restart.bat             # 重启前后端（支持 silent 参数）
```

## 后端模块分层
- 入口层：main.py（薄壳）+ routes/*（路由定义 + 请求处理）
- 共享层：shared.py（单例初始化 + 辅助函数）
- 数据获取层：tmdb_client.py、douban_client.py、bangumi_client.py、searcher.py
- 业务逻辑层：organizer.py、analyzer.py、ai_organizer.py、download_manager.py
- 基础设施层：config_manager.py、downloader.py、scraper_base.py、quality_parser.py

## 关键约束
- 路由路径不可变，前端 api.ts 中所有路径直接对应后端路由
- shared.py 是唯一的单例源，路由文件通过 `from shared import config_m, ...` 获取依赖
- 不要创建 /api/v1/ 前缀，所有路由直接挂在根路径
- 所有外部服务凭据走 config.json，不允许硬编码
- 调试必须在 backend/ 目录下执行，确保 ConfigManager 能读到 config.json

## 约定
- `_` 开头的 .py 文件是一次性脚本，不要引用也不要维护
- `test_` 开头的是测试脚本
- 核心业务逻辑不要新建文件，优先在现有模块上扩展
