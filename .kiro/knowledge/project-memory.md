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

## 后端模块化（2026-04-09）
- 旧 main.py（4163 行）拆分为 67 行入口 + 9 个路由模块 + shared.py
- 路由模块：library/scrape/organize/search/download/config/discover/system/tools
- BatchRequest 定义在 tools.py（不在 system.py），batch_manage 路由在 tools.py
- folder_types.json 路径：library.py 写入和 organizer.py 读取都指向 `backend/`
- 104 个路由路径不变，前端零改动
- restart.bat：循环等待端口释放后再启动（解决 Errno 10048 端口冲突）

## 前端组件拆分
- 8 个子目录：ai/ detail/ download/ layout/ manage/ media/ search/ settings/
- ai/SmartManager.tsx — AI 智能管理
- detail/DetailDrawer.tsx — 详情抽屉（含移动/删除/文件夹类型切换）
- detail/MovieCollectionGrid.tsx + SeriesCollectionList.tsx + TvDetail.tsx — 详情子视图
- download/DownloadManagerPanel.tsx + FileTreeNode.tsx + RecycleBinPanel.tsx — 下载管理
- layout/Breadcrumbs + FilterBar + Header + ScanPanel + Sidebar + Toolbar — 布局组件
- manage/BatchBar.tsx — 批量操作栏
- media/CardGrid + FolderTable + AddMediaPanel + AnalysisReport + DoubanRecommend + OrganizeHistory + OrganizeProgress + OperationHistory — 媒体展示
- search/SearchModal.tsx + FilterBar.tsx + BatchUpgradePanel.tsx — 搜索弹窗
- settings/SettingsModal.tsx — 设置弹窗

## 当前进度与下一步
- 搜索增强 TODO：`.kiro/docs/search-enhance-todo.md`
- 自动替换 TODO：`.kiro/docs/auto-replace-todo.md`
- 待做：磁力熊直搜、其他网盘转存 API、设置页搜索源开关、转存纳入 DownloadManager

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
- 扫描/同步的 event_generator 必须整体包 try-except，单文件失败不能中断整个流
- restart.bat 旧版 timeout 2s 不够导致端口冲突，已改为循环等待端口释放
