---
name: relocate-conflict
description: >
  归位冲突探测：基于白名单识别新旧资源 + 探测同季/同目录冲突 + 生成替换/共存/取消方案。
  Use when modifying relocate logic, debugging "replace not working" issues,
  or implementing new post-download workflows.
---

# S12 归位冲突探测

> 下载完成后，新资源需要归位到目标目录。如果目标目录已有旧资源，需要探测冲突并让用户选择。

## 归位流程

```
下载完成（completed）
  → relocate(task)：推演阶段
    ├── _scan_disk_for_whitelist(save_path) → 新文件白名单
    ├── _detect_conflicts_v2(plan, target_base, whitelist) → 冲突对列表
    └── 返回 RelocateResult(status="awaiting_confirm", coexist_pairs=[...])

  → 用户选择：
    ├── confirm_replace(task, plan) → 旧资源入回收站 + 新资源归位
    ├── archive_both(task, conflicts) → 两者都保留
    └── cancel_replace(task) → 不做任何操作
```

## 冲突探测逻辑（_detect_conflicts_v2）

```
遍历目标目录下的现有文件：
  → 如果文件在白名单中 → 跳过（这是新下载的文件）
  → 如果文件是视频文件 → 和新文件按季/集号匹配
    → 匹配到 → 生成 CoexistPair(new_file, old_file)
    → 未匹配 → 跳过
```

## CoexistPair 结构

```python
class CoexistPair:
    new_path: str      # 新文件路径
    old_path: str      # 旧文件路径
    new_size: float    # 新文件大小 GB
    old_size: float    # 旧文件大小 GB
    reason: str        # 冲突原因描述
```

## 回收站兜底

- 替换操作不直接删除旧文件，移到 `recycle_bin/`
- 可配置保留天数（`recycle_bin_retention_days`）
- 支持恢复：`POST /recycle-bin/restore`

## 洗版联动

- 洗版模式下载完成 → 自动调用 `relocate()` → 自动 `confirm_replace()`
- 归位失败不标记 completed，保留订阅继续搜索
- `local_file_path` 校验：归位时先校验路径是否存在，不存在则通过 `local_media_matcher` 重新定位
