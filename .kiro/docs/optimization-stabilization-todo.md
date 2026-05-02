# [TODO] 项目整体优化 — 收口校准阶段任务清单

> 当前阶段：功能已基本完成，优先证明主链路没有被破坏。  
> 执行原则：只做低风险收口与验证底座，不做功能扩展，不做架构升级。  
> 来源：`optimization-master-plan.md` 的“当前阶段覆盖协议”。

---

## 当前总览（2026-04-28）

### 当前主线

- 当前正在处理：搜索下载修复 + 清洗名自愈机制 + 前端英文名展示
- 并行完成：大文件拆分 P1-P5（纯重构，详见 `code-split-todo.md`）
- 上一条主线（下载→归位闭环）已暂停，详见 [download-relocate-worklog.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-worklog.md)

### 本轮完成

- 多项 bug 修复与功能优化（2026-04-30 对话）：
  - 删除操作：电影封装文件夹检测 + 空壳目录清理 + 一级分类目录保护
  - 下载管理：已删除 hash 黑名单防止 sync_from_qb 复活已删任务
  - 刮削：写入 try-except + 海报 Cache-Control 改 no-cache + 单点自愈
  - 整理后自动对账：清理已不存在的记录 + 重算质量分
  - 质量检测：refresh-quality API（单文件跑 ffprobe / 全局重算）+ 前端按钮
  - ffprobe 去掉 shell=True 修复中文 UNC 路径乱码（244 个"未知"分辨率修复）
  - 蜜柑加入无做种数信息源集合（后端+前端三处）
  - get_library_tree 自愈层3 从全量 NFO 读取改为单点触发（首屏 >10s → <1s）
  - EpisodeList 自然排序 + 排序按钮
  - CompletenessBar useEffect 依赖数组修复
- Prowlarr 下载链接修复（infoHash 构造磁力 + 代理链接预处理）
- 搜索弹窗固定高度、分季搜索中文数字支持、移除重启后端组件
- 清洗名名称污染防护（finalize 冒泡限制 + 一级分类目录不传播）
- 清洗名自愈机制（parse_legacy_clean_name 接入 + 四层回退 + 垃圾英文名检测 + 持久化）
- 前端 ShadowNameSection 展示 clean_name_en
- 清洗名多瑕疵修复（季范围尾缀/S+数字/TV版/纯数字en/电影文件夹视频补全），详见 `clean-name-fix-todo.md`
- TV文件夹影子名去集号 + split_names 去 en 尾部季集号 + 英文名可编辑（同行布局，独立热区）
- 整理替换三栏统一文件类型标签（视频/字幕/扩展名）
- 搜索 SSE 竞态保护（searchIdRef 防止旧搜索结果混入新搜索）

### 阶段判断

- 整个 stabilization TODO：约 `40%`
- `下载→归位闭环` 这条线：约 `90%-95%`
- 当前状态：已经从“补基础基线”进入“只剩真实环境长尾待证明”

### 当前远端存档点

- 分支：`origin/codex-relocate-baseline-checkpoint`
- 提交：`6195eeb` `测试: 补强下载归位闭环验证`

### 这条主线已完成什么

- 路由层：`dry-run / execute / archive-both / purge-old` 的关键胶水行为已补测试
- `file_relocator`：白名单、冲突探测、`confirm_replace`、`_execute_plan`、`action_plan` 透传、真实 RecycleBin 落盘已补测试
- `download_manager`：
  - 下载完成触发链
  - qB / Alist 边界状态、提交入口、通道推荐、状态管理分支、本地持久化小分支、订阅回调边界、同步/写盘回退、guard/no-op 分支、qB 格式化保底、Alist phase/progress 默认、自动归位补定位回退、submit/状态时间戳、失败态收口与若干长尾状态
  - 启动恢复 / 对账
  - 本地转移 / 同名跳过 / 转移失败
  - 后台局部刷新
  - 任务落盘重载
  - 升级订阅完成态
  - `_auto_relocate` 真实双线程观测
- 小范围业务修复：白名单格式、dry-run fallback、confirm 白名单兜底、执行目录对齐、`action_plan` 透传
- 隔离测试补强：`qB / Alist` 的超时、无效返回结构、提交入口异常、通道推荐阈值、状态管理分支、本地持久化小分支、订阅回调边界、同步/写盘回退、guard/no-op 分支、qB 格式化保底、Alist phase/progress 默认、自动归位补定位回退、submit/状态时间戳、失败态收口已补到 `DownloadManager` 行为保护测试

### 当前剩余风险

- 真实 NAS 上的 `organize execute` 落盘 / 封箱结果仍未证明
- 真实线程下 `confirm_replace + execute` 交叠时序仍未证明
- 真实 qB / Alist 在网络抖动、超时、返回结构变化下的更复杂长尾仍未覆盖
- 媒体库首页首屏耗时已从本地 `8000` 实测约 `22.3s` 降到约 `7.8s`，但仍高于理想值；后续若继续优化，应单独拆媒体库树构建/序列化链路做专项分析
- Windows `.pytest_cache` 权限 warning 仍是既有环境噪声
- 后续影子验证若继续复制真实大视频文件，会再次把工作区体积推高；当前已明确改成“真实文件名/结构 + 占位视频文件”的轻量副本策略

### 下一步建议

1. 不再继续向 TODO 里堆回合日志，只在独立 worklog 记详细过程
2. 若继续补这条线，优先恢复一套“轻量影子副本”验证底座，再做后续 `dry-run / execute` 回归
3. 场景 C 继续推进前，先等或重新制造一笔真实 Alist 活跃样本

---

## 0. 执行红线

- [ ] 每轮只做一种改动：结构收口 / 类型补强 / 测试补强 / 文档补强
- [ ] 当前阶段默认不改业务逻辑
- [ ] 默认不碰高风险链路：naming 规则、search filter/sort、organize executor、file_relocator 冲突探测、TV 映射、下载→归位闭环
- [ ] 前端当前只记录技术债，不改 UI / 样式 / design token
- [ ] 无法证明行为等价时停止修改

---

## 1. 行为基线主任务

> 这里只保留“是否已经形成可用基线”的任务状态，不再堆回合报告。

- [ ] 搜索链路基线
  - 范围：`/api/search/stream`、`/api/search/source`、订阅直搜调用
  - 当前：逻辑层测试已完成，真实 SSE / API 输出快照未补

- [ ] 命名链路基线
  - 范围：文件名解析、clean_name、shadow_name、cn/en/original 写入
  - 当前：clean_name 单元样本已完成，真实媒体库样本快照未补

- [ ] 刮削 / TV 映射基线
  - 范围：候选选择、TV 确权、分集映射、NFO 输出字段
  - 当前：未形成完整基线

- [ ] organize dry-run / execute 基线
  - 范围：wrap、archive、rename、reorganize seasons
  - 当前：dry-run / 路由注册 smoke 有覆盖；真实 execute 与真实 NAS 未补

- [x] 下载 → 归位闭环基线（隔离层）
  - 当前已覆盖：
    - 路由闭环
    - `file_relocator` 冲突探测 / 回收 / confirm / execute
    - `download_manager` 完成触发链 / 下载器状态 / 持久化 / 局部刷新 / 线程观测
    - 回收站默认落盘侧修正：旧资源默认回收到媒体库同卷同级的隐藏目录 `.recycle_bins/<媒体库名>`，backend 仅保留集中元数据
- 当前未证明：
    - 真实 NAS execute
    - 真实线程交叠时序
    - 真实下载器更复杂长尾（已补隔离层超时 / payload 异常，真实环境小样本仍未做）

---

## 2. 低风险结构收口

- [x] 建立基础规则中心 `backend/core/constants.py`
- [x] 规则中心剩余重复点盘点
- [x] `shared.py` 职责盘点
- [x] 路由层重逻辑盘点
- [ ] 只从低风险重复点里挑下一轮候选
  - 当前建议：不要在下载→归位闭环未做真实环境验证前继续动这一块

---

## 3. DTO / 类型补强准入

- [x] DTO 候选清单
- [x] DTO 准入检查
- [x] 第一批低风险 DTO 边界记录
- [ ] 真正落地 DTO 迁移
  - 当前结论：暂缓；这一阶段继续以“盘点/准入”为主，不做全量迁移

---

## 4. 测试与验证债务

### 当前已补到的高风险链路

- [x] `file_relocator` 冲突探测与回收动作
  - 当前：已补 `relocate()` 引擎未就绪 / 下载目录未就绪 / dry-run 空计划，`confirm_replace()` 回收失败即停止，`cancel_replace()` 沙盒回收与缺目录失败，`archive_both()` 空冲突 / 重名封箱，`_recycle_old_files()` 缺旧文件 no-op，`_execute_plan()` 的 `download_dir` fallback 与执行异常返回；已定位并开始收口“真实 execute 后再次 dry-run 仍残留 `Season 01` 目录冲突”的执行链问题
- [x] `routes/relocate.py` 关键闭环路由
  - 当前：已补 task 缺失、顶层目录 / NAS 根目录拦截、archive_both 失败不归档、purge_old 无冲突返回
- [x] `download_manager.py` 完成触发链
- [x] qB / Alist 关键状态映射、提交入口、通道推荐、状态管理分支、本地持久化小分支、订阅回调边界、同步/写盘回退、guard/no-op 分支、qB 格式化保底、Alist phase/progress 默认、自动归位补定位回退、submit/状态时间戳、失败态收口与部分长尾
- [x] 任务持久化重载
- [x] 本地转移 / 局部刷新
- [x] 自动归位真实线程启动观测

### 当前还欠的高风险验证

- [x] 真实 NAS `organize execute` 小样本验证
  - 当前：已用 `1a607cf1` 开证，真实 `dry-run -> execute` 已收口到 `archived`，并写入真实回收记录
- [ ] 真实 `confirm_replace + execute` 交叠时序验证
  - 当前：已用第二个样本 `5ad5b6f9` 复现真实 execute 收口；两笔样本都稳定暴露“执行后再次 dry-run 仍残留 1 个 `Season 01` 目录冲突”，并已进一步定位为 `action_plan` 执行阶段未按 `target_path` 重命名落盘，而是保留了原始发布组文件名
  - 最新补充（2026-04-28）：真实样本 `卡罗尔与星期二 / 军火女王` 又补出第二个执行层遗漏：`action_plan` 之前只会搬“视频同 basename 的字幕/NFO/海报”，不会把白名单里的 `Subs/Fonts` 等附属目录内容一起归到目标季目录，且多季包会把季目录上下文丢掉。本轮已把执行层改成“基于白名单 + plan 季映射”搬运未进 plan 的附属文件：单季包默认并入 `Season 01`，多季包按源季目录归到各自 `Season XX`；隔离测试已补 `single season extras` / `multi season extras` 两个回归样本
- [ ] 真实 qB / Alist 超时 / 重试 / 返回结构异常小样本验证
  - 当前：隔离层的超时 / payload 异常 / 提交入口异常 / 异常吞掉回退已补测试；真实环境已补一轮只读观测：`99c57d47`（qB）在 `sync_progress` 后从 `downloading` 回退到 `unknown`，未误收口到 `completed`；`499b0bd2`（Alist）保持 `unknown + cloud_download`，未误触发归位。已进一步修复 `sync_progress()` 只轮询 `downloading`、导致 `unknown` 永远无法自动恢复的问题，并在独立 `8014` 当前代码实例上实证：
    - `99c57d47 / 156f7e94 / 9e17d995 / 12ac52c5 / c3e3b147` 从 `unknown` 恢复到 `completed`
    - `e1927935 / fa9beea5 / 6500e314` 仍停在 `unknown`，但 `progress/updated_at` 已继续刷新，说明恢复轮询已生效
    - `499b0bd2`（Alist）最初表现为 `unknown + cloud_download`；随后已定位到代码侧根因：当前实例的 AList V3 任务查询接口应走 `GET /api/task/offline_download/undone|done`，旧代码误写成了 `/api/admin/task/...`，因此一直打到前端 HTML。修复后在独立 `8014` 当前代码实例上复测，`499b0bd2` 已从 `unknown` 收口为 `lost + Alist 中未找到对应任务`，说明这笔样本并非“待恢复”，而是旧错误路径掩盖了真实的失联状态；随后又补上了提交链对真实 Alist tid 的保存，并在同步链上改成“有真实 tid 时优先 `POST /api/task/offline_download/info?tid=...`，查不到再回退列表扫描”，避免后续继续退化成 `alist_{task.id}` 伪标识或列表猜名
  - 最新补充（2026-04-28）：真实 qB 还暴露出第二个恢复缺口：`sync_progress()` 虽然已会继续轮询 `unknown` 任务，但 `_sync_qb_progress()` 在查到未完成 torrent（如 `forcedDL` / `missingFiles`）时没有把状态从 `unknown` 收回 `downloading`，导致 `99c57d47 / e1927935 / 6500e314 / fa9beea5` 在现网 `8000` 上只刷新 `updated_at`、不刷新状态。当前工作区代码已修复这个映射，并分别通过“真实 qB hash 只读直调”和“独立 `8015` HTTP 实例下 `POST /download-manager/sync`”两层验证，确认这四笔样本都会恢复成 `downloading`；随后又补造了一笔真实 Alist 活跃样本 `85499bc0 / 5xvyCPXpAe5J9_HTL7Kxb`，定位到 `_sync_alist_progress_by_task_id()` 误把 `info.data` 当列表读取，命中真实任务后会抛异常退回 `unknown`。修复为兼容 dict payload，并在“命中真实未完成任务”时显式收回 `downloading` 后，已在独立 `8018` HTTP 实例上实证：该样本会稳定停在 `downloading + cloud_download + error=http status code 429`，不再误退 `unknown`。进一步只读核对又确认：这笔 `429` 来自上游 Prowlarr 下载链接本身，普通本机 `GET` 同样返回 `Indexer is disabled till 2026/4/28 19:05:12 due to recent failures.`，说明当前剩余问题已从“同步链 bug”切换为“上游 indexer 冷却”。本轮再补一层错误文案收口后，独立 `8019` HTTP 实例上已能直接看到 `error=Prowlarr 429: Indexer is disabled till 2026/4/28 19:05:12 due to recent failures.`，避免面板只暴露裸 `http status code 429`
  - 最新补充（2026-04-28 16:30）：本轮未继续造新任务，只做只读复核。直接核对真实下载器后确认：
    - qB 四笔样本 `99c57d47 / e1927935 / fa9beea5 / 6500e314` 当前在下载器侧仍真实存在，状态分别是 `missingFiles / forcedDL / forcedDL / forcedDL`
    - AList 当前 `undone` 列表为空，`done` 列表里仅剩真实 tid `5xvyCPXpAe5J9_HTL7Kxb`，状态 `state=7 + error=http status code 429`
    - 用当前工作区代码直接跑一轮 `DownloadManager.sync_progress()` 后，qB 四笔样本都会稳定保持 `downloading`，不会再退回 `unknown`
    - 同一轮同步里，`85499bc0` 会保持 `downloading + cloud_download`，且错误文案会从裸 `http status code 429` 升级成 `Prowlarr 429: Indexer is disabled till 2026/4/28 19:05:12 due to recent failures.`
    - 结论：当前剩余阻塞不在代码，而在上游 Prowlarr 冷却窗口；下一步要么等冷却时间过后再对 `85499bc0` 做一次只读复测，要么重新找一笔新的 AList 活跃任务继续场景 C
  - 最新补充（2026-04-28 19:07 后）：到点后继续只读复测发现，这笔样本已经从“待恢复任务”变成“纯上游观察样本”：
    - 本地 `backend/download_tasks.json` 中已不存在任务 `85499bc0`
    - 但 AList `done/info` 里真实 tid `5xvyCPXpAe5J9_HTL7Kxb` 仍存在，状态仍是 `state=7 + error=http status code 429`
    - 从 AList 返回里反解原始 `download_url` 后再次直探，返回的 Prowlarr 冷却时间已顺延到 `2026/4/29 19:07:13`
    - 用当前工作区代码构造同等任务对象重放 `_sync_alist_progress()`，结果仍稳定为 `downloading + cloud_download + Prowlarr 429...`
    - 结论：这笔样本已经完成了代码侧验证价值，当前剩余的是外部 indexer 长时冷却，不再适合作为场景 C 的阻塞样本；后续若还要继续扩 AList 异常覆盖，应等自然出现新的真实活跃样本再增量吸收
- [ ] 必要时补一个“真实环境验证记录”单独文档
  - 当前：已落一版执行清单，见 [download-relocate-real-env-checklist.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-real-env-checklist.md)

---

## 5. 当前执行任务

### 当前 task

- [ ] 整理文档结构：保持 TODO 只做执行面板
- [ ] 若继续推进下载→归位闭环，当前已选“真实环境验证”
- [ ] 按 [download-relocate-real-env-checklist.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-real-env-checklist.md) 依次执行场景 A / B / C
- [x] 先完成“action_plan 按 `target_path` 落盘”的真实样本回归验证
  - 当前：影子副本 `青春之旅` 已先暴露“同一集数被多份源文件同时命中”的执行前冲突；工作区代码补完 `target_path` + 逻辑目标双重前置拦截后，会在离线路由直调与独立 HTTP 端到端验证中于写盘前直接 `400`
- [x] 补齐 `action_plan` 对字幕 / 字体等附属文件的落盘归位
  - 当前：执行层已不再只搬“同 basename sidecar”；现在会结合 `whitelist + mapped season + 源季目录上下文` 一并搬运 `Subs/Fonts` 等附属文件。单季默认归入 `Season 01`，多季按源季目录分别落到 `Season XX`
  - 最新补充（2026-04-29）：进一步修复三个问题：
    1. 字幕文件在子目录（Subs/）中时扁平化到 Season 目录，通过集号匹配用视频标准名重命名
    2. 非字幕附属文件（字体包/SPs/CDs/OAD）提升到剧集根目录，不跟随视频进入 Season
    3. save_path 本身是季目录时不再嵌套 Season XX
  - plan_tree 预览与执行逻辑已对齐；新增 13 个测试覆盖上述场景
    4. 电影类型整理替换完全不工作（_scrape_movie 不支持 dry_run/plan），已补齐
    5. 电影目录被 classify_folder 误判为 collection（种子子目录干扰），已用 category_hint 覆盖
    6. 无冲突但有整理计划时（纯新下载），dry-run 端点也返回 plan 供前端展示
    7. 下载管理面板 UI：去掉待整理 tab、名称截断、已完成增加归档按钮
    8. 搜索 SSE 竞态保护加强：所有 setState 前检查 searchIdRef
    9. 电影分类修复：_classify_movie_category 有散落视频时忽略子目录，不再误判 collection
    10. 种子目录壳清理增强：清理只剩垃圾文件的种子目录
- [x] 按 [download-relocate-shadow-verify-plan.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-shadow-verify-plan.md) 准备影子副本验证，不再直接写正式 NAS
  - 当前：已用 `d673d8fc / 四月是你的谎言` 打通过一次重副本链路；但重视频副本会明显推高工作区体积，当前已清理旧 `shadow-verify`，并将后续策略切换为“真实文件名/目录结构/NFO + 占位视频文件”的轻量副本模式
- [ ] 若继续推进下载→归位闭环，当前已切到“场景 C：真实下载器异常小样本”
  - 当前：已完成一轮只读 `sync_progress` 观测，并修复 `unknown` 任务不会被下一轮同步重新对账的问题；在独立 `8014` 当前代码实例上，真实 qB 样本已证明“异常解除后能恢复收口”；Alist 侧已进一步定位并修复错误的任务查询路径，补上提交链保存真实 tid 的能力，并在同步链上优先按 tid 直查 `task info`，且真实复测已证明 `499b0bd2` 会从旧的 `unknown` 收口为 `lost`。本轮又补上 qB 的 `unknown -> downloading` 恢复映射，当前工作区代码对真实 `forcedDL/missingFiles` hash 已可恢复；下一步应继续找一笔“任务仍存在于 Alist done/undone/info 中”的真实样本，验证它能否恢复到 `downloading/completed`
  - 当前补充：现成样本 `85499bc0 / 5xvyCPXpAe5J9_HTL7Kxb` 仍可作为场景 C 的只读复测对象，但它现在暴露的是上游 `Prowlarr 429` 冷却，不是同步链 bug；优先级应调整为“等冷却窗口结束后复测这笔样本”，只有它彻底失效时才重新造新的 AList 活跃样本
  - 本轮补充（2026-04-28 16:39）：已尝试继续复测，但当前本机时间仍早于 `Prowlarr 429` 文案里的冷却结束点 `2026-04-28 19:05:12`，因此此刻继续打同一条链接不会产生新信号。`85499bc0` 当前任务文件仍保持 `downloading + cloud_download`，错误文案仍是可读的 `Prowlarr 429...`；下一个有效动作仍然是等冷却时间过去后再做只读复测
  - 当前结论更新：`85499bc0` 到点复测后已降级为“纯上游观察样本”，不再适合作为当前阻塞；后续若场景 C 还要继续扩覆盖，只在自然出现新的 AList 活跃样本时再增量吸收
- [ ] 为下一个对话准备轻量影子验证入口
  - 当前：规则和方向已定；下一步应把 `download-relocate-shadow-verify-plan.md` 当作唯一入口，按“只保留真实文件名/目录层级/sidecar，视频主文件用空文件或极小占位文件”重建 `shadow-verify`
- [x] 收口一轮已暴露的主链路前端回归
  - 当前：已修复 `DownloadManagerPanel` 缺少 `archived` tab、归档任务没有稳定“查看”入口、首页对绝对 NAS 路径 `save_path` 无法命中媒体库树的问题；同时把 `/library/tree` 首屏链路从“实时读 NAS 上 NFO”收回到“只用缓存库数据和树内信息推导”，避免再次退化到分钟级
- [x] 补媒体库首页性能专项入口基线
  - 当前：已新增 [library-home-performance-baseline.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/library-home-performance-baseline.md)，记录 `/library` 与 `/library/tree` 的本机粗测、当前链路判断，以及 `/library/tree` 返回结构快照测试入口
  - 最新补充（2026-04-29）：已先压掉五类低风险前端刷新成本；`分类标签 / folder_type` 修改后、`tv/season` 文件夹标准名保存后、`tv/season` 文件夹英文名保存后、文件夹封面上传 / 删除后、以及手动候选确认后，都不再全量双拉 `/library + /library/tree`，而是只刷新目录树；对应组件级测试也已补齐

### 暂停项

- [ ] 暂不切去搜索、命名、刮削链路
- [ ] 暂不做新的结构抽象或模块迁移
- [ ] 除主链路回归修复外，暂不做新的前端 UI 改动

### 参考文档

- 主协议：[optimization-master-plan.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/optimization-master-plan.md)
- 本轮详细工作记录：[download-relocate-worklog.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-worklog.md)
- 真实环境验证清单：[download-relocate-real-env-checklist.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-real-env-checklist.md)
- 项目记忆：[project-memory.md](/C:/Users/shenq/nas-video-upgrader/.kiro/knowledge/project-memory.md)
