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
│   ├── project-memory.md     # 项目记忆：跨域知识+核心红线+领域索引
│   ├── devlog.md             # 开发日志：里程碑归档（变更+决策+踩坑），只追加不删除
│   ├── api-reference.md      # API 清单（路径+方法+用途）
│   ├── data-models.md        # 核心数据结构（JSON 字段说明、状态机）
│   ├── organize-pipeline-v3.md   # 整理流水线 V3 完整设计
│   ├── pan-search-pipeline.md    # 网盘搜索流水线（4源聚合+筛选+转存）
│   ├── bt-search-pipeline.md     # BT 搜索流水线（回退链+二次匹配+评分排序）
│   ├── download-replace-pipeline.md # 下载与归位替换流水线
│   ├── discover-recommend.md     # 发现推荐模块（三源数据+探索筛选+本地感知）
│   ├── subscribe-system.md       # 订阅系统（RSS框架+匹配引擎+洗版+日历）
│   └── scroll-damping-interaction.md # 滚动阻尼交互设计
│
├── docs/              # 设计文档与 TODO 清单
│   ├── *-todo.md             # 进行中的任务清单（临时性，完成后归档到 devlog）
│   ├── _archived/            # [废弃] 文档归档（已完成/已取代，保留供追溯）
│   └── _one-off/             # [一次性] 文档归档（报告/调研/会话总结）
│
└── specs/             # Kiro Spec 历史存档（当前用 TODO 驱动，保留供追溯）
```

## 约定

- `steering/` 文件通过前置元数据控制加载时机，具体见目录树中每个文件的标注
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
