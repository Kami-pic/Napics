# [TODO] 项目整体优化 — 收口执行面板 V2

> 这是 `optimization-stabilization-todo.md` 的 `v2` 执行面板。  
> `v1` 保留作完整历史清单，不删除、不覆盖。  
> 当前目标：加快收口，但不降低主链路验证标准。  
> 当前策略：只保留“会影响用户路径判断”的阻塞项；其余转为观察项或已知风险。

---

## 当前 task

- 本轮目标：把“媒体库首页性能继续优化”从观察项拉成专项入口基线
- 本轮只做：性能基线记录 + 下一步切点判断
- 本轮不碰：
  - 搜索 / 命名 / 刮削链路业务逻辑
  - 新结构抽象 / DTO 迁移
  - 正式 NAS 写盘链路
  - 以“可能更快”为由的首页大改

---

## 进度重估（V2 口径）

- `v1` 的 `40%` 已失真，不再作为执行指标
- 按“用户主链路可用性”重估：
  - 整个 stabilization 收口：约 `80%-85%`
  - `下载→归位闭环`：约 `92%-95%`
- 当前判断：
  - 主链路阻塞项已经收口完成
  - 当前剩余内容以观察项和后续专项为主

---

## 已开证主链路

- [x] 下载提交
  - qB / Alist 提交入口、失败态、状态落盘、真实 tid/hash 持久化已覆盖
- [x] 下载进度同步
  - qB `unknown -> downloading/completed` 恢复映射已用真实样本开证
  - Alist `task info / done / undone` 三条链已对齐 AList V3
- [x] 自动归位 / confirm / execute
  - `1a607cf1`、`5ad5b6f9` 两个真实样本已证明 `dry-run -> execute -> archived`
  - `action_plan` 目标落盘与 `Subs/Fonts` 等附属资源跟随归位已补隔离回归
- [x] 前端主入口回归
  - `archived` tab、查看入口、绝对 NAS 路径命中、首页媒体库树性能回归已收口

---

## 与 V1 的未完成项映射

> 这一段是对 `v1` 未完成项的完整映射。  
> `v2` 不再省略未完成项，只改变它们的优先级和阻塞级别。

### A. 当前阻塞项

#### A1. 场景 C 最后一笔真实 AList 复测

- [x] 复测样本：`85499bc0 / 5xvyCPXpAe5J9_HTL7Kxb`
- 当前状态：
  - 本地 `download_tasks.json` 中已不存在任务 `85499bc0`
  - AList `done/info` 中真实 tid `5xvyCPXpAe5J9_HTL7Kxb` 仍存在，状态 `state=7 + error=http status code 429`
  - 从 AList 返回里反解原始 `download_url` 后再次只读探测，返回 `Prowlarr 429`，且冷却已顺延到 `2026-04-29 19:07:13`
  - 用当前工作区代码构造同等任务对象重放 `_sync_alist_progress()`，结果仍稳定为 `downloading + cloud_download + Prowlarr 429...`
- 当前判断：
  - 这笔样本已经完成了它能提供的代码侧验证价值
  - 现在剩下的是上游长期冷却，不再是同步链阻塞
  - 因此这笔样本从“阻塞项”降为“观察项”
- 结论：
  - 当前代码已证明能正确表达“真实 AList 任务存在，但上游下载链接长期 429”
  - 不再对这笔样本做日常重复复测
  - 后续若要继续扩场景 C，只在自然出现新的真实 AList 活跃样本时再增量吸收

#### A2. 轻量影子验证入口是否继续保留

- [x] 决定是否把“轻量影子副本验证”保留为下阶段入口
- 当前判断：
  - 下载→归位主链已经有真实样本开证
  - 影子验证不再是当前阻塞
- 已定处理：
  - 当前阶段默认不重建 `shadow-verify`
  - 仅在后续再出现 execute / dry-run 回归，且真实 NAS 不适合直接复现时，再启用轻量影子副本
  - 这一项从阻塞项移出，转为执行策略约定

- [x] 当前已无继续阻塞 `v2` 收口的主链路问题
  - 下一步不再围绕同一批样本重复验证，而是转去更高价值的后续项

### B. 非阻塞未完成项

- [x] 搜索链路基线
  - 来源：`v1`
  - 范围：`/api/search/stream`、`/api/search/source`、订阅直搜调用
  - 当前：
    - 逻辑层测试已完成
    - 本轮已补接口级准真实快照：
      - `backend/test_search_route_snapshots.py` 固定 `/api/search/source` 返回结构
      - 同文件固定 SSE `source_start/source_done` 事件结构，校验 `search_keywords/hit_keyword`
  - 在 `v2` 的定位：当前小闭环已收口；后续只观察真实外站波动

- [x] 命名链路基线
  - 来源：`v1`
  - 范围：文件名解析、`clean_name`、`shadow_name`、`cn/en/original` 写入
  - 当前：
    - `clean_name` 单元样本已完成
    - 本轮已把现有审计材料压缩成基线摘要：
      - `backend/media_library.json`：`clean_name` 覆盖 `3301/3302`
      - `backend/sandbox_real/`：样本 `3215`，残留问题集中在历史脏命名尾部
  - 在 `v2` 的定位：当前小闭环已收口；后续只做增量观察

- [x] 刮削 / TV 映射基线
  - 来源：`v1`
  - 范围：候选选择、TV 确权、分集映射、NFO 输出字段
  - 当前：
    - 本轮已补 1 个代表性 TV 样本快照：
      - `backend/test_scraper_tv_dry_run_actions.py` 固定 `existing_nfo -> tmdb_match -> NFO 字段 -> dry-run summary`
      - 样本结论：`tmdb_match.match_source=existing_nfo`、`summary.will_process=0`
  - 在 `v2` 的定位：当前入口快照已建立；后续只在 TV 长尾样本出现时再扩覆盖

- [ ] organize dry-run / execute 基线
  - 来源：`v1`
  - 范围：wrap、archive、rename、reorganize seasons
  - 当前：`dry-run` / 路由注册 smoke 有覆盖；真实 execute 与真实 NAS 未补成独立“基线快照”
  - 在 `v2` 的定位：未完成，但与下载→归位 execute 主链已有交叉开证；后续需要补一份独立基线摘要

- [ ] 只从低风险重复点里挑下一轮候选
  - 来源：`v1`
  - 当前结论仍是：在更高优先级基线项未收口前，继续暂缓

- [ ] 真正落地 DTO 迁移
  - 来源：`v1`
  - 当前结论仍是：暂缓；继续以盘点/准入为主，不做全量迁移

### C. 高风险未完成项

- [ ] 真实 `confirm_replace + execute` 交叠时序验证
  - 来源：`v1`
  - 当前：已有两笔真实样本未出现状态回跳，但还没有把这项正式打成“完成”
  - 在 `v2` 的定位：高风险未完成项，先降为观察，不与当前基线快照混跑

- [ ] 更大覆盖面的真实 qB / Alist 异常样本
  - 来源：`v1`
  - 当前：同步链已开证，但更复杂真实长尾仍可继续扩样本
  - 在 `v2` 的定位：高风险未完成项，后续只自然吸收，不再为了清单主动造回合

- [ ] 必要时补一个“真实环境验证记录”单独文档
  - 来源：`v1`
  - 当前：已有 [download-relocate-real-env-checklist.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-real-env-checklist.md)
  - 在 `v2` 的定位：未完成表述保留，但优先级低；除非要交付对外证据链，否则不单独扩写

---

## 观察项（不再阻塞 V2）

- [ ] `confirm_replace + execute` 更复杂交叠时序
  - 当前已有两笔真实样本未出现状态回跳；剩余属于长尾观察
- [ ] 更大覆盖面的 qB / Alist 异常样本
  - 当前同步链已开证；后续继续遇到真实样本时再增量吸收
- [ ] `5xvyCPXpAe5J9_HTL7Kxb` 上游 Prowlarr 冷却
  - 当前已确认为外部 indexer 冷却顺延到 `2026-04-29 19:07:13`，不再作为当前代码收口阻塞
- [ ] 媒体库首页性能继续优化
  - 当前 `22.3s -> 7.8s` 已脱离分钟级阻塞，后续另开专项
- [ ] `.pytest_cache` 权限 warning
  - 既有环境噪声，不作为当前收口阻塞
- [ ] 既有测试基建噪声
  - 前端 `vitest` 当前有 `9` 条历史失败，集中在 `split-components` / `subscribe-*`
  - 后端完整 `pytest .` 会被一批导入即 `sys.exit(...)` 的脚本式测试阻塞
  - 当前不把它们混入“搜索 / 命名 / 刮削基线”逻辑回合，后续单独治理

---

## 本轮执行顺序

1. `v2` 面板生效，只按本文件推进  
   验证：`v2` 已明确区分阻塞项 / 观察项 / 已开证项

2. 到点后复测 `85499bc0`  
   验证：已完成；样本已从阻塞项降为观察项

3. 根据复测结果决定这条主线是否可以标为“收口完成，转观察”  
  验证：当前样本结论已稳定，场景 C 已从阻塞项移出

4. 明确下一个小闭环候选  
   验证：后续自动推进不再回到下载→归位主线重复验证

5. 补齐搜索 / 命名 / 刮削基线快照  
   验证：
   - `search-naming-scrape-baseline-snapshot.md` 已形成结论摘要
   - 搜索路由快照与 TV 样本快照测试可通过

---

## 下一个候选闭环

- 候选 1：搜索 / 命名 / 刮削基线补快照
  - 原因：这些项在 `v1` 里长期挂着，但不再适合与下载主线混跑
  - 边界：优先文档/基线，不贸然碰业务逻辑
- 候选 2：媒体库首页性能专项
  - 原因：当前已有明确用户可见收益，且仍有进一步优化空间
  - 边界：先做基线与收口策略，不直接扩成大范围重构
- 当前推荐：
  - 候选 1 已完成当前轮收口
  - 当前下一步切到候选 2 更合理
  - 原因：搜索 / 命名 / 刮削三条基线都已补到“有入口快照、可继续观察”的程度
  - 当前入口文档：[search-naming-scrape-baseline-snapshot.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/search-naming-scrape-baseline-snapshot.md)
  - 当前专项入口文档：[library-home-performance-baseline.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/library-home-performance-baseline.md)
  - 当前已补首页树结构快照测试；本轮继续补了两条低风险前端优化：
    - `分类标签 / folder_type` 修改后只刷新 `/library/tree`
    - `tv/season` 文件夹标准名保存后只刷新 `/library/tree`
    - `FolderDetail` 文件夹封面上传 / 删除后只刷新 `/library/tree`
  - 其余更重的刷新入口暂不混改；后续若继续压性能，仍优先围绕 `useLibrary` 双请求刷新成本展开

---

## 参考文档

- `v1` 原始清单：[optimization-stabilization-todo.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/optimization-stabilization-todo.md)
- 主协议：[optimization-master-plan.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/optimization-master-plan.md)
- 工作记录：[download-relocate-worklog.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-worklog.md)
- 真实环境清单：[download-relocate-real-env-checklist.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-real-env-checklist.md)
