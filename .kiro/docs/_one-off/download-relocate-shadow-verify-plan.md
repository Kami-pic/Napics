# [一次性] 下载→归位闭环影子副本验证方案

> 目标：在不碰正式 NAS 本体的前提下，验证新代码下的 `dry-run -> execute` 是否会正确落盘、不会乱名、不会混季。  
> 默认副本根目录：`C:\Users\shenq\nas-video-upgrader\shadow-verify`

---

## 原则

- 只从正式 NAS 读取，不向正式 NAS 写入
- 每次只复制一个样本目录，不做全库镜像
- 副本验证独立于正式配置，不改现有 `config.json`
- 先保留副本执行前快照，再执行，再对比

---

## 当前结论

- `军火女王 Jormungand` 的正式样本已经被旧代码写脏，不适合作为“新代码是否修好”的直接验证样本
- 当前最稳妥的验证路径是：
  1. 从正式库复制一个样本目录到本地影子副本
  2. 在副本目录上执行新的 `dry-run -> execute`
  3. 对比副本执行前后目录树

---

## 副本目录约定

- 副本根目录：`C:\Users\shenq\nas-video-upgrader\shadow-verify`
- 每个样本单独一个子目录：
  - `shadow-verify\samples\<sample-name>\source`
  - `shadow-verify\samples\<sample-name>\before-tree.txt`
  - `shadow-verify\samples\<sample-name>\after-tree.txt`

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

- 用脚本先复制一个新鲜样本目录到 `shadow-verify`
- 不对正式 NAS 执行任何新的 `execute`
