# [TODO] 搜索增强 — TODO

## 架构

搜索弹窗分两个 Tab：
- **网盘** — pansearch + rrdynb + ddys + PanSou → Alist 转存（夸克/阿里/百度/115/PikPak）
- **BT/磁力** — Prowlarr + 磁力熊直搜 → qB 下载

## 阶段一：网盘爬虫 ✅

- [x] 1. 爬虫基础设施 `scraper_base.py`
  - [x] 1.1 请求间隔控制（1-2s 随机延迟）
  - [x] 1.2 指数退避重试（429/503/超时 自动退避，最多 3 次）
  - [x] 1.3 User-Agent 轮换池（10+ 常见浏览器 UA）
  - [x] 1.4 结果缓存（5 分钟 TTL，按关键词缓存）
  - [x] 1.5 可选代理池支持（配置项，不强制）
  - [x] 1.6 敏感词过滤器（content_filter.py，后端过滤不合适的结果）

- [x] 2. 人人电影网 (rrdynb.com) 爬虫 `pan_scraper_rrdynb.py`
  - [x] 2.1 搜索接口（cloudscraper 绕过 Cloudflare）
  - [x] 2.2 搜索结果页解析
  - [x] 2.3 详情页解析（提取网盘链接 + 提取码）
  - [x] 2.4 统一输出：PanResult 模型
  - ⚠️ 当前状态：Cloudflare 拦截，需 Playwright 才能稳定使用

- [x] 3. 低端影视 (ddys.io) 爬虫 `pan_scraper_ddys.py`
  - [x] 3.1 搜索接口
  - [x] 3.2 搜索结果页解析
  - [x] 3.3 网盘链接解析
  - [x] 3.4 提取码匹配
  - [x] 3.5 cloudscraper 实现
  - [x] 3.6 统一输出格式
  - ⚠️ 当前状态：域名不可达，需 Playwright

- [x] 4. PanSou 集成 `pan_scraper_pansou.py`
  - [x] 4.1 调用 API，过滤目标网盘类型
  - [x] 4.2 统一输出格式
  - [x] 4.3 敏感词过滤

- [x] 4b. PanSearch 爬虫 `pan_scraper_pansearch.py`（新增，当前主力源）
  - [x] 国内直连，夸克/阿里/百度
  - [x] 统一输出格式

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
  - [ ] 7.2 其他网盘转存（阿里/百度/115/PikPak）— 暂不支持，打开链接手动保存
  - [ ] 7.3 Alist 错误码详细映射（空间不足/同名冲突/链接失效/提取码错误）
  - [ ] 7.4 转存任务纳入 DownloadManager 队列
  - [ ] 7.5 转存完成后文件归位到 save_path

## 阶段三：前端搜索弹窗 ✅

- [x] 8. SearchModal 分 Tab
  - [x] 8.1 Tab 切换：BT/磁力 | 网盘
  - [x] 8.2 网盘 Tab：按网盘类型分组显示（PanResultsView）
  - [x] 8.3 网盘卡片：标题 + 网盘类型标签(彩色) + 来源 + 转存按钮（PanResultCard）
  - [x] 8.4 未挂载网盘置灰
  - [x] 8.5 转存路径复用 savePath
  - [x] 8.6 转存状态 toast（成功/失败/空间不足/链接失效）

## 阶段四：磁力直搜补充

- [ ] 9. 磁力熊 (cilixiong.org) 爬虫
  - [ ] 9.1 搜索 + 详情页 → 磁力链接
  - [ ] 9.2 合并到 BT/磁力 Tab
  - [ ] 9.3 按 btih hash 去重
  - [ ] 9.4 "最后更新时间"权重（静态做种数不可靠）

## 阶段五：配置

- [ ] 10. 设置页
  - [ ] 10.1 PanSou API 地址（可选）
  - [ ] 10.2 搜索源开关（rrdynb/ddys/pansou/pansearch/cilixiong）
  - [ ] 10.3 网盘类型优先级
  - [ ] 10.4 代理池配置（可选）
  - [ ] 10.5 敏感词列表（可自定义）

## 技术要点

- 转存 ≠ 下载：同盘转存秒完成，跨盘走离线下载（异步）
- 提取码必须和 share_url 一起提取，否则 Alist 无法转存
- Alist 挂载前置检查：未挂载的网盘类型前端置灰
- rrdynb/ddys 当前被反爬拦截，需要 Playwright 才能稳定使用
- pansearch.me 是当前主力源，连续搜索会被限频需间隔
- 夸克转存 API：stoken 含特殊字符需 URL 编码，fid_token_list 用 share_fid_token
- Alist 离线下载不支持网盘分享链接，只支持 magnet/http/ed2k
