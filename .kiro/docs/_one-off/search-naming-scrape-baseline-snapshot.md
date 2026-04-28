# [一次性] 搜索 / 命名 / 刮削基线快照

> 用途：把 `optimization-stabilization-todo.md` 中仍未划掉的三条“行为基线”压缩成一个可继续执行的快照。  
> 目标：不急着改业务逻辑，先明确“现有证据到哪里了、还差哪一步能收口”。  
> 对应面板：`optimization-stabilization-todo-v2.md`

---

## 1. 搜索链路基线

### 当前已有什么

- 已有多轮搜索能力迭代记录，见：
  - `devlog.md` 中 `2026-04-21`、`2026-04-23` 的搜索相关阶段记录
  - `search-match-filter-research.md`
  - `l1l4-integration-report.md`
- `v1` TODO 已明确：
  - 范围：`/api/search/stream`、`/api/search/source`、订阅直搜调用
  - 当前：逻辑层测试已完成，真实 SSE / API 输出快照未补
- 代码/接口侧已有明确入口：
  - SSE：`/api/search/stream`
  - 单源：`/api/search/source`
  - 前端：`frontend/lib/api.ts`

### 当前缺什么

- 缺一份“真实/准真实输出快照”级别的证据：
  - SSE 事件结构
  - 单源搜索 JSON 结构
  - 订阅直搜调用是否仍走同一编排链

### 建议最小收口

1. 不改搜索逻辑，只补一份接口级快照记录  
2. 记录 SSE 至少一轮事件序列与单源搜索响应结构  
3. 若结构无异常，则把“搜索链路基线”从阻塞态降为观察态

---

## 2. 命名链路基线

### 当前已有什么

- 清洗名系统已经有完整阶段记录，见：
  - `devlog.md` 中 `2026-04-21 清洗名系统重构 + 全链路接入 + 性能优化`
  - `devlog.md` 中 `2026-04-21 英文名缺失修复 + 全场景接入验证`
  - `devlog.md` 中 `2026-04-19 L1-L4 全场景切换 + 名称流转链路治理`
- 现有一次性材料：
  - `name-trust-audit.md`
  - `sandbox-name-report.md`
- `v1` TODO 已明确：
  - 范围：文件名解析、`clean_name`、`shadow_name`、`cn/en/original` 写入
  - 当前：`clean_name` 单元样本已完成，真实媒体库样本快照未补

### 当前缺什么

- 缺一份“当前真实媒体库字段覆盖率/样本快照”的收口摘要
- 不是缺逻辑，而是缺一份能直接回答“现在到底到哪了”的快照

### 建议最小收口

1. 复用现有 `name-trust-audit.md` 与 `sandbox-name-report.md`  
2. 从现有材料提炼一份更短的“当前覆盖率 + 已知残留类型”摘要  
3. 若无新增异常类型，则把“命名链路基线”改为“已有快照，后续只增量观察”

---

## 3. 刮削 / TV 映射基线

### 当前已有什么

- 设计与知识材料：
  - `organize-pipeline-v3.md`
  - `media-organize-architecture.md`
  - `business-skills-plan.md` 中 S10
- `v1` TODO 已明确：
  - 范围：候选选择、TV 确权、分集映射、NFO 输出字段
  - 当前：未形成完整基线

### 当前缺什么

- 这三条基线里，它是目前最弱的一条
- 缺的不是零散笔记，而是：
  - 一份典型 TV 样本的确权结果
  - 一份分集映射输出摘要
  - 一份 NFO 字段级检查结果

### 建议最小收口

1. 暂不碰实现，不做 TV 映射逻辑修改  
2. 只挑 1 个已有材料最全的 TV 样本，补一份“输入 → `tmdb_match` → 映射 → NFO 字段”的快照  
3. 这条做完，才能决定它是继续收口，还是降级为观察项

---

## 4. 优先级判断

### 最高优先

- 命名链路基线
  - 原因：现有证据最多，最容易先收口
  - 风险：低，不必碰业务逻辑

### 次优先

- 搜索链路基线
  - 原因：接口入口清晰，但需要一次输出快照采样
  - 风险：低到中，主要是跑接口和整理结果

### 暂排最后

- 刮削 / TV 映射基线
  - 原因：现有证据最散，最容易拖成新一轮深挖
  - 风险：中，必须严守“不改逻辑，只补快照”

---

## 5. 下一步建议

按下面顺序继续最稳：

1. 先做命名链路基线摘要  
2. 再做搜索链路接口级快照  
3. 最后补 1 个 TV 样本级快照，决定是否继续深挖

---

## 6. 2026-04-28 收口快照

### 6.1 命名链路

- 本轮没有改命名逻辑，只把现有证据压缩成可用结论：
  - [name-trust-audit.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/name-trust-audit.md)
    - `backend/media_library.json` 共 `3302` 条记录
    - `clean_name` 覆盖 `3301/3302`，约 `99%`
    - 当前质量问题 `386` 条，主类型是：
      - 纯数字集标题
      - 纯 `S01E01` 这类格式串
      - 少量技术标签残留（如 `AAC`）
  - [sandbox-name-report.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/sandbox-name-report.md)
    - `backend/sandbox_real/` 共 `3215` 个视频样本
    - 当前质量问题 `894` 条
    - 主体仍集中在历史原始番剧/分集命名，不是新近结构化字段回退
- 当前结论：
  - 这条链路当前不是“字段没落盘”，而是“历史脏样本仍有尾巴”
  - `clean_name` 覆盖率已经足够支撑用户路径；剩余问题以增量治理为主
  - 因此“命名链路基线”本轮可视为已补快照，后续转观察

### 6.2 搜索链路

- 本轮补的是“接口级准真实快照”，不碰外部搜索站：
  - 新增 `backend/test_search_route_snapshots.py`
    - 固定 `/api/search/source` 返回体结构：`source/results/count/search_keywords/hit_keyword`
    - 固定 SSE `/api/search/stream` 至少一轮 `source_start -> source_done` 事件结构，重点校验 `search_keywords` 和 `hit_keyword`
  - 新增 `backend/test_searcher.py`
    - 固定 Prowlarr 下载链接归一化优先级：
      - `infoHash` 优先构造标准磁链
      - 否则优先真实 `magnetUrl`
- 当前结论：
  - 搜索链路现在已有“路由返回形状 + Prowlarr 下载链接选择”的自动化快照
  - 本轮收口的是接口结构，不是外站可用性；外站波动仍按观察项处理

### 6.3 刮削 / TV 映射链路

- 本轮补的是 1 个代表性 TV 样本快照：
  - 扩充 `backend/test_scraper_tv_dry_run_actions.py`
  - 样本：`四月是你的谎言 / Season 01 / S01E01`
  - 已固定的链路点：
    - `tvshow.nfo` 可读出 `tmdb_id=61663` 和 `english_title=Your Lie in April`
    - 单集 `.nfo` 可读出 `showtitle/season/episode`
    - `_scrape_tv_v3(..., dry_run=True)` 返回：
      - `tmdb_match.tmdb_id=61663`
      - `tmdb_match.match_source=existing_nfo`
      - `summary.will_process=0`
      - `actions=["write_shadow"]`
- 当前结论：
  - 这条链路至少已有 1 个“existing_nfo -> TV 确权 -> 单集映射 -> NFO 字段”闭环样本
  - 还不能代表所有 TV 长尾，但已足够作为当前 `v2` 的基线快照入口

### 6.4 本轮验证

- 定向后端验证：
  - `python -X utf8 -m pytest backend/test_searcher.py backend/test_search_route_snapshots.py backend/test_download_manager_relocate_flow.py -k "push_to_qb or search_single_source_snapshot or search_stream_snapshot or prowlarr_search"`
  - 结果：`9 passed`
- 基线相关补充验证：
  - `python -X utf8 -m pytest backend/test_searcher.py backend/test_search_route_snapshots.py backend/test_scraper_tv_dry_run_actions.py backend/test_multilang_search.py backend/test_clean_name_system.py backend/test_download_manager_relocate_flow.py`
  - 结果：`230 passed`
- 前端构建验证：
  - `cd frontend && npm run build`
  - 结果：通过
- 当前未收口的验证阻塞：
  - `cd frontend && npm run test`
    - 结果：`9 failed / 108`
    - 失败集中在既有 `split-components` / `subscribe-*` 测试，不在本轮改动范围
  - `cd backend && python -X utf8 -m pytest .`
    - 结果：收集阶段被既有脚本式测试阻塞
    - 当前可见阻塞文件包含：
      - `test_bt_expand.py`
      - `test_detail_drawer_split.py`
      - `test_detail_e2e.py`
      - `test_detail_operations.py`
      - `test_discover_api.py`
      - 以及其他在模块导入阶段直接 `sys.exit(...)` 的历史脚本

### 6.5 收口判断

- 命名链路基线：可从“未补快照”降为“已有快照，转观察”
- 搜索链路基线：可从“未补输出快照”降为“接口级快照已补，转观察”
- 刮削 / TV 映射基线：已建立 1 个代表样本快照；后续只在出现新的 TV 长尾时再扩样本
- 当前遗留：
  - 本轮目标已完成
  - 但“完整测试全绿”仍受既有前端断言和后端脚本式测试文件阻塞，需单独开验证治理回合
