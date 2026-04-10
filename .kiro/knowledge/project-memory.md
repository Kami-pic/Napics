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

## 网盘搜索
- 主力源：pansearch.me（国内直连，夸克/阿里/百度）
- 暂不可用：rrdynb（Cloudflare 拦截）、ddys（域名不可达）— 需 Playwright
- 夸克转存已通：Alist Cookie → stoken → 文件列表 → 转存
- 待做：磁力熊直搜、其他网盘转存 API、设置页搜索源开关

## 当前进度与下一步
- 搜索增强 TODO：`.kiro/docs/search-enhance-todo.md`
- 自动替换 TODO：`.kiro/docs/auto-replace-todo.md`

## 后端模块化（2026-04-09）
- 旧 main.py（4163 行）拆分为 67 行入口 + 9 个路由模块 + shared.py
- 拆分脚本：`backend/_refactor_main.py`，验证脚本：`backend/_verify_all_apis.py`
- 104 个路由路径不变，前端零改动，15 个端点全量验证通过
- 前端重启按钮修复：后端调用 `restart.bat silent`，前端轮询后端地址等待恢复
- 前端 api.ts 中 Gemini 错误的 `/api/v1/xxx` 路径已全部改回旧路径
- 前端设置新增 qB 用户名/密码、播放器路径配置项
- 废弃文件移至 `_archived_20260409/`（确认无问题后可删除）

## 已知业务踩坑
- shadow_name 可能含中文，enName 构造时必须去掉中文字符
- 搜索缓存只缓存有结果的，空结果不缓存
- 前端过滤器是纯前端行为，不触发重新搜索
- 网盘转存必须同时提取 share_url + 提取码
- Alist 挂载状态：夸克/PikPak/115/百度 正常，阿里云分享 只能读取不能写入。
- 夸克转存 API：stoken 含特殊字符需 URL 编码，fid_token_list 用 share_fid_token 不是 fid
- pansearch.me 连续搜索会被限频，需要间隔
- alipansou.com 用 JS 加密渲染，纯 requests 拿不到结果
- Alist 离线下载不支持网盘分享链接，只支持 magnet/http/ed2k
- 快速同步新增超过 50 个文件时自动切换快速模式（跳过 ffprobe，只读文件名+大小）
- 扫描/同步的 event_generator 必须整体包 try-except，单文件失败不能中断整个流
