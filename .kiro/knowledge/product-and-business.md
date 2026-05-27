# Napics 产品定义与商业化方案

> 本文档完整描述 Napics 的产品定位、功能架构、插件生态、商业化策略和技术实现。
> 用于跨团队/跨 AI 对齐认知，查漏补缺。

---

## 一、产品定位

**一句话**：面向 NAS 高阶用户的智能媒体资产管理系统。

**目标用户**：
- 拥有 NAS（群晖/威联通/Unraid/自建）的影视爱好者
- 有 TB 级媒体库，需要自动化管理（刮削、整理、搜索、下载、追更）
- 技术水平中等偏上（能配置 Docker、Prowlarr、qBittorrent）
- 对 Emby/Plex/Jellyfin 的"播放"不满足，需要"管理"能力

**竞品对比**：

| 产品 | 定位 | 差异 |
|------|------|------|
| Plex/Emby/Jellyfin | 媒体播放器 | 只管播放，不管获取和整理 |
| MoviePilot/NasTools | 自动化下载 | 侧重自动化流水线，UI 简陋 |
| tinyMediaManager | 刮削工具 | 只管刮削，不管搜索下载 |
| **Napics** | 一站式管理 | 刮削+整理+搜索+下载+推荐+订阅，现代 UI |

**核心价值主张**：
1. **一站式**：从发现→搜索→下载→整理→刮削→浏览，全链路闭环
2. **智能化**：AI 辅助分类判定、智能搜索词构造、质量评估、推荐
3. **插件化**：搜索源/元数据源/下载器均可扩展，社区驱动
4. **现代 UI**：Next.js + Tailwind，暗色主题，流畅交互

---

## 二、功能架构

### 核心功能（Core，开源免费）

| 模块 | 功能 |
|------|------|
| 媒体库管理 | 扫描、浏览、目录树、文件夹分类判定 |
| 智能刮削 | 多源元数据匹配（TMDB/豆瓣/Bangumi）、海报下载、NFO 生成 |
| 质量分析 | 100 分制质量评分、低画质检测、编码/分辨率/HDR 识别 |
| 智能整理 | AI 分类判定、季目录归位、智能重命名（影子名）、归位替换 |
| 全网搜索 | 聚合 BT/PT/网盘多源搜索、智能关键词回退、流式结果 |
| 一键下载 | 对接 qBittorrent/OpenList、下载完成自动归位 |
| 批量升级 | 检测低画质文件、一键搜索更高质量版本替换 |
| 发现推荐 | 基于媒体库偏好的个性化推荐（TMDB/豆瓣热门） |
| 订阅追更 | RSS 定时轮询、自动下载新集、洗版升级 |
| 完整性检测 | 基于 TMDB 的季集缺失分析 |
| 插件框架 | 插件加载/注册/卸载、插件中心 UI、第三方源管理 |

### 插件能力（通过插件扩展）

| 类型 | 说明 |
|------|------|
| 元数据源 | TMDB、豆瓣、Bangumi（可扩展其他源） |
| 搜索源 | Prowlarr、BT 直搜（12+源）、网盘搜索（9+源） |
| RSS 源 | 动画 RSS（蜜柑/Nyaa/ACG.RIP 等）、影视 RSS（EZTV/YTS） |
| 下载器 | qBittorrent、OpenList/Alist |
| 存储 | OpenList 网盘挂载浏览 |
| 增强功能 | 完整性检测、发现推荐、本地媒体感知、订阅追更 |

---

## 三、插件生态架构

### 三层仓库

```
┌─────────────────────────────────────────────────────┐
│  Napics 主仓库（GPL-3.0，Kami-pic 账号）             │
│  Core + 插件框架 + SDK + 5 个预装插件                │
└─────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
┌─────────────────────────────────┐ ┌─────────────────────────┐
│ plugins-of-napics（小号仓库）    │ │ napics-pro（私有仓库）   │
│ 灰色/高风险插件（11 个分组）     │ │ 付费插件                 │
│ BT 直搜 / 网盘搜索 / RSS 源     │ │ AI 增强 / 全链路自动化   │
└─────────────────────────────────┘ └─────────────────────────┘
```

### 插件分层详情

**预装 5 个**（主仓库，开箱即用）：
- metadata-tmdb — TMDB 影视元数据
- metadata-douban — 豆瓣中文元数据
- download-qbittorrent — qBittorrent 下载
- feature-discover — 智能推荐
- feature-local-match — 本地媒体感知

**主仓库非预装 5 个**（插件中心手动安装）：
- metadata-bangumi — Bangumi 动画元数据
- feature-completeness — 季集完整性检测
- feature-subscribe — 订阅追更
- search-prowlarr — Prowlarr 搜索聚合
- storage-openlist — OpenList 网盘浏览

**社区仓库 11 个**（第三方源安装，灰色/高风险）：

BT 搜索 5 包：
- search-bt-mirror — Bitsearch/1337x/LimeTorrents（镜像站风险）
- search-bt-movie-tv — YTS/EZTV（影视公开站）
- search-bt-anime-jp — Nyaa/Bangumi Moe（日本动画）
- search-bt-anime-cn — 蜜柑/ACG.RIP/动漫花园（中文动画，需代理）
- search-bt-cn — 磁力熊/XL720（中文磁力站）

网盘搜索 3 包：
- search-pan-main — PanSearch/PanSou（聚合引擎）
- search-pan-github — 狗狗盘搜/GitHub（同源数据）
- search-pan-resource — 人人电影/低端影视（资源站直搜）

其他 3 个：
- rss-anime — 动画 RSS 源包
- rss-tv-movie — 影视 RSS 源包
- download-openlist — OpenList 离线下载

### 插件拆分原则
- 按风险特征分组：一个源挂了只影响同组，不全军覆没
- BT 按维度拆：镜像站风险 / 影视公开站 / 日本动画 / 中文动画 / 中文磁力
- 网盘按数据源拆：聚合引擎 / 同源数据 / 资源站直搜

---

## 四、商业化策略

### 定价模式：一次性买断 + 更新期

| 层级 | 价格 | 内容 |
|------|------|------|
| **免费版** | ¥0 | Core + 预装插件 + 社区插件（全部功能可用） |
| **Pro 买断** | ¥99-149 | 付费插件包，含 1 年更新 |
| **续费更新** | ¥49/年 | 到期后可选续费获取新版本，不续费仍可使用已下载版本 |
| **早鸟终身** | ¥49 | 前 100 名用户终身授权（社区种子用户） |

### 为什么不用订阅制
- NAS 用户群体极度反感"本地软件收月费"（Plex 涨价事件前车之鉴）
- Napics 是本地运行的工具，不依赖云服务
- 买断制更符合中国用户付费习惯

### 付费插件规划

| 插件 ID | 名称 | 卖点 |
|---------|------|------|
| napics-pro-ai | AI 智能整理 | 方案生成+自动执行+学习偏好 |
| napics-pro-automation | 全链路自动化 | 监控→整理→归位→通知 |
| napics-pro-subscribe | 智能订阅 | 洗版决策+质量升级+日历 |
| napics-pro-analytics | 媒体库分析 | 健康报告+存储优化建议 |

### 支付平台：LemonSqueezy

- 作为 Merchant of Record，自动处理全球税务
- 内置 License Key API（activate / validate / deactivate）
- 费率：5% + $0.50/笔
- 支持信用卡/PayPal/支付宝

### License Key 验证流程

```
用户购买 → LemonSqueezy 生成 License Key → 邮件发送给用户
→ 用户在 Napics 设置页填入 Key → 后端调用 LemonSqueezy API 验证
→ 验证通过 → 保存状态到 config.json → 解锁付费插件源下载
→ 下载后本地运行，不再验证（离线友好）
```

### 关键约束
- 不做运行时 License 验证（离线友好，NAS 可能无外网）
- 付费插件的接口和免费插件完全一致（同一套 SDK）
- 免费版功能完整，付费只是"更智能/更自动"

---

## 五、技术架构

### 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.10+ / FastAPI / Uvicorn |
| 前端 | Next.js 16 / React 19 / Tailwind CSS 4 |
| 数据 | JSON 文件持久化（无数据库） |
| 插件 SDK | napics-plugin-sdk（PyPI 包） |

### 后端分层

```
入口层        main.py（薄壳，只注册路由）
路由层        routes/*（参数校验 + 调用业务层）
业务逻辑层    organizer / renamer / download_manager / search_service 等
数据获取层    tmdb_client / searcher / scraper 等
基础设施层    config_manager / plugin_manager / license_service
插件层        plugins/*（通过 PluginContext 注册能力）
```

### 插件系统技术实现

- `plugin_manager.py` — 插件加载/注册/卸载/远程安装
- `plugin_context.py` — 插件运行时上下文（PluginContext）
- `provider_contracts.py` — Provider 协议定义
- `provider_models.py` — 数据模型（DTO）
- `license_service.py` — License Key 验证（LemonSqueezy API）

### 部署方式

- 当前：Windows 本地运行（start_all.bat）
- 计划：Docker 部署（NAS 场景）
- 前端：Next.js 静态导出 + API 代理

---

## 六、开源协议

**GPL-3.0**

- 核心代码开源，衍生作品必须也开源
- 付费插件（napics-pro）是独立仓库，通过插件接口交互，不是衍生作品
- 防止别人拿代码改名闭源商用

---

## 七、当前状态与下一步

### 已完成
- ✅ Core 功能完整（扫描/刮削/整理/搜索/下载/推荐/订阅）
- ✅ 插件框架（加载/注册/卸载/远程安装/从 URL 安装）
- ✅ 插件 SDK + 模板仓库 + 开发指南
- ✅ 社区插件仓库（11 个分组，v3.0.0）
- ✅ License Key 验证基础设施（LemonSqueezy API 对接）
- ✅ 前端设置页 Pro 授权管理
- ✅ README + GPL-3.0 LICENSE
- ✅ GitHub 仓库（Kami-pic/Napics，私有）

### 待完成（发布前）
- [ ] Docker 部署支持（Dockerfile + docker-compose）
- [ ] Web 文件夹选择器（替代 Windows PowerShell 弹窗）
- [ ] 补充产品截图（搜索页、详情页、插件中心）
- [ ] 注册 LemonSqueezy + 创建产品
- [ ] 第一个付费插件开发（napics-pro-ai 或 napics-pro-automation）

### 待完成（发布后）
- [ ] 国际化（中英双语 UI）
- [ ] 响应式适配
- [ ] 插件版本管理（检测更新 + 一键升级）
- [ ] 官方文档站

---

## 八、风险与应对

| 风险 | 应对 |
|------|------|
| BT/网盘搜索源法律风险 | 灰色插件隔离到小号仓库，主仓库零风险 |
| 搜索源频繁失效 | 按风险特征分组，一个挂了不影响其他 |
| 用户量不足以支撑付费 | 先做免费版积累用户，付费是锦上添花 |
| Plex/MoviePilot 竞争 | 差异化定位：一站式管理 vs 纯播放/纯自动化 |
| LemonSqueezy 平台风险 | License Key 验证仅下载时触发，已下载的插件永久可用 |
