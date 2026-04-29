# [一次性] 媒体库首页性能专项基线

> 对应执行面板：`optimization-stabilization-todo-v2.md`  
> 目标：先明确“首页首屏现在慢在哪、还值不值得继续压”，不直接扩成一轮大改。

---

## 1. 背景

- 已有历史记录：
  - 首页 `/library/tree` 首屏链路曾在本地 `8000` 退化到约 `22.3s`
  - 通过“首屏不再实时读 NAS NFO，只用缓存库数据和树内子节点补齐 `clean_name_*`”后，已降到约 `7.8s`
- 当前 `v2` 定位：
  - `媒体库首页性能继续优化` 已转为观察项
  - 本轮不碰搜索 / 刮削 / DTO 迁移，只给性能专项补入口基线

---

## 2. 当前链路

### 后端

- 首页首屏当前会打两条接口：
  - `GET /library`
  - `GET /library/tree`
- 其中 `/library/tree` 负责：
  - 基于 `media_library.json` 构造目录树
  - 从树结构推断 `folder_type`
  - 用缓存库数据和子树信息补齐 `clean_name_cn/en/original`
- 关键保护已存在：
  - [test_library_tree.py](/C:/Users/shenq/nas-video-upgrader/backend/test_library_tree.py) 已固定“首屏链路不读实时 NFO”

### 前端

- `useLibrary.refreshLibrary()` 和初始化加载都会并行请求：
  - `api.getLibrary()`
  - `api.getLibraryTree()`
- 首页卡顿如果再出现，优先看三段：
  - `/library/tree` 后端构树
  - `/library` 全量视频列表返回
  - 前端双请求完成后的状态刷新

---

## 3. 本轮实测

> 环境：本机现有 `http://127.0.0.1:8000`

- `GET /library/tree`
  - 本轮粗测：约 `910ms`
- `GET /library`
  - 本轮粗测：约 `305ms`

### 当前判断

- 现网本机当前已不在 `7.8s` 档位，更不在 `22.3s` 档位
- 说明上一轮主链修复已经把“明显阻塞”去掉了
- 当前剩余若还有用户体感慢，更可能来自：
  - 首次冷启动波动
  - 前端同时等待两条接口
  - 首页根目录下卡片/详情联动的额外状态刷新

---

## 4. 当前不建议做的事

- 不建议现在回到 NAS 实时 NFO / 文件系统探测
- 不建议为了“可能更快”重写 `library/tree` 数据结构
- 不建议把本轮扩成前后端联动重构

---

## 5. 下一步最小候选

### 候选 A：补首页接口快照 + 计时测试

- 做法：
  - 固定 `/library/tree` 返回形状
  - 补一个只读计时脚本或专项记录
- 优点：
  - 风险最低
  - 方便后续判定是不是又出现性能回退
- 缺点：
  - 只能监控，不能直接继续提速

### 候选 B：压前端双请求刷新成本

- 做法：
  - 盘点 `useLibrary.refreshLibrary()` 是否存在不必要的全量双拉
  - 只在必要入口刷新 `/library/tree`
- 优点：
  - 更可能直接改善首页体感
- 缺点：
  - 会开始碰前端数据流，超出“纯基线”边界

### 当前推荐

- 先做候选 A
- 理由：
  - 当前本机接口耗时已经回到秒内
  - 还没形成“必须立刻继续改代码”的证据
  - 下一轮如果用户仍感知首页慢，再切候选 B 更稳

---

## 6. 当前已补入口

- 已补首页树结构快照测试：
  - [test_library_route_snapshot.py](/C:/Users/shenq/nas-video-upgrader/backend/test_library_route_snapshot.py)
  - 作用：
    - 固定 `/library/tree` 顶层和核心子节点字段形状
    - 后续若为了性能再压树构建，可以先看是不是把前端依赖字段改坏了
- 现在这条专项的最小入口已经具备：
  - 1 条“不读实时 NFO”的保护测试
  - 1 条“返回结构稳定”的快照测试
  - 1 份本机现网粗测记录
