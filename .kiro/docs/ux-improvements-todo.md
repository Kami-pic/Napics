# [TODO] 用户体验改进

> 来源：用户反馈 2026-05-25
> 优先级：高（影响新用户首次体验和产品定位）

---

## 1. 清空媒体库时残留测试数据

**现象**：清空媒体库后仍显示 3 个文件：
- `Movie.2024.1080p.WEB-DL.x265.DDP5.1-GROUP.mkv · 5.0G`
- `Movie.2024.2160p.Remux.DTS-HD.x265-GROUP.mkv · 50.0G`
- `unknown.mkv · 1.0G`

**原因**：`media_library.json` 中的残留数据（之前测试写入后未清理）

**修复方案**：
- [ ] 检查 `media_library.json` 中是否有不存在于磁盘的文件条目
- [ ] 快速同步（`/sync`）时应自动清理磁盘上不存在的条目（现有逻辑已有 `removed = lib_paths - fs_files`，但可能没覆盖到"无 scan_paths 时"的场景）
- [ ] 或者：添加"清空媒体库"按钮，直接清空 `media_library.json`

---

## 2. 插件分层：内置 vs 第三方

**目标**：将有法律风险的直搜源插件移到第三方，产品只预装安全的内置插件。

### 分层定义

| 层级 | 说明 | 安装方式 | 示例 |
|------|------|----------|------|
| **内置（预装）** | 产品核心功能，可卸载但默认安装 | 开箱即用 | metadata-tmdb, metadata-douban, metadata-bangumi, download-qbittorrent, download-openlist, feature-completeness, feature-discover, feature-local-match, feature-subscribe, storage-openlist, search-prowlarr |
| **第三方** | 有法律风险或非核心的插件，需用户主动安装 | 从第三方源安装 | search-bt-direct（12 个直搜源）, search-pan（9 个网盘源）, rss-anime, rss-tv-movie, 所有独立搜索源插件 |

### 第三方插件安装机制（参考 Stable Diffusion WebUI Extensions）

- [ ] **插件源列表**：支持添加多个第三方 `index.json` URL（类似 SD WebUI 的 Extensions → Available → 自定义 URL）
- [ ] **默认第三方源**：预置一个官方维护的第三方源 URL（GitHub 仓库的 `index.json`）
- [ ] **GitHub URL 直装**：支持直接输入 GitHub 仓库 URL 安装插件（解析 `manifest.json` + 下载 zip）
- [ ] **插件中心 UI 改造**：
  - Tab 1：已安装（含内置 + 第三方）
  - Tab 2：可用插件（从已添加的第三方源拉取列表）
  - Tab 3：从 URL 安装（输入 GitHub 仓库地址）
  - Tab 4：插件源管理（添加/删除第三方 index.json URL）
- [ ] **后端已有基础**：`plugin_manager.py` 已实现 `fetch_remote_index` / `install_remote_plugin` / 插件源管理 API

### 需要做的改动

- [x] 从 `config.json` 的 `installed_plugins` 默认列表中移除所有搜索源插件
- [x] 新用户首次启动时只预装内置插件
- [x] 插件中心 UI 内置 Tab 隐藏已迁出插件（仅第三方 Tab 可见）
- [x] 预置官方社区源 URL（新用户开箱即有第三方源）
- [ ] 插件中心 UI 增加"从 URL 安装"入口
- [ ] 插件中心 UI 增加"插件源管理"入口
- [ ] 前端引导：搜索功能首次使用时提示"需要安装搜索源插件"（现有 `noSearchPlugin` 引导已实现）

---

## 3. 设置入口位置调整

**现状**：设置按钮在右上角 Header 中

**目标**：设置入口移到侧边栏底部，和插件按钮放在一起

**改动**：
- [ ] 从 `Header` 组件中移除设置按钮
- [ ] 在 `Sidebar` 底部添加设置按钮（在插件 🧩 按钮下方或旁边）
- [ ] 保持 `SettingsModal` 的打开逻辑不变，只是触发入口换位置
- [ ] 侧边栏底部布局：`🧩 插件` + `⚙️ 设置`（水平排列或垂直堆叠）

---

## 4. 扫描进度组件位置调整

**现状**：扫描进度浮窗在屏幕左下角（`fixed bottom-6 left-6`）

**目标**：移到屏幕底部居中，避免遮挡侧边栏底部的插件和设置按钮

**改动**：
- [ ] 将 `page.tsx` 中扫描进度组件的定位从 `fixed bottom-6 left-6` 改为 `fixed bottom-6 left-1/2 -translate-x-1/2`
- [ ] 或者用 `inset-x-0 flex justify-center` 实现居中
- [ ] 确认不会和批量搜索升级按钮（`fixed bottom-6 right-6`）重叠

---

## 5. 首页展开面板不应被页面高度限制

**现象**：首页现在会出现散装电影、tv、合集、系列卡片，点击展开后展开面板被页面容器高度限制住，内容被截断。

**原因**：之前首页只有文件夹卡片（进入后才看到内容），现在 `CardGrid` 直接渲染 `tv`/`collection`/`series`/`movie` 类型的卡片，展开面板（ExpandPanel）插入到网格中时，如果内容很多（如 8 季 × 10 集），面板高度超出可视区域。

**目标**：展开面板不限高，推荐区域（发现页）无限往下推。

**改动**：
- [ ] `ExpandPanel` 中的 `max-h-[400px]` 限制去掉或改为自适应（series/collection 的列表和网格不限高）
- [ ] 确认 `CardGrid` 的父容器没有 `overflow: hidden` 截断展开面板
- [ ] 展开面板展开时，发现页区域自然被推下去（当前已是 DOM 流式布局，应该自动生效）
- [ ] 如果展开内容过长，考虑加 "收起" 按钮而不是限高截断

---

## 6. 侧边栏导航：发现 / 媒体库快速切换

**目标**：安装发现推荐插件后，侧边栏底部（插件和设置上方）出现两个导航入口：
- **媒体库**：点击滚动到页面顶部（媒体库区域）
- **发现**：点击滚动到发现页顶部

**交互**：
- 点击后快速滚动动画（smooth scroll）到对应区域
- 当前所在区域高亮显示（类似锚点导航）
- 位置在侧边栏底部，插件/设置按钮的上方

**改动**：
- [ ] `Sidebar` 底部添加"媒体库"和"发现"两个导航按钮（仅在 `feature-discover` 插件安装时显示"发现"）
- [ ] 点击"发现"时调用 `scrollContainerRef.current.scrollTo({ top: discoverRef.offsetTop, behavior: 'smooth' })`
- [ ] 点击"媒体库"时调用 `scrollContainerRef.current.scrollTo({ top: 0, behavior: 'smooth' })`
- [ ] 根据当前滚动位置高亮对应按钮（用 IntersectionObserver 或 scroll 事件判断）
- [ ] 需要把 `scrollContainerRef` 和 `discoverRef` 的引用传给 `Sidebar`（或通过 context/事件通信）

---

## 7. 功能发现提示（扩展）

> 来源：new-user-experience-todo P2 遗留

- [ ] 首次看到质量评分时，轻提示"红色表示低质量，可以搜索更好的版本"
- [ ] 首次看到完整性条时，轻提示"灰色表示缺失的集数"

---

## 8. 错误恢复引导

> 来源：new-user-experience-todo P2 遗留

- [ ] 网络错误时提示"检查代理配置"而非只显示错误码
- [ ] TMDB 限频时提示"请稍后重试"而非静默失败

---

## 9. 国际化（中英双语）

> 来源：new-user-experience-todo P2 遗留。需求升级：不只是预留结构，需要实际支持英文切换。

- [ ] **UI 文案集中管理**：所有用户可见文案提取到 `i18n/zh-CN.json` + `i18n/en.json`
- [ ] **语言切换入口**：设置页或侧边栏底部添加语言切换（中文/English）
- [ ] **前端 i18n 方案**：用 `next-intl` 或轻量自研（context + JSON 文件）
- [ ] **后端响应国际化**：错误消息、状态描述支持 `Accept-Language` 或配置项
- [ ] **日期/数字格式**：文件大小、日期显示跟随语言设置

---

## 10. 响应式与移动端适配

> 来源：new-user-experience-todo P3 遗留
> ⚠️ 执行前必须先 git commit 当前状态作为备份，防止布局/UI 被改坏。

- [ ] **侧边栏折叠**：小屏幕自动折叠，汉堡菜单展开
- [ ] **卡片网格自适应**：根据屏幕宽度调整列数（当前已有 grid-cols-2 ~ 2xl:grid-cols-6）
- [ ] **触摸友好**：按钮最小 44px 触摸区域
- [ ] **PWA 基础**：manifest.json + service worker（离线缓存静态资源）

---

## 11. NAS 部署支持（Docker + Web 目录浏览器）

> 产品定位：NAS 上运行，浏览器远程访问（类似 Emby/Jellyfin/MediaPilot）

### 文件夹选择器改造

**现状**：`/config/browse-folder` 用 Windows PowerShell GUI 弹窗，NAS 上完全不能用。

**目标**：改为后端目录浏览 API + 前端目录树选择器（Web 版文件夹选择器）。

- [ ] 后端新增 `GET /config/browse-dir?path=/` — 返回指定路径下的子目录列表
- [ ] 前端 `PathInput` 组件改为弹出目录树浏览器（点击展开子目录，选中确认）
- [ ] 保留 PC 模式兼容：检测到 Windows 桌面环境时仍可用原生弹窗（可选）

### Docker 部署

- [ ] 编写 `Dockerfile`（Python 后端 + Node.js 前端构建）
- [ ] 编写 `docker-compose.yml`（后端 + 前端 + 数据卷映射）
- [ ] 环境变量配置：`MEDIA_PATH`、`CONFIG_PATH`、`PUID/PGID`
- [ ] 文档：群晖/威联通/Unraid 部署指南

### 性能优化（NAS 场景）

- [ ] 大媒体库（>5000 文件）扫描性能：批量 ffprobe → 并发池 + 进度回调
- [ ] `media_library.json` 读写优化：大文件（>10MB）时考虑分片或 SQLite
- [ ] 目录树构建缓存：避免每次请求都全量遍历文件系统
- [ ] 海报缓存：本地缓存 + CDN 代理，减少重复下载

---

## 执行优先级

1. **Bug 修复**：清空媒体库残留数据（立即）
2. **设置入口移位**（小改动，立即可做）
3. **扫描进度居中**（小改动，立即可做）
4. **展开面板不限高**（小改动）
5. **侧边栏导航：发现/媒体库切换**（中等改动）
6. **文件夹选择器改为 Web 目录浏览器**（中等改动，NAS 部署前置）
7. **插件分层改造**（工程量中等，分步推进）
8. **功能发现提示扩展**（小改动）
9. **错误恢复引导**（中等改动）
10. **NAS Docker 部署**（工程量中等）
11. **国际化中英双语**（工程量大，需系统性推进）
12. **响应式与移动端适配**（工程量大，需先备份）
