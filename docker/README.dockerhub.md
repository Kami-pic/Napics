# Napics

智能媒体资产管理系统 —— 扫描、识别、整理、刮削、质量分析与升级维护。

前后端打包在同一个镜像里，**一个容器、一个端口**就能跑。

- 源码与完整文档：https://github.com/Kami-pic/Napics
- 问题反馈：https://github.com/Kami-pic/Napics/issues
- License：GPL-3.0

## 支持的架构

`linux/amd64`。飞牛 / 群晖 / 威联通等 x86 NAS 都适用，暂不支持 arm64。

## 标签

| 标签 | 说明 |
|---|---|
| `latest` | 稳定版，对应 release 分支 |
| `release` | 同 `latest` |
| `dev` | 开发版，功能较新但可能不稳定 |

## 快速开始

推荐 host 网络模式，理由见下方「为什么建议 host 网络」。

```bash
docker run -d \
  --name napics \
  --network host \
  -e PORT=3032 \
  -v /vol1/1000/视频:/vol1/1000/视频 \
  -v napics-data:/app/data \
  --restart unless-stopped \
  napics/napics:latest
```

访问 `http://<NAS-IP>:3032`。

只能用桥接网络时，必须显式指定 DNS：

```bash
docker run -d \
  --name napics \
  -p 3032:3032 \
  -v /vol1/1000/视频:/vol1/1000/视频 \
  -v napics-data:/app/data \
  --dns 223.5.5.5 \
  --add-host host.docker.internal:host-gateway \
  --restart unless-stopped \
  napics/napics:latest
```

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `PORT` | `3032` | 唯一对外端口，冲突时改这个 |
| `TZ` | `Asia/Shanghai` | 时区 |

## 挂载

| 容器内路径 | 说明 |
|---|---|
| `/app/data` | 配置与媒体库索引。**必须挂出来**，否则更新镜像会丢数据 |
| 你的媒体目录 | 建议容器内外用同一个路径，见下方说明 |

## 部署要点

**媒体目录建议容器内外同路径。** 设置页里填的扫描路径是给容器看的。挂载成
`-v /vol1/1000/视频:/vol1/1000/视频` 后，设置页直接填 `/vol1/1000/视频/电影`
就行，不用在两套路径之间做心算转换，下载器返回的路径也能直接对上。如果你映射成了
别的路径（如 `:/media`），那设置页必须填 `/media/电影`。

**必须先配好扫描路径。** 出于安全考虑，文件操作被限制在已配置的媒体库范围内。
没配路径时，封面、重命名、删除等操作会提示「路径不在媒体库范围内」。

**为什么建议 host 网络。** NAS 的 Docker 默认桥接网络经常拿不到可用 DNS，
会导致容器内域名全部解析失败，刮削、搜索、发现页、插件源统统不可用。host 模式下
容器共用宿主机网络栈，DNS 直接可用；装在 NAS 上的 qBittorrent / Prowlarr /
OpenList 也能直接用 `http://127.0.0.1:端口` 访问。容器内后端只监听
`127.0.0.1:8001`，不对外暴露，所以用 host 模式不会降低安全性。

**桥接网络下访问 NAS 上的其他服务**要填 `http://host.docker.internal:端口`,
容器内的 `127.0.0.1` 指向容器自己。端口填它**映射到宿主机**的那个,不是容器内端口 ——
这两个经常不一样(比如 qBittorrent 容器内是 8080,宿主机上可能被映射成 8085)。
用 `docker ps` 看 PORTS 列箭头左边的数字。

## 首次配置

在设置页填：TMDB API Key（建议）、扫描路径（必填）、按需启用插件
（Web 播放器 / 字幕搜索 / qBittorrent / OpenList / 订阅追更等）、HTTP 代理（可选）。

搜索源和 RSS 源这类涉及具体站点的实现不随镜像分发，需要在插件中心自行安装。

## 注意

单机单用户设计，没有账号体系，**请勿直接暴露到公网**。
