# [TODO] 项目整体优化 — 收口校准阶段任务清单

> 当前阶段：功能已基本完成，优先证明主链路没有被破坏。  
> 执行原则：只做低风险收口与验证底座，不做功能扩展，不做架构升级。  
> 来源：`optimization-master-plan.md` 的“当前阶段覆盖协议”。

---

## 当前总览（2026-04-24）

### 当前主线

- 当前正在收口的主线：`下载完成 → 本地转移 → 局部刷新 → 自动归位 → confirm/execute → 回收站/持久化`
- 当前策略：暂停继续扩测试面，先把 TODO 收回成可执行清单；详细回合记录已迁到 [download-relocate-worklog.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-worklog.md)

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
  - qB / Alist 边界状态、提交入口、通道推荐、状态管理分支、本地持久化小分支、订阅回调边界、同步/写盘回退、guard/no-op 分支、qB 格式化保底、Alist phase/progress 默认与若干长尾状态
  - 启动恢复 / 对账
  - 本地转移 / 同名跳过 / 转移失败
  - 后台局部刷新
  - 任务落盘重载
  - 升级订阅完成态
  - `_auto_relocate` 真实双线程观测
- 小范围业务修复：白名单格式、dry-run fallback、confirm 白名单兜底、执行目录对齐、`action_plan` 透传
- 隔离测试补强：`qB / Alist` 的超时、无效返回结构、提交入口异常、通道推荐阈值、状态管理分支、本地持久化小分支、订阅回调边界、同步/写盘回退、guard/no-op 分支、qB 格式化保底、Alist phase/progress 默认已补到 `DownloadManager` 行为保护测试

### 当前剩余风险

- 真实 NAS 上的 `organize execute` 落盘 / 封箱结果仍未证明
- 真实线程下 `confirm_replace + execute` 交叠时序仍未证明
- 真实 qB / Alist 在网络抖动、超时、返回结构变化下的更复杂长尾仍未覆盖
- Windows `.pytest_cache` 权限 warning 仍是既有环境噪声

### 下一步建议

1. 不再继续向 TODO 里堆回合日志，只在独立 worklog 记详细过程
2. 若继续补这条线，优先做“真实 NAS execute 小样本验证”
3. 若暂不碰真实 NAS，就只补“真实下载器异常返回 / 超时 / 重试”这一类隔离测试

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
- [x] `routes/relocate.py` 关键闭环路由
- [x] `download_manager.py` 完成触发链
- [x] qB / Alist 关键状态映射、提交入口、通道推荐、状态管理分支、本地持久化小分支、订阅回调边界、同步/写盘回退、guard/no-op 分支、qB 格式化保底、Alist phase/progress 默认与部分长尾
- [x] 任务持久化重载
- [x] 本地转移 / 局部刷新
- [x] 自动归位真实线程启动观测

### 当前还欠的高风险验证

- [ ] 真实 NAS `organize execute` 小样本验证
- [ ] 真实 `confirm_replace + execute` 交叠时序验证
- [ ] 真实 qB / Alist 超时 / 重试 / 返回结构异常小样本验证
  - 当前：隔离层的超时 / payload 异常 / 提交入口异常已补测试，真实下载器小样本仍未验证
- [ ] 必要时补一个“真实环境验证记录”单独文档

---

## 5. 当前执行任务

### 当前 task

- [ ] 整理文档结构：保持 TODO 只做执行面板
- [ ] 若继续推进下载→归位闭环，优先在“真实环境验证”与“真实下载器长尾”里二选一

### 暂停项

- [ ] 暂不切去搜索、命名、刮削链路
- [ ] 暂不做新的结构抽象或模块迁移
- [ ] 暂不做前端 UI 改动

### 参考文档

- 主协议：[optimization-master-plan.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/optimization-master-plan.md)
- 本轮详细工作记录：[download-relocate-worklog.md](/C:/Users/shenq/nas-video-upgrader/.kiro/docs/_one-off/download-relocate-worklog.md)
- 项目记忆：[project-memory.md](/C:/Users/shenq/nas-video-upgrader/.kiro/knowledge/project-memory.md)
