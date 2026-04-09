---
inclusion: fileMatch
fileMatchPattern: "**/*.{py,tsx,ts,js,css}"
---

# 编码风格

## 通用原则
- 一个文件只做一件事，内聚性高就行，不卡行数
- 拆文件的信号是"一个文件里有多个不相关的功能"，不是"超过 N 行"

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
- 后端 folder_type 枚举值：movie / tv / series_collection / movie_collection / variety / misc
- 前端 folderTypes.ts 必须和后端保持一致，不允许使用简写或别名（如不能用 collection 代替 movie_collection）
- 新增或修改 folder_type 时，前后端必须同步更新
- 前端 types/index.ts 中的 interface 字段名必须和后端 Pydantic Model 的字段名一致（snake_case）

## 前端组件拆分
- 拆分信号：一个组件内有多个不相关的功能块（如表格+弹窗+独立表单）
- 不拆信号：逻辑自洽、只服务于一个功能的组件，即使行数多也不强制拆
- 内嵌子组件（如 ShadowCell）如果只在当前文件使用且逻辑简单，可以留在同一文件
- 内嵌子组件如果被多个文件引用，或逻辑复杂度超过 50 行，应拆为独立文件
- 组件文件顶部写一行中文注释说明用途
- Props 接口用 ComponentNameProps 命名并导出（如 CardGridProps）
