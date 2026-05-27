<div align="center">

# Napics

**智能媒体资产管理系统**

扫描、识别、整理、元数据管理（刮削）、质量分析与升级维护 ——
面向 PC / NAS 用户的智能媒体资产管理系统。

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://python.org)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)

![Napics](screenshots/main-ui.png)

</div>

---

## 为什么是 Napics


Napics 不负责播放，也不试图替代 Plex/Jellyfin。
它解决的是：

> 为什么你的媒体库总是越来越乱。

你可能已经有 Plex/Jellyfin 来播放，
有 MoviePilot/NasTools 来自动获取资源。

但：

- 文件名混乱
- 季集缺失
- 海报与 NFO 不完整
- 画质参差不齐
- 重复资源难以整理
- 老资源无法持续升级

Napics 关注的是：

> 管理、质量与长期维护。

核心聚焦于：
- 组织架构
- 元数据质量（刮了个削）
- 媒体内容一致性
- 长期可维护性
- 扩展功能可通过插件实现。

---


## 核心能力


### 媒体库管理与质量分析

- 自动扫描目录，识别视频元信息（分辨率、编码、HDR、字幕轨）
- 智能识别文件夹类型（电影 / 剧集 / 系列电影 / 分类聚合）
- 舒适交互，不同类型不同UI/UX方式，一目了然
- 100 分制质量评分，低画质一目了然
- 多视图浏览：目录树、详情卡片、表单管理

### 智能整理与刮削

- 多源刮削（TMDB + 可扩展元数据源），自动匹配海报和 NFO
- AI 辅助分类判定 + 季目录归位 + 智能重命名
- 平级展开，不同类型不同 UI 交互方式



### 媒体升级与维护

- 下载完成自动归位，整体替换
- 批量升级：检测低画质 → 搜索更高质量版本 → 替换
- 基于媒体库偏好的个性化推荐
- 季集完整性检测，缺什么搜什么

### 插件拓展

- 插件拓展能力。搜索/下载/订阅
- 聚合 BT / 网盘多源搜索，智能关键词回退
- 期待更多的模块化的功能


---

## 截图

<details>
<summary>展开查看更多截图</summary>

| 功能 | 截图 |
|------|------|
| 剧集管理 | ![tv](screenshots/tv.png) |
| 智能重命名 | ![rename](screenshots/smart-rename.png) |
| 发现推荐 | ![discover](screenshots/discover.png) |
| 下载管理 | ![download](screenshots/download.png) |
| 网盘浏览 | ![cloud](screenshots/cloud-drive.png) |
| 智能搜索 | ![search](screenshots/smart-search.png) |
| RSS 订阅 | ![rss](screenshots/RSS.png) |

</details>

---

## 插件系统

- 内置插件中心，支持一键安装/卸载
- 支持添加第三方插件源 URL
- 提供 SDK 和模板仓库，可开发自定义插件

详见 [插件开发指南](backend/plugins/PLUGIN_DEV_GUIDE.md)

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+

### 安装运行

```bash
git clone https://github.com/Kami-pic/napics.git
cd napics

# 后端
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 前端（新终端）
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3031`

### Windows 一键启动

```bash
start_all.bat
```

### Docker

Docker support is under active development.
预计近期提供 beta compose。

Current recommendation:
- Windows: `start_all.bat`
- Developers: manual setup
---

## 配置

首次启动后在设置页配置：

1. **TMDB API Key** — [申请地址](https://www.themoviedb.org/settings/api) （建议使用）
2. **扫描路径** — 媒体库目录（支持网络路径）
3. **可选插件** — （BT 下载 / OpenList）（可选）
4. **HTTP 代理** — 海外服务访问（可选）

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python · FastAPI · Uvicorn |
| 前端 | Next.js 16 · React 19 · Tailwind CSS 4 |
| 数据 | JSON 文件持久化（无数据库依赖） |

---

## 贡献

欢迎提交 Issue 和 Pull Request！详见 [贡献指南](CONTRIBUTING.md)。

---

## 法律声明

Napics 是一个媒体资产管理工具，提供插件扩展机制。

- Napics 不提供资源发现服务，也不提供任何默认资源站配置。
- 搜索、下载、订阅能力取决于用户安装的第三方插件。
- 第三方插件由其各自维护者负责，与本项目无关
- 用户应确保其使用方式符合当地法律法规


---

## License

[GPL-3.0](LICENSE)

---
