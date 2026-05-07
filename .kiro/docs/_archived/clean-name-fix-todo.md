# [废弃] 清洗名修复 + 下载管理问题

> 来源：2026-04-29 用户反馈的清洗名瑕疵和下载管理问题
> 状态：全部完成，季集完整性已拆到 `completeness-todo.md`，技术债务已继承过去

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
| 搜索 SSE 竞态保护 | searchIdRef 防止旧搜索结果混入新搜索，关闭弹窗时递增 ID 丢弃残留消息 | `useSearchState.ts` |

---

## 已拆出：季集缺失信息展示 → `completeness-todo.md`

## 已完成：下载管理问题（Bug 3/4/5）

## 技术债务 → 已继承到 `completeness-todo.md`
