# [TODO] 文件操作盘点 + 测试噪声治理

> 目标：先把高风险文件副作用链路和测试基建噪声收清楚，再决定是否进入文件事务层或目录分层实现。
> 当前阶段已完成：文件副作用盘点、测试噪声治理、关键入口副作用基线、第一轮最小 sidecar helper 抽取。

---

## 当前 task

- 本轮目标：收口文件操作盘点 + 测试噪声治理专项
- 本轮只做：`batch_manage(remove/copy)` 副作用基线补齐 + TODO 完成状态更新
- 本轮不碰：
  - 不改任何业务逻辑
  - 不新增用户功能
  - 不做目录重组，不移动 backend 业务文件
  - 不碰前端体验优化
  - 不清理 / 删除 / 移动历史脚本
  - 不修改真实 NAS 文件、不运行破坏性脚本

---

## 背景判断

`optimization-master-plan` 中的阶段 B / C / D 是中长期架构方向，不应一次性执行。

当前最值得先做的是 C2“文件操作事务统一”的前置盘点，因为 rename / move / delete / replace / recycle 一旦漏掉联动，会直接影响真实媒体库数据安全。

在盘点完成前，不建立 `backend/domains/*`，不抽象通用事务层，不迁移现有文件操作代码。

---

## 阶段 1：文件操作入口盘点

### 产出要求

- [x] 生成一张“入口 × 副作用”矩阵
  - 入口：用户可触发入口、路由入口、业务函数入口
  - 副作用列至少包含：
    - 文件 rename / move / copy / delete
    - NFO 同步
    - poster / fanart / season poster 移动或删除
    - `media_library.json` 路径同步
    - `recycle_bin.json` 记录
    - `organize_history` 记录
    - `download_tasks.json` 状态变更
    - snapshot / rollback 记录
    - 前端刷新入口
  - 验证：矩阵能覆盖所有 `os.rename` / `shutil.move` / `shutil.copy` / `os.remove` / `unlink` / recycle 相关调用点

- [x] 标注每个入口当前测试覆盖情况
  - 标注为：已有隔离测试 / 已有路由测试 / 只有脚本验证 / 无覆盖
  - 验证：每个高风险入口都能反查到测试文件或明确标为无覆盖

- [x] 写至少 3 个具体风险场景
  - 示例方向：
    - 重命名视频但 NFO / poster 没同步，媒体库显示和实际文件脱节
    - 替换旧资源但 recycle 记录缺失，用户无法从回收站恢复
    - 移动文件后 `media_library.json` 路径未更新，首页或详情页指向旧路径
  - 验证：每个风险场景都关联到具体入口和缺失副作用

### 建议重点入口

- [x] `renamer.py`
- [x] `organizer.py`
- [x] `structure_organizer.py`
- [x] `organize_executor.py`
- [x] `file_relocator.py`
- [x] `recycle_bin.py`
- [x] `routes/organize.py`
- [x] `routes/relocate.py`
- [x] `routes/library.py`
- [x] `download_manager.py`

> 注：以上入口已在阶段 1 审计矩阵覆盖；不是逐个迁移或逐个补测试完成。

---

## 阶段 2：测试噪声分类

### 分类规则

- [x] 正式测试：`test_*.py`
  - 目标：修到可稳定执行
  - 不允许用跳过真实失败替代修复
  - 验证：能列出失败项、归因、处理方式

- [x] 调试脚本：`_test_*.py` / `_check_*.py` / `_debug_*.py` / `_fix_*.py` / `_verify_*.py` / `_batch_*.py`
  - 目标：避免被 `pytest .` 误收集或误执行
  - 优先方案：经用户确认后，将所有 `backend/_*.py` 批量归档到 `backend/scripts/_archived/`
  - 备选方案：如果暂不移动文件，则在 `backend/conftest.py` 加 `collect_ignore_glob = ["_*.py"]`
  - 验证：`pytest .` 不再因历史脚本导入阶段 `sys.exit(...)` 中断

### 2026-05-07 分类结果

- 正式测试数量：`backend/test_*.py` 共 86 个。
- 历史调试脚本数量：`backend/_*.py` 共 98 个。
- 当前 `pytest . --collect-only` 第一阻断点：`test_bt_expand.py` 在模块导入阶段直接执行自定义测试并 `sys.exit(0)`，导致 pytest collection `INTERNALERROR`。
- 忽略 `test_bt_expand.py` 后的下一类阻断点：`test_code_split.py` 在模块导入阶段重包 `sys.stdout` / `sys.stderr`，导致 pytest capture 收尾时报 `ValueError: I/O operation on closed file`。
- 正式测试中存在 `sys.exit` 的文件：`test_bt_expand.py`、`test_detail_drawer_split.py`、`test_detail_e2e.py`、`test_detail_operations.py`、`test_discover_api.py`、`test_enrich_integration.py`、`test_final_features.py`、`test_move_wrapped.py`、`test_name_trust_audit.py`、`test_organize_pipeline.py`、`test_phase_c_e2e.py`、`test_phase4_e2e.py`、`test_rename_organize.py`、`test_rss_e2e.py`、`test_subscribe_api.py`、`test_subscribe_e2e.py`、`test_todo_completion.py`。
- 正式测试中存在顶层 stdout/stderr 重包风险的文件：`test_code_split.py`、`test_final_features.py`、`test_local_match_e2e.py`、`test_local_media_matcher.py`、`test_phase_c_e2e.py`、`test_phase4_e2e.py`、`test_rss_e2e.py`。
- 处理方式建议：阶段 3 先做 pytest 收集治理，不移动历史脚本时用 `backend/conftest.py` 排除 `backend/_*.py`；正式 `test_*.py` 的脚本化文件不能简单跳过，需要逐个改成 pytest 可收集函数或登记为独立脚本专项。
- 验证命令已执行：
  - `cd backend && python -X utf8 -m pytest . --collect-only`
  - `cd backend && python -X utf8 -m pytest . --collect-only --ignore=test_bt_expand.py`

### 明确不做

- 不花时间修一次性调试脚本
- 不删除历史脚本
- 不批量移动文件，除非用户明确确认；归档路径固定为 `backend/scripts/_archived/`
- 不把测试治理和业务修复混在同一轮提交

---

## 阶段 3：最小治理实现

> 只有阶段 1 / 2 盘点完成后才进入。

- [x] 后端 pytest 收集治理
  - 方案 A：经用户确认后批量移动 `backend/_*.py` 到 `backend/scripts/_archived/`
  - 方案 B：新增或更新 `backend/conftest.py`，配置 `collect_ignore_glob = ["_*.py"]`
  - 推荐：优先方案 A，目录更干净，减少 AI 误判；方案 B 更保守，不移动文件
  - 本轮处理：未获批批量移动脚本，已采用方案 B，新增 `backend/conftest.py`
  - 验证：`cd backend && python -X utf8 -m pytest . --collect-only` 当前仍被正式测试 `test_bt_expand.py` 的导入期 `sys.exit(0)` 打断，不是 `_*.py` 历史脚本打断

- [x] 正式测试失败归类
  - 只处理 `test_*.py` 中真实失败
  - 如果失败属于当前无关业务缺陷，记录到本 TODO 的“后续技术债”区，不混改业务逻辑
  - 当前归类：
    - `test_bt_expand.py`：顶层执行自定义测试并 `sys.exit(0)`，导致 pytest collection `INTERNALERROR`
    - `test_code_split.py`：顶层重包 `sys.stdout` / `sys.stderr`，在忽略 `test_bt_expand.py` 后导致 pytest capture 收尾 `ValueError`
  - 处理方式：不在本轮混改脚本式正式测试；后续应逐个改成 pytest 原生函数，或从正式测试集中移出并登记为独立脚本专项
  - 验证：
    - `cd backend && python -X utf8 -m pytest . --collect-only`
    - `cd backend && python -X utf8 -m pytest . --collect-only --ignore=test_bt_expand.py`

- [x] 前端历史失败只做归类，不在本专项修体验
  - 范围：`split-components` / `subscribe-*` 等历史失败
  - 当前结果：`frontend` 下 `npm run test` 为 10 个测试文件、116 条测试全通过
  - 残留风险：`subscribe-final.test.tsx` 存在 `vi.mock("@/lib/api")` 非顶层 warning，当前不是失败，但 Vitest 后续版本会把它升级为错误
  - 处理方式：不在本专项修前端体验；如后续升级 Vitest 或该 warning 变红，再开前端测试基建专项
  - 验证：`cd frontend && npm run test`

---

## 阶段 4：是否进入文件事务层

只有满足以下条件，才允许新开实现任务：

- [x] “入口 × 副作用”矩阵已完成
- [x] 高风险入口已有测试或已明确补测试计划
  - 已补：`routes/rename.py::rename_item` 单文件重命名、单视频电影文件夹重命名副作用基线
  - 已补：`routes/tools.py::batch_manage(move/delete)` 散装视频移动/删除副作用基线
  - 已补：`routes/tools.py::batch_manage(remove/copy)` 副作用基线
- [x] `pytest` 收集噪声已治理
  - `_*.py` 历史脚本已通过 `backend/conftest.py` 排除
  - 正式 `test_*.py` 中脚本式测试仍需独立治理，不作为 `_*.py` 噪声处理
- [x] 已识别最危险的 1-2 个入口，不做全量重构
  - 入口 1：`routes/tools.py::batch_manage(move/delete)`，用户可触发、文件副作用最大、覆盖缺口明显
  - 入口 2：`routes/rename.py::rename_item`，高频入口，涉及视频/文件夹/sidecar/library 联动
- [x] 用户确认进入实现阶段
  - 2026-05-08 用户回复“继续”

### 2026-05-08 阶段 4 判断

- 当前不直接进入 `backend/core/file_ops/` 事务层实现。
- 理由：`batch_manage` 仍缺少副作用测试矩阵；正式 `test_*.py` 还有脚本式收集阻断，直接迁移文件操作无法证明等价。
- 本轮选择：先冻结 `rename_item` 行为，新增 `backend/test_rename_side_effects.py`。
- 覆盖场景：
  - 单视频文件重命名后，同步 `.nfo`、`-poster.jpg` 和 `media_library` 的 `file_path` / `file_name`
  - 单视频电影文件夹重命名后，同步文件夹名、视频名、`.nfo`、`-poster.jpg` 和 `media_library` 的 `file_path` / `file_name` / `folder_name`
- 验证：`cd backend && python -X utf8 -m pytest test_rename_side_effects.py -p no:cacheprovider`

### 下一步建议

- `rename_item` + `batch_manage(move/delete)` 已有测试保护，可以开始评估只抽一个极小的 sidecar helper。
- `batch_manage(copy/remove)` 仍未补，不应作为第一轮事务层迁移目标。
- 第一轮实现仍应保持外部接口和行为不变，只迁移一个低风险重复点，不做全量文件事务层。

### 2026-05-08 补充基线

- 新增 `backend/test_batch_manage_side_effects.py`
- 覆盖场景：
  - 散装视频批量移动后，同步同名前缀 `.nfo`、`-poster.jpg` 和 `media_library` 的 `file_path` / `file_name` / `folder_name`
  - 散装视频批量删除后，调用回收站 `move_to_bin`，文件从原路径移出，并从 `media_library` 移除
  - 从媒体库移除时，只更新 `media_library` 和 `excluded_paths`，不删除磁盘文件
  - 散装视频复制时，只复制视频本体，不复制同名 sidecar，不更新 `media_library`
- 验证：`cd backend && python -X utf8 -m pytest test_batch_manage_side_effects.py -p no:cacheprovider`

### 2026-05-08 第一轮最小实现

- 新增 `backend/core/file_ops/sidecars.py`
- 只抽取同名前缀 sidecar 移动/重命名 helper：`.nfo`、`-poster.jpg`、`-poster.png`、`-fanart.jpg`、`-clearlogo.png`、`-thumb.jpg`
- 已接入入口：
  - `routes/rename.py::rename_item`
  - `routes/tools.py::batch_manage(move)` 的散装文件分支
- 行为保持：
  - 只处理存在的 sidecar
  - 单个 sidecar 失败时吞掉异常，不阻断主视频/文件夹操作
  - 不改变任何 HTTP 接口和返回结构
- 验证：`cd backend && python -X utf8 -m pytest test_rename_side_effects.py test_batch_manage_side_effects.py -p no:cacheprovider`

### 允许的下一步

- 局部新增 `backend/core/file_ops/` 的小入口
- 只迁移一个低风险重复点
- 保持外部接口和行为不变
- 迁移前后必须有行为快照或集成测试证明等价

### 禁止的下一步

- 一次性迁移所有文件操作
- 同时建立 `backend/domains/*` 五个子域
- 同时重构下载 / 整理 / 刮削主链路
- 为了架构美观移动文件

---

## 体验优化另开线

以下体验问题不混入本专项：

- 搜索结果排序 / 过滤是否好用
- 整理预览是否清晰
- 下载管理面板信息密度
- 首页加载体感
- 下载器断连后的恢复提示
- 刮削失败批量重试
- 媒体库数据一致性自检

处理方式：日常使用时记录不顺手的点，攒到一定量后开独立体验优化轮次。

---

## 完成标准

- [x] 文件操作入口和副作用链路可被审阅
- [x] 高风险入口的测试缺口清楚
- [x] pytest 噪声治理方案明确，且不误修调试脚本
- [x] 是否值得进入 C2 文件事务层有证据支撑
- [x] 没有业务行为改动

## 收口结论

- 本专项已完成。
- 当前已允许的后续方向：只围绕已有基线保护的小范围重复点继续抽 helper。
- 当前仍不允许：
  - 全量文件事务层
  - 批量迁移所有文件操作
  - 同时重构下载 / 整理 / 刮削主链路
- 独立后续专项：
  - 正式 `test_*.py` 脚本化治理（`test_bt_expand.py`、`test_code_split.py` 等）
  - `batch_manage(copy)` 是否应复制 sidecar 的产品行为确认
  - `recycle_bin.restore` 是否应同步 `media_library` 的产品行为确认
