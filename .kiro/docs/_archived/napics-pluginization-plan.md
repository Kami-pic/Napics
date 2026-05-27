# NAS Video Upgrader 插件化与部署形态改造计划 v2

> 面向 Codex / Agent 的工程任务书。  
> 目标：将当前项目从“个人全链路工具”改造成“核心能力可公开 + 外部能力插件化 + 私有增强层可保留 + 多部署形态可演进”的结构。

---

## 0. 当前结论

本项目不应继续向“播放端”扩张。播放端由 Plex / Jellyfin / Emby / Infuse 等成熟产品承担。  
本项目的长期定位应是：

> 面向 NAS 高阶用户的 AI 媒体资产管理与整理系统。

核心价值不在资源站数量，而在：

- 媒体库整理
- 低质量资源识别
- 质量评分与升级判断
- 中文媒体生态理解
- AI 文件名解析 / 匹配 / 诊断
- 可插拔外部服务接入

本轮改造不是重写项目，也不是目录美化。  
本轮第一目标是：

> 完成依赖方向反转：核心业务依赖 Provider 契约，不直接依赖具体爬虫、下载器、RSS 源、元数据源、云盘源。

---

## 1. 改造总原则

1. 先契约化，不搬目录。
2. 先迁移已有基类、低状态、低耦合模块。
3. 不在同一轮同时做目录重组和逻辑修改。
4. 不改变现有用户可见行为。
5. 不新增 `shared.py` 全局依赖。
6. 插件初始化必须通过 `ProviderRegistry` / `ProviderContext` 获取依赖。
7. 前端不得继续硬编码 provider 列表，应逐步从后端读取。
8. 网盘源、直搜源、自动转存等敏感能力必须插件化，不进入公开 Core。
9. 当前 PC 自用环境必须保持可用。
10. NAS / Docker / 多 CPU 架构是部署层演进，不应和业务插件化混在同一轮完成。

---

## 2. 产品边界定义

### 2.1 Core：建议公开保留

Core 是低法律风险、长期有价值、可形成品牌的部分。

应保留：

- 媒体库扫描
- 文件树浏览
- 视频基础信息提取
- 媒体类型识别
- 质量评分
- 低质量资源识别
- 季集完整性检测
- 刮削框架
- TMDB / Bangumi 等正规元数据源适配
- NFO 生成
- 海报下载
- 文件整理流水线
- Action Plan
- 快照与回滚
- 重命名规则
- 影子名 / 英文别名
- AI 文件名解析
- AI 候选匹配
- AI 媒体库诊断
- L1-L4 搜索匹配通用能力层

Core 的定位是：

> AI 驱动的媒体资产管理与整理系统。

不是：

> 自动看片工具 / 资源站壳子 / 网盘聚合工具。

---

### 2.2 Plugin：必须抽离

以下能力必须从核心业务逻辑中解耦：

- BT 直搜源
- 网盘搜索源
- RSS 源
- Prowlarr 接口
- qBittorrent 接口
- Alist / OpenList 接口
- 下载器适配器
- 云盘链接解析器
- Provider 级别过滤规则
- Provider 级别搜索词构造策略
- Provider 级别反爬 / header / proxy / parser 逻辑
- 元数据源适配器：TMDB / 豆瓣 / Bangumi / 未来 AniDB / AniList / Trakt

插件化后，核心只知道：

```text
SearchProvider
MetadataProvider
RSSProvider
DownloadProvider
StorageProvider
NotificationProvider
```

核心不应该直接知道：

```text
Bitsearch / Nyaa / 蜜柑 / 1337x / 阿里云盘 / 夸克 / PikPak / 某个具体站点
```

---

### 2.3 Private：长期私有

以下能力可以继续存在，但不建议进入公开核心仓库：

- 内置 BT 资源站实现
- 内置网盘搜索实现
- 自动转存链路
- 高级洗版策略
- 私有搜索规则库
- 字幕组 / 压制组信誉库
- 资源站质量画像
- AI ranking 私有策略
- 针对特定资源站的 fallback 规则
- 针对中文资源生态的高维护爬虫

原则：

> Core 开放能力框架，Private 保留具体资源获取能力。

---

## 3. 暂不做目录大重组

现阶段不要追求类似下面的“漂亮目录”：

```text
backend/core/media_library/
backend/core/organizer/
backend/core/scraper/
```

原因：

- import 变更多
- git diff 噪声大
- git blame 被污染
- 测试失败时不好定位
- Agent 容易顺手改逻辑

当前阶段只允许新增少量基础文件，例如：

```text
backend/provider_contracts.py
backend/provider_registry.py
backend/provider_context.py
backend/provider_models.py
```

或者等价命名。

等 Provider 契约稳定后，再单独规划目录重组。目录重组必须作为独立阶段，不能和业务逻辑修改混合。

---

## 4. Provider 契约优先级

第一优先级：

- `SearchProvider`
- `MetadataProvider`
- `RSSProvider`

第二优先级：

- `DownloadProvider`
- `StorageProvider`
- `NotificationProvider`

特别说明：

`MetadataProvider` 必须与 `SearchProvider` 同等重要，不能作为附属接口处理。

原因：

- 豆瓣可能限频或不可用
- Bangumi 数据质量不稳定
- TMDB 依赖 API Key 和网络环境
- 未来可能接入 Trakt / AniDB / AniList
- 刮削系统是核心能力，不是边缘能力

---

## 5. ProviderContext 与 shared.py 收口

插件系统不能继续扩大 `shared.py` 单例污染。

新插件代码禁止新增：

```python
from shared import xxx
```

插件初始化必须通过 `ProviderContext` 注入依赖。

建议 `ProviderContext` 至少包含：

```text
config
logger
cache
http_client
event_bus，可选
feature_flags，可选
runtime_info，可选
```

推荐调用方式：

```python
provider.initialize(context)
```

不允许 Provider 自己从全局 shared 中拿配置、logger、downloader、search_service。

---

## 6. Provider API 与前端动态感知

前端必须逐步停止硬编码 provider 列表。

当前前端中类似以下内容应被审计并逐步迁移：

- `DIRECT_SOURCES`
- `NO_SEEDER_INFO`
- 源名称硬编码
- 源品牌色硬编码
- 搜索 Tab 写死
- 设置页写死 provider 类型

需要新增后端 API：

```http
GET /api/providers
```

建议返回结构：

```json
{
  "search": [
    {
      "id": "prowlarr",
      "name": "Prowlarr",
      "type": "bt",
      "enabled": true,
      "capabilities": ["search", "seeders", "size", "magnet"],
      "riskLevel": "user_configured"
    }
  ],
  "metadata": [],
  "rss": [],
  "download": [],
  "storage": []
}
```

前端只负责根据后端返回的 provider metadata 渲染 UI。  
源能力由 `capabilities` 决定，不再由前端手写判断。

---

## 7. 私有插件组织方式

不建议公开仓库出现完整私有插件目录。

建议结构：

```text
backend/plugins/
  search/
    README.md
    __init__.py
    example_provider.py
    private_bt/
    private_pan/
  metadata/
    README.md
    __init__.py
    tmdb_provider.py
  rss/
    README.md
    __init__.py
    example_provider.py
  download/
    README.md
    __init__.py
  storage/
    README.md
    __init__.py
```

`.gitignore` 建议：

```gitignore
backend/plugins/**/private_*/
```

公开版保留：

- Provider SDK
- example provider
- 低风险 provider
- Provider 开发文档

私有版保留：

- private_bt
- private_pan
- private_storage
- private_ranking

不要直接忽略整个 `bt_sources/` 或 `pan_sources/`，否则公开版会变成“缺了一块”，不利于社区理解插件机制。

---

## 8. 分阶段执行计划

### Phase 1：边界审计与测试基线

只做文档和审计，不改业务逻辑。

输出：

- 当前搜索源清单
- 当前 RSS 源清单
- 当前元数据源清单
- 当前下载器清单
- 当前云盘 / 存储源清单
- 当前 `shared.py` 依赖清单
- 当前前端硬编码 provider 清单
- 当前可验证测试命令
- 当前 PC 自用环境启动方式

生成文档：

```text
docs/pluginization-audit.md
```

验收：

- 有完整模块清单
- 每个搜索源、网盘源、RSS 源、下载器、元数据源都有归类
- 没有修改现有运行逻辑

---

### Phase 2：建立 Provider 契约与 Registry

只新增接口和注册机制，不迁移具体实现。

新增：

- Provider 基础协议
- `SearchProvider`
- `MetadataProvider`
- `RSSProvider`
- `DownloadProvider`
- `StorageProvider`
- `ProviderRegistry`
- `ProviderContext`
- `GET /api/providers` API 初版

禁止：

- 移动现有目录
- 修改现有搜索逻辑
- 修改下载状态机
- 修改整理逻辑
- 修改刮削决策逻辑

验收：

- 所有 DTO 使用 Pydantic 或明确类型定义
- 禁止裸 dict 作为跨层接口
- API 可返回静态或半静态 provider 列表
- 单元测试能通过

---

### Phase 3：迁移 BT 直搜源为 SearchProvider

优先迁移已有 `ScraperBase` 的 BT 直搜源。

原因：

- 数量多，收益明显
- 已经是独立文件
- 已有基类，离 Provider 接口最近
- 状态少，迁移风险低

目标：

- 每个 BT 直搜源实现 `SearchProvider`
- 原有 parser 可保留在 provider 内部
- 原有搜索结果结构保持兼容
- 原有过滤、排序、L1-L4 能力层不改变
- 可以通过 registry 获取启用源列表

验收：

- route 不直接调用具体 BT 源
- Core 不直接 import 具体 BT 源
- 搜索结果排序逻辑仍集中在 L1-L4 能力层
- 每个 provider 可单独启用 / 禁用

---

### Phase 4：迁移 RSS 源为 RSSProvider

优先迁移已有 `RSSSourceBase` 的 RSS 源。

目标：

- RSS 源实现 `RSSProvider`
- 保持订阅系统行为不变
- 不改轮询策略
- 不改自动下载逻辑
- 不改订阅匹配逻辑

验收：

- 订阅系统不直接 import 具体 RSS 源
- 添加新 RSS provider 不需要改订阅核心逻辑
- RSS provider 只提供候选，不做最终下载决策

---

### Phase 5：迁移 MetadataProvider

将 TMDB / 豆瓣 / Bangumi 抽象为 `MetadataProvider`。

目标：

- 统一 search / detail / episode / artwork / alias 能力边界
- 保持现有刮削行为不变
- 不在本阶段新增新元数据源
- 允许未来接入 AniDB / AniList / Trakt

验收：

- 刮削核心不直接绑定某个元数据源实现
- 原有 TMDB / 豆瓣 / Bangumi 行为保持兼容
- 多源候选匹配逻辑仍属于 Core

---

### Phase 6：迁移 Prowlarr

将 Prowlarr 作为特殊 `SearchProvider`。

要求：

- 保持用户显式配置
- 不内置 indexer
- 不改变原搜索结果字段
- 不改变 Prowlarr 配置方式

验收：

- Prowlarr 搜索结果进入统一 `SearchResult`
- Core 不直接 import Prowlarr client
- Prowlarr 可单独启用 / 禁用

---

### Phase 7：迁移 qB / OpenList

将 qB / OpenList 抽象为 `DownloadProvider` / `StorageProvider`。

注意：

- 此阶段涉及状态机，必须单独执行
- 不与搜索源迁移混合
- 必须先补充回归测试
- 不改变现有下载任务结构和归位逻辑

验收：

- qB 下载任务进入统一 `DownloadTask`
- OpenList / Alist 进入统一 Storage 或 Download 接口
- 下载完成后的归位逻辑仍属于 Core
- qB 同步行为没有新增副作用

---

### Phase 8：迁移网盘源与私有插件

网盘源不得进入公开核心。

目标：

- 公开仓库只保留 provider sdk 和 example provider
- 私有实现使用 `private_*` 目录
- `.gitignore` 排除 `private_*` 实现

示例：

```text
backend/plugins/search/example_provider.py
backend/plugins/search/private_pan/
backend/plugins/search/private_bt/
```

验收：

- Core 仓库可以在没有网盘 provider 的情况下运行
- 网盘搜索不是默认能力
- 网盘 provider 可在私有环境单独加载

---

### Phase 9：前端 Provider 动态感知

目标：前端不再维护静态 provider 列表。

任务：

- 搜索源 Tab 从 `GET /api/providers` 获取
- 设置页从 `GET /api/providers` 获取
- 源能力展示由 provider capabilities 决定
- `NO_SEEDER_INFO` 等规则由后端 metadata 或 capabilities 决定
- 源名称、类型、状态、风险提示由后端返回

验收：

- 新增 provider 时，前端无需新增硬编码源表
- 禁用 provider 后，前端自动隐藏或标记不可用
- 前端只做展示，不承担 provider 业务判断

---

## 9. 客户端与部署形态计划

### 9.1 先区分“客户端”与“部署形态”

本产品短期不应拆成多个真正客户端。  
更合理的理解是：

```text
Backend Core + Web UI + 不同部署壳
```

也就是：

- PC 本地运行：当前自用形态
- NAS Docker 运行：第一公开目标
- NAS 套件形态：后续增强
- 桌面客户端：可选，不优先
- 移动端：不做完整客户端，只做远程管理 Web / PWA

不要现在就做：

- Windows 客户端
- macOS 客户端
- iOS / Android App
- NAS 原生套件

这些都会过早分散精力。

---

### 9.2 推荐部署优先级

推荐顺序：

```text
1. PC 本地开发 / 自用
2. Docker Compose 单机部署
3. NAS Docker 部署
4. 多架构 Docker 镜像
5. Synology / QNAP 文档化安装
6. 可选桌面壳 / PWA
7. 可选 NAS 原生套件
```

原因：

- Docker 是 NAS 用户最通用的交付方式
- Synology / QNAP 原生套件维护成本高
- 多 CPU 架构可以通过 Docker buildx 解决
- Web UI 已经足够作为主客户端

---

### 9.3 Runtime Profile 设计

需要新增运行形态概念：

```text
RuntimeProfile
```

建议至少支持：

```text
pc-dev
pc-local
nas-docker
nas-package
open-core
private-full
```

不同 profile 控制：

- 默认数据目录
- 默认日志目录
- 是否允许本地路径浏览
- 是否启用私有插件
- 是否启用高风险 provider
- 是否开启代理配置
- 是否展示调试功能
- 是否允许自动更新

示例：

```text
PC 环境：允许直接访问本机路径，适合开发和自用。
NAS Docker：所有路径必须通过 volume mount 显式提供。
Open Core：默认不加载 private_* provider。
Private Full：允许加载私有 provider。
```

---

### 9.4 配置与数据目录规范

为 NAS 化做准备，必须减少硬编码路径。

建议统一：

```text
/app/config
/app/data
/app/cache
/app/logs
/app/plugins
/media
/downloads
```

Docker Compose 中通过 volume 映射：

```yaml
volumes:
  - ./config:/app/config
  - ./data:/app/data
  - ./cache:/app/cache
  - ./logs:/app/logs
  - ./plugins:/app/plugins
  - /volume1/video:/media
  - /volume1/downloads:/downloads
```

Core 不应该假设：

- Windows 盘符
- SMB 挂载路径
- NAS 固定路径
- 当前工作目录

---

### 9.5 多 CPU 架构计划

NAS 用户常见架构：

```text
linux/amd64
linux/arm64
linux/arm/v7，可选
```

短期建议只承诺：

```text
linux/amd64
linux/arm64
```

`linux/arm/v7` 不建议第一阶段承诺。原因：

- 旧 NAS 性能弱
- Python / Node 依赖可能编译慢
- AI / 视频分析能力体验差
- 维护成本高

Docker 构建方向：

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t nas-video-upgrader:latest .
```

验收标准：

- amd64 可构建
- arm64 可构建
- 镜像启动后能访问 Web UI
- 可挂载媒体目录
- 可写 config / data / cache / logs

---

### 9.6 前后端部署方式

短期推荐：

```text
单容器优先
```

即：

- FastAPI 后端
- Next.js 前端构建产物
- 同一个容器启动
- 统一端口访问

原因：

- NAS 用户部署简单
- 少一个反代配置
- 少一个跨域问题
- 便于 open-core 传播

后续再考虑：

```text
backend container + frontend container
```

但不要第一阶段就增加复杂度。

---

### 9.7 Docker 化阶段计划

#### Deploy Phase 1：环境变量与路径收口

目标：让项目不依赖开发机路径。

任务：

- 增加 `.env.example`
- 统一 config/data/cache/logs 路径
- 检查 Windows 路径硬编码
- 检查 SMB 路径假设
- 检查临时文件写入位置

#### Deploy Phase 2：Dockerfile 草案

目标：能在本机通过 Docker 启动。

任务：

- 编写 Dockerfile
- 编写 docker-compose.yml
- 后端启动命令固定化
- 前端 build 产物服务方式确定

#### Deploy Phase 3：NAS Docker 文档

目标：让 Synology / QNAP 用户能照文档部署。

任务：

- 群晖 Container Manager 安装说明
- QNAP Container Station 安装说明
- volume 映射说明
- 权限说明
- 媒体目录挂载说明

#### Deploy Phase 4：多架构镜像

目标：支持 amd64 / arm64。

任务：

- buildx 构建
- 验证 arm64 依赖
- 标记不支持或弱支持的功能

---

## 10. 客户端策略结论

短期不要做“多客户端”。

推荐策略：

```text
Web UI 是唯一正式客户端。
PC / NAS / Docker 只是不同部署形态。
```

未来如需增强体验，优先顺序是：

1. PWA：成本最低，适合远程管理。
2. 桌面壳：只用于托盘、开机启动、本地路径权限，不承载核心逻辑。
3. NAS 原生套件：等 Docker 用户验证后再做。
4. 移动 App：不建议做，除非已有大量用户需要远程通知与轻管理。

---

## 11. 法律风险边界

对外强调：

- 媒体库整理
- 质量识别
- 低质量资源发现
- 中文媒体生态适配
- AI 辅助修复
- 插件化外部服务接入

对外弱化或不宣传：

- 内置资源站
- 网盘搜索
- 自动下载
- 自动转存
- 资源获取链路

公开版默认不应内置高风险 provider。  
商业化不应围绕“资源获取能力”收费，而应围绕：

- AI 质量分析
- AI 媒体库诊断
- 高级整理计划
- 高级质量引擎
- 配置同步
- 云端规则库
- 媒体知识库

---

## 12. 明确禁止事项

本轮插件化期间，禁止：

1. 边迁移边修改搜索评分逻辑。
2. 边迁移边新增 provider。
3. 边迁移边修复非阻塞 bug。
4. 将 provider 内部逻辑继续泄漏到 Core。
5. 用裸 dict 替代 DTO。
6. 在 route 中直接调用具体资源站。
7. 在 Core 中出现具体资源站名称。
8. 将网盘搜索源放进公开核心。
9. 将“自动下载侵权资源”作为产品卖点。
10. 为了兼容旧代码继续扩大 `shared.py` 单例污染。
11. 在插件化阶段同时做目录大重组。
12. 在插件化阶段同时做 Docker 化。
13. 在 Docker 化阶段同时改业务逻辑。

---

## 13. 每轮执行格式

每一轮只允许做一种改动。

每轮开始前必须写清：

```text
本轮目标：
本轮涉及文件：
本轮不碰范围：
预期行为是否等价：
验证命令：
```

每轮完成后必须输出：

```text
变更摘要：
行为是否变化：
新增/修改文件：
测试结果：
遗留问题：
下一步建议：
```

默认验证命令：

```bash
cd backend && python -X utf8 -m pytest test_*.py
cd frontend && npm run test
cd frontend && npm run build
```

如果某项测试无法运行，必须说明原因，不能静默跳过。

---

## 14. 最终验收标准

最终目标不是“文件移动完成”，而是满足以下边界：

```text
Core 负责理解媒体。
Plugin 负责连接外部世界。
Private 负责高风险资源能力。
Deploy 负责运行环境差异。
```

具体检查：

- Core 是否可以在没有 BT / 网盘 provider 的情况下运行？
- Core 是否仍能完成扫描、整理、刮削、质量识别？
- 搜索源是否都通过 `SearchProvider` 接入？
- 元数据源是否都通过 `MetadataProvider` 接入？
- RSS 源是否都通过 `RSSProvider` 接入？
- 下载器是否都通过 `DownloadProvider` 接入？
- 云盘能力是否都通过 `StorageProvider` 接入？
- 订阅系统是否不依赖具体 RSS 源？
- UI 是否能识别 provider 启用 / 禁用状态？
- 自用版本是否能继续加载私有 provider？
- Docker 部署是否不依赖 Windows 路径？
- NAS 部署是否只通过 volume 显式访问媒体目录？
- 多架构镜像是否至少支持 amd64 / arm64？

---

## 15. 一句话原则

> 把长期有价值的媒体理解能力留在 Core，把高波动高风险的资源连接能力移到 Plugin，把最敏感的资源站和网盘实现留在 Private，把 PC / NAS / Docker 差异放到 Deploy 层解决。


---

## 16. 双仓库策略与品牌重命名

### 16.1 两套代码并行维护

本项目将维护两套独立代码：

| | 私有自用版 | 公开版 |
|---|---|---|
| 目录 | `C:\Users\shenq\nas-video-upgrader` | `C:\Users\shenq\napics-media-manager` |
| 品牌名 | nas-video-upgrader（内部） | Napics Media Manager |
| Git 仓库 | 原仓库，继续维护 | 新仓库（从原仓库 clone） |
| 功能范围 | 全功能（含私有插件） | Core + Builtin Plugin + Example |
| 用途 | 作者日常使用 | 公开发布 / 社区 |

操作方式：

```bash
# 从原仓库 clone 到新位置
git clone C:\Users\shenq\nas-video-upgrader C:\Users\shenq\napics-media-manager

# 进入新目录
cd C:\Users\shenq\napics-media-manager

# 断开与原仓库的关联（独立发展）
git remote remove origin

# 设置新的远程仓库（GitHub 公开仓库）
git remote add origin https://github.com/xxx/napics-media-manager.git

# 不需要立即安装依赖（node_modules / venv 不会被 clone）
# 只有需要运行测试时才 npm install / pip install
```

### 16.2 品牌重命名清单

公开版需要将 "nas-video-upgrader" / "NAS Video Upgrader" 统一改为 "Napics Media Manager"。

涉及位置：

**前端**：
- `frontend/app/layout.tsx` — title / meta description
- `frontend/components/layout/Header.tsx` — 顶栏标题（已改为 Napics Media Manager）
- `frontend/package.json` — name 字段
- `frontend/public/` — favicon / manifest（如有）

**后端**：
- 无硬编码产品名（后端不展示品牌名）

**文档**：
- `README.md` — 项目名和描述
- `.kiro/docs/` — 文档标题中的旧名
- `AI_GUIDE.md` — 项目概述
- `AGENTS.md` — 如有提及

**Git**：
- 目录名：`napics-media-manager`
- GitHub 仓库名：`napics-media-manager`

**不改**：
- 内部变量名、函数名、文件名（不涉及品牌展示的技术命名不动）
- config.json 中的字段名
- API 路径

### 16.3 从私有版同步修复到公开版

当私有版修了一个公开版也需要的 bug 时：

```bash
# 在私有版生成 patch
cd C:\Users\shenq\nas-video-upgrader
git format-patch -1 HEAD    # 生成最近一次提交的 patch 文件

# 在公开版应用 patch
cd C:\Users\shenq\napics-media-manager
git am ../nas-video-upgrader/0001-xxx.patch
```

或者更简单的方式：手动 cherry-pick 关键改动。两个仓库独立发展后，差异会越来越大，同步频率会自然降低。

---

## 17. 硬件环境与部署策略补充

### 17.1 当前硬件现状

- **开发机**：Windows PC（性能充足）
- **NAS**：群晖 DS218play（RTD1296 ARM 1.4GHz / 1GB DDR4 / 不可扩展）

DS218play 的限制：
- 1GB 内存无法同时运行 Python 后端 + Node.js 前端
- ARM 弱核 CPU 无法承受并发爬虫 + ffprobe 分析
- Docker 本身在 1GB 设备上运行就很勉强

结论：**DS218play 不是本项目的目标部署硬件。**

### 17.2 推荐的开发与测试策略

```
日常开发：PC 直接跑 backend + frontend（当前方式，不变）
Docker 验证：PC 上用 Docker Desktop 构建并测试镜像
发布：推送镜像到 Docker Hub / GitHub Container Registry
部署：目标机器 docker pull + docker-compose up
```

不需要在 NAS 上开发或测试。Docker 的意义是"本地验证通过 → 任何地方都能跑"。

### 17.3 目标用户硬件画像

本项目的目标用户大概率使用：
- 群晖 DS220+ / DS720+ / DS920+（Intel J4125 / Celeron，4GB+ 内存）
- 威联通 TS-x64 系列（Intel / AMD，4GB+ 内存）
- Unraid / TrueNAS（x86 自组，8GB+ 内存）
- N100 小主机（8-16GB 内存，专门跑 Docker）

最低硬件要求建议：
- CPU：x86_64 或 ARM64（≥2GHz）
- 内存：≥2GB 可用（推荐 4GB）
- 存储：系统盘 1GB 空间（镜像 + 数据）

### 17.4 如果作者想 24/7 运行

推荐方案：加一台 N100 小主机（500-800 元）

```
N100 小主机              DS218play
├── Docker               ├── 视频文件
│   ├── Backend          └── 纯存储（NFS/SMB 共享）
│   └── Frontend
└── NFS 挂载 NAS 媒体目录
```

优点：比换 NAS 便宜，比 PC 常开省电，性能绰绰有余。

---

## 18. 补充建议（来自 Kiro 的审查意见）

### 18.1 Dockerfile 策略

建议多阶段构建（multi-stage build）：

```dockerfile
# Stage 1: 前端构建
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: 运行时
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/.next ./frontend/.next
COPY --from=frontend-build /app/frontend/node_modules ./frontend/node_modules
COPY --from=frontend-build /app/frontend/package.json ./frontend/
# 启动脚本同时启动后端和前端
```

### 18.2 RuntimeProfile 实现建议

不要在早期做完整 Profile 系统。先用环境变量做最简路径抽象：

```bash
DATA_DIR=/app/data          # 默认值，Docker 中使用
CONFIG_DIR=/app/config
CACHE_DIR=/app/cache
MEDIA_DIR=/media
DOWNLOADS_DIR=/downloads
```

后端 `config_manager.py` 读取环境变量，有则用环境变量，无则用当前目录（兼容 PC 开发）。

### 18.3 首次启动向导（Setup Wizard）

建议在 Deploy Phase 3 之后增加独立阶段：

- 检测是否首次启动（config.json 不存在或为空）
- Web UI 引导：配置媒体目录 → 配置 TMDB API Key → 可选配置下载器
- 完成后写入 config.json，跳转主页

这比 Docker 化更影响新用户体验。

### 18.4 前端 SSR vs 静态

当前前端如果没有用到 Next.js 的 SSR 特性（getServerSideProps / Server Components 动态数据），可以考虑：
- `next export` 生成纯静态文件 → 用 Python 后端直接托管（省掉 Node.js 运行时）
- 这样 Docker 镜像只需要 Python，体积和内存占用都小很多

如果用了 SSR，则保持 `next start`。

---

## 19. 执行时间线建议

```
现在          → 继续私有版稳定性收口（测试基线、bug 修复）
稳定后        → Clone 新仓库 + 品牌重命名（1 天）
              → Phase 1 审计（1-2 天）
              → Phase 2 建立契约（2-3 天）
              → Phase 3-4 迁移 BT/RSS 源（各 2-3 天）
              → Phase 5-7 迁移 Metadata/Prowlarr/qB（各 3-5 天）
              → Phase 8 网盘源私有化（1-2 天）
              → Phase 9 前端动态感知（2-3 天）
Docker 化     → Deploy Phase 1-2（环境变量 + Dockerfile，2-3 天）
              → Deploy Phase 3（NAS 文档，1 天）
              → Deploy Phase 4（多架构镜像，1 天）
首次发布      → README + Setup Wizard + GitHub Release
```

总计约 4-6 周（非全职投入）。不急，按节奏来。
