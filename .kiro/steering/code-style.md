---
inclusion: fileMatch
fileMatchPattern: "**/*.{py,tsx,ts,js,css}"
---

# 编码风格

## 通用原则
- 一个文件只做一件事，优先按职责拆分
- 行数上限作为兜底红线：前端 .tsx 不超过 300 行，后端路由文件不超过 400 行，非路由 Python 模块按职责拆分不硬卡行数

## Python 后端
- 函数/变量命名：snake_case（如 `get_video_metadata`、`save_path`）
- 类命名：PascalCase（如 `DownloadManager`、`VideoInfo`）
- 私有函数/方法：单下划线前缀（如 `_fallback_info`、`_get_download_manager`）
- 数据模型：统一用 Pydantic BaseModel
- import 顺序：标准库 → 第三方库（fastapi/pydantic/requests）→ 项目模块
- 字符串：双引号优先
- 注释和 docstring：用中文
- 错误处理：外层 try-except 兜底，不让单个失败中断整体流程
- 打印日志：`print(f"[模块名] 描述: {变量}")` 格式
- 文件读写：统一 `encoding="utf-8"`，JSON 写入加 `ensure_ascii=False`

## 前端
- 组件命名：PascalCase（如 `SearchModal`、`CardGrid`）
- 文件命名：PascalCase.tsx（如 `DetailDrawer.tsx`）
- 样式：Tailwind CSS 4，不用 CSS Modules
- 颜色：主背景 #0f0f0f，面板 #141414，边框 white/[0.06]

## 前后端类型对齐
- 后端 folder_type 枚举值：movie / tv / collection / series / season / mixed
- 一级分类标签 category_tag：movie / tv
- 前端 folderTypes.ts 必须和后端保持一致
- 新增或修改 folder_type 时，前后端必须同步更新
- 前端 types/index.ts 中的 interface 字段名必须和后端 Pydantic Model 的字段名一致（snake_case）

## 前端组件拆分
- 拆分信号：一个组件内有多个不相关的功能块（如表格+弹窗+独立表单）
- 不拆信号：300 行以内、逻辑自洽、只服务于一个功能的组件不强制拆
- 内嵌子组件（如 ShadowCell）如果只在当前文件使用且逻辑简单，可以留在同一文件
- 内嵌子组件如果被多个文件引用，或逻辑复杂度超过 40 行，应拆为独立文件
- 组件文件顶部写一行中文注释说明用途
- Props 接口用 ComponentNameProps 命名并导出（如 CardGridProps）

## 开发流程强制规则（AI 必须遵守）
- **先拆后写**：新建功能模块时，先规划组件/文件拆分方案，再动手写代码。不允许先堆在一个文件里"后面再拆"
- **单文件上限**：单个 .tsx 组件文件超过 300 行时，必须立即拆分，不等用户提醒
- **工具函数独立**：proxyUrl、缓存逻辑、数据标准化等工具函数，从一开始就放在独立的 utils 文件中，不要内嵌在组件文件里
- **子组件独立**：超过 40 行的子组件（如 ExpandDetail、SkeletonGrid）必须拆为独立文件
- **memo 组件独立**：用 React.memo 包裹的组件必须拆为独立文件，方便复用和测试
- **新增功能前检查**：往现有文件添加代码前，先检查文件行数。如果添加后会超过 300 行，先拆分再添加
- **后端同理**：路由文件中的辅助函数超过 20 行必须下沉到业务层，单个路由文件超过 400 行必须拆分
