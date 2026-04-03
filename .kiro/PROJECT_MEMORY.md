# NAS Media Manager — 项目记忆

## 概述
NAS 影视媒体库管理工具。前端 Next.js 16 + React 19 + Tailwind CSS 4，后端 Python FastAPI。
扫描 NAS 视频、刮削元数据、智能整理、搜索升级资源、发现新影片、批量管理。

## 后端核心模块 (backend/)
- `main.py` — FastAPI 入口，树构建，所有 API
- `tmdb_client.py` — TMDB 刮削（ScrapeResult 含 seasons_info），parse_filename（含 absolute_episode）
- `scraper.py` — NFO 读写 + 海报下载 + 递归刮削 + `_scrape_tv_v3` 确权式刮削
- `organizer.py` — 文件夹分类 + 重命名 + 文件包裹 + `reorganize_seasons_by_nfo`
- `analyzer.py` — 独立分析层 + 层级清洗
- `ai_organizer.py` — AI 建议 + `ai_extract_episode`
- `config_manager.py` — 配置管理（含 sort_weights 可配置排序权重、torrent_blacklist）
- `shadow_name_manager.py` — 影子名 CRUD
- `searcher.py` — ProwlarrClient + enhanced_search（回退链+二次匹配+全局过滤）
- `secondary_matcher.py` — 二次匹配器
- `global_filter.py` — 全局过滤器
- `quality_parser.py` — BT 标题质量解析（release_group、is_surround）
- `episode_search.py` — 剧集搜索策略（整季包+逐集+同源匹配）
- `batch_recommend.py` — 批量推荐算法（6 维度加权评分，权重可配置）
- `download_manager.py` — 下载任务队列（沙盒隔离、持久化防抖、qB/Alist 双通道、完成后自动转移到 save_path）
- `file_relocator.py` — 文件归位器（复用 V3 流水线）
- `recycle_bin.py` — 回收站（30 天过期清理）
- `torrent_blacklist.py` — 无效种子黑名单（TTL 24h）
- `analysis_cache.py` — 分析结果缓存（增量更新）
- `downloader.py` — qBittorrentClient + AlistManager（add_torrent 直接传 save_path 给 qB）
- `pan_models.py` — 网盘搜索统一数据模型（PanType/PanResult/PanSearchResponse/MountInfo/TransferRequest/TransferResult/PathMapping）
- `scraper_base.py` — 爬虫基类（Session 持久化/warm_up/UA 轮换/指数退避/缓存/链接预检）
- `content_filter.py` — 敏感词过滤 + 三项硬指标质量过滤（分辨率/体积/整季）
- `pan_scraper_pansearch.py` — PanSearch (pansearch.me) 爬虫，国内可直连，支持夸克/阿里/百度
- `pan_scraper_rrdynb.py` — 人人电影网爬虫（Cloudflare 拦截，暂不可用，需 Playwright）
- `pan_scraper_ddys.py` — 低端影视爬虫（域名不可达，暂不可用）
- `pan_scraper_pansou.py` — PanSou API 客户端（需用户配置 API 地址）
- `pan_search_service.py` — 网盘搜索聚合服务（并发调用/去重/过滤/分组/挂载标记）

## 前端核心模块 (frontend/)
- `app/page.tsx` — 主页面，三排布局：Header | 面包屑+Toolbar | 内容区
- `components/layout/Header.tsx` — 顶栏：标题+统计 | 扫描、下载管理、表单管理、设置
- `components/layout/Toolbar.tsx` — 工具栏（和面包屑同行）：快速同步、撤回操作、健康报告 | 批处理、视图切换
- `components/media/CardGrid.tsx` — 卡片网格 + 展开面板
- `components/detail/DetailDrawer.tsx` — 详情面板（搜索词构造：cnName 去重+enName 去中文）
- `components/search/SearchModal.tsx` — 搜索弹窗（标签系统+缓存+过滤器+保存路径可编辑）
- `components/search/BatchUpgradePanel.tsx` — 批量升级面板
- `components/media/AnalysisReport.tsx` — 健康报告弹窗（从 Toolbar 打开）
- `components/media/OperationHistory.tsx` — 操作历史弹窗（整理记录 Tab + 回收站 Tab 合并）
- `components/media/OrganizeProgress.tsx` — 一键整理进度面板（SSE 5 步）
- `components/download/DownloadManagerPanel.tsx` — 下载管理面板（进度+删除记录+新旧替换确认）
- `components/settings/SettingsModal.tsx` — 设置弹窗（排序权重+过滤规则+编码偏好+回收站）

## 页面布局（当前）
- 第一排 Header：标题+统计 | 扫描媒体库、下载管理、表单管理、⚙设置
- 第二排：面包屑 | 快速同步、撤回操作、健康报告、批处理、卡片/列表
- 快速同步状态在 Header 副标题显示（同步中.../+N -N）
- 撤回操作 → 打开 OperationHistory 弹窗（整理记录+回收站两个 Tab）
- 健康报告 → 打开 AnalysisReport 弹窗
- 下载管理 → 打开 DownloadManagerPanel 弹窗

## 搜索词构造规则
- cnName：从 clean_name 提取中文字符，Set 去重避免重复
- enName：shadow_name 去年份再去中文字符 > clean_name 中英文部分
- 搜索框默认词：cnName + enName（cn/en 实质相同时只用 cn）
- 搜索标签按 isSame 判断避免重复标签
- 保存路径：优先 searchContext.savePath（视频/文件夹实际路径）> currentFolder > NAS 根路径

## 下载管理架构
- qB 下载：直接传 save_path 给 qB（不再用沙盒），qB 下载到目标目录
- 旧任务兼容：沙盒中的旧任务完成后 _relocate_to_save_path 自动转移
- Alist 双阶段：cloud_download → local_sync → completed
- 下载完成后自动转移文件到 save_path（_relocate_to_save_path）
- 删除记录：DELETE /download-manager/task + POST /download-manager/delete-tasks
- unknown/lost 状态也可删除

## 配置
- NAS: `\\DS218play\share\视频\`
- TMDB: 已配置 + proxy `http://127.0.0.1:7897`
- Prowlarr: `localhost:9696` / qBittorrent: `localhost:8080` / Alist: `localhost:5244`
- Alist 挂载网盘：夸克、阿里、百度、115、PikPak
- 启动：start.bat / 停止：stop.bat / 前端 3031 / 后端 8000

## 颜色体系
- 主背景 `#0f0f0f`，面板 `#141414`，搜索卡片 `#0f0f0f`
- 边框 `white/[0.06]`，输入框 `white/[0.04]`
- 标签：4K 金色、1080p 蓝色、环绕声紫色、中字蓝色、整季黄色、720p/编码/索引器 灰色

## 下一步：搜索增强（TODO 在 .kiro/docs/search-enhance-todo.md）
- 搜索弹窗双通道：BT/磁力（Prowlarr→qB）| 网盘（pansearch→夸克转存/打开）
- 底部通道切换开关（BT/磁力 | 网盘），搜索按钮颜色跟随通道
- 夸克转存已实现：从 Alist 自动提取 Cookie → 调用夸克 API 一键转存到自己的夸克网盘
- 网盘筛选器：按网盘类型（夸克/阿里/百度）筛选结果
- BT 结果去掉 Alist 按钮，只保留"下载"（走 qB）
- 当前可用源：pansearch.me（国内直连，夸克/阿里/百度）
- 暂不可用：rrdynb（Cloudflare 拦截）、ddys（域名不可达）— 需 Playwright
- 待做：更多搜索源、磁力熊直搜、配置管理、百度/115/PikPak 转存 API

## 搜索增强新增模块
- `quark_transfer.py` — 夸克网盘转存（从 Alist 提取 Cookie → stoken → 文件列表 → 转存）
- `pan_scraper_pansearch.py` — PanSearch 爬虫（pansearch.me，国内直连）
- `pan_search_service.py` — 网盘搜索聚合（并发调用/关键词相关性过滤/去重/分组）
- API: `/search/pan`（网盘搜索）、`/alist/mounts`（挂载状态）、`/alist/transfer`（夸克转存）

## 启动脚本
- `start.bat` / `stop.bat` — 只管前后端（不动 Alist/qB/Prowlarr）
- `start_all.bat` / `stop_all.bat` — 全部服务
- `restart.bat` — 一键重启前后端

## 下一步待做（TODO 在 .kiro/docs/auto-replace-todo.md）
- 下载完成自动替换闭环：实时刷新 → 一键替换 → 自动整理开关
- 标准化结构增强：散装封装进 Season、新旧共存检测、分类→标准化→替换三步流水线
- 搜索增强：更多网盘搜索源、磁力熊直搜、百度/115/PikPak 转存 API
- 测试田：模拟文件夹用于安全测试替换流程

## 设计文档索引
- 搜索下载 spec：`.kiro/specs/search-download/`
- 搜索增强 TODO：`.kiro/docs/search-enhance-todo.md`
- V3 架构：`.kiro/docs/organize-guide-v3.md`
- 整理 TODO：`.kiro/docs/organize-todo.md`

## 已知问题与经验教训
- Prowlarr 本地连接必须禁用系统代理
- start.bat 只管前后端，start_all.bat 管全部服务（Alist/qB/Prowlarr 不适合频繁停止）
- 后端 uvicorn 不要用 --reload（新文件触发重载时 import 链路会出问题导致 500）
- 搜索词不要用 scrape.title，要用 clean_name 拆分中英文 + shadow_name 作英文名
- shadow_name 可能含中文，enName 构造时必须去掉中文字符
- cnParts 提取中文段后用 Set 去重，避免 clean_name 中重复中文名
- 搜索缓存只缓存有结果的，空结果不缓存
- 前端过滤器是纯前端行为，不触发重新搜索
- qB add_torrent 同时支持种子 URL 和磁力链接
- ddys.io 有较强反爬（JS 验证/混淆），可能需要 cloudscraper 或 playwright
- 网盘转存必须同时提取 share_url + 提取码
- Alist 未挂载的网盘类型前端应置灰标"未挂载"
- Alist 挂载状态：夸克/PikPak/115 work，阿里 token 过期，百度授权问题
- 夸克转存 API：stoken 含特殊字符需 URL 编码，fid_token_list 用 share_fid_token 不是 fid
- pansearch.me 连续搜索会被限频，需要间隔
- alipansou.com 用 JS 加密渲染，纯 requests 拿不到结果
- Alist 离线下载不支持网盘分享链接，只支持 magnet/http/ed2k
- 网盘转存需要各网盘自己的 API（夸克已实现，其他待做）
- 快速同步新增超过 50 个文件时自动切换快速模式（跳过 ffprobe，只读文件名+大小）
- 扫描/同步的 event_generator 必须整体包 try-except，单文件失败不能中断整个流
- ffprobe 必须设 timeout=15（SMB 路径上 rm/rmvb 等老格式可能卡住）
- 标准化结构需要处理"散装+新下载文件夹共存"的场景，先封装散装再处理替换
- 执行顺序：分类（tv/movie/mix）→ 标准化（散装封装）→ 替换（新旧对比）
