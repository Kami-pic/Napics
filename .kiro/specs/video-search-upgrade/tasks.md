# 实现计划：视频搜索升级与新增影片

## 概述

按依赖关系分阶段实现：先后端基础模块（质量解析），再后端 API 端点，然后前端类型和 API 封装，最后前端组件。每个阶段包含对应的测试子任务。

## 任务

- [x] 1. 新建质量解析模块 `backend/quality_parser.py`
  - [x] 1.1 实现 `QualityTag`、`QualityLevel` Pydantic 模型和 `parse_quality` 函数
    - 从 BT 标题中解析分辨率（720p/1080p/2160p）、来源（Bluray/WEB-DL/Remux/HDTV）、视频编码（x264/x265/HEVC/AV1）、音频编码（AAC/DTS/DTS-HD/TrueHD/Atmos）、中文字幕标记（CHS/CHT/中字/简繁等）
    - 生成 `display` 格式化字符串，包含所有非空标记
    - _需求：1.2_
  - [x] 1.2 实现 `get_quality_level` 和 `compare_quality` 函数
    - 按设计文档的 8 级质量等级排名表计算 rank 值
    - `compare_quality` 对比当前视频分辨率与搜索结果质量，返回 "higher" / "equal" / "lower"
    - _需求：2.2, 2.3, 2.4_
  - [ ]* 1.3 属性测试：质量标签解析正确性
    - **属性 1：质量标签解析正确性**
    - 使用 hypothesis 随机组合分辨率/来源/编码/字幕标记生成 BT 标题，验证 `parse_quality` 正确提取所有标记
    - **验证需求：1.2**
  - [ ]* 1.4 属性测试：质量等级排序一致性与传递性
    - **属性 2：质量等级排序一致性与传递性**
    - 随机生成 QualityTag 三元组，验证 `get_quality_level` 的全序关系和传递性
    - **验证需求：2.2, 2.3, 2.4**
  - [ ]* 1.5 单元测试：质量解析边界情况
    - 测试空标题、无质量标记标题、完整标题解析、compare_quality 各种对比场景
    - _需求：1.2, 2.2, 2.3_

- [x] 2. 增强后端搜索模块 `backend/searcher.py`
  - [x] 2.1 增强 `SearchResult` 模型和 `ProwlarrClient.search` 方法
    - `SearchResult` 新增 `quality: Optional[QualityTag]` 和 `quality_rank: int` 字段
    - `search` 方法中调用 `quality_parser.parse_quality` 解析每条结果的质量信息
    - 搜索结果按做种数降序排列
    - _需求：1.2, 1.3, 5.1_
  - [ ]* 2.2 属性测试：搜索结果结构完整性
    - **属性 5：搜索结果结构完整性**
    - 随机生成 Prowlarr API 原始响应，验证处理后每条结果包含所有必需字段
    - **验证需求：5.1, 7.4**
  - [ ]* 2.3 属性测试：搜索结果按做种数降序排列
    - **属性 7：搜索结果按做种数降序排列**
    - 随机生成 SearchResult 列表，验证排序后做种数降序
    - **验证需求：1.3**

- [x] 3. 检查点 — 确保后端基础模块测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 4. 增强后端 API 端点 `backend/main.py`（搜索升级部分）
  - [x] 4.1 增强 `POST /download` 端点
    - 新增 `DownloadRequest` Pydantic 模型，支持 `download_type` 参数（"qb" / "alist"）
    - 根据 `download_type` 路由到 qBittorrent 或 Alist 客户端
    - 未配置对应服务时返回明确错误信息
    - _需求：3.1, 3.2, 3.3, 3.4, 3.5, 5.2_
  - [x] 4.2 新增 `POST /batch-search` 端点
    - 接受 `BatchSearchRequest`（视频列表），逐个搜索，间隔 2 秒
    - 返回 EventSource 流式进度：searching → result → done
    - 自动推荐质量等级最高且做种数 > 0 的结果
    - 单个失败标记为 error 继续处理
    - _需求：4.1, 4.2, 4.3, 4.4, 4.6, 5.3_
  - [x] 4.3 新增 `POST /batch-download` 端点
    - 接受 `BatchDownloadRequest`（下载任务列表），批量推送并返回每个任务的成功/失败状态
    - _需求：4.7, 5.4_
  - [ ]* 4.4 属性测试：最佳推荐选择算法
    - **属性 4：最佳推荐选择算法**
    - 随机生成 SearchResult 列表 + FilterState，验证推荐算法选择做种数 > 0 中质量等级最高的结果
    - **验证需求：2.8, 4.3**
  - [ ]* 4.5 单元测试：下载路由和批量端点
    - 测试 download_type="qb" 和 "alist" 路由、未配置时返回错误、批量搜索单个失败不影响队列
    - _需求：3.2, 3.3, 3.4, 5.5_

- [x] 5. 新增豆瓣热榜与新增影片后端 API
  - [x] 5.1 增强 `backend/douban_client.py`，新增 `get_hot_list(type)` 方法
    - 调用豆瓣热榜接口获取热门电影/剧集列表
    - 被反爬时返回空列表
    - _需求：8.2, 9.1_
  - [x] 5.2 新增 `GET /douban/hot` 和 `GET /douban/search` 端点
    - `/douban/hot` 接受 type 参数（movie/tv），返回热榜列表
    - `/douban/search` 接受 query 参数，复用已有 `douban_client.search()`
    - _需求：9.1, 9.2_
  - [x] 5.3 新增 `POST /add-media` 端点
    - 接受 `AddMediaRequest`，在 save_path 下创建以影片名命名的文件夹
    - 使用 `scraper` 模块生成 NFO 文件和下载封面
    - 海报下载失败不阻断流程
    - _需求：8.6, 8.7, 9.3_
  - [ ]* 5.4 属性测试：预刮削 NFO 往返一致性
    - **属性 6：预刮削 NFO 往返一致性**
    - 随机生成影片信息，写入 NFO 后读取回来，验证 title/year/rating/overview/genres/director/cast 一致
    - **验证需求：8.7**
  - [ ]* 5.5 单元测试：豆瓣热榜和新增影片端点
    - 测试热榜返回格式、搜索无结果返回空列表、预刮削创建文件夹和 NFO
    - _需求：8.2, 8.8, 9.1_

- [x] 6. 检查点 — 确保所有后端 API 和测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 7. 前端类型定义和 API 封装
  - [x] 7.1 扩展 `frontend/types/index.ts`
    - 新增 `QualityTag`、`EnhancedSearchResult`、`FilterState`、`BatchUpgradeTask`、`DoubanHotItem`、`AddMediaInfo` 类型定义
    - _需求：1.2, 2.5, 4.1, 8.2_
  - [x] 7.2 扩展 `frontend/lib/api.ts`
    - 新增 `batchSearch`、`batchDownload`、`doubanHot`、`doubanSearch`、`addMedia` API 方法
    - 增强 `download` 方法支持 `download_type` 参数
    - _需求：5.1, 5.2, 5.3, 5.4, 9.1, 9.2, 9.3_

- [x] 8. 新增前端筛选组件 `frontend/components/search/FilterBar.tsx`
  - 实现可组合筛选条件栏：分辨率下限、来源类型、视频编码、音频编码、字幕要求、文件大小上限、最低做种数
  - 提供"清除筛选"按钮恢复默认值
  - 实现前端筛选逻辑函数 `applyFilters(results, filters)`
  - _需求：2.5, 2.6, 2.7_
  - [ ]* 8.1 属性测试：筛选函数正确性
    - **属性 3：筛选函数正确性**
    - 使用 fast-check 随机生成 EnhancedSearchResult[] + FilterState，验证筛选后每条结果满足所有条件，默认筛选返回原始列表
    - **验证需求：2.6, 2.7**

- [x] 9. 重构增强 `frontend/components/search/SearchModal.tsx`
  - [x] 9.1 增强 SearchModal 核心功能
    - 新增 `currentResolution`、`qbConfigured`、`alistConfigured` props
    - 顶部显示当前视频分辨率作为对比基准
    - 可编辑搜索关键词 + 重新搜索按钮
    - 集成 FilterBar 组件进行实时筛选
    - 搜索结果按做种数降序排列
    - _需求：1.1, 1.3, 1.6, 2.1, 2.5, 2.6_
  - [x] 9.2 实现质量对比高亮和下载通道选择
    - 质量高于当前视频的结果绿色高亮 Quality_Tag，等于或低于灰色
    - 下载按钮提供 qBittorrent / Alist 通道选择
    - 未配置的通道按钮禁用并显示"未配置"提示
    - 下载成功 Toast 提示 + 3 秒后关闭，失败保持弹窗
    - _需求：2.2, 2.3, 3.1, 3.5, 6.1, 6.2_
  - [ ]* 9.3 属性测试：搜索结果排序
    - **属性 7（前端）：搜索结果按做种数降序排列**
    - 使用 fast-check 随机生成 SearchResult[]，验证排序后做种数降序
    - **验证需求：1.3**

- [x] 10. 新增批量升级面板 `frontend/components/search/BatchUpgradePanel.tsx`
  - 实现批量搜索进度展示（已完成数/总数/当前视频名称）
  - 搜索完成后展示汇总结果面板，每个视频显示推荐资源的 Quality_Tag、大小、做种数
  - 支持逐个确认/移除和一键全部下载
  - 下载通道选择（qBittorrent / Alist）
  - 下载完成后显示成功数/失败数汇总
  - _需求：4.1, 4.4, 4.5, 4.6, 4.7, 6.3_

- [x] 11. 新增影片面板 `frontend/components/media/AddMediaPanel.tsx`
  - [x] 11.1 实现豆瓣发现和搜索功能
    - 默认展示豆瓣热门电影/剧集榜单（tab 切换），显示名称、年份、评分、封面
    - 搜索框输入关键词搜索豆瓣影片
    - 豆瓣接口不可用时显示"加载失败"，提供搜索框作为替代入口
    - _需求：8.1, 8.2, 8.3, 8.8_
  - [x] 11.2 实现资源搜索和下载入库流程
    - 选择影片后使用影片名称（优先英文/原名）搜索 BT 资源
    - 复用 FilterBar 筛选体系
    - 选择资源后选择保存目录 + 下载通道 → 推送下载
    - 下载成功后调用 `POST /add-media` 完成预刮削，触发媒体库刷新
    - _需求：8.4, 8.5, 8.6, 8.7, 9.4, 9.5_

- [x] 12. 集成接入：将新组件接入主页和详情面板
  - 在 `DetailDrawer` 中接入增强版 SearchModal（传入 currentResolution 等新 props）
  - 在主页 Header 区域添加"新增影片"入口，打开 AddMediaPanel
  - 在批量操作栏中添加"批量搜索升级"按钮，打开 BatchUpgradePanel
  - _需求：1.1, 4.1, 8.1_

- [x] 13. 最终检查点 — 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户确认。

## 说明

- 标记 `*` 的子任务为可选测试任务，可跳过以加速 MVP 开发
- 每个任务引用了对应的需求编号，确保需求全覆盖
- 检查点用于阶段性验证，确保增量开发的稳定性
- 属性测试验证设计文档中定义的正确性属性，单元测试覆盖边界情况
