# S19 预入库媒体创建

> 业务型 Skill：按标题/年份创建媒体目录 + 预写 NFO + 封面，先建库位后下载
> 实现入口：`routes/discover.py` → `POST /discover/add-media`

## 核心思路

用户在发现页/搜索结果中看到一部想要的影片，点击"加入媒体库"时：
1. 不需要先下载视频文件
2. 立即在 NAS 上创建标准目录结构 + NFO + 封面
3. 媒体库树中立刻可见该条目（状态为"待下载"）
4. 后续搜索/订阅下载完成后，视频文件落入已有目录

## 数据流

```
用户点击"加入" → 前端传入 title/year/tmdb_id/media_type
    → 后端确定目标路径（根据 category_tag 选择电影/剧集根目录）
    → 创建标准目录（如 "黑镜 Black Mirror (2011)/"）
    → 从 TMDB 拉取详情 → 写入 tvshow.nfo 或 movie.nfo
    → 下载封面 poster.jpg
    → 更新 media_library.json（新增节点，标记 pre_added: true）
    → 返回成功，前端刷新树
```

## 目录命名规则

| 类型 | 目录名格式 | 示例 |
|------|-----------|------|
| 电影 | `{中文名} {英文名} ({年份})` | `盗梦空间 Inception (2010)` |
| 剧集 | `{中文名} {英文名} ({首播年份})` | `黑镜 Black Mirror (2011)` |

- 中文名/英文名从 TMDB 详情获取
- 如果只有一种语言名称，不重复

## NFO 写入

- 电影：`movie.nfo`（title/originaltitle/year/tmdbid/plot/genre）
- 剧集：`tvshow.nfo`（title/originaltitle/year/tmdbid/plot/genre/status）
- 复用现有 `nfo_handler.py` 的写入函数

## 封面下载

- 从 TMDB 获取 poster_path → 拼接完整 URL → 下载到目录内 `poster.jpg`
- 复用现有 `poster_downloader.py`

## 与其他模块的交互

| 模块 | 交互方式 |
|------|---------|
| 媒体库树 | 新增节点到 media_library.json，folder_type=movie/tv |
| 搜索 | 预入库条目可作为搜索上下文（已知 tmdb_id → 精确搜索词） |
| 订阅 | 预入库的剧集可直接创建订阅（tmdb_id 已知） |
| 整理 | 下载完成后整理时，目标目录已存在，走"归位"而非"新建" |
| 完整性检测 | 预入库的 TV 可立即计算完整度（有 tmdb_id，本地 0 集） |

## 边界情况

- 重复添加：检查 media_library.json 中是否已有相同 tmdb_id，有则跳过
- NAS 不可达：创建目录失败时返回错误，不写 media_library.json
- TMDB 详情获取失败：仍创建目录和空 NFO（只有 title/year/tmdbid），封面跳过
- 用户删除预入库目录：下次 scan 时自动清理 media_library.json 中的孤立记录

## 前端交互

- 发现页/搜索详情页的"加入媒体库"按钮
- 点击后显示目标路径预览 → 确认 → 创建
- 创建成功后按钮变为"已在库中"（灰色）
- 本地感知模块（S11）负责在卡片上标记"已在库"状态
