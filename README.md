<div align="center">

# Napics

**智能媒体资产管理系统**

面向 PC/NAS 用户的一站式影视管理工具——从发现到入库到整理，全链路闭环。补齐链路上的“最后一万公里，冲刺交给你”。

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://python.org)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)

![Napics](screenshots/tv.png)

</div>

---

## 特色功能


**特色交互**
- 服务整理癖（媒体库扫描）和随意党（自行添加媒体，整不整理无所谓）
- 自动识别文件夹类型（电影，剧集，系列电影，分类聚合，管你啥大杂烩）
- 平级展开，不同类型不同UI/UX方式，一目了然，舒服使用/管理
- 多视图，传统目录，丰富详情，表单管理 一应俱全


**媒体库管理**
- 自动扫描 NAS 目录，识别视频元信息（分辨率、编码、HDR、字幕轨）
- 多源刮削（TMDB / 豆瓣 / Bangumi），自动匹配海报和 NFO
- 100 分制质量评分，低画质一目了然
- AI 辅助分类判定 + 季目录归位 + 智能重命名


**下载与归位**
- 对接 qBittorrent / OpenList(Alist)，一键下载
- 下载完成自动归位到媒体库对应目录
- 批量升级：检测低画质 → 搜索更高质量版本 → 替换

**发现与订阅**
- 基于媒体库偏好的个性化推荐
- RSS 订阅自动追更，支持洗版升级
- 季集完整性检测，缺什么搜什么

**插件架构**
- 搜索源、元数据源、下载器均可插件化扩展
- 内置插件中心 + 第三方插件源支持
- 提供 SDK 和模板仓库，开发自定义插件

**全网搜索（需配合插件)**
- 具有相关能力聚合 BT / 网盘多源搜索，智能关键词回退
- SSE 流式推送，边搜边看
- 搜索结果综合评分排序，自动过滤垃圾资源



> *以上都是AI帮我写的* 

> *可能有吹嘘成分;* 
> *但也可能还没表达清楚更多厉害的功能等你发掘。*


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

---

## 配置

首次启动后在设置页配置：

1. **TMDB API Key** — [申请地址](https://www.themoviedb.org/settings/api)
2. **扫描路径** — 媒体库目录（支持 NAS SMB 路径）
3. **qBittorrent** — BT 下载（可选）
4. **HTTP 代理** — 海外服务访问（可选）
5. **端口配置**  — package.json里改，如果不方便后续再迭代进设置里吧

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python · FastAPI · Uvicorn |
| 前端 | Next.js 16 · React 19 · Tailwind CSS 4 |
| 数据 | JSON 文件持久化（无数据库依赖） |

---

## 插件开发

```bash
pip install napics-plugin-sdk
```

详见 [插件开发指南](backend/plugins/PLUGIN_DEV_GUIDE.md)

---

## 贡献

欢迎提交 Issue 和 Pull Request。肯定有很多bug...一个人测不过来...
独自出工，我的agent 牛马出的力。 特别想赚钱给他把饲料升级成咖啡 :p
---

## License

[GPL-3.0](LICENSE)

---

## 致谢

[TMDB](https://www.themoviedb.org/) · [Prowlarr](https://prowlarr.com/) · [qBittorrent](https://www.qbittorrent.org/) · [OpenList](https://github.com/AlistGo/alist)
