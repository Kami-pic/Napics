# [一次性] 回收站落盘侧修复记录

## 背景

- 现场定位发现本机 `backend/recycle_bin/` 累积了大量真实旧视频文件，占用约 `70G`
- 这些文件来自整理替换时被回收的旧资源，本应留在媒体库所在存储侧，而不是搬回运行机本地

## 根因

1. `config.recycle_bin_path` 默认是空字符串
2. `shared._get_recycle_bin()` 之前在路径为空时会静默回退到 `backend/recycle_bin`
3. `file_relocator._recycle_old_files()` 对旧视频、同名 NFO、海报、`movie.nfo / season.nfo` 全部调用 `RecycleBin.move_to_bin()`
4. `RecycleBin.move_to_bin()` 使用 `shutil.move()`，于是 NAS 上的旧文件被跨盘移动到本地 backend 目录

## 本轮修复

- 回收站文件实体默认按旧文件所属媒体库根动态落盘：
  - 命中媒体库根：`<媒体库根上级>/.recycle_bins/<媒体库名>`
  - 未命中媒体库根：退到源文件父目录下的 `.recycle_bins`
- backend 只集中保存 `recycle_bin.json` 元数据，避免多媒体库根时回收站列表分裂
- 保留 `recycle_bin_path` 作为显式覆盖入口；只有用户手动配置时才使用固定目录
- 兼容读取旧的回收站元数据位置，避免历史记录直接丢失
- 过期清理补齐目录删除能力，避免被回收的旧季目录无法清掉
- 设置页 placeholder 直接按当前媒体库路径计算默认示例，提示“库外同卷同级隐藏回收站”

## 验证

- `python -X utf8 -m pytest test_file_relocator_conflicts.py test_recycle_bin.py`
- 结果：`21 passed`

## 影响边界

- 只修正回收站的落盘位置与元数据管理
- 不改整理判定、冲突探测、下载调度、前端接口协议
