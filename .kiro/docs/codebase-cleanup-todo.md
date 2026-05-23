# [TODO] 代码整理与文件拆分

> 面向公开发布的代码整理计划：文件拆分、测试归档、一次性脚本清理、插件物理隔离。

---

## 一、前端文件拆分（>300 行）

| 行数 | 文件 | 拆分方案 |
|------|------|----------|
| 530 | `components/search/BatchUpgradePanel.tsx` | 逻辑自洽的全屏弹窗，内部按 phase 切换视图，暂不拆 |
| 481 | `components/detail/FolderDetail.tsx` | 已拆出多个子组件（DetailComponents/CandidatePicker/ShadowNameSection/PosterUpload/CompletenessBar），剩余逻辑自洽，暂不拆 |
| 445→346 | `components/settings/SettingsModal.tsx` | ✅ 拆出 `AISettingsSection.tsx`（134 行） |
| 443→388 | `components/media/CardGrid.tsx` | ✅ 拆出 `cardGridUtils.ts`（工具函数+类型定义，34 行） |
| 427 | `components/media/DoubanRecommend.tsx` | 已废弃（.gitignore 排除），跳过 |
| 421 | `app/page.tsx` | 拆出 usePageModals（弹窗状态管理 hook）/ ScanController（扫描逻辑） |
| 395 | `components/download/DownloadManagerPanel.tsx` | 拆出 DownloadTaskItem / DownloadProgress 子组件 |
| 377 | `components/media/ExpandDetail.tsx` | 拆出 ExpandEpisodeList / ExpandSeasonTabs |
| 359 | `app/manage/page.tsx` | 轻微超标，暂不拆 |
| 331 | `components/search/FilterBar.tsx` | 轻微超标，暂不拆 |
| 324 | `components/search/SearchSettingsPanel.tsx` | 轻微超标，暂不拆 |

---

## 二、后端路由文件拆分（>400 行）

| 行数 | 文件 | 拆分方案 |
|------|------|----------|
| 1235 | `routes/library.py` | ✅ **已完成**。拆出 `routes/library_tree.py`（目录树构建，431 行）、`routes/library_crud.py`（CRUD+完整度+质量分，352 行），library.py 保留扫描同步（246 行） |
| 842 | `routes/media_info.py` | ✅ **已完成**。拆出 `routes/media_detail.py`（详情多源获取，436 行），media_info.py 保留候选搜索+选择（321 行） |
| 671 | `routes/scrape.py` | ✅ **已完成**。拆出 `routes/scrape_execute.py`（执行/批量/删除，218 行），scrape.py 保留搜索/读取/选择（406 行） |
| 660 | `routes/relocate.py` | 拆出 dry-run 推演逻辑到业务层 `file_relocator.py`（已有，检查是否下沉完全） |
| 634 | `routes/organize.py` | 拆出 action plan 构建到业务层 |
| 595 | `routes/search.py` | ✅ **已完成**。拆出 `routes/search_single.py`（单源搜索+单关键词搜索，233 行），search.py 保留主搜索/流式/网盘/源管理（302 行） |
| 477 | `routes/discover.py` | 轻微超标，暂不拆 |
| 468 | `routes/download.py` | 轻微超标，暂不拆 |
| 425 | `routes/tools.py` | 轻微超标，暂不拆 |

---

## 三、测试文件归档

当前 `backend/` 根目录有 **107 个 test_*.py** 文件，混在业务代码中。

### 方案
- [x] 创建 `backend/tests/` 目录
- [x] 所有 `test_*.py` 移入 `backend/tests/`
- [x] 更新 pytest 配置（`pytest.ini` 或 `pyproject.toml`）指定 `testpaths = ["tests"]`
- [x] 确认 `python -m pytest tests/` 能正常运行
- [x] `.gitignore` 中确认 `__pycache__` 已排除

---

## 四、一次性脚本清理

当前 `backend/` 根目录有 **87 个 _*.py** 一次性脚本（调试/批处理/迁移/验证）。

### 方案
- [x] 创建 `backend/_scripts/` 目录（或 `scripts/debug/`）
- [x] 所有 `_*.py` 移入该目录
- [x] 在 `.gitignore` 中添加 `backend/_scripts/`（公开版不发布）
- [ ] 或者直接删除（已归档到 git 历史，随时可恢复）

---

## 五、插件物理隔离

当前插件代码（BT 源/网盘源/RSS 源/下载器/元数据源）散落在 `backend/` 根目录，和 Core 代码混在一起。

### 当前插件文件清单

**BT 搜索源**（12 个）：`bt_scraper_*.py`
**网盘搜索源**（9 个）：`pan_scraper_*.py`
**RSS 订阅源**（9 个）：`rss_source_*.py`
**Provider 框架**（12 个）：`provider_*.py` + `*_provider_adapter.py` + `*_provider_factory.py`
**外部服务客户端**：`tmdb_client.py`、`douban_client.py`、`douban_api_v2.py`、`bangumi_client.py`、`downloader.py`（qB/Alist）

### 目标目录结构

```
backend/
├── core/                    # Core 核心（公开）
│   ├── constants.py         # 已有
│   ├── provider_contracts.py
│   ├── provider_models.py
│   ├── provider_registry.py
│   ├── provider_context.py
│   └── provider_runtime.py
├── plugins/                 # 插件目录（每个插件一个文件夹）
│   ├── bt_search/           # BT 搜索源插件
│   │   ├── __init__.py
│   │   ├── manifest.json    # 插件元数据
│   │   ├── adapter.py       # bt_search_provider_adapter
│   │   ├── factory.py       # bt_search_provider_factory
│   │   └── sources/         # 各源实现
│   │       ├── bitsearch.py
│   │       ├── nyaa.py
│   │       ├── mikan.py
│   │       └── ...
│   ├── pan_search/          # 网盘搜索源插件
│   │   ├── __init__.py
│   │   ├── manifest.json
│   │   ├── adapter.py
│   │   ├── factory.py
│   │   └── sources/
│   │       ├── pansearch.py
│   │       ├── rrdynb.py
│   │       └── ...
│   ├── rss_subscribe/       # RSS 订阅源插件
│   │   ├── __init__.py
│   │   ├── manifest.json
│   │   ├── adapter.py
│   │   ├── factory.py
│   │   └── sources/
│   │       ├── mikan.py
│   │       ├── nyaa.py
│   │       └── ...
│   ├── metadata_tmdb/       # TMDB 元数据插件
│   │   ├── __init__.py
│   │   ├── manifest.json
│   │   ├── adapter.py
│   │   ├── factory.py
│   │   └── client.py        # tmdb_client.py
│   ├── metadata_douban/     # 豆瓣元数据插件
│   │   ├── __init__.py
│   │   ├── manifest.json
│   │   └── client.py        # douban_client + douban_api_v2
│   ├── metadata_bangumi/    # Bangumi 元数据插件
│   │   ├── __init__.py
│   │   ├── manifest.json
│   │   └── client.py
│   ├── download_qbittorrent/ # qBittorrent 下载器插件
│   │   ├── __init__.py
│   │   ├── manifest.json
│   │   ├── adapter.py
│   │   └── client.py
│   ├── download_alist/      # Alist/OpenList 存储插件
│   │   ├── __init__.py
│   │   ├── manifest.json
│   │   ├── adapter.py
│   │   └── client.py
│   └── search_prowlarr/     # Prowlarr 聚合搜索插件
│       ├── __init__.py
│       ├── manifest.json
│       ├── adapter.py
│       ├── factory.py
│       └── client.py        # searcher.py 中 Prowlarr 相关
├── routes/                  # 路由层（不变）
├── tests/                   # 测试（从根目录迁入）
└── ...                      # Core 业务模块（organizer/scraper/analyzer 等）
```

### 执行步骤

- [ ] **Phase A**：创建 `plugins/` 目录结构，先迁移一个插件（如 `bt_search`）验证 import 链路
- [ ] **Phase B**：迁移剩余搜索源插件（pan_search / rss_subscribe / search_prowlarr）
- [ ] **Phase C**：迁移元数据插件（metadata_tmdb / metadata_douban / metadata_bangumi）
- [ ] **Phase D**：迁移下载器插件（download_qbittorrent / download_alist）
- [ ] **Phase E**：Provider 框架文件移入 `core/`
- [ ] **Phase F**：更新所有 import 路径，确保测试通过
- [ ] **Phase G**：每个插件添加 `manifest.json`（name/version/description/dependencies/capabilities）

### 约束

- 迁移过程中行为等价，不改逻辑
- 每个 Phase 完成后跑完整测试
- `core/` 不允许 import `plugins/` 中的具体实现
- `plugins/` 通过 `provider_registry` 注册，Core 通过契约接口调用

---

## 六、执行优先级

1. **测试文件归档**（低风险，立即可做）
2. **一次性脚本清理**（低风险，立即可做）
3. **`routes/library.py` 拆分**（本轮改动导致膨胀，优先处理）
4. **前端超标文件拆分**（CardGrid / SettingsModal / FolderDetail / page.tsx）
5. **插件物理隔离**（工程量最大，分 Phase 推进）
6. **其他后端路由拆分**（按需）
