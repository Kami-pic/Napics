# 核心数据结构

## media_library.json — 媒体库
数组，每项是一个视频文件记录（VideoInfo）：
- `file_path` — 完整文件路径
- `file_name` — 文件名
- `folder_name` — 所属文件夹（相对路径）
- `size_gb` — 文件大小（GB）
- `duration_min` — 时长（分钟）
- `resolution` — 分辨率（如 "1920x1080"）
- `height` / `width` — 高/宽像素
- `bitrate_kbps` — 码率
- `codec` — 视频编码（h264/hevc 等）
- `audio_codec` — 音频编码
- `audio_channels` — 声道数
- `subtitle_count` — 字幕轨数量
- `hdr_type` — "SDR" / "HDR10" / "DV"
- `has_poster` — 是否有封面
- `has_nfo` — 是否有 NFO
- `is_low_res` — 是否低分辨率
- `clean_name` — 清洗后的名称（后续添加）

## download_tasks.json — 下载任务
数组，每项是一个 DownloadTask：
- `id` — 任务 ID（UUID）
- `media_name` — 媒体名称
- `download_url` — 下载链接
- `save_path` — 最终目标路径
- `download_dir` — 沙盒路径
- `channel` — "qb" / "alist"
- `downloader_hash` — qB hash 或 Alist task ID
- `category_hint` — "movie" / "tv"
- `status` — pending → downloading → completed → relocating → archived / failed / lost
- `progress` — 0.0 ~ 1.0
- `speed` / `eta` — 速度和预计时间
- `phase` — Alist 阶段："cloud_download" / "local_sync"
- `error` — 错误信息
- `is_season_pack` — 是否整季包
- `season_number` — 季号
- `created_at` / `updated_at` — 时间戳

## config.json — 应用配置
AppConfig 模型，主要字段：
- `nas_paths` — NAS 路径列表
- `prowlarr_url` / `prowlarr_api_key` — Prowlarr 配置
- `tmdb_api_key` / `http_proxy` — TMDB 配置
- `qb_url` — qBittorrent 地址
- `alist_url` / `alist_token` — Alist 配置
- `category_tags` — 一级分类标签（路径 → movie/tv）
- `search_filter` — 搜索过滤规则（must_include/must_exclude）
- `preferred_codec` — 编码偏好（默认 x265）
- `sort_weights` — 种子排序权重（6 维度）
- `recycle_bin_path` / `recycle_bin_retention_days` — 回收站配置

## folder_types.json — 文件夹类型
对象，路径 → 类型映射：
- 类型：movie / tv / series_collection / movie_collection / variety / misc
