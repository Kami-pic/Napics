---
name: library-scan-tree
description: >
  媒体库扫描与树构建：扫描视频文件 + 抽取元数据 + 构建目录树 + 分类标签 + 增量同步。
  Use when modifying scan/sync logic, tree building (finalize/post_process),
  or debugging "clean_name shows 未设置" issues.
---

# S8 媒体库扫描与树构建

> 扫描是媒体库的入口，树构建是所有 UI 展示的基础。

## 扫描流程（scanner.py + routes/library.py）

```
用户点击扫描 → GET /scan?path=xxx（SSE 流式）
  → 遍历 NAS 目录，找到所有视频文件
  → 对每个视频：ffprobe 提取元数据（分辨率/编码/音频/字幕/HDR/时长）
  → 写入 media_library.json
  → SSE 推送进度
```

**快速同步**（GET /quick-sync）：
- 只扫描新增/删除的文件（对比 media_library.json 和磁盘）
- 新增超过 50 个文件时自动切换快速模式（跳过 ffprobe）
- ffprobe 必须设 timeout=15，长队列加 try-except 兜底

## 树构建（get_library_tree）

```
media_library.json → 构建目录树
  → finalize 阶段：
    ├── 文件夹节点 → clean_for_folder(folder_name, shadow_name, folder_type)
    ├── 如果 en/original 为空且有 NFO → 从 NFO 补全（exists 预检避免无用 IO）
    └── 分类标签注入（category_tag: movie/tv）
  → post_process 阶段：
    ├── season 子文件夹 → clean_for_folder(parent_cn=父级cn, folder_type="season")
    ├── 视频节点 → clean_from_filename(parent_cn=父级cn, parent_en=父级en)
    └── 尊重已有的高优先级 clean_name（manual/nfo/tmdb 不被覆盖）
```

**性能优化**：
- NFO 补全加 `os.path.exists` 预检，跳过无 NFO 的文件夹（1854ms→1146ms）
- 文件夹 clean_name 不持久化，每次树构建动态计算

## 分类体系

| 类型 | 说明 |
|------|------|
| movie | 电影 |
| tv | 剧集 |
| collection | 电影合集（如"漫威宇宙"） |
| series | 系列剧（如"权力的游戏"全系列） |
| season | 季文件夹 |
| mixed | 混合内容 |

一级分类标签（category_tag）只有 movie/tv，通过 `config.json` 的 `category_tags` 配置。
文件夹类型可手动覆盖：`backend/folder_types.json`。

## 踩坑经验

- TV/season 文件夹 clean_name 显示"未设置" → ShadowNameSection 缺少 folderCleanName prop
- NFO 补全对所有文件夹读取导致 SMB IO 过重 → 加 exists 预检
- 树构建时动态计算可能覆盖已有的高优先级 clean_name → post_process 加优先级检查
