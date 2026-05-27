# [废弃] 媒体库添加与管理改造

> 全部完成，已归档。

> 核心目标：提供符合用户直觉的媒体库添加体验，兼容 Plex/Jellyfin 心智模型。

---

## 背景

当前问题：
- `nas_paths` 命名暗示只能用于 NAS，实际工具不限设备
- 一级文件夹只有 movie/tv 两种 category_tag，限制了自动识别能力
- 没有"分类添加文件夹"的虚拟聚合概念
- 无媒体库时没有引导入口

---

## 设计概要

### 两种添加模式

| | 添加媒体库（自动识别） | 分类添加文件夹（新功能） |
|---|---|---|
| 行为 | 添加路径 → 递归扫描 → 自动识别所有层级文件夹类型 | 添加路径 → 创建虚拟一级文件夹 → 内容归入其中 |
| 根目录 | 忽略根目录，内容平铺扫入 | 保留根目录名作为虚拟聚合文件夹名 |
| 标签 | 递归自动识别（不限一级） | 用户手动选择 |
| 多路径 | 每个路径独立扫入 | 多路径合并到同一个虚拟文件夹 |

### 数据结构改造

```json
// config.json 改造
{
  // 重命名：nas_paths → scan_paths（兼容迁移）
  "scan_paths": ["D:\\Media"],

  // 新增：虚拟媒体库
  "media_libraries": [
    {
      "name": "电影",
      "category_tag": "movie",
      "paths": ["\\\\NAS\\电影", "D:\\电影2"],
      "exclude_dirs": ["样片"]
    },
    {
      "name": "动画番剧",
      "category_tag": "anime_tv",
      "paths": ["\\\\NAS\\动画"],
      "exclude_dirs": []
    }
  ],

  // 全局排除（保留，设置页展示）
  "exclude_dirs": "@eaDir,#recycle"
}
```

### 标签体系

用户可见标签（6 种）：
- 电影 (`movie`)
- 电视剧 (`tv`)
- 动画番剧 (`anime_tv`)
- 动画电影 (`anime_movie`)
- 综艺 (`variety`)
- 其他 (`other`)

标签 → 底层文件结构类型映射：
```
movie / anime_movie / other  → 按 movie 逻辑处理
tv / anime_tv / variety      → 按 tv 逻辑处理
```

### UI 入口

**无媒体库时（scan_paths 为空 且 media_libraries 为空）：**
- 主区域显示引导区，两个按钮：
  1. 添加媒体库 — 弹窗：路径 + 排除 → 写入 scan_paths → 扫描
  2. 分类添加文件夹 — 弹窗：路径（多选）+ 命名 + 标签 + 排除 → 写入 media_libraries → 扫描

**有媒体库后：**
- 一级目录第一张卡片 = "添加媒体文件夹"（功能 = 分类添加文件夹）
- 设置页保留完整的路径管理（scan_paths + media_libraries 统一展示）

### 分类添加弹窗字段

- 路径（支持多个，+ 添加）
- 文件夹名称（默认 = 第一个路径的根目录名，可编辑）
- 标签选择（电影/电视剧/动画番剧/动画电影/综艺/其他）
- 排除目录（可选，该库独立的排除规则）

---

## 实现任务

### Phase 1：数据层改造

- [x] **1.1 config 字段重命名**
  - `nas_paths` → `scan_paths`（后端 AppConfig + 迁移逻辑）
  - 保留 `nas_paths` 读取兼容（读到旧字段自动迁移到 `scan_paths`）
  - 前端所有引用同步更新
  - 验证：config 保存/读取正常，旧配置自动迁移 ✅

- [x] **1.2 新增 media_libraries 字段**
  - 后端 AppConfig 新增 `media_libraries: List[MediaLibrary]`
  - MediaLibrary Pydantic 模型：name, category_tag, paths, exclude_dirs
  - config_manager 读写支持
  - 验证：手动写入 config.json 后能正确读取 ✅

- [x] **1.3 标签体系扩展**
  - 后端 `organizer.py` 的 `_CATEGORY_KEYWORD_MAP` 扩展支持 anime_tv/anime_movie/variety/other
  - 前端 `folderTypes.ts` 的 `CATEGORY_TAG_LABELS` 同步扩展
  - 标签 → 文件结构类型映射函数（`category_tag_to_structure_type`）
  - 验证：新标签能正确映射到 movie/tv 处理逻辑 ✅

### Phase 2：递归识别改造

- [x] **2.1 去除一级目录限制**
  - `routes/library.py` 的 `_infer_folder_type_from_tree` 不再只对一级目录做 category_tag 判定
  - 所有层级都走完整的类型识别逻辑
  - `category_tag` 从 media_libraries 配置向下传播（而非只从目录名推断）
  - 新增 `_guess_structure_type_from_tree` 自主推断函数（5 种信号：季目录名、集号文件名、时长、文件夹名关键词、子目录结构）
  - 改进 `top_category_paths` 判定：只有目录名匹配分类关键词或在 configured_tags 中的才算一级分类
  - 验证：非一级目录也能被正确识别为 movie/tv/collection 等 ✅

- [x] **2.2 scan_paths 扫描逻辑适配**
  - scan_paths 的路径：忽略根目录，内容平铺（现有逻辑不变）
  - media_libraries 的路径：保留根目录名作为虚拟一级文件夹（Phase 3 实现）
  - 树构建时合并两种来源（Phase 3 实现）
  - 验证：scan_paths 模式下的扫描结果在树中正确展示 ✅

### Phase 3：后端 API

- [x] **3.1 媒体库 CRUD 接口**
  - `POST /library/add` — 添加虚拟媒体库（name + category_tag + paths + exclude_dirs）
  - `PUT /library/{name}` — 修改媒体库（改名/改标签/增删路径/改排除）
  - `DELETE /library/{name}` — 删除虚拟媒体库
  - `GET /library/list` — 列出所有媒体库（含 scan_paths 的自动识别库）
  - 验证：CRUD 操作正确持久化到 config.json ✅

- [x] **3.2 扫描接口适配**
  - `GET /scan` 新增 `library_name` 参数
  - media_libraries 的路径扫描后，folder_name 以库名为前缀
  - 树构建时根据 media_libraries 映射正确计算节点路径
  - 多路径合并到同一虚拟文件夹时，内容合并展示
  - 验证：扫描结果树结构正确 ✅

### Phase 4：前端 — 引导与添加弹窗

- [x] **4.1 无媒体库引导区**
  - 新组件 `EmptyLibraryGuide.tsx`
  - 检测条件：stats.total === 0 且无 fileTree
  - 按钮 1"添加媒体库"→ 打开设置页
  - 按钮 2"分类添加文件夹"→ 打开 AddLibraryModal
  - 验证：无媒体库时显示引导 ✅

- [x] **4.2 分类添加弹窗组件**
  - 新组件 `AddLibraryModal.tsx`
  - 字段：路径列表（可多选）+ 名称（默认根目录名）+ 标签选择 + 排除
  - 提交后调用 `POST /library/add` → 触发扫描
  - 验证：弹窗交互正常 ✅

- [x] **4.3 常驻添加卡片**
  - CardGrid 一级目录第一张卡片 = "添加媒体文件夹"
  - 点击打开分类添加弹窗
  - 样式：虚线边框 + 加号图标 + 文字
  - 验证：有媒体库时第一张卡片始终存在 ✅

### Phase 5：设置页适配

- [x] **5.1 设置页路径管理统一**
  - 展示 scan_paths（自动识别路径）
  - 展示 media_libraries（分类添加的库，含名称/标签/路径/排除）
  - 全局排除 + 各库独立排除都可见
  - 验证：设置页能完整管理所有路径 ✅

- [x] **5.2 字段命名更新**
  - UI 文案从"NAS 扫描路径"改为"扫描路径"
  - 去除所有 NAS 相关的限定性描述
  - 验证：UI 中无 NAS 字样 ✅

---

## 兼容与迁移

- 旧 `nas_paths` 字段：读取时自动迁移到 `scan_paths`，保存时只写 `scan_paths`
- 旧 `category_tags` 字段：继续工作，作为手动覆盖的标签配置
- `media_libraries` 为空时行为和现在完全一致（纯 scan_paths 模式）
- 不破坏现有用户的任何数据

---

## 执行顺序

```
Phase 1（数据层）→ Phase 2（识别改造）→ Phase 3（API）→ Phase 4（前端）→ Phase 5（设置页）
```

Phase 1-2 是基础设施，Phase 3-5 是用户可见功能。
每个 Phase 内部按编号顺序执行，Phase 之间有依赖不可跳跃。

---

## 与其他 TODO 的关系

- `new-user-experience-todo.md`：本文件覆盖了其中"首次启动引导"和"媒体库结构灵活化"的 P0 部分
- `plugin-center-todo.md`：无直接依赖，但空状态引导（P1）会引用插件中心
- 插件化改造：本改造不涉及 Provider 层，不冲突
