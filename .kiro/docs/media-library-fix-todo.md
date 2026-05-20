# [TODO] 媒体库添加与管理 — 遗留问题修复

> 上一轮完成了基础框架，本轮修复实际使用中发现的问题。

---

## 问题清单

### P0：核心逻辑缺陷

- [ ] **4. 虚拟文件夹标记未生效**
  - 添加分类文件夹（如综艺）后，卡片无标签显示，详情页无类型切换
  - 根因：`is_virtual_library` 标记逻辑依赖 `_lib_category_tags`（库名匹配），但树构建时库名节点的 path 可能和 `top_category_paths` 不匹配
  - 需要排查 `finalize` 中 `is_virtual_library` 的赋值条件是否正确触发
  - 详情页的类型切换（category_tag 下拉）对虚拟文件夹应该调用 `PUT /library/{name}` 而非 `POST /library/category-tag`

- [ ] **5. 设置页类型标签不同步**
  - 添加分类文件夹后，设置页中该路径的类型标签显示为"媒体库"而非对应类型
  - 根因：设置页的 `libPathMap` 从 `config.media_libraries` 读取，但 `AddLibraryModal` 保存后 config 状态可能未刷新
  - 或者 `media_libraries` 的 paths 和 `scan_paths` 中的路径格式不一致（斜杠/反斜杠）

- [ ] **7. 删除扫描路径应同步删除虚拟文件夹**
  - 设置页删除一个路径时，如果该路径属于某个 media_library，应同时从 media_libraries 中移除
  - 当前只从 `scan_paths` 中删除，media_libraries 中的记录残留

### P1：交互与 UI 问题

- [ ] **1. 删除路径的确认逻辑优化**
  - 当前每个路径删除都弹相同的 confirm
  - 应该判断：路径下有内容 → "该路径下有 X 个媒体，确定删除？"
  - 路径下无内容 → 直接删除不确认
  - 最后一个路径 → "将清空整个媒体库"

- [ ] **2. 路径输入组件化**
  - 提取为独立组件 `PathInput.tsx`，统一所有使用路径输入的地方
  - 包含：文件夹选择按钮 + 输入框 + 可选的类型标签下拉 + 可选的删除按钮
  - 使用位置：设置页、AddScanPathModal、AddLibraryModal

- [ ] **2.1 文件夹选择按钮高度对齐**
  - 选择按钮高度应和 input 框完全一致（当前偏小）

- [ ] **2.2 删除 icon 增大**
  - 框内的 × 删除图标太小，适当增大到 14-16px

- [ ] **3. 路径 placeholder 恢复**
  - 设置页路径输入的 placeholder 应恢复为 `如 Z:\Movies 或 \\NAS\media 或 /volume1/video`
  - 当前改成了 `选择或输入路径`，信息量不够

### P2：数据一致性

- [ ] **6. 父子路径冲突处理**
  - 添加的文件夹如果是已有路径的子目录（或父目录），不应报错
  - 代码层面：扫描时去重，相同文件不重复入库
  - 允许多个路径指向有重叠的目录，但扫描结果不重复

- [ ] **8. 排除路径不生效**
  - AddLibraryModal 中的排除路径字段保存到了 `media_libraries[].exclude_dirs`
  - 但扫描时没有读取 `media_libraries` 的 exclude_dirs 来过滤
  - 需要在 `scan_path` 接口中，根据 library_name 查找对应的 exclude_dirs 并应用
  - 排除逻辑应和全局 `exclude_dirs` 相同（支持多行/逗号分隔的文件夹名）

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
- 如果库名和树节点名不匹配（比如路径末段名 vs 用户自定义名），标记就不会生效
- 需要改为按路径匹配而非按名称匹配
