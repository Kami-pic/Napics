# [当前] provider-download-phase7-todo.md

## 范围

Phase 7：迁移 qB / OpenList 为 `DownloadProvider` / `StorageProvider`。

本清单只跟踪下载器与存储适配，不包含 BT 直搜、RSS、Metadata、Prowlarr、网盘搜索源迁移。

## 当前子任务

- [x] 新增 `backend/download_provider_adapter.py`，用通用 adapter 包装已有 qB / OpenList 提交能力。
- [x] 新增 `backend/download_provider_factory.py`，集中现有 qB / OpenList 构造函数，作为后续替换下载调用链的兼容桥。
- [x] 新增 `backend/test_download_provider_adapter.py`，验证 adapter 满足 `DownloadProvider` 协议并保持提交参数兼容。
- [x] 新增 `backend/test_download_provider_factory.py`，验证 Download provider 清单与静态 metadata 一致。
- [x] `/api/providers` 的 download 分类补充 qBittorrent / OpenList 静态清单。
- [x] `/download` 和 `/batch-download` 的直接提交路径改为通过 `DownloadProvider` adapter 调用，响应结构保持兼容。
- [x] `DownloadManager._push_to_qb()` / `_push_to_alist()` 的提交动作改为通过 `DownloadProvider` adapter 调用，保留旧 hash / task id 兼容规则。
- [x] qBittorrent `DownloadProvider.progress()` 支持读取单任务进度，`DownloadManager._sync_qb_progress()` 改为通过 provider 获取结构化进度。
- [x] OpenList `DownloadProvider.progress()` 支持通过真实 task id 读取单任务进度，`DownloadManager._sync_alist_progress_by_task_id()` 改为通过 provider 获取结构化进度。
- [x] 新增 `DownloadTaskInfo` DTO 与 `DownloadProvider.list_tasks()` 契约，qBittorrent provider 支持只读任务列表，`DownloadManager._get_qb_hashes()` 改为通过 provider 获取 hash 集合。
- [x] `/download-manager/sync-from-qb` 的 qB 列表读取改为通过 `DownloadProvider.list_tasks()`，保留原导入、对账和响应结构。
- [x] 新增 `DownloadFileInfo` DTO 与 `DownloadProvider.list_files()` 契约，归位替换路由的 qB 文件白名单读取改为通过 provider 调用。
- [x] 新增 OpenList `StorageProvider` 只读适配层，`/alist/mounts` 改为通过 provider 读取挂载列表，响应结构保持兼容。
- [x] OpenList 旧 `alist_*` marker 的 undone/done 列表读取改为通过 `DownloadProvider.list_tasks(status)`，保留原匹配与状态处理逻辑。
- [x] OpenList `StorageProvider.list_dir()` / `exists()` 支持只读文件浏览能力，当前不新增路由和前端入口。

## 暂不做

- 不修改 `QBittorrentClient` / `AlistManager` 内部请求逻辑。
- 不修改 `DownloadManager` 状态机。
- 不修改 `/download-manager/*` 队列和状态机。
- 不修改归位替换与文件白名单逻辑。
- 不修改订阅自动下载逻辑。
- 不新增 OpenList 存储文件浏览路由或前端入口。
- 不修改 OpenList 旧 `alist_*` marker 的列表扫描匹配逻辑。
- 不修改前端 provider 感知逻辑。

## 收口结论

- Phase 7 的 qB / OpenList 下载与存储适配边界已完成。
- qB 提交、进度、任务列表、文件白名单读取均通过 `DownloadProvider` 进入。
- OpenList 提交、真实 task id 进度、旧 `alist_*` marker 列表扫描读取均通过 `DownloadProvider` 进入。
- OpenList 挂载列表、只读目录浏览、存在性检查均通过 `StorageProvider` 进入。
- `DownloadManager` 仍保留 Core 下载任务状态机、匹配规则、归位触发和持久化逻辑。
- `QBittorrentClient` / `AlistManager` 保留为底层客户端实现，只由 provider factory / shared 兼容构造点引用。
- `/alist/transfer` / `quark_transfer.py` 属于网盘转存与私有能力边界，不在 Phase 7 内继续迁移，后续随 Phase 8 私有化处理。
- 前端 provider 动态感知不在 Phase 7 内处理，按 Phase 9 推进。

## 验证

- `cd backend && python -X utf8 -m pytest test_download_provider_adapter.py test_download_provider_factory.py test_provider_contracts.py test_provider_registry.py test_provider_api.py`
- `cd backend && python -X utf8 -m pytest test_download_route_provider_bridge.py test_download_provider_adapter.py test_download_provider_factory.py test_provider_api.py`
- `cd backend && python -X utf8 -m pytest test_download_manager_relocate_flow.py test_download_provider_adapter.py test_download_provider_factory.py`
- `cd backend && python -X utf8 -m pytest test_download_manager_relocate_flow.py test_download_provider_adapter.py test_provider_contracts.py`
- `cd backend && python -X utf8 -m pytest test_download_route_provider_bridge.py test_download_provider_adapter.py test_download_manager_relocate_flow.py`
- `cd backend && python -X utf8 -m pytest test_relocate_routes.py test_download_provider_adapter.py test_provider_contracts.py`
- `cd backend && python -X utf8 -m pytest test_storage_provider_adapter.py test_provider_api.py test_download_provider_adapter.py test_relocate_routes.py`
- `cd backend && python -X utf8 -m pytest test_download_provider_adapter.py test_download_manager_relocate_flow.py test_provider_contracts.py`
- `cd backend && python -X utf8 -m pytest test_storage_provider_adapter.py test_provider_api.py test_provider_contracts.py`

## 最终验证记录

- 已通过：`python -X utf8 -m pytest test_download_provider_adapter.py test_download_provider_factory.py test_download_route_provider_bridge.py test_download_manager_relocate_flow.py test_storage_provider_adapter.py test_provider_api.py test_relocate_routes.py test_provider_contracts.py`
- 结果：`171 passed`
- 完整后端测试未作为 Phase 7 收口门槛：当前工作区缺少 `backend/media_library.json`，`test_local_match_e2e.py` 在收集阶段直接读取该文件会阻塞完整 pytest。
