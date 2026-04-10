# 网盘搜索流水线

## 架构概览

```
用户输入关键词
    ↓
PanSearchService.search_sync()  ← 聚合调度层
    ├── PanSearchScraper     (pansearch.me, 主力源)
    ├── PanSouClient         (pansou.app, 增强版 plugins+channels)
    ├── GogoPansoScraper     (gogopanso.com:3642, JSON API)
    └── GitHubPanScraper     (本地索引, 24h刷新)
    ↓
聚合处理流水线
    ├── 1. share_url 精确去重
    ├── 2. 标题相似度去重 (Levenshtein > 0.9 同 pan_type 折叠)
    ├── 3. 关键词相关性过滤 (2字滑窗匹配, 过滤后为空则回退全部)
    ├── 4. 敏感词过滤 (content_filter.py)
    ├── 5. 质量过滤 (分辨率/体积/整季判定)
    ├── 6. Alist 挂载状态标记
    └── 7. 按网盘类型分组 (优先级: 夸克>阿里>115>PikPak>百度)
    ↓
前端展示 (PanResultsView)
    ├── 筛选器: 网盘类型 / 来源 / 分辨率 / 仅整季
    ├── 分组卡片: 按网盘类型分组展示
    └── 操作: 夸克→自动转存, 其他→打开链接+复制提取码
```

## 搜索源详情

| 源 | 文件 | 类型 | 接口 | 特点 |
|---|---|---|---|---|
| PanSearch | pan_scraper_pansearch.py | 爬虫 | GET pansearch.me/search | 量最大, 偶尔限频 |
| PanSou | pan_scraper_pansou.py | API | GET pansou.app/api/search | plugins+channels, TG频道代搜 |
| 狗狗盘搜 | pan_scraper_gogopanso.py | API | GET gogopanso.com:3642/search | 每日更新, 存活率100% |
| GitHub | pan_scraper_github.py | 本地索引 | raw.githubusercontent.com | 1374条夸克, 24h刷新 |

## 数据流转

1. 所有源输出统一 `PanResult` 模型 (pan_models.py)
2. share_url 域名白名单校验 (VALID_PAN_DOMAINS)
3. 标题自动清洗 (去站点水印/乱码) + 分辨率自动提取
4. 前端通过 `/search/pan?keyword=xxx` 调用, 返回 PanSearchResponse

## 新增搜索源的步骤

1. 创建 `backend/pan_scraper_xxx.py`, 继承 ScraperBase, 实现 search() 返回 List[PanResult]
2. 在 `pan_search_service.py` 中 import 并在 __init__ 中注册
3. 在 `shared.py` 的 search_sources 字典中添加开关
4. 在 `pan_search_service.py` 的 all_source_names 列表中添加
5. 在前端 SearchModal.tsx 的 SOURCE_LABELS 中添加中文标签

## 转存链路

```
用户点击转存 → POST /alist/transfer
    ├── 夸克: quark_transfer.py → Alist Cookie → stoken → 转存
    └── 其他: 返回提示手动保存
```
