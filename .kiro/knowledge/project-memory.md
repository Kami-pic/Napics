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
- 发现推荐 TODO：`.kiro/docs/discover-recommend-todo.md`（阶段 1 完成，阶段 2 探索筛选基本完成）
- 阶段 2 已完成：探索 5 源筛选（豆瓣电影/剧集+TMDB电影/剧集+Bangumi）、综合推荐算法、TOP250 排序标签、评分双滑块、候补机制、详情匹配修复、滚动自动加载、磁吸阻尼吸附
- 阶段 2 剩余：本地媒体库感知(2.7)、详情候选选择、冷门降权、Fallback 补位
- 待做：磁力熊直搜、其他网盘转存 API、设置页搜索源开关、转存纳入 DownloadManager

## 发现推荐模块（2026-04-10 新增，04-11 大幅增强，04-12 详情面板升级+阶段2探索筛选完成）
- `douban_api_v2.py`：豆瓣 App API v2 签名鉴权，9 个榜单 + 探索 + 搜索 + 详情
  - 探索接口 `movie_explore`/`tv_explore`：过滤非影视条目（无标题或无年份且无评分的合集/豆列）
  - 豆瓣探索 sort 参数：T=近期热度（默认） U=综合排序 S=高分优先 R=首播时间
  - sort=T 数据量不稳定（豆瓣 API 行为），后端自动用 sort=U 补位
- `bangumi_client.py`：所有请求加了代理支持（从 config.json 的 http_proxy 读取）
- `tmdb_client.py` discover()：支持 count 参数，超过 20 条自动请求多页合并
- 阶段 2 探索页文件：
  - `ExplorePage.tsx`：探索页主组件（筛选+无限滚动+卡片网格）
  - `ExploreFilterBar.tsx`：探索筛选栏（对照 MP 前端源码完整修正）
  - `RecommendTabContent.tsx`：推荐 tab 渲染组件
  - `combined_recommend.py`：综合推荐算法（三源融合排序）
- 探索筛选配置（完全对齐 MP 前端 discover-DW2W5EZR.js）：
  - 豆瓣：排序(T/U/S/R) + 风格(22个) + 地区(15个常用) + 年代(年代段+动态6年) + 评分双滑块
  - 豆瓣电影额外排序：TOP250（走 movie_top250 接口，显示排名角标）
  - TMDB 电影：排序(6个含升降序) + 风格(19个) + 语言(13个) + 评分双滑块
  - TMDB 剧集：排序(6个，日期用 first_air_date) + 风格(16个) + 语言 + 评分双滑块
  - Bangumi：类别 cat(其他/TV/OVA/Movie/WEB) + 排序(rank/date) + 年份(最近10年)
- 探索页增强：
  - 二级 tab 电影蓝/剧集绿色彩规范
  - 筛选切换立即清空+骨骼屏+loadIdRef 竞态防护
  - 评分过滤后不足 count 条时通用候补机制（用其他排序补位）
  - reqSize = colCount * 4 动态计算，TMDB 多页合并支持
- 详情匹配修复（04-12）：
  - 豆瓣 ID 拉取失败时自动尝试 movie↔tv（探索列表的 media_type 可能不准）
  - 两种都失败说明是非影视条目，直接返回 found:false，不 fallback 搜索（避免匹配错误）
  - 已知案例：豆瓣探索混入合集/豆列（如 "WOWOW 連続ドラマW"），ID 404 后搜索匹配到错误影片
- 滚动交互（04-12）：
  - `hooks/useScrollDamping.ts`：磁吸阻尼 hook，详见 `knowledge/scroll-damping-interaction.md`
  - 下滑距墙 < 460px 吸附到发现页（350ms），上滑距墙 > 260px 吸附回顶部（200ms）
  - 推荐/探索卡片滚动自动加载：前 4 批 IntersectionObserver + 400ms 延时 + 骨骼行，之后手动点击
  - 数据截断到 colCount 整数倍，避免最后一行不满
  - 综合推荐 60 条上限 + 排名角标 + "今天就推荐这么多吧"
  - 媒体库和发现页间距 mt-10（40px）

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
- Bangumi calendar API 的 bgm_id 和卡片标题偶尔错位，需要标题校验防止匹配到错误条目
- 空字符串 `""` 是任何字符串的子串（`"" in "abc"` → True），条件判断时必须先检查非空
- React 中 `{0 && <Component />}` 会渲染文本 "0"，falsy 数值条件必须用 `> 0` 或 `!!` 转布尔
- 扫描/同步的 event_generator 必须整体包 try-except，单文件失败不能中断整个流
- restart.bat 旧版 timeout 2s 不够导致端口冲突，已改为循环等待端口释放
