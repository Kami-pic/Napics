# NAS Video Upgrader 插件化改造计划

> 面向 Codex / Agent 的工程任务书。  
> 目标：将当前项目从“个人全链路工具”改造成“核心能力开源 + 高风险能力插件化 + 私有增强层可保留”的结构。

---

## 0. 改造总目标

当前项目已经具备完整链路：媒体库扫描、刮削、整理、搜索、下载、归位、订阅、洗版、AI 辅助。下一阶段不继续堆功能，而是进行边界重构。

本轮改造目标：

1. 明确 Core 与 Plugin 的边界。
2. 将高风险、高波动、强外部依赖能力从核心代码中抽离。
3. 保留核心产品竞争力：资源整理、质量识别、媒体理解、AI 辅助、中文生态适配。
4. 为未来开源 / 商业化 / 私有自用三套路径预留结构。
5. 保持当前自用功能可继续运行，不因抽象而破坏现有体验。

本轮不是重写项目，不做播放端，不做新功能。

---

## 1. 产品边界定义

### 1.1 Core：必须保留在核心仓库

Core 是项目长期可公开、可维护、低法律风险的部分。

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

### 1.2 Plugin：必须抽离成插件

以下能力必须从核心业务逻辑中解耦，不能继续散落在 route / service / manager 中直接调用。

必须插件化：

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

插件化后，核心只知道：

```text
SearchProvider
DownloadProvider
CloudDriveProvider
RssProvider
MetadataProvider
```

核心不应该知道：

```text
Bitsearch / Nyaa / 蜜柑 / 1337x / 阿里云盘 / 夸克 / PikPak / 某个具体站点
```

---

### 1.3 Private：建议长期私有

以下能力可以继续存在，但不建议进入公开核心仓库。

建议私有：

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

## 2. 目标目录结构

建议逐步演进到以下结构，不要求一次性完成。

```text
backend/
├── core/
│   ├── media_library/
│   ├── organizer/
│   ├── scraper/
│   ├── quality/
│   ├── completeness/
│   ├── ai/
│   └── matching/
│
├── plugins/
│   ├── contracts/
│   │   ├── search_provider.py
│   │   ├── download_provider.py
│   │   ├── cloud_drive_provider.py
│   │   ├── rss_provider.py
│   │   └── metadata_provider.py
│   │
│   ├── registry.py
│   ├── loader.py
│   ├── config_schema.py
│   └── builtin/
│       ├── prowlarr/
│       ├── qbittorrent/
│       ├── openlist/
│       └── tmdb/
│
├── private_plugins/
│   ├── bt_sources/
│   ├── cloud_drive_sources/
│   └── rss_sources/
│
├── routes/
├── shared.py
└── main.py
```

说明：

- `core/` 不允许直接 import 具体资源站。
- `plugins/contracts/` 定义稳定接口。
- `plugins/builtin/` 只放低风险或用户显式配置型插件。
- `private_plugins/` 可保留给自用，不进入公开仓库。
- 现阶段不强制拆成多个 Python package，先完成代码边界即可。

---

## 3. 插件接口设计

### 3.1 SearchProvider

用于资源搜索，但不关心资源来自 BT、网盘还是聚合服务。

```python
from typing import Protocol, Iterable, Optional
from pydantic import BaseModel

class SearchQuery(BaseModel):
    keyword: str
    media_type: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    year: Optional[int] = None
    aliases: list[str] = []
    language_hints: list[str] = []

class SearchResult(BaseModel):
    provider: str
    title: str
    url: str
    resource_type: str  # torrent | magnet | cloud | webpage | rss_item
    size: Optional[int] = None
    seeders: Optional[int] = None
    publish_time: Optional[str] = None
    raw: dict = {}

class SearchProvider(Protocol):
    name: str
    provider_type: str

    def is_enabled(self) -> bool:
        ...

    def search(self, query: SearchQuery) -> Iterable[SearchResult]:
        ...
```

要求：

- Provider 只负责获取原始候选。
- 评分、过滤、排序必须回到 Core 的 L1-L4 能力层处理。
- 不允许 Provider 自己决定最终是否下载。

---

### 3.2 DownloadProvider

用于下载任务提交与状态同步。

```python
from typing import Protocol, Optional
from pydantic import BaseModel

class DownloadRequest(BaseModel):
    title: str
    url: str
    resource_type: str
    save_path: Optional[str] = None
    category: Optional[str] = None
    metadata: dict = {}

class DownloadTask(BaseModel):
    provider: str
    task_id: str
    title: str
    status: str
    progress: float = 0
    save_path: Optional[str] = None
    raw: dict = {}

class DownloadProvider(Protocol):
    name: str

    def submit(self, request: DownloadRequest) -> DownloadTask:
        ...

    def list_tasks(self) -> list[DownloadTask]:
        ...

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        ...
```

要求：

- qBittorrent、Alist、OpenList 都应通过该接口接入。
- Core 不直接依赖 qB API。
- 下载完成后的归位逻辑属于 Core，不属于 DownloadProvider。

---

### 3.3 CloudDriveProvider

用于云盘挂载、云端下载、链接解析、文件同步。

```python
from typing import Protocol, Optional
from pydantic import BaseModel

class CloudLink(BaseModel):
    provider: str
    url: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    password: Optional[str] = None
    raw: dict = {}

class CloudDriveProvider(Protocol):
    name: str

    def parse_link(self, url: str) -> Optional[CloudLink]:
        ...

    def transfer(self, link: CloudLink, target_path: str) -> dict:
        ...

    def list_remote(self, path: str) -> list[dict]:
        ...
```

要求：

- 阿里、夸克、百度、115、PikPak 等具体实现不进入 Core。
- Core 只保留接口和状态模型。
- 云端转存默认不在公开版启用。

---

### 3.4 RssProvider

用于订阅源轮询。

```python
from typing import Protocol
from pydantic import BaseModel

class RssItem(BaseModel):
    provider: str
    title: str
    url: str
    publish_time: str | None = None
    raw: dict = {}

class RssProvider(Protocol):
    name: str

    def poll(self) -> list[RssItem]:
        ...
```

要求：

- RSS 源只提供候选。
- 是否匹配订阅、是否下载、是否升级，由 Core 决定。

---

## 4. 分阶段执行计划

### Phase 1：边界盘点，不改逻辑

目标：先确认哪些文件属于 Core，哪些属于 Provider。

任务：

1. 扫描后端代码，列出所有直接访问外部资源的模块。
2. 标记模块类型：
   - Core
   - Builtin Plugin
   - Private Plugin
   - Deprecated / One-off Script
3. 输出 `docs/pluginization-audit.md`。
4. 不做任何业务逻辑修改。

验收：

- 有完整模块清单。
- 每个搜索源、网盘源、RSS 源、下载器都有归类。
- 没有修改现有运行逻辑。

---

### Phase 2：建立插件契约

目标：先建立接口，不迁移实现。

任务：

1. 新建 `backend/plugins/contracts/`。
2. 定义：
   - `SearchProvider`
   - `DownloadProvider`
   - `CloudDriveProvider`
   - `RssProvider`
   - `MetadataProvider`
3. 新建统一 DTO：
   - `SearchQuery`
   - `SearchResult`
   - `DownloadRequest`
   - `DownloadTask`
   - `CloudLink`
   - `RssItem`
4. 新建 `backend/plugins/registry.py`。
5. 现有代码暂时不强制接入。

验收：

- 所有 DTO 使用 Pydantic 或明确类型定义。
- 禁止裸 dict 作为跨层接口。
- 单元测试能通过。

---

### Phase 3：迁移 Prowlarr / qBittorrent / OpenList

目标：优先迁移低风险、用户显式配置型外部服务。

任务：

1. 将 Prowlarr 封装为 `SearchProvider`。
2. 将 qBittorrent 封装为 `DownloadProvider`。
3. 将 Alist / OpenList 封装为 `CloudDriveProvider` 或 `DownloadProvider`。
4. 原 route / service 改为通过 registry 获取 provider。
5. 保留原有配置兼容。

验收：

- 用户现有配置不需要大规模改动。
- Prowlarr 搜索结果进入统一 `SearchResult`。
- qB 下载任务进入统一 `DownloadTask`。
- Core 不直接 import qB / Prowlarr client。

---

### Phase 4：迁移 BT 直搜源

目标：把所有 BT 直搜源从 Core 中抽离。

任务：

1. 为每个 BT 搜索源创建独立 provider wrapper。
2. 保留原 parser，但移动到 provider 内部。
3. Core 搜索流程只接收 `SearchResult`。
4. Core 统一执行：
   - 清洗
   - 匹配
   - 过滤
   - 排序
   - 黑名单判断
5. Provider 不再承担业务决策。

验收：

- 禁止 Core 直接 import 具体 BT 源。
- 禁止 route 直接调用具体 BT 源。
- 搜索结果排序逻辑集中在 L1-L4 能力层。
- 每个 provider 可单独启用 / 禁用。

---

### Phase 5：迁移网盘搜索源

目标：将网盘搜索源完全插件化，并默认进入 Private Plugin。

任务：

1. 创建 `private_plugins/cloud_drive_sources/`。
2. 迁移：
   - pansearch
   - pansou
   - gogopanso
   - github
   - rrdynb
   - ddys
   - 其他网盘源
3. Core 仅保留 `CloudDriveProvider` 和 `CloudLink`。
4. 公开版默认不启用网盘搜索源。
5. UI 中将网盘功能标记为 external plugin。

验收：

- Core 仓库可以在没有网盘 provider 的情况下运行。
- 网盘搜索不是默认能力。
- 网盘 provider 可在私有环境单独加载。

---

### Phase 6：订阅系统去 Provider 耦合

目标：订阅系统只处理订阅规则，不处理具体来源。

任务：

1. RSS 轮询改为通过 `RssProvider`。
2. 直搜补充改为通过 `SearchProvider`。
3. 订阅匹配逻辑保留在 Core。
4. 自动下载逻辑通过 `DownloadProvider`。
5. 洗版策略与 provider 解耦。

验收：

- 订阅系统不直接 import 具体 RSS 源。
- 订阅系统不直接 import 具体 BT 源。
- 添加新 RSS provider 不需要改订阅核心逻辑。

---

### Phase 7：公开版裁剪与私有版保留

目标：形成两套可维护版本。

建议分支：

```text
main                # 自用完整版本
open-core           # 可公开核心版本
private-plugins     # 私有插件实现
```

或目录隔离：

```text
backend/plugins/builtin/
backend/private_plugins/
```

任务：

1. 清理个人配置、API Key、NAS 路径。
2. 移除一次性调试脚本。
3. 增加 `.env.example`。
4. 增加 Docker Compose 草案。
5. 增加公开版 README。
6. 增加 Provider 开发文档。

验收：

- 公开版可在无私有插件情况下启动。
- 公开版不包含具体高风险资源站实现。
- 自用版仍可加载私有插件。

---

## 5. 明确禁止事项

本轮插件化期间，禁止：

1. 边迁移边修改搜索评分逻辑。
2. 边迁移边新增 provider。
3. 边迁移边修复非阻塞 bug。
4. 将 provider 内部逻辑继续泄漏到 core。
5. 用裸 dict 替代 DTO。
6. 在 route 中直接调用具体资源站。
7. 在 core 中出现具体资源站名称。
8. 将网盘搜索源放进公开核心。
9. 将“自动下载侵权资源”作为产品卖点。
10. 为了兼容旧代码继续扩大 shared.py 单例污染。

---

## 6. 核心验收标准

最终目标不是“文件移动完成”，而是满足以下边界：

```text
Core 负责理解媒体。
Plugin 负责连接外部世界。
Private 负责高风险资源能力。
```

具体检查：

- Core 是否可以在没有 BT / 网盘 provider 的情况下运行？
- Core 是否仍能完成扫描、整理、刮削、质量识别？
- 搜索源是否都通过 SearchProvider 接入？
- 下载器是否都通过 DownloadProvider 接入？
- 云盘能力是否都通过 CloudDriveProvider 接入？
- 订阅系统是否不依赖具体 RSS 源？
- UI 是否能识别 provider 启用 / 禁用状态？
- 自用版本是否能继续加载私有 provider？

---

## 7. 推荐优先级

建议执行顺序：

```text
1. 审计边界
2. 建立 contracts
3. 迁移 Prowlarr
4. 迁移 qBittorrent
5. 迁移 OpenList / Alist
6. 迁移 BT 直搜源
7. 迁移网盘源
8. 解耦订阅系统
9. 整理公开版分支
```

不要一开始就迁移所有爬虫。

优先迁移 Prowlarr / qB / OpenList，因为它们是用户显式配置的外部服务，风险较低，也最适合作为插件系统样板。

---

## 8. 给 Agent 的执行方式

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

## 9. 最终定位

本项目公开后的核心定位应是：

> 面向 NAS 高阶用户的 AI 媒体资产管理与整理系统。

避免定位为：

> 自动下载工具 / 免费影视工具 / 网盘搜索工具 / 资源站聚合器。

对外强调：

- 媒体库整理
- 质量识别
- 低质量资源发现
- 中文媒体生态适配
- AI 辅助修复
- 插件化外部服务接入

对外弱化：

- 内置资源站
- 网盘搜索
- 自动下载
- 自动转存
- 资源获取链路

---

## 10. 一句话原则

> 把长期有价值的媒体理解能力留在 Core，把高波动高风险的资源连接能力移到 Plugin，把最敏感的资源站和网盘实现留在 Private。






