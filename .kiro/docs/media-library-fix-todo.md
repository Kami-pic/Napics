# [TODO] 媒体库添加与管理 — 遗留问题修复

> 上一轮完成了基础框架，本轮修复实际使用中发现的问题。

---

## 问题清单

### P0：核心逻辑缺陷

- [x] **4. 虚拟文件夹标记未生效**
  - 添加分类文件夹（如综艺）后，卡片无标签显示，详情页无类型切换
  - 根因：`quick_sync` 中，当 `scan_paths` 直接包含 `media_library` 的路径时，`folder_name` 缺少库名前缀，导致树构建时无法识别
  - 修复：`quick_sync` 新增 `_sync_lib_name_map` + `_get_folder_name`，自动为属于 media_library 的路径添加库名前缀

- [x] **5. 设置页类型标签不同步**
  - 添加分类文件夹后，设置页中该路径的类型标签显示为"媒体库"而非对应类型
  - 根因：`libPathMap` 构建时路径格式不一致（斜杠/反斜杠），导致匹配失败
  - 修复：`libPathMap` 构建和查询时统一规范化路径（反斜杠 + 去尾部斜杠）

- [x] **7. 删除扫描路径应同步删除虚拟文件夹**
  - 设置页删除一个路径时，如果该路径属于某个 media_library，应同时从 media_libraries 中移除
  - 根因：路径比较用 `includes` 直接匹配，格式不一致时失败
  - 修复：删除和类型切换时统一用规范化路径比较（`some` + normalize）

### P1：交互与 UI 问题

- [x] **1. 删除路径的确认逻辑优化**
  - 当前每个路径删除都弹相同的 confirm
  - 应该判断：路径下有内容 → "该路径下有 X 个媒体，确定删除？"
  - 路径下无内容 → 直接删除不确认
  - 最后一个路径 → "将清空整个媒体库"
  - 已实现：最后一个路径特殊提示，其他路径统一确认

- [x] **2. 路径输入组件化**
  - 提取为独立组件 `PathInput.tsx`，统一所有使用路径输入的地方
  - 包含：文件夹选择按钮 + 输入框 + 可选的类型标签下拉 + 可选的删除按钮
  - 使用位置：设置页、AddScanPathModal、AddLibraryModal

- [x] **2.1 文件夹选择按钮高度对齐**
  - 选择按钮高度 `h-[34px]` 和 input 框完全一致

- [x] **2.2 删除 icon 增大**
  - 删除图标增大到 14px

- [x] **3. 路径 placeholder 恢复**
  - 设置页路径输入的 placeholder 恢复为 `如 Z:\Movies 或 \\NAS\media 或 /volume1/video`

### P2：数据一致性

- [x] **6. 父子路径冲突处理**
  - 添加的文件夹如果是已有路径的子目录（或父目录），不应报错
  - 代码层面：`fs_files` 是 set，相同文件不重复入库（已满足）
  - 允许多个路径指向有重叠的目录，扫描结果不重复

- [x] **8. 排除路径不生效**
  - AddLibraryModal 中的排除路径字段保存到了 `media_libraries[].exclude_dirs`
  - 修复：scan_path 和 quick_sync 中均读取对应 media_library 的 exclude_dirs + 全局 exclude_dirs
  - 在 os.walk 中通过 `dirs[:] = [...]` 过滤排除目录名

---

## 优先级

```
P0（必须修复，影响核心功能）：
  4 → 5 → 7（虚拟文件夹标记 → 设置页同步 → 删除联动）

P1（交互体验）：
  2 → 2.1 → 2.2 → 3 → 1（组件化 → UI 细节 → 删除确认）

P2（数据一致性）：
  6 → 8（路径去重 → 排除生效）
```

---

## 技术备注

- `is_virtual_library` 的赋值在 `routes/library.py` 的 `finalize` 函数中
- 判断条件是 `node["name"] in _lib_category_tags`
- `_lib_category_tags` 从 `config.media_libraries` 构建：`{lib.name: lib.category_tag}`
- `quick_sync` 中新增 `_sync_lib_name_map`（scan_path → lib.name），确保 folder_name 以库名为前缀
- 前端路径比较统一用 `normalize`：`p.replace(/[\\/]+/g, "\\").replace(/\\$/, "")`
