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
│   ├── api-conventions.md    # [fileMatch] API 约定（改 main.py 时加载）
│   └── organize-workflow.md  # [fileMatch] 整理流水线规范（改整理代码时加载）
│
├── knowledge/         # 项目知识库（AI 按需读取，了解项目是什么）
│   ├── project-memory.md     # 项目记忆：业务逻辑细节、踩坑经验、当前进度
│   ├── api-reference.md      # API 清单（路径+方法+用途）
│   ├── data-models.md        # 核心数据结构（JSON 字段说明、状态机）
│   ├── organize-pipeline-v3.md # 整理流水线 V3 完整设计（三段式解耦架构）
│   ├── pan-search-pipeline.md  # 网盘搜索流水线（4源聚合+筛选+转存）
│   ├── bt-search-pipeline.md   # BT 搜索流水线（回退链+二次匹配+评分排序）
│   └── download-replace-pipeline.md # 下载与归位替换流水线（双通道+两段式推演）
│
├── docs/              # 设计文档与 TODO 清单
│   ├── media-organize-architecture.md # [当前] 分类体系+整理架构+前端展示规则
│   ├── auto-replace-todo.md          # [TODO] 下载自动替换（核心归位已完成，自动化待做）
│   └── search-enhance-todo.md        # [TODO] 搜索增强（阶段1-3已完成，磁力直搜+配置待做）
│
└── specs/             # Kiro Spec（历史存档，当前用 TODO 驱动，保留供追溯）
    ├── media-organize/        # v1.0 2026-04-03 [已完成] 整理功能补全（备份/快照/season.nfo/分片合并）
    ├── search-accuracy/       # v1.0 2026-04-03 [已完成] 搜索匹配准确性（影子名/增强评分/索引器优先级）
    ├── search-download/       # v1.0 2026-04-03 [已完成] 搜索下载优化（质量解析/剧集搜索/下载管理/归位）
    ├── video-search-upgrade/  # v1.0 2026-04-03 [已完成] 搜索升级+新增影片（豆瓣发现/批量升级）
    └── search-enhance/        # v1.0 2026-04-03 [进行中] 搜索增强双通道（网盘爬虫+转存）
```

## 约定

- `steering/` 里的 `.md` 文件带 `inclusion: always` 前置元数据，每次对话自动加载
- `knowledge/project-memory.md` 是项目业务知识库，AI 在涉及相关功能时按需读取
- 新增设计文档放 `docs/`，行为规则放 `steering/`，项目知识放 `knowledge/`
- 不要在其他位置维护重复内容

## docs 命名规范

- 文件名用小写英文 + 连字符，如 `feature-name-todo.md`
- 每个文件开头用标签标注状态：
  - `[当前]` — 仍在使用的设计/架构文档
  - `[TODO]` — 进行中的任务清单
  - `[废弃]` — 已被新版取代或已全部完成，可随时清理
  - `[一次性]` — 调试记录、报告、会话总结等，完成后不再更新，可随时清理
- 版本迭代时，旧文档标记为 `[废弃]` 而不是删除，方便追溯
- `[废弃]` 和 `[一次性]` 文档积累过多时可以批量清理
