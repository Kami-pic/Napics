# 项目记忆

> 只记录 steering/knowledge 其他文件没覆盖的动态业务知识。更新前必须经用户确认。

## 搜索词构造规则
- cnName：从 clean_name 提取中文字符，cnParts 用 Set 去重避免重复中文名
- enName：shadow_name 去年份再去中文字符 > clean_name 中英文部分
- 搜索框默认词：cnName + enName（cn/en 实质相同时只用 cn）
- 搜索标签按 isSame 判断避免重复标签
- 保存路径：优先 searchContext.savePath > currentFolder > NAS 根路径

## 下载管理
- qB：直接传 save_path，旧沙盒任务完成后 _relocate_to_save_path 自动转移
- Alist 双阶段：cloud_download → local_sync → completed
- 删除记录：DELETE /download-manager/task + POST /download-manager/delete-tasks
- unknown/lost 状态也可删除
- 归位替换：file_relocator.py（relocate → confirm_replace / archive_both / cancel_replace）

## 整理流水线（V3）
- 三段式：分类 → 标准化 → 替换，详见 `knowledge/organize-pipeline-v3.md`
- 分类体系：movie/tv/collection/series/season/mixed（一级标签只有 movie/tv）
- 文件夹类型手动覆盖：`backend/folder_types.json`（前端改类型即时写入，持久化）
- 一级分类标签：`config.json` 的 `category_tags`（如 `其他视频 → movie`）

## 网盘搜索（2026-04-10 扩展）
- 当前启用 4 个源：pansearch + pansou(增强版) + gogopanso + github
- PanSearch (pansearch.me)：主力源，夸克/阿里/百度，直接 requests
- PanSou 增强版 (pansou.app)：支持 plugins(10个插件) + channels(60+ TG频道)，无需 TG 账号
- 狗狗盘搜 (gogopanso.com)：公开 JSON API（端口3642），每日更新，存活率100%，数据源=aliyunpanshare
- GitHub 仓库：Zishuzuinb/QuarkShare + leobba/quark-share，本地索引1374条夸克资源，24h刷新
- 暂不可用：rrdynb/ddys（Cloudflare）、慢读/我能搜（纯JS渲染需Playwright）
- 通用站点框架（凌风云/盘搜搜/小白盘/趣盘搜）：代码保留但全部暂关（需登录/403/超时）
- 夸克转存已通：Alist Cookie → stoken → 文件列表 → 转存
- 前端筛选器：网盘类型 + 来源 + 分辨率 + 仅整季（下拉选择框，和 BT FilterBar 同级布局）
- 前端来源标签映射：SOURCE_LABELS（pansearch/pansou/gogopanso/github）

## 后端模块化（2026-04-09 初拆，04-12 大文件拆分）
- 旧 main.py（4163 行）拆分为 67 行入口 + 9 个路由模块 + shared.py
- 2026-04-12 大文件拆分（4 个后端 + 2 个前端）：
  - scraper.py(1193行) → nfo_handler.py + poster_downloader.py + scraper.py（递归刮削）
  - organizer.py(1862行) → renamer.py（重命名+影子名）+ structure_organizer.py（结构整理+归档）+ organizer.py（分类判定~550行）
  - routes/scrape.py(1169行) → routes/media_info.py（候选搜索+详情多源）+ routes/poster.py（海报管理+图片代理）
  - routes/organize.py(1306行) → routes/relocate.py（归位替换）+ routes/analyze.py（分析诊断）
- 所有拆分通过 re-export 保持向后兼容，现有 `from organizer import xxx` / `from scraper import xxx` 全部不用改
- 循环依赖通过延迟导入解决（renamer/structure_organizer 在函数内部 `from organizer import ...`）
- 路由路径不变，前端 api.ts 零改动
- 回归测试：后端 33 项 + 前端 34 项 = 67 项全部通过

## 前端组件拆分
- 8 个子目录：ai/ detail/ download/ layout/ manage/ media/ search/ settings/
- detail/ 已拆分（2026-04-11）：DetailDrawer.tsx 1339行→62行瘦壳 + 11 个独立文件
  - DetailDrawer.tsx（入口）→ FolderDetail / VideoDetail / CandidatePicker / ShadowNameSection / useScrape / BatchPanel / EditableTitle / DetailComponents / PosterUpload / detailCache
- media/ 已拆分（2026-04-11 + 04-12）：
  - DiscoverPage.tsx 681行→313行 + 6 个独立文件（DiscoverCard / DiscoverHeader / ExpandDetail / WeeklyCombinedView / SkeletonGrid / discoverUtils）
  - CardGrid.tsx 573行→351行 + 3 个独立文件（CardPoster / EpisodeList / ExpandPanel）
  - CardPoster 独立后可被 ExpandPanel / DiscoverPage 等复用
- search/ 已拆分（2026-04-12）：
  - SearchModal.tsx 855行→467行 + 3 个独立文件（EpisodeTable / PanFilterBar / PanResultsView）
  - PanFilterBar 导出 PanFilterState / DEFAULT_PAN_FILTERS / applyPanFilters / PAN_TYPE_COLORS 等常量
- BatchUpgradePanel.tsx（530行）暂不拆：状态机逻辑自洽
- 颜色规范：`lib/mediaColors.ts`（电影蓝/剧集绿/动画紫/书籍粉/游戏橙/评分品牌色）
- 测试框架：vitest + @testing-library/react，测试文件在 `frontend/__tests__/`

## 当前进度与下一步
- 代码拆分 TODO：`.kiro/docs/code-split-todo.md`（后端 4 项 + 前端 2 项已完成，剩余前端 5-8 低优先级）
- 搜索增强 TODO：`.kiro/docs/search-enhance-todo.md`
- 自动替换 TODO：`.kiro/docs/auto-replace-todo.md`
- 发现推荐 TODO：`.kiro/docs/discover-recommend-todo.md`（阶段 1 完成，阶段 2 探索筛选待做）
- 待做：磁力熊直搜、其他网盘转存 API、设置页搜索源开关、转存纳入 DownloadManager
- 待做：发现页详情匹配错误时的候选选择（阶段 2，类似刮削候选面板）

## 发现推荐模块（2026-04-10 新增，04-11 大幅增强，04-12 详情面板升级）
- `douban_api_v2.py`：豆瓣 App API v2 签名鉴权，9 个榜单 + 探索 + 搜索 + 详情
  - `_normalize_item` 从 `card_subtitle` 解析 genres/countries/year（合集接口不直接返回这些字段）
  - `episodes_info` 字段（如"22集全"）从原始 API 的 `episodes_info` 提取
  - 搜索结果过滤非影视条目（`target_type not in ("movie","tv")`）
  - 搜索 `responseGroup: "large"` 获取 Bangumi 评分
- 详情多源算法（`/media/info?source=&id=`）：
  - douban：豆瓣 v2 详情（优先用 id 直接拉）→ TMDB fallback
  - tmdb：TMDB → 豆瓣 v2 fallback
  - bangumi：Bangumi 详情（优先用 bgm_id 直接拉）→ 豆瓣 v2 → TMDB
  - `_enrich_ratings`：主源命中后并行补充其他两源评分 + external_ids（tmdb_id/imdb_id）
  - 返回 `ratings: {douban, tmdb, bangumi}` + `external_ids: {tmdb_id, imdb_id}` + `source`
- 详情面板功能（04-12 新增）：
  - 数据源下拉（豆瓣/TMDB/Bangumi）+ 🔄 刷新按钮（清缓存+用选中源重新请求）
  - 三源评分：豆瓣5个tab+TMDB趋势显示双评分（豆瓣+TMDB），热门动画+Bangumi趋势显示三源评分
  - 外部链接：豆瓣/TMDB/IMDB/Bangumi，有数据就显示，没数据不显示
  - Bangumi 趋势 tab 的 item.douban_id 实际是 bgm_id → 豆瓣链接不显示，改为 Bangumi 链接
  - 数据来源标签：底部小字 `数据来自 豆瓣/TMDB/Bangumi`
  - 缓存管理：`deleteCachedDetail` 支持清除单条缓存
- 推荐接口 fallback：API v2 失败时回退到旧版网页接口（5 个豆瓣源有映射）
- 图片缓存优化：`/scrape/poster` 改为 `Cache-Control: public, max-age=3600`，`/proxy/image` 改为 `max-age=86400`
- 发现页 tab 切换优化：`display:none` 保持已加载 tab 的 DOM，图片不重新加载
- 发现页卡片信息：标题 + 年份·国家·集数 + 类型标签（genres），评分用品牌色（豆瓣黄/TMDB蓝/Bangumi粉）
- 豆瓣详情封面走 `/proxy/image` 代理（防盗链）
- 刮削候选面板：三源评分（品牌色星星）+ 类型标签（`getMediaTypeColor`）+ 裂图 fallback
- 媒体库颜色统一：电影蓝色、剧集绿色（CardGrid 标签 + 一级目录标签）

## 已知业务踩坑
- shadow_name 可能含中文，enName 构造时必须去掉中文字符
- 搜索缓存只缓存有结果的，空结果不缓存
- 前端过滤器是纯前端行为，不触发重新搜索
- 网盘转存必须同时提取 share_url + 提取码
- Alist 挂载状态：夸克/PikPak/115/百度 正常，阿里云分享只能读取不能写入
- 夸克转存 API：stoken 含特殊字符需 URL 编码，fid_token_list 用 share_fid_token
- pansearch.me 连续搜索会被限频，需要间隔
- gogopanso API 端口 3642，标题有拼音首字母前缀需清洗（如 "L流浪地球2" → "流浪地球2"）
- GitHub 仓库索引：首次搜索触发拉取（约6秒），之后24h内纯本地匹配
- Alist 离线下载不支持网盘分享链接，只支持 magnet/http/ed2k
- 快速同步新增超过 50 个文件时自动切换快速模式（跳过 ffprobe，只读文件名+大小）
- 快速同步增加文件大小变化检测（差异>5%自动重新 ffprobe），解决替换高清版本后仍显示低画质的问题
- 网盘搜索爬虫超时从 30s 降到 15s，慢源不拖累整体
- 发现页 ExpandDetail 的 img 加 key 强制重挂载，解决切换卡片封面残留问题
- 扫描/同步的 event_generator 必须整体包 try-except，单文件失败不能中断整个流
- restart.bat 旧版 timeout 2s 不够导致端口冲突，已改为循环等待端口释放
