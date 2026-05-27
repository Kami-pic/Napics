# [TODO] 拆分回归排查

> 之前多轮对话中的代码拆分（路由拆分、组件拆分、插件独立化）可能引入了 bug。
> 需要逐行对比拆分前后代码，确认功能和显示无回归。

---

## 已排查并修复

### routes/library.py 拆分（→ library.py + library_tree.py + library_crud.py）
- [x] 逐行对比完成，拆分前 commit: `e142ac1~1`
- [x] **修复**：`config_manager.py` 第 158 行 `lib_path` → `self.lib_path`（导致 /library/tree 500）
- [x] **修复**：`library_tree.py` 一级分类目录 folder_type 手动覆盖不生效
- [x] **确认**：scan、sync、library CRUD、category-tag 端点逻辑等价

### 插件系统
- [x] **修复**：`main.py` 启动时未调用 `load_installed_plugins()`（plugin registry 始终为空）
- [x] **修复**：`conftest.py` 让测试能 import 已移入插件的模块
- [x] **修复**：`pan_search_provider_factory.py` 裸 import 崩溃

### 前端
- [x] **修复**：CardGrid 展开面板位置偏移（"添加媒体文件夹"按钮 `data-card` → `data-add-card`）
- [x] **修复**：紫色小横杠 bug（hdr_type 空值检查）
- [x] **修复**：插件中心缺排序 + "已安装"Tab

### 本轮新发现并修复
- [x] **修复**：`routes/scrape.py` 中 `ShadowNameRequest` 类未定义（端点从 tools.py 移出时遗漏），导致 `POST /media/shadow-name` 返回 422
- [x] **修复**：`ExpandPanel.tsx` 从 `./CardGrid` 导入 `getSeasonLabel`/`CardItem` 造成循环依赖，改为从 `./cardGridUtils` 直接导入
- [x] **修复**：`tests/test_bt_expand.py` 引用已移除的 `shared.py` getter 函数（`_get_bitsearch_scraper` 等），更新为验证新的 `bt_search_provider_factory` 接口
- [x] **修复**：`tests/test_bt_search_provider_factory.py` 测试环境未加载插件导致 `get_direct_bt_scraper_factories()` 返回空集，添加插件预加载逻辑

---

## 待排查

### 后端路由拆分

| 拆分 | 原文件 | 拆出文件 | 拆分 commit | 状态 |
|------|--------|----------|-------------|------|
| media_info 拆分 | routes/media_info.py | routes/media_detail.py | `f86108e` | ✅ 逐行对比完成，无遗漏 |
| scrape 拆分 | routes/scrape.py | routes/scrape_execute.py | `5911d00` | ✅ 逐行对比完成，无遗漏 |
| search 拆分 | routes/search.py | routes/search_single.py | `5911d00` | ✅ 逐行对比完成，无遗漏 |
| relocate 拆分 | routes/relocate.py | relocate_tree_builder.py | `82871b1` | ✅ 逐行对比完成，无遗漏 |
| organize 业务层拆分 | routes/organize.py | organize_executor.py / renamer.py / structure_organizer.py | 更早 | ✅ 模块可正常导入 |

### 插件独立拆分

- [x] 12 个 BT 源独立插件的 `__init__.py` 注册逻辑是否正确 — ✅ 每个独立插件正确调用 `ctx.register_scraper_search_provider()`
- [x] 9 个网盘源独立插件的 `__init__.py` 注册逻辑是否正确 — ✅ `search-pan` 捆绑包正确注册 9 个源
- [x] `plugin_guard.py` 的 `BT_SOURCE_PLUGIN_MAP` / `PAN_SOURCE_PLUGIN_MAP` 是否覆盖所有场景 — ✅ 覆盖完整
- [x] `bt_search_provider_factory.py` 从 plugin registry 获取时，独立插件和旧捆绑包是否都能正确工作 — ✅ 验证通过（12 个源全部注册）
- [x] `pan_search_service.py` 从 plugin registry 获取时，独立插件是否正确注册 `scraper_class` — ✅ 5 个源正常初始化
- [x] 前端搜索源列表（`/api/search/sources`）是否正确返回已安装的独立插件源 — ✅ 端点正常

### 前端组件拆分

| 拆分 | 原文件 | 拆出文件 | 状态 |
|------|--------|----------|------|
| ExpandPanel | CardGrid.tsx | ExpandPanel.tsx | ✅ props 完整，循环依赖已修复 |
| cardGridUtils | CardGrid.tsx | cardGridUtils.ts | ✅ re-export 正确 |
| AISettingsSection | SettingsModal.tsx | AISettingsSection.tsx | ✅ props 匹配 |

**排查重点结果**：
- [x] ExpandPanel 拆出后，props 传递是否完整（特别是 refreshKey、batchMode）— ✅ 完整
- [x] cardGridUtils 拆出后，`getSeasonLabel`、`CardItem` 类型导出是否正确 — ✅ 正确
- [x] CardGrid 中 `renderList` 的展开面板插入逻辑是否与拆分前等价 — ✅ 等价
- [x] 前端 API 调用路径是否与后端路由拆分后的端点一致 — ✅ 全部对齐

### 前后端联动验证

- [x] SearchModal 接收 cnName/enName/originalName 链路：FolderDetail/VideoDetail → page.tsx → SearchModal → useSearchState — ✅ 完整
- [x] 发现页 DiscoverPage → SearchModal 的搜索词传递 — ✅ 正确
- [x] 所有 API 端点路径与后端路由匹配 — ✅ 无偏差

---

## 排查原则

1. 用 `git show <commit>~1:path` 导出拆分前代码
2. 逐行对比拆分后的所有文件，确认：
   - 没有遗漏的代码
   - 变量名/路径没有错误
   - import 完整
   - 路由路径一致
   - 共享状态正确传递
3. 对每个端点做端到端测试（TestClient）
4. 前端用 getDiagnostics 检查类型错误

---

## 已知的非拆分问题（用户报告但与拆分无关）

- 下载管理中有测试集合 → 数据残留，非代码问题
- 撤回操作和健康报告没关联 → 设计如此，两个独立功能
- 快速同步"像扫描" → 代码逻辑正确（调的是 /sync），可能是 UI 反馈误导
