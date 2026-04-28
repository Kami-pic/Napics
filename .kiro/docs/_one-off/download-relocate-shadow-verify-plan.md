# [一次性] 下载→归位闭环影子副本验证方案

> 目标：在不碰正式 NAS 本体的前提下，验证新代码下的 `dry-run -> execute` 是否会正确落盘、不会乱名、不会混季。  
> 默认副本根目录：`C:\Users\shenq\nas-video-upgrader\shadow-verify`  
> 当前策略：默认使用“真实文件名 / 目录结构 / sidecar + 占位视频文件”的轻量副本，不再复制大体积真实视频本体

---

## 原则

- 只从正式 NAS 读取，不向正式 NAS 写入
- 每次只复制一个样本目录，不做全库镜像
- 副本验证独立于正式配置，不改现有 `config.json`
- 先保留副本执行前快照，再执行，再对比
- 默认不复制真实大视频文件；视频主文件只保留同名占位文件
- 只有在必须验证真实 I/O、移动耗时、回收站真实落盘时，才单独引入 1 个真实样本

---

## 当前结论

- `军火女王 Jormungand` 的正式样本已经被旧代码写脏，不适合作为“新代码是否修好”的直接验证样本
- 当前最稳妥的验证路径是：
  1. 从正式库复制一个样本目录到本地影子副本
  2. 在副本目录上执行新的 `dry-run -> execute`
  3. 对比副本执行前后目录树
- 2026-04-28 起，副本生成方式切换为：
  1. 保留真实目录层级
  2. 保留真实文件名
  3. 保留 `.nfo` / 海报 / 字幕等 sidecar
  4. 视频主文件改成空文件或极小占位文件

---

## 副本目录约定

- 副本根目录：`C:\Users\shenq\nas-video-upgrader\shadow-verify`
- 每个样本单独一个子目录：
  - `shadow-verify\samples\<sample-name>\source`
  - `shadow-verify\samples\<sample-name>\case`
  - `shadow-verify\samples\<sample-name>\before-tree.txt`
  - `shadow-verify\samples\<sample-name>\after-tree.txt`
- 轻量副本要求：
  - 视频文件名、扩展名保持不变
  - 视频文件内容允许为 `0 byte` 或极小占位内容
  - sidecar 保留真实内容
  - 不再维护 `shadow-verify\library` 这种整棵副本镜像

---

## 推荐样本

优先顺序：

1. 新鲜、未执行过真实 `execute` 的下载样本
2. 能稳定进入 `awaiting_confirm` 的单季样本
3. 避免继续使用已经被旧代码污染过的正式样本目录

---

## 执行步骤

### 1. 复制样本目录到副本

- 输入：
  - 正式库样本目录绝对路径
  - 副本样本名
- 输出：
  - `shadow-verify\samples\<sample-name>\source`
- 复制规则：
  - 视频文件：创建同名占位文件
  - `.nfo` / `.srt` / `.ass` / `.ssa` / 图片文件：保留真实内容
  - 目录层级：与正式样本一致

### 2. 记录执行前快照

- 记录目录树
- 记录视频文件数
- 记录 NFO / 海报 / 字幕文件列表

### 3. 对副本运行 `dry-run`

- 目标：
  - 确认副本也能进入 `awaiting_confirm`
  - 保存 `coexist_pairs / plan / old_tree / plan_tree`

### 4. 对副本运行 `execute`

- 目标：
  - 验证视频主文件是否按 `target_path` 真正落盘
  - 验证 sidecar 是否一起迁移/改名
  - 验证不会把不同季内容混进同一个 `Season 01`
- 注意：
  - 轻量副本只验证命名、路径、sidecar、冲突与动作链
  - 不拿它验证真实 NAS I/O 吞吐或大文件移动耗时

### 5. 记录执行后快照

- 记录 `after-tree.txt`
- 对比执行前后：
  - 视频主文件是否变成标准命名
  - 目录中是否仍残留原始发布组文件名
  - 字幕 / episode.nfo / poster 是否跟随目标文件

---

## 通过判据

- 副本 execute 后目录中不再残留原始发布组视频文件名
- 视频主文件按 `target_path` 落盘
- sidecar 跟随主文件迁移
- 不出现把两季或两段内容混到同一个 `Season 01` 的结果

---

## 失败判据

- 副本中仍出现“原始文件名 + 标准文件名”并存
- 字幕 / NFO / 海报丢失或留在旧位置
- 目录层级错误
- 不同季内容被错误归并

---

## 当前下一步

- 用脚本按“真实名字 + 占位视频文件”重建一个新鲜样本到 `shadow-verify`
- 优先恢复一个能稳定进入 `awaiting_confirm` 的轻量单季样本
- 不对正式 NAS 执行任何新的 `execute`
