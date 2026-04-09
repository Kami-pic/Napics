# 项目记忆

> 本文件只记录"steering 和 knowledge 其他文件都没覆盖的、随开发动态变化的业务知识"。
> 不要在这里重复写产品定义（→ product.md）、技术栈（→ tech.md）、代码结构（→ structure.md）、
> 编码风格（→ code-style.md）、API 清单（→ api-reference.md）、数据结构（→ data-models.md）。
> 更新前必须经用户确认。

## 搜索词构造规则
- cnName：从 clean_name 提取中文字符，Set 去重避免重复
- enName：shadow_name 去年份再去中文字符 > clean_name 中英文部分
- 搜索框默认词：cnName + enName（cn/en 实质相同时只用 cn）
- 搜索标签按 isSame 判断避免重复标签
- 保存路径：优先 searchContext.savePath（视频/文件夹实际路径）> currentFolder > NAS 根路径

## 下载管理架构
- qB 下载：直接传 save_path 给 qB，下载到目标目录
- 旧任务兼容：沙盒中的旧任务完成后 _relocate_to_save_path 自动转移
- Alist 双阶段：cloud_download → local_sync → completed
- 删除记录：DELETE /download-manager/task + POST /download-manager/delete-tasks
- unknown/lost 状态也可删除

## 整理流水线（V3）
- 执行顺序：分类（tv/movie/mix）→ 标准化（散装封装）→ 替换（新旧对比）
- 标准化结构需要处理"散装+新下载文件夹共存"的场景，先封装散装再处理替换
- 详细设计见 `.kiro/docs/organize-guide-v3.md`

## 网盘搜索现状
- 当前可用源：pansearch.me（国内直连，夸克/阿里/百度）
- 暂不可用：rrdynb（Cloudflare 拦截）、ddys（域名不可达）— 需 Playwright
- 夸克转存已实现：从 Alist 提取 Cookie → stoken → 文件列表 → 转存
- 待做：更多搜索源、磁力熊直搜、百度/115/PikPak 转存 API

## 当前进度与下一步
- 搜索增强 TODO：`.kiro/docs/search-enhance-todo.md`
- 自动替换 TODO：`.kiro/docs/auto-replace-todo.md`

## 后端模块化重构（2026-04-09）
- 旧 main.py（4163 行）拆分为 67 行入口 + 9 个路由模块 + shared.py
- 拆分脚本：`backend/_refactor_main.py`，验证脚本：`backend/_verify_all_apis.py`
- 104 个路由路径完全不变，前端零改动，15 个端点全量验证通过
- 前端重启按钮修复：后端调用 `restart.bat silent`，前端轮询后端地址等待恢复
- 前端 api.ts 中 Gemini 错误的 `/api/v1/xxx` 路径已全部改回旧路径
- 前端设置新增 qB 用户名/密码、播放器路径配置项
- 废弃文件移至 `_archived_20260409/`（确认无问题后可删除）

## 已知业务踩坑
- shadow_name 可能含中文，enName 构造时必须去掉中文字符
- cnParts 提取中文段后用 Set 去重，避免 clean_name 中重复中文名
- 搜索缓存只缓存有结果的，空结果不缓存
- 前端过滤器是纯前端行为，不触发重新搜索
- 网盘转存必须同时提取 share_url + 提取码
- Alist 挂载状态：夸克/PikPak/115 正常，阿里 token 过期，百度授权问题
- 夸克转存 API：stoken 含特殊字符需 URL 编码，fid_token_list 用 share_fid_token 不是 fid
- pansearch.me 连续搜索会被限频，需要间隔
- alipansou.com 用 JS 加密渲染，纯 requests 拿不到结果
- Alist 离线下载不支持网盘分享链接，只支持 magnet/http/ed2k
- 快速同步新增超过 50 个文件时自动切换快速模式（跳过 ffprobe，只读文件名+大小）
- 扫描/同步的 event_generator 必须整体包 try-except，单文件失败不能中断整个流
