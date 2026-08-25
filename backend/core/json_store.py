"""JSON 落盘工具：原子写入，避免 NAS 断电或并发写导致文件截断损坏。

先写同目录临时文件并 fsync，再用 os.replace 原子替换目标文件。
os.replace 在同一文件系统上是原子操作（Windows / Linux 均成立），
因此读方永远看到的是完整的旧内容或完整的新内容，不会读到半截 JSON。
"""
import json
import logging
import os
import tempfile
import time
from typing import Any

logger = logging.getLogger(__name__)


_REPLACE_ATTEMPTS = 6
_REPLACE_BACKOFF_SEC = 0.02


def _replace_with_retry(tmp_path: str, path: str) -> None:
    """os.replace + 短重试。

    Windows 上目标文件正被另一次替换或杀软 / 索引服务持有时会抛
    PermissionError(13)，而这只是瞬时占用，重试就能过去。
    首次成功时没有任何额外开销。
    """
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(tmp_path, path)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(_REPLACE_BACKOFF_SEC * (attempt + 1))


def cleanup_stale_temp_files(path: str) -> int:
    """清掉目标文件遗留的临时文件，返回清掉的个数。

    唯一命名的好处是并发写不会互相踩，代价是进程被硬杀（服务重启、任务管理器
    结束进程）时留下的残骸没人覆盖。启动时扫一遍即可，正常路径的残骸由
    atomic_write_json 自己的 except 分支清理。
    """
    target_dir = os.path.dirname(os.path.abspath(path)) or "."
    prefix = os.path.basename(path) + "."
    removed = 0
    try:
        for name in os.listdir(target_dir):
            if name.startswith(prefix) and name.endswith(".tmp"):
                try:
                    os.remove(os.path.join(target_dir, name))
                    removed += 1
                except OSError:
                    pass
    except OSError:
        return 0
    if removed:
        logger.info(f"[json_store] 清理了 {removed} 个残留临时文件: {path}")
    return removed


def atomic_write_json(path: str, data: Any, *, compact: bool = False, indent: int = 4) -> None:
    """原子写入 JSON 文件。

    compact=True 时用紧凑分隔符（省体积、序列化更快），用于大数据文件；
    否则按 indent 缩进，用于需要人工查看的配置文件。
    """
    dump_kwargs = {"ensure_ascii": False}
    if compact:
        dump_kwargs["separators"] = (",", ":")
    else:
        dump_kwargs["indent"] = indent

    # 临时文件名必须唯一。用固定的 `<path>.tmp` 时两个并发写会争同一个文件：
    # Windows 上直接 PermissionError（两次写入全部失败、调用方却以为保存了），
    # POSIX 上则是内容交错写坏。
    target_dir = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(
        dir=target_dir, prefix=os.path.basename(path) + ".", suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, **dump_kwargs)
            f.flush()
            os.fsync(f.fileno())
        _replace_with_retry(tmp_path, path)
    except Exception:
        # 清理残留临时文件，避免下次写入被半成品干扰
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise
