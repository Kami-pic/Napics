# [TODO] 清洗名修复 + 下载管理问题

> 来源：2026-04-29 用户反馈的清洗名瑕疵和下载管理问题
> 状态：清洗名修复已完成，下载管理问题待新对话处理

---

## 已完成：清洗名修复（2026-04-29）

### 修复的 Bug

| Bug | 根因 | 修复 | 文件 |
|-----|------|------|------|
| `冰与火之歌1-8季` → `18季` | strip_noise 把 `-` 替换空格后数字合并 | strip_noise 新增步骤 0a：去除季范围尾缀 | `clean_name_system.py` |
| `火线16季` → `火线16季` | 紧跟中文的 `数字+季` 没被清理 | strip_noise 增加 `(?<=CJK)\d{1,2}季$` 清理 | `clean_name_system.py` |
| `守望尘世S1` → `守望尘世S` | split_by_language 把 S 归入 cn | strip_noise 去除尾部 `S\d*$`（紧跟中文时） | `clean_name_system.py` |
| `方子传TV版` → en 异常 | TV版 紧跟中文名时未被清理 | strip_noise 步骤 7 改为也去紧跟中文的 TV版 | `clean_name_system.py` |
| `better call saul s5` → `s 5` | split_by_language 把 s 和 5 拆成独立 token | token 化正则增加 S/E+数字 整体模式 | `text_processing.py` |
| 电影文件夹搜索词带"电影" | cnName 回退到 node.name（一级分类目录名） | 前端回退时过滤一级分类目录名 | `FolderDetail.tsx` / `VideoDetail.tsx` |
| `我的阿勒泰 2160p` → en=`02` | 文件名 `02.xxx.mkv` 清洗后纯数字被写入 en | clean_from_filename 纯数字 en 清空 + 冒泡垃圾检测 | `clean_name_system.py` / `library.py` |
| 电影文件夹下视频缺清洗名 | post_process 只处理 tv/season，遗漏 movie | 条件增加 movie 类型 | `library.py` |

### 改动文件清单

- `backend/clean_name_system.py` — strip_noise 增强（季范围/尾部季号/TV版）+ clean_from_filename 纯数字 en 过滤
- `backend/text_processing.py` — split_by_language 季集号 token 保护
- `backend/routes/library.py` — post_process 增加 movie + 自愈层2 冒泡垃圾检测
- `frontend/components/detail/FolderDetail.tsx` — 搜索词回退过滤一级分类目录名
- `frontend/components/detail/VideoDetail.tsx` — 同上

### 验证

- 后端：90 个现有测试 + 18 个相关测试全部通过，零回归
- 前端：构建通过，getDiagnostics 无错误

---

## 已完成：补充修复（2026-04-29 下午）

### 修复的 Bug

| Bug | 根因 | 修复 | 文件 |
|-----|------|------|------|
| TV 文件夹影子名带集号（`冰菓 Hyouka S01E01`） | shadow_name 从子视频冒泡时没去掉尾部季集号 | 冒泡时用正则去除尾部 S01E01/S01/E03 | `library.py` |
| `clean_name_en` 含季集号（`Hyouka S01E01`） | split_names 没去 en 尾部季集号 | split_names 返回前去除 en 尾部 SxxExx/Sxx/Exx | `clean_name_system.py` |

### 新增功能

| 功能 | 说明 | 文件 |
|------|------|------|
| 英文名可编辑 | ShadowNameSection 清洗名行同行布局，中文名和英文名各自独立编辑热区 | `ShadowNameSection.tsx` / `library.py` |
| 后端 clean_name_en 保存 | `/library/clean-name` 端点扩展支持 `clean_name_en` 字段 | `library.py` |
| 整理替换三栏文件类型标签 | plan 栏和 old 栏补上文件类型标签（视频/字幕/扩展名） | `FileTreeNode.tsx` |

---

## 待处理：季集缺失信息展示（新对话）

> 用户需求：从刮削源获取剧集有多少季、每季多少集，对比本地已有的，展示缺失信息

### 设计方向

- 数据源：TMDB API（`/tv/{id}` 返回 seasons 列表，`/tv/{id}/season/{n}` 返回 episodes 列表）
- 对比逻辑：TMDB 总集数 vs 本地已有集数（从树结构中统计）
- 展示位置：FolderDetail 面板中，tv 类型文件夹显示季集完整度
- 示例：`better call saul` → TMDB 6 季，本地有 S1-S5 → 显示"缺 S6"
- 集级别：`纸牌屋 S3` → TMDB 13 集，本地有 12 集 → 显示"缺 E07"

### 实现步骤（预估）

1. 后端：新增 `/library/completeness` 端点，接收 tmdb_id + folder_path，返回季集完整度
2. 后端：从 TMDB 获取总季集数，从树结构统计本地已有集数，计算差集
3. 前端：FolderDetail 中 tv 类型显示完整度标签（如 "S1-S5 / 6季" + 缺失标记）
4. 缓存：TMDB 季集数据缓存到 scrape_cache，避免重复请求

---

## 待处理：下载管理问题（新对话）

### Bug 3：自动同步没触发

- **根因**：后端没有定时调用 `sync_progress` 的后台线程。只有前端请求 `/download-manager/active` 或手动点击 `/download-manager/sync` 时才同步
- **修复方向**：在 `main.py` 的 `startup_event` 中启动一个后台线程，每 10-15 秒调用一次 `sync_progress`
- **注意**：需要处理线程安全（已有 `_lock`）和优雅关闭

### Bug 4：已完成和待整理重复

- **现状**：`completed`（已完成）和 `awaiting_confirm`（待整理）在前端是两个独立的筛选 Tab
- **用户反馈**：从用户角度看两者都是"下载完了等我处理"，保留一个即可
- **修复方向**：前端合并为一个 Tab（如"已完成"），内部用标签区分是否需要确认替换
- **涉及文件**：`frontend/components/download/DownloadManagerPanel.tsx`

### Bug 5：删除的失败任务重启后又出现

- **根因**：`sync_from_qb` 步骤 3 会把 qB 中所有种子导入为新任务。用户在 download_tasks.json 中删除了记录，但 qB 中的种子还在，下次 sync 时又被导入
- **修复方向**：维护一个"已删除 hash 黑名单"（如 `deleted_hashes.json`），sync_from_qb 导入时跳过黑名单中的 hash。或者在 delete_task 时同时从 qB 中删除种子（需用户确认）
- **关联**：与 Bug 3 有关——如果自动同步触发了 sync_from_qb，删除的任务会更频繁地复活
- **涉及文件**：`backend/download_manager.py`、`backend/routes/download.py`

---

## 技术债务

- `media_library.json` 中已有的脏数据（如 `clean_name_en: "02"`）需要一次性清洗脚本修复
- `1984` 等纯数字作品名在 strip_noise 步骤 13 中被误删（尾部纯数字集号清理），暂不处理
