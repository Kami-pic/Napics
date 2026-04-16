# 项目记忆

> 只记录跨模块的业务知识和核心红线。特定领域细节见对应 knowledge 文件。
> 更新原则：直接覆写旧内容，不保留矛盾的历史版本。

## 跨域业务知识

### 搜索架构（BT/磁力 + 网盘 双 Tab）
- BT/磁力：Prowlarr（主力）+ 5 个直搜源（Bitsearch/磁力熊/XL720/Nyaa/蜜柑）
- SSE 全源并行搜索（/api/search/stream），as_completed 逐个推送，前端增量追加
- 去重：同源内 infohash 去重，跨源不去重
- 磁力链接源（磁力熊/XL720）seeders=0 且 size=0，不受做种数筛选影响
- 直搜源统一输出 SearchResult 格式，routes/search.py 的 SSE 端点合并
- 网盘：6 个源（pansearch/pansou/gogopanso/github/rrdynb/ddys），pan_search_service.py 聚合
- 前端三层分离：results(全量) → displayResults(智能过滤+排序) → filtered(筛选器+源开关)
- 搜索设置在 SearchModal ⚙️ 二级菜单（搜索源/过滤规则/索引器/排序权重），不在总设置页
- 需代理的源（Bitsearch/Nyaa/蜜柑）从 config.http_proxy 读取，和 TMDB 共用
- 直连源（磁力熊/XL720/rrdynb）不走代理
- XL720 响应极慢（超时 12s + 1 次重试），搜索质量差需中文子串过滤

### 搜索词构造
- cnName：从 clean_name 提取中文字符，cnParts 用 Set 去重
- enName：shadow_name 去年份再去中文字符 > clean_name 中英文部分
- 搜索框默认词：cnName + enName（cn/en 实质相同时只用 cn）
- 保存路径：优先 searchContext.savePath > currentFolder > NAS 根路径
- discoverUtils.ts 的 normalizeItem 是所有推荐/探索/搜索数据的统一入口，新增字段必须在此传递

### 下载管理
- qB：直接传 save_path，旧沙盒任务完成后自动转移
- Alist 双阶段：cloud_download → local_sync → completed
- 归位替换：file_relocator.py（relocate → confirm_replace / archive_both / cancel_replace）

### 整理流水线
- 三段式架构，详见 knowledge/organize-pipeline-v3.md
- 分类体系：movie/tv/collection/series/season/mixed（一级标签只有 movie/tv）
- 文件夹类型手动覆盖：`backend/folder_types.json`
- 一级分类标签：`config.json` 的 `category_tags`

### 质量评分体系（跨搜索/订阅/整理的全局基准）
- 100 分制（分辨率45+来源20+音频20+编码10+字幕5）
- 搜索/订阅/整理模块统一调用 compare_quality_score()，阈值5分
- quality_score >= 35 判定有质量，回退 height >= 720
- config_manager.save_library() 自动注入 quality_score 字段

### 本地媒体感知（跨推荐/探索/搜索的全局机制）
- local_media_matcher.py：三层匹配（tmdb_id → title+year → title）+ 内存索引
- 推荐/探索/搜索三个接口统一注入 local_status + local_folder
- 中文匹配用前缀（startswith），避免"你的名字"误匹配"以你的名字呼唤我"

## 核心红线

- shadow_name 可能含中文，enName 构造时必须去掉中文字符
- 搜索用 clean_name + 去中文的 shadow_name 拼接，不要直接搜片名
- 豆瓣 API v2 请求间随机延迟 1-3 秒 + 随机 UA，防封
- pansearch.me 连续搜索会被限频，需要间隔
- 网盘转存必须同时提取 share_url + 提取码
- ffprobe 必须设 timeout=15，长队列加 try-except 兜底
- 后台数据和角色快照是独立路径，改一个不要影响另一个
- Bangumi calendar API 的 bgm_id 和卡片标题偶尔错位，需要标题校验
- 发现页 ExpandDetail 的 img 加 key 强制重挂载，解决切换卡片封面残留
- media_library.json 中 shadow_tmdb_id 覆盖率极低，片名匹配是主力
- gogopanso 标题有拼音首字母前缀需清洗（如 "L流浪地球2" → "流浪地球2"）
- normalize_text 会去掉标点和空格，中英混合标题需分别提取中文部分匹配
- 快速同步新增超过 50 个文件时自动切换快速模式（跳过 ffprobe）
- 搜索缓存只缓存有结果的，空结果不缓存
- BT 直搜源统一输出 SearchResult 格式，按 infohash（大写）去重合并到 Prowlarr 结果
- Bitsearch API 有 429 限频，缓存 10 分钟 + 请求间延迟 2-4s
- curl_cffi 是绕 CF 中低级保护的关键，所有有 CF 风险的爬虫必须启用
- rrdynb 多次搜索会触发 CF 限频（临时性，过段时间自动解除），请求间延迟 1.5-3s
- ddys 已升级为 JSON API（POST /api/search-netdisk），link 字段是 base64 编码
- 蜜柑 RSS 同时服务于 BT 搜索（即时）和订阅系统（定时轮询），共用 rss_source_mikan.py
- 新增 BT 直搜源步骤：写爬虫(继承 ScraperBase) → shared.py 加 getter → routes/search.py 的 scrapers 列表加一行

## 领域索引

- 整理流水线 → `knowledge/organize-pipeline-v3.md`
- 网盘搜索 → `knowledge/pan-search-pipeline.md`
- BT 搜索 → `knowledge/bt-search-pipeline.md`
- 下载归位替换 → `knowledge/download-replace-pipeline.md`
- 发现推荐 → `knowledge/discover-recommend.md`
- 订阅系统 → `knowledge/subscribe-system.md`
- 滚动交互 → `knowledge/scroll-damping-interaction.md`
- API 清单 → `knowledge/api-reference.md`
- 数据结构 → `knowledge/data-models.md`
- BT 搜索扩展 TODO → `docs/bt-expand-todo.md`
