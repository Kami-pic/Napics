---
inclusion: manual
---

# .kiro 目录结构说明

仅在维护 .kiro 知识库时需要参考本文件。

```
.kiro/
├── steering/          # AI 行为规则（自动/手动加载）
│   ├── ai-rules.md           # [always] 核心行为准则
│   ├── project-structure.md  # [manual] 本文件
│   ├── product.md            # [manual] 产品定义
│   ├── tech.md               # [fileMatch] 技术栈
│   ├── structure.md          # [fileMatch] 代码结构
│   ├── code-style.md         # [fileMatch] 编码风格
│   ├── api-conventions.md    # [fileMatch] API 约定
│   └── organize-workflow.md  # [fileMatch] 整理流水线规范
├── knowledge/         # 项目知识库（AI 按需读取）
│   ├── project-memory.md     # 业务逻辑、踩坑经验、当前进度
│   ├── api-reference.md      # API 清单
│   ├── data-models.md        # 核心数据结构
│   └── organize-pipeline-v3.md
├── docs/              # 设计文档与 TODO
└── specs/             # Kiro Spec 历史存档
```

## 约定
- 新增设计文档放 `docs/`，行为规则放 `steering/`，项目知识放 `knowledge/`
- docs 文件名：小写英文+连字符，如 `feature-name-todo.md`
- docs 状态标签：`[当前]` / `[TODO]` / `[废弃]` / `[一次性]`
