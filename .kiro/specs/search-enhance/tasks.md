# 任务清单：搜索增强 (search-enhance)

## 阶段一：爬虫基础设施 + 数据模型

- [x] 1. 数据模型与基础设施
  - [x] 1.1 创建 `backend/pan_models.py`：PanType 枚举、PanResult 模型（含 share_url 域名白名单校验、resolution/size_gb/is_complete/file_count/alive/clean_title 字段）、PanSearchResponse、SourceStatus、MountInfo、TransferRequest、TransferResult、PathMapping（SMB↔Alist 路径映射）
  - [x] 1.2 创建 `backend/scraper_base.py`：ScraperBase 基类 — requests.Session 会话持久化、warm_up() 预热、random_delay(1-2s)、UA 轮换池(10+)、request_with_backoff(指数退避 2s/4s/8s)、结果缓存(5min TTL)、可选代理池、标题清洗逻辑（去站点水印/乱码、提取分辨率、整季判定）、fast_check_url() 链接存活预检
  - [x] 1.3 创建 `backend/content_filter.py`：ContentFilter 敏感词过滤器 + PanResultFilter 三项硬指标过滤（分辨率强校验/体积区间控制/整季判定）

## 阶段二：网盘爬虫（三个源）

- [x] 2. 人人电影网爬虫
  - [x] 2.1 创建 `backend/pan_scraper_rrdynb.py`：RrdynbScraper 继承 ScraperBase — 帝国 CMS POST 表单搜索、搜索结果页解析（标题/详情页URL/年份）、详情页网盘链接提取（正则匹配 share_url + password 配对）、_validate_share_url 域名白名单校验、多网盘类型独立 PanResult 条目、统一输出 PanResult 列表

- [x] 3. 低端影视爬虫
  - [x] 3.1 创建 `backend/pan_scraper_ddys.py`：DdysScraper 继承 ScraperBase — warm_up() 覆写（首页获取 Cookie/Token）、Cloudscraper 优先 → Playwright 降级、搜索结果页解析、_decrypt_resource_id() JS 解密逻辑（Base64 变体/位移加密）、混淆 URL 还原、5 秒超时强制返回（已解析部分结果或空结果）、统一输出 PanResult 列表

- [x] 4. PanSou API 集成
  - [x] 4.1 创建 `backend/pan_scraper_pansou.py`：PanSouClient 继承 ScraperBase — 调用 /api/search、按目标网盘类型过滤、敏感词过滤、未配置 API 地址时跳过返回空结果、统一输出 PanResult 列表

## 阶段三：网盘搜索聚合 API

- [x] 5. 网盘搜索聚合服务
  - [x] 5.1 创建 `backend/pan_search_service.py`：PanSearchService — 根据 AppConfig 初始化已启用的爬虫实例、asyncio.gather 并发调用、双重去重（share_url 精确 + 标题 Levenshtein > 0.9 同 pan_type 折叠）、敏感词过滤、按网盘类型分组（优先级从 AppConfig 读取）、实时比对 AlistManager 挂载缓存标记 mounted 状态、返回 PanSearchResponse（含各源状态）
  - [x] 5.2 在 `backend/main.py` 新增 `GET /search/pan` 路由 — 接收 keyword 参数，调用 PanSearchService.search()，返回 PanSearchResponse

## 阶段四：Alist 挂载检查 + 转存链路

- [ ] 6. Alist 挂载状态管理
  - [ ] 6.1 扩展 `backend/downloader.py` AlistManager — get_mount_status()（启动时调用 /api/admin/storage/list 动态构建 pan_type→驱动映射，关键词反向匹配不硬编码）、refresh_mount_cache()（5 分钟定时刷新）、is_mounted()、get_mount_path()
  - [ ] 6.2 在 `backend/main.py` 新增 `GET /alist/mounts` 路由 — 返回已挂载网盘类型列表及挂载路径

- [ ] 7. Alist 转存链路（三不转存原则）
  - [ ] 7.1 扩展 `backend/downloader.py` AlistManager — check_local_cache_space()（PC 本地缓存盘 + 目标 SMB 磁盘双重空间校验）、transfer_pan_share()（同盘秒传 vs 跨盘离线判定，跨盘前先校验本地空间，Size > Available*0.8 拦截）、_map_error_code()（空间不足/同名冲突/链接失效/提取码错误/本地缓存不足）、跨盘转存完成后强制清理 Alist 临时目录
  - [ ] 7.2 扩展 `backend/download_manager.py` DownloadTask — 新增 task_type/transfer_type/pan_type/share_url/password/transfer_id 字段、submit() 支持 transfer 类型任务（三不转存前置校验：空间不足不转存/非整季不转存/无法归位不转存）、transfer_id 防重复提交（sha256(share_url)[:12]）、_sync_alist_progress() 兼容转存任务状态同步
  - [ ] 7.3 创建 `backend/path_mapper.py`：SMB↔Alist 路径映射器 — 建立本地 SMB 路径与 Alist 虚拟路径的映射关系、归位安全策略（目标已存在同名文件夹→重命名.tmp→移动新资源→成功后删.tmp/失败恢复）、语义化重命名（强制格式：中文名 (年份) S0x）
  - [ ] 7.4 在 `backend/main.py` 新增 `POST /alist/transfer` 路由 — 接收 TransferRequest，三不转存前置校验，调用 AlistManager.transfer_pan_share()，创建 DownloadTask 纳入队列

## 阶段五：磁力熊直搜补充

- [ ] 8. 磁力熊爬虫
  - [ ] 8.1 创建 `backend/pan_scraper_cilixiong.py`：CilixiongScraper 继承 ScraperBase — 搜索 cilixiong.org、详情页磁力链接提取、输出 SearchResult（复用现有模型，indexer 标记为"磁力熊"）、提取"最后更新时间"作为排序权重
  - [ ] 8.2 扩展 `backend/searcher.py` enhanced_search — 并发调用 Prowlarr + CilixiongScraper、按 btih hash 去重 + 标题规范化去重（Levenshtein > 0.9 且大小一致则折叠）、磁力熊结果 indexer 字段标记"磁力熊"、CilixiongScraper 失败时仅返回 Prowlarr 结果

## 阶段六：前端搜索弹窗改造

- [ ] 9. SearchModal Tab 切换
  - [ ] 9.1 修改 `frontend/components/search/SearchModal.tsx` — 新增 Tab 切换（BT/磁力 | 网盘），默认 BT/磁力 Tab、切换 Tab 时保留各 Tab 缓存结果、搜索仅触发当前 Tab 对应数据源
  - [ ] 9.2 网盘 Tab 实现 — 调用 `/search/pan` 接口、按网盘类型分组展示、网盘卡片（标题 + 彩色类型标签 + 来源 + 转存按钮）、未挂载网盘置灰 + "未挂载"标签 + 转存按钮禁用、转存路径复用 savePath、转存状态 toast（成功/失败/空间不足/链接失效/本地缓存不足）
  - [ ] 9.3 搜索源状态栏 — 底部显示各源状态（✓成功/✗失败/○禁用）

## 阶段七：配置管理

- [ ] 10. 搜索源配置
  - [ ] 10.1 扩展 `backend/config_manager.py` AppConfig — 新增 search_sources（rrdynb/ddys/pansou/cilixiong 开关）、pansou_api_url、pan_type_priority、scraper_proxy、sensitive_words 字段
  - [ ] 10.2 修改 `frontend/components/settings/SettingsModal.tsx` — 新增"搜索源"配置区：搜索源开关、PanSou API 地址、网盘优先级拖拽排序、代理地址、敏感词列表管理
