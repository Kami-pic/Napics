# API 清单

所有路由定义在 backend/main.py 中。

## 媒体库
- `GET /scan?path=` — 扫描 NAS 目录（SSE 流式）
- `GET /library` — 获取媒体库列表
- `GET /library/tree` — 获取目录树结构
- `POST /library/folder-type` — 设置文件夹类型
- `POST /library/category-tag` — 设置一级分类标签
- `POST /library/clean-name` — 修改清洗名
- `GET /quick-sync` — 快速同步（SSE 流式）

## 刮削
- `GET /scrape/by-name?name=&path=` — 按名称刮削
- `GET /scrape/candidates?name=` — TMDB 候选列表
- `GET /scrape/douban-candidates?name=` — 豆瓣候选列表
- `GET /scrape/bangumi-candidates?name=` — Bangumi 候选列表
- `POST /scrape/select?path=&tmdb_id=&media_type=` — 选择候选并刮削
- `POST /scrape/douban-select` — 选择豆瓣候选
- `POST /scrape/bangumi-select` — 选择 Bangumi 候选
- `GET /scrape/data?path=` — 读取刮削数据
- `POST /scrape/execute?path=` — 执行刮削
- `POST /scrape/batch` — 批量刮削
- `DELETE /scrape?path=` — 删除刮削数据
- `POST /scrape/upload-poster` — 上传海报
- `POST /scrape/set-poster-url` — 从 URL 设置海报
- `DELETE /scrape/poster?path=` — 删除海报
- `GET /scrape/supplement?path=` — 补充刮削

## 搜索
- `GET /search?keyword=` — BT/磁力搜索（Prowlarr）
- `GET /search/pan?keyword=` — 网盘搜索
- `GET /search/single?keyword=` — 单关键词搜索

## 下载
- `POST /download` — 提交下载任务
- `POST /download/submit` — 提交下载（新版）
- `GET /download-manager/tasks` — 获取下载任务列表
- `GET /download-manager/progress` — 获取下载进度
- `POST /download-manager/sync` — 同步下载进度
- `POST /download-manager/sync-qb` — 从 qB 同步
- `DELETE /download-manager/task?task_id=` — 删除单个任务
- `POST /download-manager/delete-tasks` — 批量删除任务
- `POST /download-manager/confirm-replace` — 确认替换
- `POST /download-manager/cancel-replace` — 取消替换
- `POST /batch-search` — 批量搜索
- `POST /batch-download` — 批量下载

## 整理
- `GET /organize/folder?path=` — 整理单个文件夹
- `GET /organize/structure?path=` — 结构整理
- `GET /organize/full?path=` — 完整整理（SSE 流式）
- `POST /organize/dry-run` — 整理预览
- `POST /organize/execute` — 执行整理
- `POST /organize/archive-both` — 归档新旧
- `POST /organize/purge-old` — 清除旧文件
- `GET /rename/videos?path=` — 视频重命名
- `GET /rename/item?old_path=&new_name=` — 重命名单项
- `GET /reorganize/seasons?path=` — 季目录重组
- `GET /merge-scattered-seasons?path=` — 合并散落季
- `GET /organize/history` — 整理历史
- `GET /organize/history/detail?snapshot_id=` — 历史详情

## 发现
- `GET /douban/hot` — 豆瓣热门
- `GET /douban/search?query=` — 豆瓣搜索
- `GET /media-info?title=` — 获取影视信息
- `POST /add-media` — 添加新影片

## 配置
- `GET /config` — 获取配置
- `POST /config` — 更新配置
- `GET /config/sort-weights` — 获取排序权重
- `POST /config/sort-weights` — 保存排序权重
- `GET /config/search-filter` — 获取搜索过滤规则
- `POST /config/search-filter` — 保存搜索过滤规则

## 其他
- `GET /analysis/report` — 健康报告
- `POST /analysis/invalidate` — 清除分析缓存
- `GET /recycle-bin` — 回收站列表
- `POST /recycle-bin/restore` — 恢复回收站项
- `POST /recycle-bin/cleanup` — 清理回收站
- `GET /alist/mounts` — Alist 挂载状态
- `POST /alist/transfer` — 网盘转存
- `GET /proxy/image?url=` — 图片代理
- `POST /backup/create` — 创建备份
- `POST /backup/restore` — 恢复备份
