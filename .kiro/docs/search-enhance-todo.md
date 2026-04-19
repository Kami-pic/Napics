# [废弃] 搜索增强 — TODO

## 架构

搜索弹窗分两个 Tab：
- **网盘** — pansearch + PanSou(增强版) + 通用站点(凌风云/盘搜搜/小白盘/趣盘搜) + 慢读搜索 + 我能搜 + rrdynb + ddys → Alist 转存（夸克/阿里/百度/115/PikPak）
- **BT/磁力** — Prowlarr + Bitsearch + 磁力熊 + XL720 + Nyaa + 蜜柑 → qB 下载

## 阶段一：网盘爬虫 ✅

- [x] 1. 爬虫基础设施 `scraper_base.py`
  - [x] 1.1 请求间隔控制（1-2s 随机延迟）
  - [x] 1.2 指数退避重试（429/503/超时 自动退避，最多 3 次）
  - [x] 1.3 User-Agent 轮换池（10+ 常见浏览器 UA）
  - [x] 1.4 结果缓存（5 分钟 TTL，按关键词缓存）
  - [x] 1.5 可选代理池支持（配置项，不强制）
  - [x] 1.6 敏感词过滤器（content_filter.py，后端过滤不合适的结果）

- [x] 2. 人人电影网 (rrdynb.com) 爬虫 `pan_scraper_rrdynb.py`
  - [x] 2.1 搜索接口（GET /plus/search.php?q=关键词，普通 session 即可）
  - [x] 2.2 搜索结果页解析（dl.item-third-dl 选择器）
  - [x] 2.3 详情页解析（a 标签 + 正则双路径提取网盘链接 + 提取码）
  - [x] 2.4 统一输出：PanResult 模型
  - [x] 2.5 非分享链接过滤（pan.baidu.com/download 等）
  - ✅ 当前状态：正常可用，多次搜索后可能触发限频（请求间延迟 1.5-3s 缓解）

- [x] 3. 低端影视 (ddys.io) 爬虫 `pan_scraper_ddys.py`
  - [x] 3.1 JSON API 搜索（POST /api/search-netdisk {"q": "关键词"}）
  - [x] 3.2 base64 链接解码（link 字段 → 真实网盘 URL）
  - [x] 3.3 disk_type 中文映射 + URL 域名降级识别
  - [x] 3.4 提取码字段直接从 API 获取
  - [x] 3.5 域名从 ddys.pro 更新为 ddys.io
  - [x] 3.6 统一输出格式
  - ✅ 当前状态：正常可用，JSON API 稳定，单次搜索 100+ 条结果

- [x] 4. PanSou 集成 `pan_scraper_pansou.py`
  - [x] 4.1 调用 API，过滤目标网盘类型
  - [x] 4.2 统一输出格式
  - [x] 4.3 敏感词过滤

- [x] 4b. PanSearch 爬虫 `pan_scraper_pansearch.py`（新增，当前主力源）
  - [x] 国内直连，夸克/阿里/百度
  - [x] 统一输出格式

- [x] 4c. PanSou 增强版 `pan_scraper_pansou.py`（升级）
  - [x] 支持 plugins 参数（hunhepan/pansearch/jikepan/qupansou/labi 等 10 个插件）
  - [x] 支持 channels 参数（60+ TG 频道，服务端代搜无需 TG 账号）
  - [x] 支持 cloud_types 过滤 + merged_by_type 响应格式
  - [x] 旧接口降级兼容

- [x] 4d. 通用网盘搜索站爬虫 `pan_scraper_sites.py`（新增）
  - [x] 模板化设计：SiteConfig + GenericPanSiteScraper
  - [x] 已配置站点：凌风云/盘搜搜/小白盘/趣盘搜
  - [x] MultiSiteScraper 聚合多站点结果
  - [x] 结构化解析 + 全文正则降级
  - ⚠️ 当前状态：凌风云需登录、盘搜搜 404、小白盘 403、趣盘搜超时，全部暂关

- [x] 4e. 慢读搜索 `pan_scraper_slowread.py`（新增）
  - [x] so.slowread.net，支持 16 种网盘类型
  - [x] API 接口探测 + HTML 解析双路径
  - [x] 统一输出格式
  - ⚠️ 当前状态：纯 JS 渲染，requests 无法获取结果，需 Playwright 或逆向 API，暂关

- [x] 4f. 我能搜 `pan_scraper_wnsearch.py`（新增）
  - [x] wnsearch.top，夸克/百度/迅雷/UC
  - [x] API 接口探测 + HTML 解析双路径
  - [x] 统一输出格式
  - ⚠️ 当前状态：纯 JS 渲染，同上，暂关

- [x] 4g. 狗狗盘搜 `pan_scraper_gogopanso.py`（新增）
  - [x] gogopanso.com（aliyunpanshare 搜索前端），每日更新影视资源
  - [x] 公开 JSON API（gogopanso.com:3642/search），无反爬
  - [x] 夸克/阿里/百度，链接存活率 100%
  - [x] 标题清洗（去拼音首字母前缀）
  - ✅ 当前状态：正常可用，已启用

- [x] 5. 搜索聚合 API `pan_search_service.py` + `/search/pan`
  - [x] 5.1 并发调用已启用的源
  - [x] 5.2 结果合并去重（share_url 精确去重 + 标题相似度去重）
  - [x] 5.3 关键词相关性过滤（标题必须含搜索词片段，过滤后为空时回退返回全部）
  - [x] 5.4 按网盘类型分组 + 优先级排序
  - [x] 5.5 未挂载的网盘类型标记 `mounted: false`

## 阶段二：Alist 转存对接 ✅（夸克已通）

- [x] 6. Alist 挂载状态检查
  - [x] 6.1 查询 Alist 已挂载存储列表
  - [x] 6.2 建立 pan_type → Alist 驱动映射
  - [x] 6.3 API `/alist/mounts` 返回已挂载网盘列表
  - [x] 6.4 前端搜索结果中未挂载的网盘置灰

- [x] 7. 夸克转存链路 `quark_transfer.py`
  - [x] 7.1 从 Alist 提取 Cookie → stoken → 文件列表 → 转存
  - [搁置] 7.2 其他网盘转存（阿里/百度/115/PikPak）— 逆向工作量大且易失效，不做
  - [搁置] 7.3 Alist 错误码详细映射 — 依赖 7.2，不做
  - [搁置] 7.4 转存任务纳入 DownloadManager 队列 — 依赖 7.2，不做
  - [搁置] 7.5 转存完成后文件归位到 save_path — 依赖 7.2，不做

## 阶段三：前端搜索弹窗 ✅

- [x] 8. SearchModal 分 Tab
  - [x] 8.1 Tab 切换：BT/磁力 | 网盘
  - [x] 8.2 网盘 Tab：按网盘类型分组显示（PanResultsView）
  - [x] 8.3 网盘卡片：标题 + 网盘类型标签(彩色) + 来源 + 转存按钮（PanResultCard）
  - [x] 8.4 未挂载网盘置灰
  - [x] 8.5 转存路径复用 savePath
  - [x] 8.6 转存状态 toast（成功/失败/空间不足/链接失效）

## 阶段四：BT 直搜补充 ✅

> 详细设计和进度见 `bt-expand-todo.md`

- [x] 9. Bitsearch (bitsearch.to) — JSON API，欧美片源核心，curl_cffi+代理
- [x] 10. 磁力熊 (cilixiong.org) — POST 搜索→详情页→磁力，国产片补充，直连
- [x] 11. XL720 (xl720.com) — GET 搜索→详情页→磁力+迅雷，国产片补充，直连
- [x] 12. Nyaa (nyaa.si) — HTML 表格解析，动画/日剧核心，代理直连绕过 Prowlarr
- [x] 13. 蜜柑计划 (mikanani.me) — RSS 搜索+订阅框架注册，番剧订阅核心，代理
- [x] 14. 反爬基础设施：scraper_base 新增 curl_cffi + CF 统一检测 is_cf_blocked()
- [x] 15. 搜索路由重构：_merge_bt_extra_sources() 统一合并 5 源，infohash 去重
- [x] 16. 前端适配：索引器标签品牌色（蓝/橙/紫/粉）+ IndexerSelect 品牌色圆点

## 阶段五：配置 ✅（核心已完成）

> 搜索源开关已在 SearchModal 内 SearchSettingsPanel 实现，持久化到 config.json。
> 其余设置项（PanSou 地址/代理池/敏感词列表）为低优先级，按需推进。

- [x] 10.2 搜索源开关（SearchSettingsPanel + /search/sources 端点 + config.json 持久化）
- [搁置] 10.1 PanSou API 地址（可选）— 低优先级
- [搁置] 10.3 网盘类型优先级 — 低优先级
- [搁置] 10.4 代理池配置（可选）— 低优先级
- [搁置] 10.5 敏感词列表（可自定义）— 低优先级

## 技术要点

- 转存 ≠ 下载：同盘转存秒完成，跨盘走离线下载（异步）
- 提取码必须和 share_url 一起提取，否则 Alist 无法转存
- Alist 挂载前置检查：未挂载的网盘类型前端置灰
- rrdynb 启用 curl_cffi 浏览器指纹，多次搜索后可能触发 CF 限频（临时性）
- ddys 已升级为 JSON API（POST /api/search-netdisk），不再需要 HTML 解析
- pansearch.me 是当前主力源，连续搜索会被限频需间隔
- 夸克转存 API：stoken 含特殊字符需 URL 编码，fid_token_list 用 share_fid_token
- Alist 离线下载不支持网盘分享链接，只支持 magnet/http/ed2k
- PanSou 增强版：通过 plugins + channels 参数一次调用覆盖 10 个搜索插件 + TG 频道
- 通用站点爬虫：模板化设计，新增站点只需添加 SiteConfig 配置
- 慢读/我能搜：API 探测 + HTML 解析双路径，适应站点变化

