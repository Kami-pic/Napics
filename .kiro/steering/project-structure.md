---
inclusion: always
---

# .kiro 目录结构说明

```
.kiro/
├── steering/          # AI 行为规则
│   ├── ai-rules.md           # [always] 核心行为准则
│   ├── project-structure.md  # [always] 本文件，目录结构说明
│   ├── product.md            # [manual] 产品定义（用 # 引用）
│   ├── tech.md               # [fileMatch] 技术栈（写代码时自动加载）
│   ├── structure.md          # [fileMatch] 代码结构（写代码时自动加载）
│   ├── code-style.md         # [fileMatch] 编码风格（写代码时自动加载）
│   ├── api-conventions.md    # [fileMatch] API 约定（改路由时加载）
│   └── organize-workflow.md  # [fileMatch] 整理流水线规范（改整理代码时加载）
│
├── knowledge/         # 项目知识库（AI 按需读取，了解项目是什么）
│   ├── project-memory.md     # 项目记忆：业务逻辑细节、踩坑经验、当前进度
│   ├── api-reference.md      # API 清单（路径+方法+用途）
│   ├── data-models.md        # 核心数据结构（JSON 字段说明、状态机）
│   └── organize-pipeline-v3.md # 整理流水线 V3 完整设计（三段式解耦架构）
│
├── docs/              # 设计文档与 TODO 清单
│   ├── media-organize-architecture.md # [当前] 文件夹分类体系设计
│   ├── folder-type-refactor.md       # [当前] 分类标签重构设计
│   ├── auto-replace-todo.md          # [TODO] 下载自动替换（进行中）
│   └── search-enhance-todo.md        # [TODO] 搜索增强（进行中）
│
└── specs/             # Kiro Spec（历史存档，当前用 TODO 驱动，保留供追溯）
    ├── media-organize/        # v1.0 [已完成]
    ├── search-accuracy/       # v1.0 [已完成]
    ├── search-download/       # v1.0 [已完成]
    ├── video-search-upgrade/  # v1.0 [已完成]
    └── search-enhance/        # v1.0 [进行中]
```

# 后端代码结构（2026-04-09 模块化重构后）

```
backend/
├── main.py                  ← 入口（67 行薄壳），只做 include_router
├── shared.py                ← 全局单例 + 共享辅助函数
├── routes/                  ← 路由模块（按业务域拆分，104 个路由）
│   ├── library.py           ← /library/* /scan /sync（媒体库）
│   ├── scrape.py            ← /scrape/* /media/shadow-name /proxy/image（刮削）
│   ├── organize.py          ← /organize/* /analyze/* /rename（整理）
│   ├── search.py            ← /api/search /search/* /alist/*（搜索）
│   ├── download.py          ← /download* /batch-search /batch-download（下载）
│   ├── config.py            ← /config/* /no-scrape /cache/* /backup /restore（配置）
│   ├── discover.py          ← /douban/* /movie/poster /add-media（发现）
│   ├── system.py            ← /recycle-bin/* /torrent-blacklist/* /analysis/* /api/system/*（系统）
│   └── tools.py             ← /batch_manage /ai/* /play（杂项）
├── config_manager.py        ← 配置管理（单例在 shared.py 中初始化）
├── organizer.py             ← 文件夹分类 + 重命名 + 整理流水线
├── scraper.py               ← NFO 读写 + 海报 + 递归刮削
├── analyzer.py              ← 独立分析层
├── searcher.py              ← ProwlarrClient + enhanced_search
├── download_manager.py      ← 下载任务队列
├── file_relocator.py        ← 文件归位器（洗版替换）
├── tmdb_client.py           ← TMDB API 客户端
├── downloader.py            ← qBittorrent + Alist 客户端
└── ... (其他业务模块)
```

## 关键约束

1. **路由路径不可变** — 前端 api.ts 中所有路径直接对应后端路由，改路径必须前后端同步
2. **启动方式** — `cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000`
3. **不要用 reload=True** — Windows + SMB 路径下会崩溃
4. **shared.py 是唯一的单例源** — 路由文件通过 `from shared import config_m, ...` 获取依赖
5. **不要创建 /api/v1/ 前缀** — 前端不用 v1 路径，所有路由直接挂在根路径
6. **backend/app/ 目录已废弃** — 是之前不完整重构的残留，不要使用
7. **所有外部服务凭据和路径必须走 config.json** — 不允许硬编码账号密码、API Key、文件路径。通过 `config_m.config.xxx` 读取。调试/测试时必须先确认 `backend/config.json` 存在且配置正确
8. **调试前必须加载配置** — 任何涉及后端的调试、测试、脚本运行，都必须在 `backend/` 目录下执行，确保 `ConfigManager` 能读到 `config.json`。不要在项目根目录直接运行后端代码

## docs 命名规范

- 文件名用小写英文 + 连字符，如 `feature-name-todo.md`
- 状态标签：`[当前]` 使用中 / `[TODO]` 进行中 / `[废弃]` 已取代 / `[一次性]` 完成后不更新
